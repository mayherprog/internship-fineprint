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


if __name__ == "__main__":
    unittest.main()
