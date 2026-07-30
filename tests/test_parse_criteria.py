"""The parser must never say more than the quote. Every refusal here is a
documented failure mode that produced (or nearly produced) a wrong record."""
import sys
import pathlib
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import parse_criteria as pc  # noqa: E402


class ClassYearWindows(unittest.TestCase):
    def test_between_window(self):
        parsed, why = pc.parse_class_year(
            "You will graduate between December 2027-June 2028")
        self.assertEqual(parsed, {"graduates_between": ["2027-12", "2028-06"]})

    def test_seasons_map_to_month_bounds(self):
        parsed, _ = pc.parse_class_year(
            "Open to students graduating December 2026 through Summer 2028")
        self.assertEqual(parsed, {"graduates_between": ["2026-12", "2028-08"]})

    def test_or_later_is_open_ended(self):
        parsed, _ = pc.parse_class_year(
            "expected graduation date of December 2027 or later")
        self.assertEqual(parsed, {"graduates_from": "2027-12"})

    def test_by_only(self):
        parsed, _ = pc.parse_class_year("Must graduate by August 2028")
        self.assertEqual(parsed, {"graduates_by": "2028-08"})


class ClassYearRefusals(unittest.TestCase):
    """A row the screener cannot decide costs the reader one click.
    A wrong parse costs them an application."""

    def test_hedged_language_never_parses(self):
        parsed, why = pc.parse_class_year("Class of 2028, preferred — typically juniors")
        self.assertIsNone(parsed)
        self.assertIn("hedged", why)

    def test_single_date_without_direction_word(self):
        parsed, why = pc.parse_class_year("Graduating in May 2028")
        self.assertIsNone(parsed)

    def test_out_of_order_tokens_refused(self):
        parsed, why = pc.parse_class_year(
            "graduating June 2028, having enrolled by September 2024")
        self.assertIsNone(parsed)


class SponsorshipWhitelists(unittest.TestCase):
    """Pattern whitelists, not sentiment. The named near-misses are real
    sentences that must not match."""

    def test_flat_refusal_parses_false(self):
        self.assertEqual(pc.parse_sponsorship(
            "We do not provide visa sponsorship for our interns."),
            {"sponsors": False})

    def test_availability_parses_true(self):
        self.assertEqual(pc.parse_sponsorship(
            "Visa sponsorship is available for this position"),
            {"sponsors": True})

    def test_practice_scoped_sentence_must_not_become_sponsors_true(self):
        # KPMG's sentence is scoped by practice; parsing it as a blanket
        # "sponsors: true" is the exact overstatement this project exists
        # to prevent.
        self.assertIsNone(pc.parse_sponsorship(
            "Practices that historically consider candidates requiring visa "
            "sponsorship on a limited basis: Select Tax jobs, Audit Data Engineering"))

    def test_cpt_ok_requires_cpt_not_just_opt(self):
        # Akuna's SWE posting says OPT/STEM without CPT and must not match;
        # sentences that do name CPT for F-1 students must.
        self.assertIsNone(pc.parse_sponsorship(
            "Legal authorization to work in the U.S. on the first day, "
            "including F-1 students using OPT or STEM"))
        self.assertEqual(pc.parse_sponsorship(
            "including F-1 students using CPT, OPT or STEM"),
            {"cpt_ok": True})
        self.assertEqual(pc.parse_sponsorship(
            "Students eligible for CPT/OPT are encouraged to apply"),
            {"cpt_ok": True})

    def test_no_future_sponsorship(self):
        self.assertEqual(pc.parse_sponsorship(
            "authorized to work in the U.S. without requiring sponsorship, "
            "now or in the future"),
            {"no_future_sponsorship": True})


if __name__ == "__main__":
    unittest.main()
