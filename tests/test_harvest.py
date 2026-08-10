"""The harvester's guarantees, none of which involve the network.

Two of these tests exist because the corresponding mistake was actually made
on 2026-08-10 and cost a re-run:

  - `sponsor` matched "financial sponsors" on every private-equity page, so
    the sponsorship pattern now requires visa/authorisation language.
  - candidate sentences were trusted straight out of the extractor. They are
    now re-checked against the same normalised haystacks verify_quotes.py
    builds, because a quote that cannot be found on the page it came from
    becomes a FAIL row three commits later.

The third guarantee is audit_silent's: it must look at silent fields and only
silent fields, since the whole point is covering the blind spot left by
verify_quotes.py, which iterates `stated` rows exclusively.
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import audit_silent  # noqa: E402
import harvest  # noqa: E402
from verify_quotes import norm  # noqa: E402


class ReadableText(unittest.TestCase):
    def test_script_and_style_bodies_are_not_prose(self):
        text = harvest.readable_text(
            "<p>Interns must be graduating in 2028.</p>"
            "<script>var role = 'graduate';</script><style>.a{color:red}</style>")
        self.assertIn("graduating in 2028", text)
        self.assertNotIn("var role", text)
        self.assertNotIn("color:red", text)

    def test_block_boundaries_do_not_weld_sentences_together(self):
        # Without a boundary these two list items become one "sentence" that
        # appears nowhere on the page.
        text = harvest.readable_text(
            "<li>All applicants must be enrolled undergraduate students</li>"
            "<li>Applications are reviewed on a rolling basis each autumn</li>")
        sentences = [s.strip() for s in harvest.SENT_SPLIT.split(text) if s.strip()]
        self.assertEqual(len(sentences), 2, sentences)

    def test_collapsed_accordion_answers_survive(self):
        # The Blackstone case: the FAQ answer is in the markup and absent from
        # innerText. Reading innerText is what made this project miss quotes.
        text = harvest.readable_text(
            '<details><summary>Do you sponsor?</summary>'
            '<p>We do not provide visa sponsorship for internships.</p></details>')
        self.assertIn("We do not provide visa sponsorship for internships", text)

    def test_entities_are_unescaped(self):
        self.assertIn("Smith & Co", harvest.readable_text("<p>Smith &amp; Co</p>"))


class FieldPatterns(unittest.TestCase):
    def test_financial_sponsors_is_not_a_sponsorship_statement(self):
        for sentence in (
                "We advise financial sponsors and corporate clients on transactions.",
                "Our Equity Capital Markets group serves the firm's sponsor clients.",
                "Evercore provides restructuring advice to companies and sponsors."):
            self.assertIsNone(harvest.FIELD_PATTERNS["sponsorship"].search(sentence),
                              f"private-equity sense matched: {sentence}")

    def test_real_sponsorship_statements_still_match(self):
        for sentence in (
                "We are unable to provide visa sponsorship for this role.",
                "Candidates must have unrestricted work authorization in the U.S.",
                "This position is not eligible for CPT or OPT.",
                "International students are welcome to apply."):
            self.assertIsNotNone(harvest.FIELD_PATTERNS["sponsorship"].search(sentence),
                                 f"missed: {sentence}")

    def test_cooling_off_catches_the_two_known_lockout_shapes(self):
        # The Point72 Academy rule and the Chicago Trading Company cap are the
        # most restrictive verified rules in the database; a pattern that
        # misses either shape is not worth running.
        for sentence in (
                "You may only submit one application to the Academy program globally.",
                "You are allowed to submit one application per position during the "
                "recruiting cycle.",
                "Unsuccessful candidates may reapply after twelve months."):
            self.assertIsNotNone(harvest.FIELD_PATTERNS["cooling_off"].search(sentence),
                                 f"missed: {sentence}")


class CandidateSentences(unittest.TestCase):
    def test_boilerplate_is_not_a_candidate(self):
        text = ("We are an equal opportunity employer and consider applicants "
                "without regard to race, color, religion or citizenship status.")
        self.assertEqual(harvest.candidate_sentences(text), [])

    def test_sentence_must_be_long_enough_to_be_a_claim(self):
        self.assertEqual(harvest.candidate_sentences("Visa sponsorship."), [])

    def test_a_candidate_is_tagged_with_every_field_it_could_serve(self):
        text = ("Interns graduating in 2028 receive a monthly salary of $12,000 "
                "for the summer.")
        [cand] = harvest.candidate_sentences(text)
        self.assertEqual(set(cand["fields"]), {"class_year", "compensation"})

    def test_repeated_sentences_are_reported_once(self):
        sentence = ("All applicants must be currently enrolled undergraduate "
                    "students in good standing. ")
        self.assertEqual(len(harvest.candidate_sentences(sentence * 3)), 1)


class EveryCandidateIsOnThePage(unittest.TestCase):
    """Stage 5, the guarantee the whole pipeline exists to provide."""

    PAGE = ("<h2>Students</h2>"
            "<p>All applicants must be currently enrolled undergraduate students.</p>"
            "<p>We are unable to provide visa sponsorship &amp; cannot petition.</p>"
            "<p>You may submit only one application per recruiting cycle.</p>")

    def kept(self):
        cands = harvest.candidate_sentences(harvest.readable_text(self.PAGE))
        hay = harvest.haystacks(self.PAGE)
        return [c for c in cands if any(norm(c["quote"]) in h for h in hay)], cands

    def test_the_page_yields_candidates_at_all(self):
        _, cands = self.kept()
        self.assertGreaterEqual(len(cands), 3, cands)

    def test_every_kept_candidate_is_verbatim_on_the_page(self):
        kept, _ = self.kept()
        hay = harvest.haystacks(self.PAGE)
        for cand in kept:
            self.assertTrue(any(norm(cand["quote"]) in h for h in hay), cand)

    def test_nothing_is_silently_discarded_on_this_page(self):
        # If this ever fails, the extractor and the verifier have drifted apart
        # and the drop counter in the report is hiding real material.
        kept, cands = self.kept()
        self.assertEqual(len(kept), len(cands))

    def test_a_quote_not_on_the_page_is_rejected_by_the_same_predicate(self):
        hay = harvest.haystacks(self.PAGE)
        invented = "We sponsor visas for all interns without exception."
        self.assertFalse(any(norm(invented) in h for h in hay))

    def test_entity_escaped_text_is_still_matched(self):
        hay = harvest.haystacks(self.PAGE)
        quote = "We are unable to provide visa sponsorship & cannot petition."
        self.assertTrue(any(norm(quote) in h for h in hay))


class NotAPage(unittest.TestCase):
    def test_machine_endpoints_are_not_followed(self):
        for href in ("/wp-json/oembed/1.0/embed?url=x", "/feed/", "/sitemap.xml",
                     "/brochure.pdf", "/author/jt/"):
            self.assertIsNotNone(harvest.NOT_A_PAGE.search(href), href)

    def test_real_student_pages_are_followed(self):
        for href in ("/careers/students/", "/early-careers", "/campus-recruiting",
                     "/careers/students-graduates/students-graduates-u-s/"):
            self.assertIsNone(harvest.NOT_A_PAGE.search(href), href)
            self.assertIsNotNone(harvest.STUDENT_LINK.search(href), href)


class SilentAudit(unittest.TestCase):
    REC = {"programs": [{
        "id": "p1",
        "source": {"url": "https://example.test/program"},
        "fields": {
            "class_year": {"state": "silent"},
            "sponsorship": {"state": "stated", "quote": "q",
                            "source_url": "https://example.test/s"},
            "process": {"state": "silent", "source_url": "https://example.test/own"},
            "compensation": {"state": "unverified"},
        },
        "cooling_off": {"state": "silent"},
    }]}

    def test_only_silent_fields_are_examined(self):
        fields = {f for _, f, _ in audit_silent.silent_fields(self.REC)}
        self.assertEqual(fields, {"class_year", "process", "cooling_off"})

    def test_a_field_without_its_own_url_falls_back_to_the_program_source(self):
        urls = {f: u for _, f, u in audit_silent.silent_fields(self.REC)}
        self.assertEqual(urls["class_year"], "https://example.test/program")
        self.assertEqual(urls["cooling_off"], "https://example.test/program")
        self.assertEqual(urls["process"], "https://example.test/own")

    def test_a_silent_field_citing_no_page_is_skipped_not_guessed(self):
        rec = {"programs": [{"id": "p", "fields": {"process": {"state": "silent"}},
                             "cooling_off": {"state": "silent"}}]}
        self.assertEqual(list(audit_silent.silent_fields(rec)), [])

    def test_sentences_for_returns_only_that_field(self):
        text = ("Candidates may submit only one application per recruiting cycle "
                "to this programme. Interns receive a monthly salary of $12,000 "
                "plus a housing stipend.")
        cooling = audit_silent.sentences_for(text, "cooling_off")
        money = audit_silent.sentences_for(text, "compensation")
        self.assertEqual(len(cooling), 1)
        self.assertIn("only one application", cooling[0])
        self.assertEqual(len(money), 1)
        self.assertIn("$12,000", money[0])


if __name__ == "__main__":
    unittest.main()
