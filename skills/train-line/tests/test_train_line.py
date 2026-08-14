#!/usr/bin/env python3
"""Unit tests for the public train-line skill."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import departures
import journey


class ConfigurationTests(unittest.TestCase):
    def test_missing_config_is_clear(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "config.json"
            with self.assertRaisesRegex(departures.ConfigurationError, "not configured"):
                departures.load_token(missing)

    def test_placeholder_token_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"darwin_api_token": "YOUR_DARWIN_TOKEN_HERE"}))
            with self.assertRaisesRegex(departures.ConfigurationError, "non-placeholder"):
                departures.load_token(path)

    def test_valid_token_is_stripped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"darwin_api_token": "  test-token  "}))
            self.assertEqual(departures.load_token(path), "test-token")

    def test_wsdl_and_timeouts_are_safe(self):
        self.assertTrue(departures.WSDL.startswith("https://"))
        self.assertGreater(departures.REQUEST_TIMEOUT_SECONDS, 0)
        self.assertLessEqual(departures.REQUEST_TIMEOUT_SECONDS, 30)

    def test_cli_without_config_fails_before_network(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "departures.py"), "WAT"],
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Configuration error:", result.stderr)
        self.assertIn("darwin_api_token", result.stderr)
        self.assertNotIn("Darwin request failed", result.stderr)


class StationTests(unittest.TestCase):
    def test_public_alias(self):
        crs, name = journey.resolve_station("waterloo", journey.load_stations())
        self.assertEqual((crs, name), ("WAT", "London Waterloo"))

    def test_crs_fallback(self):
        self.assertEqual(journey.resolve_station("clj", {}), ("CLJ", "CLJ"))


class LinkTests(unittest.TestCase):
    def test_national_rail_link(self):
        url = journey.build_nationalrail_url("WAT", "CLJ", "2026-08-15", "09:00")
        self.assertIn("https://www.nationalrail.co.uk/journey-planner/", url)
        self.assertIn("origin=WAT", url)
        self.assertIn("destination=CLJ", url)
        self.assertIn("leavingDate=20260815", url)
        self.assertIn("leavingTime=0900", url)

    def test_journeycheck_link(self):
        self.assertEqual(
            journey.build_journeycheck_url("wat", "clj"),
            "https://www.journeycheck.com/swr/search?from=WAT&to=CLJ",
        )

    def test_cli_outputs_read_only_sources(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "journey.py"),
                "--from",
                "WAT",
                "--to",
                "CLJ",
                "--date",
                "2026-08-15",
                "--time",
                "09:00",
            ],
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("nationalrail.co.uk", result.stdout)
        self.assertIn("journeycheck.com", result.stdout)


class FormattingTests(unittest.TestCase):
    def test_nrcc_html_is_removed(self):
        class Message:
            __values__ = {"_value_1": "<p>Signal failure at <b>Clapham</b></p>"}

        result = departures.extract_nrcc(Message())
        self.assertEqual(result, "Signal failure at Clapham")


if __name__ == "__main__":
    unittest.main(verbosity=2)
