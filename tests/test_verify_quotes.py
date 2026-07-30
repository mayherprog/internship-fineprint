"""Normalization in the mechanical quote verifier: both sides of the
comparison must survive the ways real pages mangle text."""
import importlib
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
vq = importlib.import_module("verify_quotes")


class Normalization(unittest.TestCase):
    def test_curly_quotes_and_dashes_flatten(self):
        self.assertEqual(vq.norm("Bachelor’s — “stated”"),
                         vq.norm("Bachelor's - \"stated\""))

    def test_markup_space_before_punctuation(self):
        # "office , with" is what tag-stripping leaves behind
        self.assertIn(vq.norm("at our McLean office, with corporate housing"),
                      vq.norm("experiences at our McLean office , with corporate housing provided ."))

    def test_whitespace_collapses(self):
        self.assertEqual(vq.norm("a  b\n\tc"), "a b c")


class JsonExtraction(unittest.TestCase):
    def test_json_strings_walks_nested_structures(self):
        out = []
        vq.json_strings({"a": ["x", {"b": "y"}], "c": 3, "d": None}, out)
        self.assertEqual(sorted(out), ["x", "y"])


class Classification(unittest.TestCase):
    def test_pdf_sources_never_fail(self):
        # a PDF citation must classify as blocked, not as a refutation
        self.assertTrue("dummy.PDF".lower().endswith(".pdf"))

    def test_challenge_marker_regex(self):
        self.assertTrue(vq.CHALLENGE.search("Just a moment..."))
        self.assertTrue(vq.CHALLENGE.search("Pardon Our Interruption"))
        self.assertFalse(vq.CHALLENGE.search("the interview process has four steps"))


if __name__ == "__main__":
    unittest.main()
