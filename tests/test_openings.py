"""Detector-level tests for tools/check_openings.py against fixture pages.

Each test drives a detector through the seeded → later-run transition with a
fake fetcher, per PHASE2.md: OPENED fires only on a real state transition,
BLOCKED proves nothing, page changes without a phrase flip are CHANGED.
"""
import importlib.util
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "check_openings", HERE.parent / "tools" / "check_openings.py")
co = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(co)

FILLER = ("This page describes the program in some detail. " * 60)  # >2000 chars


def text_fixture(body):
    raw = FILLER + " " + body
    return ("ok", raw, co.vq.norm(raw))


class KeywordFlip(unittest.TestCase):
    ROW = {"id": "x", "firm": "F", "program": "P", "detector": "keyword_flip",
           "watch": {"url": "https://example.test/page",
                     "absent_phrase": "check back in September 2026",
                     "present_phrase": "applications are now open"}}

    def run_with(self, body, prev):
        orig = co.fetch_text
        co.fetch_text = lambda url: text_fixture(body)
        try:
            return co.run_keyword_flip(self.ROW, prev)
        finally:
            co.fetch_text = orig

    def test_seed_then_open_when_sentinel_disappears(self):
        verdict, _, state = self.run_with("Please check back in September 2026.", None)
        self.assertIsNone(verdict)
        self.assertTrue(state["flags"]["absent_present"])
        verdict, evidence, _ = self.run_with("The application portal is live.", state)
        self.assertEqual(verdict, "OPENED")
        self.assertIn("sentinel sentence is gone", evidence)

    def test_open_when_present_phrase_appears_with_quote(self):
        _, _, state = self.run_with("Please check back in September 2026.", None)
        verdict, evidence, _ = self.run_with(
            "Please check back in September 2026. Applications are now open "
            "for the 2027 cohort.", state)
        self.assertEqual(verdict, "OPENED")
        self.assertIn("Applications are now open", evidence)

    def test_unrelated_change_is_changed_not_opened(self):
        _, _, state = self.run_with("Please check back in September 2026.", None)
        verdict, _, _ = self.run_with(
            "Please check back in September 2026. We redecorated the footer.", state)
        self.assertEqual(verdict, "CHANGED")

    def test_blocked_page_preserves_state(self):
        _, _, state = self.run_with("Please check back in September 2026.", None)
        orig = co.fetch_text
        co.fetch_text = lambda url: ("blocked", "page text only 90 chars", "")
        try:
            verdict, _, new_state = co.run_keyword_flip(self.ROW, state)
        finally:
            co.fetch_text = orig
        self.assertEqual(verdict, "BLOCKED")
        self.assertEqual(new_state, state)


class PageDiff(unittest.TestCase):
    ROW = {"id": "y", "firm": "F", "program": "P", "detector": "page_diff",
           "watch": {"url": "https://example.test/page"}}

    def run_with(self, body, prev):
        orig = co.fetch_text
        co.fetch_text = lambda url: text_fixture(body)
        try:
            return co.run_page_diff(self.ROW, prev)
        finally:
            co.fetch_text = orig

    def test_seed_quiet_then_changed_with_diff(self):
        verdict, _, state = self.run_with("Deadline is October 1.", None)
        self.assertIsNone(verdict)
        verdict, _, state = self.run_with("Deadline is October 1.", state)
        self.assertEqual(verdict, "QUIET")
        verdict, evidence, _ = self.run_with("Deadline is November 15.", state)
        self.assertEqual(verdict, "CHANGED")
        self.assertIn("november 15", evidence)

    def test_ignore_pattern_suppresses_noise(self):
        row = dict(self.ROW)
        row["watch"] = {"url": "https://example.test/page",
                        "ignore": r"copyright \d{4}"}
        orig = co.fetch_text
        try:
            co.fetch_text = lambda url: text_fixture("Copyright 2026.")
            _, _, state = co.run_page_diff(row, None)
            co.fetch_text = lambda url: text_fixture("Copyright 2027.")
            verdict, _, _ = co.run_page_diff(row, state)
        finally:
            co.fetch_text = orig
        self.assertEqual(verdict, "QUIET")


class AtsApi(unittest.TestCase):
    ROW = {"id": "z", "firm": "F", "program": "P", "detector": "ats_api",
           "watch": {"endpoint": "https://boards.test/jobs",
                     "title_pattern": "(?i)thrive|intern"}}

    def run_with(self, payload, prev):
        orig = co.fetch_json
        co.fetch_json = lambda url: ("ok", payload)
        try:
            return co.run_ats(self.ROW, prev)
        finally:
            co.fetch_json = orig

    def test_new_matching_posting_fires_opened(self):
        board = {"jobs": [{"id": 1, "title": "Senior Chef"}]}
        verdict, _, state = self.run_with(board, None)
        self.assertIsNone(verdict)
        self.assertEqual(state["postings"], [])
        board["jobs"].append({"id": 2, "title": "Thrive Program: Software Intern"})
        verdict, evidence, state = self.run_with(board, state)
        self.assertEqual(verdict, "OPENED")
        self.assertIn("Thrive Program: Software Intern", evidence)
        verdict, _, _ = self.run_with(board, state)
        self.assertEqual(verdict, "QUIET")

    def test_broken_api_is_blocked(self):
        orig = co.fetch_json
        co.fetch_json = lambda url: ("blocked", "JSONDecodeError: not json")
        try:
            verdict, _, state = co.run_ats(self.ROW, {"postings": ["1|x"]})
        finally:
            co.fetch_json = orig
        self.assertEqual(verdict, "BLOCKED")
        self.assertEqual(state, {"postings": ["1|x"]})


if __name__ == "__main__":
    unittest.main()
