#!/usr/bin/env python3
"""Validate every record in data/ against the rules that make this data trustworthy.

Dependency-free on purpose, in the style of the test suite in
mayherprog/registered-backtests: each check asserts an invariant the data could
plausibly violate, rather than restating the schema.

The rules being enforced, in plain English:

  1. `stated` requires a verbatim quote. A claim that a firm says something is
     only publishable if the firm's sentence is right there.
  2. Nothing but `stated` may carry a quote. A quote on a `silent` row would
     mean the row contradicts itself.
  3. `summary_note` is only legal on `unverified`. It is the escape hatch for
     "a human wrote a summary and nobody has checked the source", and it must
     never sit next to a claim that the firm stated something.
  4. `silent` requires a source URL. You cannot report that a firm publishes
     nothing unless you can say which page you read.
  5. A quote requires either a source URL or an explicit reason there isn't one
     (`url_pending`, `blocked`). Quotes with no provenance are how a private
     note becomes a public fact.
  6. Tier 3 may never be the sole basis for a cooling-off claim. Aggregated
     candidate reports establish "widely reported", never "true", and a wrong
     cooling-off row is the most expensive error this project can make.

Usage:  python3 tools/validate.py [data_dir]
"""

import json
import pathlib
import re
import sys

STATES = {"stated", "silent", "unverified"}
TIERS = {1, 2, 3}
SOURCE_STATUS = {"ok", "url_pending", "blocked", "dead"}
APPLY_KINDS = {"posting", "program_page", "careers_hub"}
AUDIENCE = {
    "undergraduate", "sophomore", "freshman", "law_student_jd",
    "graduate", "phd", "paralegal", "high_school", "all", "unknown",
}
SECTORS = {
    "technology", "banking_finance", "quant_trading", "consulting",
    "law", "asset_management", "government", "other",
}
TRIGGERS = {"assessment_attempt", "rejection", "application", "offer_declined", "unknown"}
SCOPES = {"this_role", "this_program", "all_roles", "all_offices_all_roles", "unknown"}
FIELD_KEYS = ("class_year", "sponsorship", "process", "compensation")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SLUG_RE = re.compile(r"^[a-z0-9-]+$")

failures = []
passes = 0


def check(name, cond, detail=""):
    global passes
    if cond:
        passes += 1
    else:
        failures.append(f"{name}" + (f"  --  {detail}" if detail else ""))


def check_field(where, field, is_cooling_off=False):
    state = field.get("state")
    quote = field.get("quote")
    url = field.get("source_url")
    status = field.get("source_status")

    check(f"{where}: state is legal", state in STATES, f"got {state!r}")

    # Rule 1 — a claim needs the firm's own sentence.
    if state == "stated":
        check(f"{where}: stated carries a verbatim quote",
              isinstance(quote, str) and quote.strip() != "",
              "state is 'stated' but there is no quote")

    # Rule 2 — nothing else may carry one.
    if state in ("silent", "unverified"):
        check(f"{where}: non-stated row carries no quote",
              quote in (None, ""),
              f"state is {state!r} but a quote is present: {str(quote)[:60]!r}")

    # Rule 3 — summaries are never presented as the firm's words.
    if "summary_note" in field:
        check(f"{where}: summary_note only on unverified",
              state == "unverified",
              f"summary_note present while state is {state!r}")

    # Rule 4 — silence is a claim about a page you actually read.
    if state == "silent":
        check(f"{where}: silent names the page that was checked",
              bool(url),
              "state is 'silent' but no source_url records what was read")

    # Rule 5 — a quote must be traceable, or say why it isn't.
    if quote:
        check(f"{where}: quote is traceable",
              bool(url) or status in ("url_pending", "blocked"),
              "quote has neither a source_url nor a stated reason for lacking one")
        check(f"{where}: quote is not a fragment marker",
              "..." not in quote[:4] and not quote.strip().startswith("…"),
              f"quote looks truncated: {quote[:50]!r}")

    if "tier" in field:
        check(f"{where}: tier is 1, 2 or 3", field["tier"] in TIERS, f"got {field.get('tier')!r}")
    if status is not None:
        check(f"{where}: source_status is legal", status in SOURCE_STATUS, f"got {status!r}")
    if "checked" in field:
        check(f"{where}: checked is ISO date", bool(DATE_RE.match(field["checked"] or "")),
              f"got {field.get('checked')!r}")

    # Machine-readable graduation windows may only annotate a stated quote,
    # and must be well-formed: the screener's exclusions ride on them.
    parsed = field.get("parsed") or {}
    if any(k in parsed for k in ("graduates_between", "graduates_from", "graduates_by")):
        check(f"{where}: graduation parse annotates a stated quote",
              state == "stated" and bool(quote),
              "a parsed window exists without the quote that justifies it")
        gb = parsed.get("graduates_between")
        if gb is not None:
            ok = (isinstance(gb, list) and len(gb) == 2 and
                  all(re.match(r"^\d{4}-\d{2}$", str(x)) for x in gb) and gb[0] <= gb[1])
            check(f"{where}: graduates_between is an ordered YYYY-MM pair", ok, f"got {gb!r}")
        for key in ("graduates_from", "graduates_by"):
            if key in parsed:
                check(f"{where}: {key} is YYYY-MM",
                      bool(re.match(r"^\d{4}-\d{2}$", str(parsed[key]))),
                      f"got {parsed[key]!r}")

    # Rule 6 — the most expensive field may not rest on forum reports alone.
    if is_cooling_off and state == "stated":
        check(f"{where}: cooling-off claim is not tier 3 alone",
              field.get("tier") in (1, 2),
              "a cooling-off period is asserted on tier 3 (aggregated candidate reports)")
        parsed = field.get("parsed") or {}
        if "trigger" in parsed:
            check(f"{where}: cooling-off trigger is legal",
                  parsed["trigger"] in TRIGGERS, f"got {parsed.get('trigger')!r}")
        if "scope" in parsed:
            check(f"{where}: cooling-off scope is legal",
                  parsed["scope"] in SCOPES, f"got {parsed.get('scope')!r}")


