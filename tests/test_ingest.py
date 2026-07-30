"""Dedup and rule-detection invariants in the research ingester."""
import importlib
import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
ing = importlib.import_module("ingest_research")


class RuleRegexes(unittest.TestCase):
    def test_reapply_detector_hits_real_sentences(self):
        real = [
            "We do not allow multiple applications. Please apply to the ONE role",
            "You are allowed to submit one application per position",
            "You may submit one application per role each year.",
            "candidates may retake the assessment after a waiting period",
        ]
        for s in real:
            self.assertTrue(ing.REAPPLY_RE.search(s), s)

    def test_hedged_rule_detector(self):
        self.assertTrue(ing.HEDGED_RULE_RE.search(
            "we usually recommend waiting about a year before reapplying"))
        self.assertFalse(ing.HEDGED_RULE_RE.search(
            "You cannot reapply for a position if you have been declined for it."))


class TranscriberScrub(unittest.TestCase):
    """Clauses naming a private person must never reach published data.
    Tested against a stand-in name so the test itself stays impersonal."""

    def test_redaction_drops_the_naming_clause(self):
        tr = importlib.import_module("transcribe_tracker")
        original = tr.REDACT_NAMES
        try:
            tr.REDACT_NAMES = ("alice",)
            out = tr.scrub("Master's degree required — Alice is ineligible")
            self.assertNotIn("alice", out.lower())
            self.assertIn("Master's degree required", out)
        finally:
            tr.REDACT_NAMES = original


if __name__ == "__main__":
    unittest.main()
