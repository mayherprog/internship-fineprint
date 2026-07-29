#!/usr/bin/env python3
"""Annotate stated class-year and sponsorship quotes with machine-readable parses.

Runs after ingest, edits data/*.json in place, and prints every annotation it
makes so a human can review the quote against the parse. `parsed` is always
subordinate to `quote`: nothing here creates a claim, it only makes an existing
quoted claim filterable. When in doubt, this script parses NOTHING — a row the
screener cannot decide lands in the honest third bucket, which costs the reader
one click. A wrong parse costs them an application.

Refusals, deliberate:
  - Hedged language ("usually", "typically", "preferred") is not a criterion and
    is never parsed.
  - Rows whose cycle or source note marks them stale/archived are never parsed;
    a stale window presented as a current exclusion is worse than no parse.
  - Year-only statements ("full-time roles in 2028") are ambiguous and skipped.
  - Sponsorship parses use explicit pattern whitelists, not sentiment. KPMG's
    practice-scoped sentence, for example, must not become "sponsors: true".

Usage:  python3 tools/parse_criteria.py [data_dir]
"""

import json
import pathlib
import re
import sys

MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}
for m in list(MONTHS):
    MONTHS[m[:3]] = MONTHS[m]
# A season is a month range; use its bounds when a quote speaks in seasons.
SEASONS = {"spring": (1, 6), "summer": (6, 8), "fall": (9, 12),
           "autumn": (9, 12), "winter": (12, 12)}

TOKEN = re.compile(
    r"\b(" + "|".join(list(MONTHS) + list(SEASONS)) + r")\.?,?\s+(20\d\d)\b", re.I)
HEDGED = re.compile(r"\busual|typical|preferr|encourag|generally\b", re.I)
STALE = re.compile(r"archiv|stale|carried over|prior cycle|not a 20\d\d[- ]cycle", re.I)
OPEN_ENDED = re.compile(r"or\s+(later|after|beyond)", re.I)
BY_ONLY = re.compile(r"\b(?:graduat\w*\s+)?(?:by|no later than|before)\s", re.I)

annotations = []
skipped = []


def ym(name, year, end=False):
    name = name.lower().rstrip(".,")
    if name in SEASONS:
        lo, hi = SEASONS[name]
        return f"{year}-{hi if end else lo:02d}"
    return f"{year}-{MONTHS[name]:02d}"


def parse_class_year(quote):
    if HEDGED.search(quote):
        return None, "hedged language, not a criterion"
    toks = TOKEN.findall(quote)
    if not toks:
        return None, None
    if len(toks) >= 2:
        a = ym(toks[0][0], toks[0][1])
        b = ym(toks[-1][0], toks[-1][1], end=True)
        if a > b:
            return None, "tokens out of order, refusing to guess"
        return {"graduates_between": [a, b]}, None
    # exactly one dated token
    tok = toks[0]
    if OPEN_ENDED.search(quote):
        return {"graduates_from": ym(tok[0], tok[1])}, None
    if BY_ONLY.search(quote[:quote.lower().find(tok[0].lower())] or quote):
        return {"graduates_by": ym(tok[0], tok[1], end=True)}, None
    return None, "single date without a direction word"


# Explicit whitelists. A pattern earns its place by matching a sentence that was
# read in full; near-misses stay unparsed on purpose.
SPONSOR_FALSE = re.compile(
    r"unable to offer visa sponsorship"
    r"|do not offer any type of employment-based immigration sponsorship"
    r"|we do not provide visa sponsorship", re.I)
SPONSOR_TRUE = re.compile(
    r"\bprovides visa sponsorship\b"
    r"|supportive of us immigration sponsorship"
    r"|visa sponsorship is available", re.I)
# Explicit acceptance of F-1 students working on CPT/OPT. Matched narrowly:
# Akuna's SWE posting says "OPT or STEM" without CPT, and must not match.
CPT_OK = re.compile(
    r"students eligible for cpt/opt"
    r"|f-1 students using cpt", re.I)
NO_FUTURE = re.compile(r"without requiring sponsorship, now or in the future", re.I)
CPT_REFUSED = re.compile(
    r"will not provide any assistance[^.]*curricular practical training", re.I)
US_AUTH_REQUIRED = re.compile(
    r"must be authorized to work in the u\.?s\.?\b", re.I)


def parse_sponsorship(quote):
    p = {}
    if SPONSOR_FALSE.search(quote):
        p["sponsors"] = False
    if SPONSOR_TRUE.search(quote):
        p["sponsors"] = True
    if CPT_OK.search(quote):
        p["cpt_ok"] = True
    if NO_FUTURE.search(quote):
        p["no_future_sponsorship"] = True
    if CPT_REFUSED.search(quote):
        p["cpt_refused"] = True
    if US_AUTH_REQUIRED.search(quote):
        p["us_work_auth_required"] = True
    return p or None


def main():
    data_dir = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "data")
    changed = 0
    for path in sorted(data_dir.glob("*.json")):
        rec = json.loads(path.read_text())
        dirty = False
        for prog in rec["programs"]:
            context = f"{prog.get('cycle','')} {prog.get('source',{}).get('note','')}"
            if STALE.search(context):
                skipped.append((rec["firm"], prog["id"], "stale/archived cycle"))
                continue

            cy = prog["fields"].get("class_year", {})
            if cy.get("state") == "stated" and "parsed" not in cy:
                parsed, why = parse_class_year(cy["quote"])
                if parsed:
                    cy["parsed"] = parsed
                    annotations.append((rec["firm"], "class_year", cy["quote"][:58], parsed))
                    dirty = True
                elif why:
                    skipped.append((rec["firm"], prog["id"], why))

            sp = prog["fields"].get("sponsorship", {})
            if sp.get("state") == "stated" and "parsed" not in sp:
                parsed = parse_sponsorship(sp["quote"])
                if parsed:
                    sp["parsed"] = parsed
                    annotations.append((rec["firm"], "sponsorship", sp["quote"][:58], parsed))
                    dirty = True
        if dirty:
            path.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n")
            changed += 1

    print(f"annotated {len(annotations)} fields across {changed} firm files\n")
    print("REVIEW EVERY LINE — the parse must not say more than the quote:")
    for firm, kind, q, parsed in annotations:
        print(f"  {firm[:24]:26} {kind:12} \"{q}…\"  ->  {json.dumps(parsed)}")
    print("\nrefused to parse:")
    for firm, pid, why in skipped:
        print(f"  {firm[:24]:26} {pid[:40]:42} {why}")


if __name__ == "__main__":
    main()