def check_program(firm, prog):
    pid = prog.get("id", "<no id>")
    where = f"{firm}/{pid}"

    check(f"{where}: id is a slug", bool(SLUG_RE.match(pid or "")), f"got {pid!r}")
    check(f"{where}: has a name", bool((prog.get('name') or '').strip()))
    check(f"{where}: audience is legal", prog.get("audience") in AUDIENCE,
          f"got {prog.get('audience')!r}")

    source = prog.get("source") or {}
    check(f"{where}: source status is legal", source.get("status") in SOURCE_STATUS,
          f"got {source.get('status')!r}")
    check(f"{where}: source checked is ISO date", bool(DATE_RE.match(source.get("checked") or "")),
          f"got {source.get('checked')!r}")
    # A row with no URL must say why, so the gap is visible rather than silent.
    if not source.get("url"):
        check(f"{where}: missing URL is explained",
              source.get("status") in ("url_pending", "blocked", "dead") and bool(source.get("note")),
              "no source URL and no note explaining why")

    # Rule 7 — every program carries a navigable apply link: the live posting
    # when one exists, otherwise the firm's own program page or careers hub.
    # Navigation only — the link never implies anything about eligibility.
    apply = prog.get("apply") or {}
    check(f"{where}: has an apply link", bool(apply.get("url")),
          "every program must link a page a candidate can apply from")
    if apply:
        check(f"{where}: apply url is https",
              str(apply.get("url") or "").startswith("https://"),
              f"got {apply.get('url')!r}")
        check(f"{where}: apply kind is legal", apply.get("kind") in APPLY_KINDS,
              f"got {apply.get('kind')!r}")
        if apply.get("checked"):
            check(f"{where}: apply checked is ISO date",
                  bool(DATE_RE.match(apply["checked"])),
                  f"got {apply.get('checked')!r}")

    fields = prog.get("fields") or {}
    for key in FIELD_KEYS:
        check(f"{where}: has field {key}", key in fields)
        if key in fields:
            check_field(f"{where}.{key}", fields[key])

    check(f"{where}: has cooling_off", "cooling_off" in prog)
    if "cooling_off" in prog:
        check_field(f"{where}.cooling_off", prog["cooling_off"], is_cooling_off=True)

    for i, uq in enumerate(prog.get("unfiled_quotes") or []):
        check(f"{where}.unfiled[{i}]: has a quote", bool((uq.get('quote') or '').strip()))


def main():
    data_dir = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "data")
    files = sorted(data_dir.glob("*.json"))
    if not files:
        sys.exit(f"no records found in {data_dir}/")

    seen_ids = {}
    programs = 0
    for path in files:
        try:
            rec = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            check(f"{path.name}: parses as JSON", False, str(e))
            continue

        check(f"{path.name}: has a firm name", bool((rec.get('firm') or '').strip()))
        # A firm name is a firm, not a posting title. "Five Rings QT Intern
        # 2027" as a firm means transcription leaked a program title upward.
        check(f"{path.name}: firm name is not a posting title",
              not re.search(r"\b(Intern(ship)?s?|Summer|20\d\d|Analyst|Placement)\b",
                            rec.get("firm") or "", re.I),
              f"firm reads as a posting: {rec.get('firm')!r}")
        check(f"{path.name}: sector is legal", rec.get("sector") in SECTORS,
              f"got {rec.get('sector')!r}")
        check(f"{path.name}: has at least one program", bool(rec.get("programs")))

        firm = rec.get("firm", path.stem)
        for prog in rec.get("programs") or []:
            programs += 1
            key = (path.name, prog.get("id"))
            check(f"{firm}: program id {prog.get('id')!r} is unique in file",
                  key not in seen_ids)
            seen_ids[key] = True
            check_program(firm, prog)

    print(f"\n{len(files)} firm files, {programs} programs\n")
    for f in failures:
        print(f"FAIL  {f}")
    print(f"\n{passes} passed, {len(failures)} failed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
