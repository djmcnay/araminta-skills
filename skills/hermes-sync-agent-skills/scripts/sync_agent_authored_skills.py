#!/usr/bin/env python3
"""Inventory and back up locally agent-authored Hermes skills safely.

The scanner examines only direct entries in ``source_skills_root`` in sorted
name order.  A skill is eligible only when its ``SKILL.md`` has the exact
frontmatter declaration ``ownership: agent-authored``. The declaration is
an affirmative ownership signal for newly created agent skills; legacy or
otherwise unmarked skills are reported as UNKNOWN and are
never copied automatically.

Before accepting that signal, the scanner excludes bundles named by configured
Hermes manifests, hub/tap names found in configured metadata, paths resolving
under configured external directories, archives, and any symlinked tree.  It
uses only the Python standard library and never follows or creates symlinks.

``--inventory`` reports the complete classification.  ``--apply`` copies only
eligible skills into the configured Araminta checkout and stages/commits only
the files this run changed.  It never pushes, never deletes stale backups, and
refuses a non-Git checkout or a destination outside that checkout.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

OWNERSHIP_KEY = "ownership"
OWNERSHIP_VALUE = "agent-authored"
ARCHIVE_SUFFIXES = {".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".whl"}
NAME_KEYS = {"name", "skill_name", "skill", "slug", "id"}
SECRET_FILE_NAMES = {".env", ".netrc", "credentials", "credentials.json", "id_rsa", "id_ed25519"}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|secret|password)\\s*[:=]\\s*[^\\s${][^\\s]*"),
)


@dataclass(frozen=True)
class InventoryItem:
    """One deterministic source entry classification for human/agent review."""

    name: str
    status: str
    reason: str
    source: Path


@dataclass(frozen=True)
class Plan:
    """Validated copy operations and the checkout used for a local commit."""

    inventory: tuple[InventoryItem, ...]
    copies: tuple[tuple[Path, Path], ...]
    checkout: Path
    commit_message: str


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object, giving a useful error for absent or malformed files."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def config_path(value: str, base: Path) -> Path:
    """Resolve a config path relative to its config file without accepting links."""
    path = Path(value).expanduser()
    candidate = path if path.is_absolute() else base / path
    if has_symlink_component(candidate):
        raise ValueError(f"configured path must not traverse a symlink: {candidate}")
    return candidate.resolve()


def is_relative_to(child: Path, parent: Path) -> bool:
    """Return whether *child* is below *parent* on supported Python versions."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def has_symlink_component(path: Path) -> bool:
    """Return true when a supplied lexical path traverses an existing symlink."""
    return any(part.is_symlink() for part in (path, *path.parents))


def reject_symlinks(directory: Path) -> None:
    """Reject a directory tree containing a symlink rather than following it."""
    if directory.is_symlink():
        raise ValueError(f"symlinked skill: {directory}")
    for current, directories, files in os.walk(directory, followlinks=False):
        for name in sorted([*directories, *files]):
            if (Path(current) / name).is_symlink():
                raise ValueError(f"skill contains symlink: {Path(current) / name}")


def names_from_metadata(value: Any) -> set[str]:
    """Extract conservative skill-name hints from varied manifest/metadata JSON.

    Hermes metadata formats have changed.  We only accept simple string values
    stored under common name fields, recursively, avoiding path-like values.
    """
    names: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in NAME_KEYS and isinstance(child, str):
                if child and Path(child).name == child and "/" not in child and "\\" not in child:
                    names.add(child)
            if key.lower() in {"installed", "skills"} and isinstance(child, dict):
                for candidate in child:
                    if candidate and Path(candidate).name == candidate and "/" not in candidate and "\\" not in candidate:
                        names.add(candidate)
            names.update(names_from_metadata(child))
    elif isinstance(value, list):
        for child in value:
            names.update(names_from_metadata(child))
    return names


def configured_paths(config: dict[str, Any], base: Path, key: str) -> tuple[Path, ...]:
    """Resolve optional one-or-many metadata paths, rejecting malformed config."""
    raw = config.get(key, [])
    if raw is None:
        return ()
    values = [raw] if isinstance(raw, str) else raw
    if not isinstance(values, list) or any(not isinstance(item, str) or not item for item in values):
        raise ValueError(f"{key} must be a path or array of paths")
    return tuple(config_path(item, base) for item in values)


def known_names(paths: tuple[Path, ...], label: str) -> set[str]:
    """Read optional Hermes metadata in JSON or bundled-manifest text form.

    Modern hub metadata is JSON. Hermes' bundled manifest is a line-oriented
    ``name:hash`` file, so accepting both avoids treating every bundled skill
    as unknown on installations using that native manifest format.
    """
    names: set[str] = set()
    for path in paths:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"{label} must be a real readable metadata file: {path}")
        try:
            names.update(names_from_metadata(read_json(path)))
        except ValueError:
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError as exc:
                raise ValueError(f"cannot read {label}: {path}: {exc}") from exc
            for line in lines:
                name, separator, _ = line.partition(":")
                if separator and name and Path(name).name == name and "/" not in name and "\\" not in name:
                    names.add(name)
    return names


