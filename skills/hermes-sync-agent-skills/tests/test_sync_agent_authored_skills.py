"""Tests for automatic ownership inventory and safe local distribution commits."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "sync_agent_authored_skills.py"
SPEC = importlib.util.spec_from_file_location("sync_agent_authored_skills", SCRIPT)
assert SPEC and SPEC.loader
sync = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sync
SPEC.loader.exec_module(sync)


class SyncAgentAuthoredSkillsTests(unittest.TestCase):
    """Exercise classification, copying, commits, and no-delete behavior in temp repos."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "hermes-skills"
        self.source.mkdir()
        self.checkout = self.root / "araminta"
        subprocess.run(["git", "init", "-q", str(self.checkout)], check=True)
        subprocess.run(["git", "-C", str(self.checkout), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.checkout), "config", "user.name", "Test"], check=True)
        (self.checkout / "README.md").write_text("distribution\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.checkout), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(self.checkout), "commit", "-qm", "initial"], check=True)
        self.destination = self.checkout / "skills" / "agent-authored"
        self.bundled = self.root / "bundled.json"
        self.hub = self.root / "hub.json"
        self.external = self.root / "external"
        self.external.mkdir()
        self.config = self.root / "config.json"
        self.write_config()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def skill(self, name: str, marked: bool = True, root: Path | None = None) -> Path:
        directory = (root or self.source) / name
        directory.mkdir(parents=True, exist_ok=True)
        marker = "ownership: agent-authored\n" if marked else ""
        (directory / "SKILL.md").write_text(f"---\nname: {name}\n{marker}---\nbody\n", encoding="utf-8")
        return directory

    def write_config(self, **updates: object) -> None:
        data: dict[str, object] = {
            "source_skills_root": str(self.source),
            "araminta_checkout": str(self.checkout),
            "destination_agent_authored_root": str(self.destination),
            "bundled_manifest_paths": [str(self.bundled)],
            "hub_metadata_paths": [str(self.hub)],
            "external_skill_dirs": [str(self.external)],
        }
        data.update(updates)
        self.bundled.write_text(json.dumps({"skills": [{"name": "bundled"}]}), encoding="utf-8")
        self.hub.write_text(json.dumps({"installed_skills": [{"skill_name": "hubbed"}]}), encoding="utf-8")
        self.config.write_text(json.dumps(data), encoding="utf-8")

    def statuses(self) -> dict[str, tuple[str, str]]:
        items, _ = sync.inventory(self.config)
        return {item.name: (item.status, item.reason) for item in items}

    def commits(self) -> int:
        return int(subprocess.run(["git", "-C", str(self.checkout), "rev-list", "--count", "HEAD"], text=True, capture_output=True, check=True).stdout)

    def test_automatic_ownership_selection_and_exclusions(self) -> None:
        self.skill("eligible")
        self.skill("legacy", marked=False)
        self.skill("bundled")
        self.skill("hubbed")
        self.skill("external", root=self.external)
        (self.source / "archive.zip").write_bytes(b"not relevant")
        states = self.statuses()
        self.assertEqual(states["eligible"][0], "ELIGIBLE")
        self.assertEqual(states["legacy"], ("UNKNOWN", "unmarked legacy or unknown provenance"))
        self.assertIn("bundled manifest", states["bundled"][1])
        self.assertIn("hub/tap", states["hubbed"][1])
        self.assertEqual(states["archive.zip"], ("EXCLUDED", "archive"))
        self.assertNotIn("external", states)

    def test_line_oriented_bundled_manifest_is_supported(self) -> None:
        self.skill("bundled")
        self.bundled.write_text("bundled:deadbeef\n", encoding="utf-8")
        self.hub.write_text(json.dumps({"installed": {}}), encoding="utf-8")
        self.assertIn("bundled manifest", self.statuses()["bundled"][1])

    def test_configured_external_path_is_excluded(self) -> None:
        external_child = self.skill("external-child")
        self.write_config(external_skill_dirs=[str(external_child)])
        self.assertEqual(self.statuses()["external-child"], ("EXCLUDED", "configured external directory"))

    def test_inventory_reports_unknown_and_dry_run_writes_nothing(self) -> None:
        self.skill("eligible")
        self.skill("legacy", marked=False)
        plan = sync.build_plan(self.config)
        with redirect_stdout(StringIO()) as output:
            sync.apply_plan(plan, dry_run=True)
        self.assertIn("ELIGIBLE eligible", output.getvalue())
        self.assertIn("UNKNOWN legacy", output.getvalue())
        self.assertIn("DRY-RUN", output.getvalue())
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.commits(), 1)

    def test_apply_copies_and_commits_only_eligible_skill(self) -> None:
        self.skill("eligible")
        self.skill("legacy", marked=False)
        sync.apply_plan(sync.build_plan(self.config), dry_run=False)
        self.assertEqual((self.destination / "eligible" / "SKILL.md").read_text(encoding="utf-8").splitlines()[-1], "body")
        self.assertFalse((self.destination / "legacy").exists())
        self.assertEqual(self.commits(), 2)
        committed = subprocess.run(["git", "-C", str(self.checkout), "show", "--name-only", "--format="], text=True, capture_output=True, check=True).stdout
        self.assertIn("skills/agent-authored/eligible/SKILL.md", committed)

    def test_no_change_apply_makes_no_empty_commit_and_never_deletes(self) -> None:
        self.skill("eligible")
        stale = self.destination / "stale"
        stale.mkdir(parents=True)
        (stale / "SKILL.md").write_text("keep", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.checkout), "add", "skills"], check=True)
        subprocess.run(["git", "-C", str(self.checkout), "commit", "-qm", "existing backup"], check=True)
        sync.apply_plan(sync.build_plan(self.config), dry_run=False)
        commits = self.commits()
        self.assertTrue((self.destination / "eligible").exists())
        sync.apply_plan(sync.build_plan(self.config), dry_run=False)
        self.assertEqual(self.commits(), commits)
        self.assertTrue(stale.exists())

    def test_rejects_symlinked_source(self) -> None:
        skill = self.skill("eligible")
        outside = self.root / "outside"
        outside.mkdir()
        (skill / "link").symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.statuses()["eligible"][0], "EXCLUDED")
        self.assertIn("symlink", self.statuses()["eligible"][1])

    def test_rejects_symlinked_destination(self) -> None:
        self.skill("eligible")
        target = self.root / "somewhere-else"
        target.mkdir()
        self.destination.parent.mkdir(parents=True)
        self.destination.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            sync.build_plan(self.config)

    def test_refuses_non_git_destination_checkout(self) -> None:
        self.skill("eligible")
        non_git = self.root / "not-git"
        non_git.mkdir()
        self.write_config(araminta_checkout=str(non_git), destination_agent_authored_root=str(non_git / "skills"))
        with self.assertRaisesRegex(ValueError, "not a Git checkout"):
            sync.build_plan(self.config)


if __name__ == "__main__":
    unittest.main()
