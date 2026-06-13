"""Unit tests for the LLM-triage request construction (stdlib unittest)."""

import json
import unittest

from thanhtra.core import triage


class RuleSetTest(unittest.TestCase):
    def test_rule_count_is_24(self):
        self.assertEqual(len(triage.ALL_RULES), 24)

    def test_critical_rules_are_subset(self):
        self.assertTrue(triage.CRITICAL_RULES <= set(triage.ALL_RULES))

    def test_new_v13_rules_present(self):
        self.assertIn("EXCEPTION-MISHANDLING", triage.ALL_RULES)
        self.assertIn("INSECURE-RANDOMNESS", triage.ALL_RULES)


class SchemaTest(unittest.TestCase):
    def test_schema_is_json_serializable(self):
        json.dumps(triage.TRIAGE_SCHEMA)

    def test_schema_enumerates_all_rules(self):
        self.assertIn("EXCEPTION-MISHANDLING", json.dumps(triage.TRIAGE_SCHEMA))


class RequestBodyTest(unittest.TestCase):
    def test_anthropic_body_shape(self):
        body = triage.build_request_body({}, "claude-opus-4-8")
        self.assertEqual(body["model"], "claude-opus-4-8")
        self.assertEqual(body["thinking"], {"type": "adaptive"})
        self.assertIn("system", body)
        self.assertIsInstance(body["messages"], list)
        self.assertTrue(body["messages"])

    def test_evidence_is_carried_in_message(self):
        body = triage.build_request_body(
            {"hotspots_by_rule": {"SQL-INJECTION": [{"path": "a.py", "line": 1}]}},
            "claude-opus-4-8",
        )
        self.assertIn("SQL-INJECTION", body["messages"][0]["content"])


class SystemPromptTest(unittest.TestCase):
    def test_critical_rules_injected(self):
        self.assertIn("HARDCODED-SECRET", triage.system_text())

    def test_anti_prompt_injection_guardrail_present(self):
        s = triage.system_text()
        self.assertIn("untrusted repository content", s)
        self.assertIn("not a command", s)


if __name__ == "__main__":
    unittest.main()