def ownership_marker(skill_file: Path) -> bool:
    """Return true only for the exact supported boolean frontmatter declaration."""
    try:
        lines = skill_file.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError(f"SKILL.md is not UTF-8: {skill_file}") from exc
    if not lines or lines[0].strip() != "---":
        return False
    for line in lines[1:]:
        if line.strip() == "---":
            return False
        match = re.fullmatch(
            r"\s*" + re.escape(OWNERSHIP_KEY) + r"\s*:\s*" + re.escape(OWNERSHIP_VALUE) + r"\s*(?:#.*)?",
            line,
        )
        if match:
            return True
    return False


def secret_like_file(directory: Path) -> Path | None:
    """Find an obvious credential file/value; this is a guardrail, not a DLP scan."""
    for current, _, files in os.walk(directory, followlinks=False):
        for name in sorted(files):
            path = Path(current) / name
            if name.lower() in SECRET_FILE_NAMES:
                return path
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if any(pattern.search(text) for pattern in SECRET_PATTERNS):
                return path
    return None


def inventory(config_pathname: Path) -> tuple[tuple[InventoryItem, ...], dict[str, Any]]:
    """Classify every direct source entry without writing to either filesystem."""
    config = read_json(config_pathname)
    base = config_pathname.parent
    required = ("source_skills_root", "destination_agent_authored_root", "araminta_checkout")
    if any(not isinstance(config.get(key), str) or not config[key] for key in required):
        raise ValueError("config requires source_skills_root, destination_agent_authored_root, and araminta_checkout")
    source_input = Path(config["source_skills_root"]).expanduser()
    if has_symlink_component(source_input):
        raise ValueError(f"source_skills_root must not traverse a symlink: {source_input}")
    source_root = config_path(config["source_skills_root"], base)
    if not source_root.is_dir():
        raise ValueError(f"source_skills_root must be a real directory: {source_root}")
    bundled = known_names(configured_paths(config, base, "bundled_manifest_paths"), "bundled_manifest_paths")
    installed = known_names(configured_paths(config, base, "hub_metadata_paths"), "hub_metadata_paths")
    external = configured_paths(config, base, "external_skill_dirs")
    items: list[InventoryItem] = []
    for entry in sorted(source_root.iterdir(), key=lambda path: path.name):
        if entry.is_symlink():
            items.append(InventoryItem(entry.name, "EXCLUDED", "symlinked entry", entry))
        elif entry.suffix.lower() in ARCHIVE_SUFFIXES and entry.is_file():
            items.append(InventoryItem(entry.name, "EXCLUDED", "archive", entry))
        elif not entry.is_dir():
            items.append(InventoryItem(entry.name, "EXCLUDED", "not a skill directory", entry))
        elif any(is_relative_to(entry.resolve(), root) for root in external):
            items.append(InventoryItem(entry.name, "EXCLUDED", "configured external directory", entry))
        elif entry.name in bundled:
            items.append(InventoryItem(entry.name, "EXCLUDED", "Hermes bundled manifest", entry))
        elif entry.name in installed:
            items.append(InventoryItem(entry.name, "EXCLUDED", "hub/tap metadata", entry))
        else:
            try:
                reject_symlinks(entry)
                skill_file = entry / "SKILL.md"
                if not skill_file.is_file() or skill_file.is_symlink():
                    items.append(InventoryItem(entry.name, "UNKNOWN", "missing real SKILL.md/frontmatter", entry))
                elif ownership_marker(skill_file):
                    risky = secret_like_file(entry)
                    reason = "obvious secret-like content" if risky else "frontmatter ownership marker"
                    status = "EXCLUDED" if risky else "ELIGIBLE"
                    items.append(InventoryItem(entry.name, status, reason, entry))
                else:
                    items.append(InventoryItem(entry.name, "UNKNOWN", "unmarked legacy or unknown provenance", entry))
            except ValueError as exc:
                items.append(InventoryItem(entry.name, "EXCLUDED", str(exc), entry))
    return tuple(items), config


def git_checkout(path: Path) -> Path:
    """Require *path* to be exactly the top level of a usable Git checkout."""
    if has_symlink_component(path) or not path.is_dir():
        raise ValueError(f"araminta_checkout must be a real non-symlink directory: {path}")
    result = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"], text=True, capture_output=True)
    if result.returncode:
        raise ValueError(f"araminta_checkout is not a Git checkout: {path}")
    top = Path(result.stdout.strip()).resolve()
    if top != path.resolve():
        raise ValueError(f"araminta_checkout must be its Git checkout root: {path}")
    return top


