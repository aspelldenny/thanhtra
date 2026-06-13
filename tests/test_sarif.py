"""Unit tests for SARIF 2.1.0 emission (stdlib unittest)."""

import unittest

from thanhtra import __version__
from thanhtra.core import sarif


def _doc(findings, verdict="FAIL"):
    return {"generated_at": "2026-01-01T00:00:00Z",
            "triage": {"verdict": verdict, "findings": findings}}


class BuildRulesTest(unittest.TestCase):
    def test_driver_declares_24_rules(self):
        self.assertEqual(len(sarif.build_rules()), 24)

    def test_rule_has_id_and_name(self):
        rule = sarif.build_rules()[0]
        self.assertIn("id", rule)
        self.assertIn("name", rule)


class ToSarifTest(unittest.TestCase):
    def test_maps_a_real_finding(self):
        out = sarif.to_sarif(_doc([{
            "rule_id": "SQL-INJECTION", "severity": "CRITICAL",
            "file": "api/users.py", "line": 42, "title": "x", "reasoning": "y",
        }]))
        self.assertEqual(out["version"], "2.1.0")
        run = out["runs"][0]
        self.assertEqual(len(run["results"]), 1)
        self.assertEqual(run["results"][0]["ruleId"], "SQL-INJECTION")
        self.assertEqual(run["results"][0]["level"], "error")  # CRITICAL -> error

    def test_semantic_version_tracks_package_version(self):
        out = sarif.to_sarif(_doc([]))
        self.assertEqual(out["runs"][0]["tool"]["driver"]["semanticVersion"], __version__)

    def test_false_positives_are_dismissed(self):
        out = sarif.to_sarif(_doc([{
            "rule_id": "XSS", "severity": "HIGH", "file": "a.py", "line": 1,
            "false_positive": True,
        }]))
        self.assertEqual(len(out["runs"][0]["results"]), 0)

    def test_missing_triage_raises(self):
        with self.assertRaises(ValueError):
            sarif.to_sarif({"generated_at": "t"})


if __name__ == "__main__":
    unittest.main()
