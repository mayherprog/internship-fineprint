"""The shipped payload never carries maintainer-only fields.

DESIGN.md: `source.note` is never rendered and never shipped; the same holds
for every note-like field the schema allows (`apply.note`, `cooling_off.notes`).
These tests pin the strip in tools/build.py's load(), which feeds index.html
AND web/public/data.json — so a note can never reach either page merely by
being written into a record.
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build  # noqa: E402

ROWS = build.load(ROOT / "data")


class PayloadStripsMaintainerNotes(unittest.TestCase):
    def test_rows_exist(self):
        self.assertGreater(len(ROWS), 100)

    def test_source_note_never_ships(self):
        for r in ROWS:
            self.assertNotIn("note", r["source"], f"{r['id']}: source.note shipped")

    def test_apply_note_never_ships(self):
        for r in ROWS:
            if r.get("apply"):
                self.assertNotIn("note", r["apply"], f"{r['id']}: apply.note shipped")

    def test_cooling_off_notes_never_ship(self):
        for r in ROWS:
            self.assertNotIn("notes", r["cooling_off"],
                             f"{r['id']}: cooling_off.notes shipped")

    def test_known_maintainer_notes_absent_from_payload(self):
        # The two notes the audit caught leaking: Bain CREW and D. E. Shaw.
        import json
        payload = json.dumps(ROWS)
        self.assertNotIn("verify the full sentence", payload)
        self.assertNotIn("Recheck when", payload)

    def test_summary_note_still_ships(self):
        # The one deliberate exception: rendered as explicitly-not-the-firm's-
        # wording on unverified rows. Stripping it would be a regression.
        fields = [f for r in ROWS for f in r["fields"].values()]
        self.assertTrue(any("summary_note" in f for f in fields))


class DeadlineDisplay(unittest.TestCase):
    """Pipeline status markers never reach the deadline slot; firm-stated
    phrases and dates always pass through verbatim."""

    def test_status_markers_render_as_not_stated(self):
        for raw in ("unverified",
                    "unverified - no close date found in extracted page data",
                    "unverified — apply-faq page states a rolling basis",
                    "unstated", "—", "-"):
            self.assertEqual(build.deadline_display(raw), "not stated", raw)

    def test_real_values_pass_through(self):
        for raw in ("Rolling", "2026-10-30", "Friday, July 31 at 11:59pm ET",
                    "~Mar 2027 (2026 deadline was Mar 6)",
                    "priority deadline September 15, 2026; final deadline October 15, 2026"):
            self.assertEqual(build.deadline_display(raw), raw)

    def test_empty_stays_empty(self):
        self.assertEqual(build.deadline_display(""), "")

    def test_payload_carries_no_marker_deadlines(self):
        for r in ROWS:
            for key in ("opens", "closes"):
                self.assertFalse(r[key].lower().startswith(("unverified", "unstated")),
                                 f"{r['id']}.{key}: pipeline marker shipped: {r[key]!r}")


class ReadmeInjection(unittest.TestCase):
    """README counts are generated, never hand-written: the injected regions
    must carry the same totals load() and the validator report."""

    def test_sections_carry_current_counts(self):
        sections = build.readme_sections(ROWS, ROOT / "data")
        self.assertIn(f"over {len(ROWS)} programs", sections["quickstart"])
        firms = len({r["firm"] for r in ROWS})
        self.assertIn(f"{len(ROWS)} programs across {firms} firms",
                      sections["coverage"])

    def test_injection_is_idempotent(self):
        import tempfile
        readme = ROOT / "README.md"
        with tempfile.TemporaryDirectory() as td:
            copy = pathlib.Path(td) / "README.md"
            copy.write_text(readme.read_text())
            build.inject_readme(ROWS, ROOT / "data", copy)
            once = copy.read_text()
            build.inject_readme(ROWS, ROOT / "data", copy)
            self.assertEqual(once, copy.read_text())

    def test_missing_markers_abort(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            copy = pathlib.Path(td) / "README.md"
            copy.write_text("# no markers here\n")
            with self.assertRaises(SystemExit):
                build.inject_readme(ROWS, ROOT / "data", copy)


if __name__ == "__main__":
    unittest.main()