def build_plan(config_pathname: Path) -> Plan:
    """Build a copy-only plan from inventory and validate its Git destination."""
    items, config = inventory(config_pathname)
    base = config_pathname.parent
    checkout = git_checkout(config_path(config["araminta_checkout"], base))
    destination = config_path(config["destination_agent_authored_root"], base)
    if has_symlink_component(Path(config["destination_agent_authored_root"]).expanduser()):
        raise ValueError("destination_agent_authored_root must not traverse a symlink")
    if not is_relative_to(destination, checkout):
        raise ValueError("destination_agent_authored_root must resolve inside araminta_checkout")
    if destination.exists() and (destination.is_symlink() or not destination.is_dir()):
        raise ValueError(f"destination_agent_authored_root must be a real directory: {destination}")
    copies = tuple((item.source, destination / item.name) for item in items if item.status == "ELIGIBLE")
    message = config.get("commit_message", "backup agent-authored Hermes skills")
    if not isinstance(message, str) or not message.strip() or "\x00" in message:
        raise ValueError("commit_message must be a non-empty ordinary string")
    return Plan(items, copies, checkout, message)


def report(items: tuple[InventoryItem, ...]) -> list[str]:
    """Render the full deterministic inventory for autonomous agent inspection."""
    lines = [f"{item.status} {item.name}: {item.reason}" for item in items]
    return lines or ["NO-OP: no entries in source_skills_root"]


def changed_paths(checkout: Path, before: set[str]) -> list[str]:
    """Return Git paths changed since *before*, including untracked copied files."""
    result = subprocess.run(
        ["git", "-C", str(checkout), "status", "--porcelain", "-z", "--untracked-files=all"],
        text=True,
        capture_output=True,
        check=True,
    )
    after = {entry[3:] for entry in result.stdout.split("\0") if entry and len(entry) > 3}
    return sorted(after - before)


def reject_dirty_destination(plan: Plan) -> None:
    """Avoid overwriting or staging a destination with changes from another task."""
    destination = plan.copies[0][1].parent if plan.copies else None
    if destination is None:
        return
    relative = destination.relative_to(plan.checkout)
    result = subprocess.run(
        ["git", "-C", str(plan.checkout), "status", "--porcelain", "--", str(relative)],
        text=True,
        capture_output=True,
        check=True,
    )
    if result.stdout:
        raise ValueError(f"destination has pre-existing Git changes; refusing to overwrite it: {destination}")


def apply_plan(plan: Plan, dry_run: bool) -> list[str]:
    """Report, optionally copy eligible trees, then commit only new changed paths."""
    lines = report(plan.inventory)
    lines.extend(f"COPY {source} -> {destination}" for source, destination in plan.copies)
    if not plan.copies:
        lines.append("NO-OP: no automatically eligible skills")
    for line in lines:
        print(line)
    if dry_run:
        print("DRY-RUN: no files changed")
        return lines
    reject_dirty_destination(plan)
    before = set(changed_paths(plan.checkout, set()))
    for source, destination in plan.copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination, symlinks=False, copy_function=shutil.copy2, dirs_exist_ok=True)
    paths = changed_paths(plan.checkout, before)
    if not paths:
        print("NO-COMMIT: no distribution changes")
        return lines
    subprocess.run(["git", "-C", str(plan.checkout), "add", "--", *paths], check=True)
    staged = subprocess.run(["git", "-C", str(plan.checkout), "diff", "--cached", "--quiet"], check=False)
    if staged.returncode == 0:
        print("NO-COMMIT: no staged distribution changes")
        return lines
    subprocess.run(["git", "-C", str(plan.checkout), "commit", "-m", plan.commit_message, "--", *paths], check=True)
    print(f"COMMIT: {plan.commit_message}")
    return lines


def main(argv: list[str] | None = None) -> int:
    """Run an inventory by default, or copy and locally commit with ``--apply``."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", required=True, type=Path, help="local gitignored config JSON")
    parser.add_argument("--inventory", action="store_true", help="report classifications only (default)")
    parser.add_argument("--apply", action="store_true", help="copy eligible skills and create a local Git commit")
    parser.add_argument("--dry-run", action="store_true", help="show the apply plan without writing or committing")
    args = parser.parse_args(argv)
    if args.inventory and args.apply:
        parser.error("--inventory and --apply cannot be used together")
    try:
        if args.apply or args.dry_run:
            apply_plan(build_plan(args.config), args.dry_run)
        else:
            items, _ = inventory(args.config)
            for line in report(items):
                print(line)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
