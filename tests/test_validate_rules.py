"""Rule 8 of tools/validate.py: no rendered field may carry a maintainer
imperative ("verify", "recheck", "TODO", "before publishing"). Those phrases
are working notes to a future maintainer; on a reader-facing field they leak
scraping mechanics into a reference work. Maintainer-only fields
(source.note, apply.note, cooling_off.notes) are exempt on purpose — that is
where such phrases belong."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import validate  # noqa: E402


def minimal_program():
    return {
        "id": "test-program",
        "name": "Test Program",
        "audience": "undergraduate",
        "source": {"url": "https://example.com/x", "checked": "2026-09-29",
                   "status": "ok"},
        "apply": {"url": "https://example.com/x", "kind": "program_page"},
        "fields": {
            "class_year": {"state": "stated", "tier": 1,
                           "quote": "Open to students graduating in 2028.",
                           "source_url": "https://example.com/x"},
            "sponsorship": {"state": "silent", "source_url": "https://example.com/x"},
            "process": {"state": "unverified"},
            "compensation": {"state": "unverified"},
        },
        "cooling_off": {"state": "silent", "source_url": "https://example.com/x"},
    }


def failures_for(prog):
    validate.failures = []
    validate.passes = 0
    validate.check_program("Test Firm", prog)
    return validate.failures


def imperative_failures(prog):
    return [f for f in failures_for(prog) if "maintainer imperative" in f]


class MaintainerImperativeRule(unittest.TestCase):
    def test_clean_program_passes(self):
        self.assertEqual(failures_for(minimal_program()), [])

    def test_imperative_in_quote_fails(self):
        prog = minimal_program()
        prog["fields"]["class_year"]["quote"] = \
            "Open to 2028 graduates — verify the full sentence before publishing"
        self.assertTrue(imperative_failures(prog))

    def test_imperative_in_cycle_fails(self):
        prog = minimal_program()
        prog["cycle"] = "2027 (TODO: recheck when the cycle pages go live)"
        self.assertTrue(imperative_failures(prog))

    def test_imperative_in_summary_note_fails(self):
        prog = minimal_program()
        prog["fields"]["process"]["summary_note"] = "Recheck next cycle"
        self.assertTrue(imperative_failures(prog))

    def test_case_insensitive(self):
        prog = minimal_program()
        prog["location"] = "New York (VERIFY office list)"
        self.assertTrue(imperative_failures(prog))

    def test_word_boundary_no_false_positive(self):
        # "verified", "unverified", "rechecking" as part of larger legitimate
        # words must not trip: "verify" is anchored on both sides, and only
        # the recheck stem is deliberately open-ended.
        prog = minimal_program()
        prog["fields"]["class_year"]["quote"] = \
            "Applicants must hold verified enrollment status."
        self.assertEqual(imperative_failures(prog), [])

    def test_maintainer_only_fields_are_exempt(self):
        prog = minimal_program()
        prog["source"]["note"] = "verify the full sentence before publishing"
        prog["cooling_off"]["notes"] = "Recheck when the cycle pages go live"
        self.assertEqual(imperative_failures(prog), [])

    def test_live_dataset_is_clean(self):
        _, _, _, fails = validate.run(ROOT / "data")
        self.assertEqual([f for f in fails if "maintainer imperative" in f], [])


if __name__ == "__main__":
    unittest.main()
