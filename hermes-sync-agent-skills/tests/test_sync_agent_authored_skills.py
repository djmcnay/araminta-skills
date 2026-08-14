"""Tests for explicit selection, dry runs, copying, and deletion safeguards."""

from __future__ import annotations

import importlib.util
import json
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
    """Exercise the security contract without touching a real Hermes install."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "hermes-skills"
        self.destination = self.root / "araminta" / "skills" / "agent-authored"
        (self.source / "approved-skill").mkdir(parents=True)
        (self.source / "approved-skill" / "SKILL.md").write_text("approved", encoding="utf-8")
        (self.source / "official-skill").mkdir()
        (self.source / "official-skill" / "SKILL.md").write_text("official", encoding="utf-8")
        self.manifest = self.root / "manifest.json"
        self.config = self.root / "config.json"
        self.config.write_text(json.dumps({"source_skills_root": str(self.source), "destination_agent_authored_root": str(self.destination), "manifest_path": str(self.manifest)}), encoding="utf-8")
        self.write_manifest()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_manifest(self, skills: list[dict] | None = None, retire: list[str] | None = None) -> None:
        self.manifest.write_text(json.dumps({"version": 1, "skills": skills if skills is not None else [{"name": "approved-skill", "origin": "agent-authored-local", "reviewed_by": "test", "review_note": "locally agent-authored"}], "retire": retire if retire is not None else []}), encoding="utf-8")

    def test_selection_is_manifest_only(self) -> None:
        plan = sync.build_plan(self.config, prune=False, allow_delete=False)
        self.assertEqual([destination.name for _, destination in plan.copies], ["approved-skill"])
        self.assertNotIn("official-skill", [destination.name for _, destination in plan.copies])

    def test_dry_run_does_not_create_destination(self) -> None:
        plan = sync.build_plan(self.config, prune=False, allow_delete=False)
        with redirect_stdout(StringIO()) as output:
            sync.apply_plan(plan, dry_run=True)
        self.assertIn("DRY-RUN", output.getvalue())
        self.assertFalse(self.destination.exists())

    def test_copy_creates_independent_file_copy(self) -> None:
        plan = sync.build_plan(self.config, prune=False, allow_delete=False)
        sync.apply_plan(plan, dry_run=False)
        copied = self.destination / "approved-skill" / "SKILL.md"
        self.assertEqual(copied.read_text(encoding="utf-8"), "approved")
        self.assertFalse(copied.is_symlink())

    def test_delete_requires_explicit_double_opt_in(self) -> None:
        retired = self.destination / "retired-skill"
        retired.mkdir(parents=True)
        (retired / "SKILL.md").write_text("old", encoding="utf-8")
        self.write_manifest(retire=["retired-skill"])
        with self.assertRaisesRegex(ValueError, "allow-delete"):
            sync.build_plan(self.config, prune=True, allow_delete=False)
        self.assertTrue(retired.exists())
        no_prune = sync.build_plan(self.config, prune=False, allow_delete=False)
        sync.apply_plan(no_prune, dry_run=False)
        self.assertTrue(retired.exists())
        prune_plan = sync.build_plan(self.config, prune=True, allow_delete=True)
        sync.apply_plan(prune_plan, dry_run=False)
        self.assertFalse(retired.exists())

    def test_rejects_symlink_source(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        (self.source / "approved-skill" / "outside-link").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            sync.build_plan(self.config, prune=False, allow_delete=False)

    def test_rejects_symlinked_destination(self) -> None:
        target = self.root / "somewhere-else"
        target.mkdir()
        self.destination.parent.mkdir(parents=True)
        self.destination.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            sync.build_plan(self.config, prune=False, allow_delete=False)


if __name__ == "__main__":
    unittest.main()
