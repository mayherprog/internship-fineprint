"""The sector list exists once, in schema/program.schema.json.

On 2026-08-10 `private_equity` and `venture_capital` were added to the schema
alone. The record passed schema validation, tools/validate.py rejected it with
"sector is legal -- got 'private_equity'", and every other copy of the list had
to be patched by hand. These tests fail the moment a copy drifts again, and
they run before the pipeline in CI so the message names the file to fix rather
than surfacing as a confusing validation error on one record.
"""
import importlib
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

sectors = importlib.import_module("sectors")
build = importlib.import_module("build")
validate = importlib.import_module("validate")
ingest = importlib.import_module("ingest_research")
tracker = importlib.import_module("transcribe_tracker")

SCHEMA_ENUM = json.loads(
    (ROOT / "schema" / "program.schema.json").read_text())["properties"]["sector"]["enum"]


class SchemaIsTheSourceOfTruth(unittest.TestCase):
    def test_loader_returns_the_schema_enum_verbatim(self):
        self.assertEqual(list(sectors.SECTOR_ORDER), SCHEMA_ENUM)
        self.assertEqual(sectors.SECTORS, set(SCHEMA_ENUM))

    def test_validator_accepts_exactly_the_schema_enum(self):
        self.assertEqual(set(validate.SECTORS), set(SCHEMA_ENUM))

    def test_ingester_allowlist_is_the_schema_enum(self):
        # A research sector outside the enum is downgraded to "other". If this
        # allowlist lags the schema, a legal new sector is silently discarded.
        self.assertEqual(set(ingest.SECTORS), set(SCHEMA_ENUM))


class EverySectorCanBeRendered(unittest.TestCase):
    def test_build_labels_every_sector(self):
        # build.py asserts this at import; assert it here too so the failure
        # names this rule rather than arriving as an import error.
        self.assertEqual(set(build.SECTOR_LABEL), set(SCHEMA_ENUM))

    def test_no_label_is_the_raw_slug(self):
        for sector, label in build.SECTOR_LABEL.items():
            self.assertTrue(label.strip(), f"{sector} has an empty label")
            self.assertNotEqual(label, sector,
                                f"{sector} was given its slug as a display name")

    def test_front_end_labels_match_the_schema_and_the_python_map(self):
        web = sectors.assert_web_labels_match(build.SECTOR_LABEL)
        self.assertEqual(set(web), set(SCHEMA_ENUM))

    def test_a_missing_label_is_loud(self):
        incomplete = {s: "x" for s in list(SCHEMA_ENUM)[:-1]}
        with self.assertRaises(SystemExit) as caught:
            sectors.assert_labels_cover_schema(incomplete, "a test map")
        self.assertIn(SCHEMA_ENUM[-1], str(caught.exception))

    def test_an_unknown_label_is_loud(self):
        with self.assertRaises(SystemExit) as caught:
            sectors.assert_labels_cover_schema(
                {**build.SECTOR_LABEL, "crypto_exchange": "Crypto"}, "a test map")
        self.assertIn("crypto_exchange", str(caught.exception))


class TrackerMapsOnlyToLegalSectors(unittest.TestCase):
    """transcribe_tracker.py does not copy the enum, but it hardcodes sector
    values as the targets of its firm and column maps. A renamed enum value
    would leave those pointing at a sector no record may legally carry."""

    def test_column_map_targets_are_legal(self):
        for source, sector in tracker.SECTOR_MAP.items():
            self.assertIn(sector, SCHEMA_ENUM, f"SECTOR_MAP[{source!r}]")

    def test_canonical_firm_sectors_are_legal(self):
        for prefix, (firm, sector) in tracker.CANON.items():
            self.assertIn(sector, SCHEMA_ENUM, f"CANON[{prefix!r}] -> {firm}")


class DataUsesOnlyLegalSectors(unittest.TestCase):
    def test_every_record_sector_is_in_the_enum(self):
        for path in sorted((ROOT / "data").glob("*.json")):
            sector = json.loads(path.read_text()).get("sector")
            self.assertIn(sector, SCHEMA_ENUM, f"{path.name}")


if __name__ == "__main__":
    unittest.main()
