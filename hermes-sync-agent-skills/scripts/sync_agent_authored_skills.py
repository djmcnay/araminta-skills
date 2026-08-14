#!/usr/bin/env python3
"""Safely back up explicitly reviewed, agent-authored Hermes skills.

Purpose: copy an allowlisted subset of a local Hermes skills directory into an
Araminta profile distribution.  The tool deliberately performs no discovery:
the reviewable manifest is the only source of selection.  This prevents bundled,
hub/tap-installed, external-directory, archive, and otherwise unknown skills
from being copied merely because they appear in a Hermes directory.

Architecture: configuration names the local source root, destination root, and
manifest.  The manifest contains exact one-component skill names plus a required
``agent-authored-local`` provenance assertion.  Each selected source must be a
real directory immediately below the source root and contain no symlinks.  Files
are copied with ``shutil.copy2``; symlinks are never followed or created.

Intent and use: run ``--dry-run`` first, inspect its deterministic plan and the
manifest in review, then rerun without it to copy.  Normal runs never delete.
Deletion requires both ``--prune`` and ``--allow-delete`` and applies only to
explicitly named entries in ``retire``.  This is a backup helper, not a Hermes
installer and it never changes the source directory.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_ORIGIN = "agent-authored-local"


@dataclass(frozen=True)
class Plan:
    """A validated, deterministic set of copy and optional delete operations."""

    copies: tuple[tuple[Path, Path], ...]
    deletes: tuple[Path, ...]


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object or raise a clear ValueError."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"JSON object required: {path}")
    return data


def safe_name(value: Any, field: str) -> str:
    """Require a portable single directory name, never a path."""
    if not isinstance(value, str) or not value or value in {".", ".."}:
        raise ValueError(f"{field} must be a non-empty skill name")
    if Path(value).name != value or "/" in value or "\\" in value:
        raise ValueError(f"{field} must be one directory name, not a path: {value!r}")
    return value


def is_relative_to(child: Path, parent: Path) -> bool:
    """Return whether child is below parent without relying on Python version magic."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def has_symlink_component(path: Path) -> bool:
    """Return whether path or any existing ancestor is a symlink."""
    return any(component.is_symlink() for component in (path, *path.parents))


def reject_symlinks(directory: Path) -> None:
    """Reject a source tree containing any symlink instead of following it."""
    if directory.is_symlink():
        raise ValueError(f"source skill is a symlink: {directory}")
    for current, dirs, files in os.walk(directory, followlinks=False):
        current_path = Path(current)
        for entry in sorted([*dirs, *files]):
            if (current_path / entry).is_symlink():
                raise ValueError(f"source skill contains a symlink: {current_path / entry}")


def build_plan(config_path: Path, prune: bool, allow_delete: bool) -> Plan:
    """Validate config and manifest, returning only permitted operations."""
    config = read_json(config_path)
    config_dir = config_path.parent
    required = ("source_skills_root", "destination_agent_authored_root", "manifest_path")
    if any(not isinstance(config.get(key), str) or not config[key] for key in required):
        raise ValueError("config requires non-empty source_skills_root, destination_agent_authored_root, and manifest_path")

    source_root_input = Path(config["source_skills_root"]).expanduser()
    destination_root_input = Path(config["destination_agent_authored_root"]).expanduser()
    if has_symlink_component(source_root_input):
        raise ValueError(f"source_skills_root must not traverse a symlink: {source_root_input}")
    if has_symlink_component(destination_root_input):
        raise ValueError(f"destination_agent_authored_root must not traverse a symlink: {destination_root_input}")
    source_root = source_root_input.resolve()
    destination_root = destination_root_input.resolve()
    manifest_path = Path(config["manifest_path"])
    if not manifest_path.is_absolute():
        manifest_path = config_dir / manifest_path
    manifest = read_json(manifest_path)
    if manifest.get("version") != 1 or not isinstance(manifest.get("skills"), list):
        raise ValueError("manifest must have version 1 and a skills array")
    if not source_root.is_dir():
        raise ValueError(f"source_skills_root must be a real directory: {source_root}")

    copies: list[tuple[Path, Path]] = []
    names: set[str] = set()
    for item in manifest["skills"]:
        if not isinstance(item, dict):
            raise ValueError("each manifest skill entry must be an object")
        name = safe_name(item.get("name"), "skill name")
        if name in names:
            raise ValueError(f"duplicate manifest skill: {name}")
        names.add(name)
        if item.get("origin") != REQUIRED_ORIGIN:
            raise ValueError(f"{name}: origin must be {REQUIRED_ORIGIN!r}")
        if not isinstance(item.get("reviewed_by"), str) or not item["reviewed_by"].strip():
            raise ValueError(f"{name}: reviewed_by is required")
        if not isinstance(item.get("review_note"), str) or not item["review_note"].strip():
            raise ValueError(f"{name}: review_note is required")
        source = source_root / name
        destination = destination_root / name
        if not source.is_dir() or source.is_symlink() or source.resolve().parent != source_root:
            raise ValueError(f"{name}: source must be a real direct child of source_skills_root")
        reject_symlinks(source)
        if destination.exists():
            if destination.is_symlink() or not destination.is_dir():
                raise ValueError(f"{name}: destination must be a real directory")
            reject_symlinks(destination)
        copies.append((source, destination))

    deletes: list[Path] = []
    if prune:
        if not allow_delete:
            raise ValueError("--prune requires --allow-delete; normal sync never deletes")
        retire = manifest.get("retire", [])
        if not isinstance(retire, list):
            raise ValueError("manifest retire must be an array")
        for raw_name in retire:
            name = safe_name(raw_name, "retired skill name")
            if name in names:
                raise ValueError(f"retired skill is still selected for copy: {name}")
            target = destination_root / name
            if target.exists():
                if target.is_symlink() or not target.is_dir() or target.resolve().parent != destination_root:
                    raise ValueError(f"refusing to delete unsafe retired destination: {target}")
                deletes.append(target)
    return Plan(tuple(sorted(copies, key=lambda item: item[1].name)), tuple(sorted(deletes)))


def apply_plan(plan: Plan, dry_run: bool) -> list[str]:
    """Print and optionally execute a plan.  Returns deterministic action lines."""
    actions = [f"COPY {source} -> {destination}" for source, destination in plan.copies]
    actions.extend(f"DELETE {target}" for target in plan.deletes)
    if not actions:
        actions.append("NO-OP")
    for action in actions:
        print(action)
    if dry_run:
        print("DRY-RUN: no files changed")
        return actions
    for source, destination in plan.copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination, symlinks=False, copy_function=shutil.copy2, dirs_exist_ok=True)
    for target in plan.deletes:
        shutil.rmtree(target)
    return actions


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and return a shell-friendly status code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", required=True, type=Path, help="local config JSON (normally gitignored)")
    parser.add_argument("--dry-run", action="store_true", help="print the validated plan without changing files")
    parser.add_argument("--prune", action="store_true", help="process explicit manifest retire entries")
    parser.add_argument("--allow-delete", action="store_true", help="required acknowledgement for --prune")
    args = parser.parse_args(argv)
    try:
        plan = build_plan(args.config, args.prune, args.allow_delete)
        apply_plan(plan, args.dry_run)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
