#!/usr/bin/env python3
"""Hunt for false `silent` rows: the failure mode nothing in the repo can see.

tools/verify_quotes.py iterates only fields whose state is "stated", so it
catches a quote that was invented and is structurally blind to a quote that was
missed. tools/validate.py checks that a silent field names the page it was read
from, but never opens that page. So a field marked `silent` on a page that
plainly states a rule passes every gate in the project, and on 2026-08-10
exactly that was found on Chicago Trading Company: cooling_off recorded as
`silent` while the posting said "You are allowed to submit one application per
position (i.e. SE Intern and QT Intern) during the recruiting cycle."

This does the reverse of verify_quotes: for each SILENT field, fetch the page
it cites and report sentences that look like they answer that very field. It
proves nothing on its own -- "sponsorship" matching a sentence about financial
sponsors is noise, and that judgement is the reader's. It just refuses to let
silence go unexamined.

Exit code is always 0. A hit is a review queue, not a failure.

Usage: python3 tools/audit_silent.py [out.json] [--only firm-slug]
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from harvest import (FIELD_PATTERNS, NOISE, SENT_SPLIT, curl,  # noqa: E402
                     readable_text)

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def silent_fields(rec: dict):
    """(program_id, field_name, url) for every silent field that cites a page."""
    for prog in rec["programs"]:
        fallback = prog.get("source", {}).get("url", "")
        for name, field in prog.get("fields", {}).items():
            if field.get("state") == "silent":
                url = field.get("source_url") or fallback
                if url:
                    yield prog["id"], name, url
        co = prog.get("cooling_off", {})
        if co.get("state") == "silent":
            url = co.get("source_url") or fallback
            if url:
                yield prog["id"], "cooling_off", url


def sentences_for(text: str, field: str) -> list[str]:
    """Noise-free sentences on the page that match this field's pattern."""
    pattern = FIELD_PATTERNS[field]
    seen, out = set(), []
    for sent in SENT_SPLIT.split(text):
        sent = sent.strip(" .·|-")
        if not (40 <= len(sent) <= 400) or NOISE.search(sent):
            continue
        if not pattern.search(sent) or sent.lower() in seen:
            continue
        seen.add(sent.lower())
        out.append(sent)
    return out


def check(job: tuple) -> dict | None:
    firm, pid, field, url = job
    if url.lower().endswith(".pdf"):
        return None
    status, body = curl(url)
    if status != 200 or len(body) < 1500:
        return None                      # unreachable proves nothing either way
    hits = sentences_for(readable_text(body), field)
    if not hits:
        return None
    return {"firm": firm, "program": pid, "field": field, "url": url,
            "candidates": hits[:8], "total": len(hits)}


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    out_path = pathlib.Path(args[0] if args else "silent_audit.json")

    jobs, checked = [], 0
    for path in sorted(DATA.glob("*.json")):
        if only and path.stem != only:
            continue
        rec = json.loads(path.read_text())
        for pid, field, url in silent_fields(rec):
            jobs.append((rec["firm"], pid, field, url))
            checked += 1

    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        found = [r for r in pool.map(check, jobs) if r]

    out_path.write_text(json.dumps(found, indent=1))
    print(f"examined {checked} silent fields, {len(found)} sit on a page that "
          f"says something shaped like that field\n")
    by_field: dict[str, int] = {}
    for r in found:
        by_field[r["field"]] = by_field.get(r["field"], 0) + 1
    for field, n in sorted(by_field.items(), key=lambda kv: -kv[1]):
        print(f"  {field:14} {n:3} rows to review")
    print(f"\nfull report: {out_path}")


if __name__ == "__main__":
    main()
