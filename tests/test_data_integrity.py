"""Whole-dataset invariants, enforced on every commit. These duplicate the
sharpest rules from tools/validate.py so CI fails loudly even if someone
edits data without running the pipeline."""
import json
import pathlib
import re
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = sorted((ROOT / "data").glob("*.json"))
AGGREGATOR = re.compile(
    r"builtin\w*\.com|ziprecruiter|wayup|prosple|themuse|glassdoor|indeed\.com"
    r"|simplify\.jobs|levels\.fyi", re.I)


def fields_of(prog):
    yield from prog.get("fields", {}).items()
    yield "cooling_off", prog.get("cooling_off", {})


class DatasetInvariants(unittest.TestCase):
    def test_dataset_is_not_empty(self):
        self.assertGreater(len(DATA), 50)

    def test_stated_always_has_a_quote(self):
        for path in DATA:
            rec = json.loads(path.read_text())
            for prog in rec["programs"]:
                for name, f in fields_of(prog):
                    if f.get("state") == "stated":
                        self.assertTrue(f.get("quote"),
                            f"{path.name}:{prog['id']}:{name} stated without a quote")

    def test_quotes_never_cite_aggregators(self):
        for path in DATA:
            rec = json.loads(path.read_text())
            for prog in rec["programs"]:
                for name, f in fields_of(prog):
                    if f.get("quote"):
                        self.assertFalse(AGGREGATOR.search(f.get("source_url") or ""),
                            f"{path.name}:{prog['id']}:{name} quote cites an aggregator")

    def test_silence_carries_its_source(self):
        # "publishes nothing" is a claim about a page somebody read
        for path in DATA:
            rec = json.loads(path.read_text())
            for prog in rec["programs"]:
                co = prog.get("cooling_off", {})
                if co.get("state") == "silent":
                    self.assertTrue(co.get("source_url") or (prog.get("source") or {}).get("url"),
                        f"{path.name}:{prog['id']} silent cooling-off without a read URL")

    def test_full_validator_passes(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "validate.py")],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-500:])


if __name__ == "__main__":
    unittest.main()
