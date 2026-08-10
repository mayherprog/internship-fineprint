#!/usr/bin/env python3
"""Normalise raw per-firm research output (research/) into schema records (data/).

Research agents return a near-schema shape. This step makes it exactly legal
without ever touching a quote. Everything it does is one of:

  - drop empty quote strings, so a `silent` row cannot look like a claim
  - turn "" source URLs into null
  - fold a stray field-level `note` into `summary_note`, which is only legal
    on `unverified` rows, and drop it otherwise
  - coerce a free-text `audience` down to the closest enum value
  - refuse to publish a program the researcher could not even locate
  - move a cooling-off quote that is not about reapplying out of the
    cooling-off field, rather than letting it masquerade as one

The last rule is the important one. An agent filed Morgan Stanley's "you can
select and rank up to three preferred office locations" under cooling_off. It
is a real, correctly quoted sentence, and it is not a reapplication rule. Left
alone it would render as "Morgan Stanley states a cooling-off policy", which is
false. It moves to unfiled_quotes and the cooling-off field returns to silent.

Usage:  python3 tools/ingest_research.py [research_dir] [data_dir]
"""

import json
import pathlib
import re
import sys
import unicodedata

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sectors import SECTORS  # noqa: E402  -- the schema is the source of truth

AUDIENCE = ("undergraduate", "sophomore", "freshman", "law_student_jd",
            "graduate", "phd", "paralegal", "high_school", "all", "unknown")

# Researchers occasionally filed a program under the wrong audience while
# quoting the sentence that proves it wrong (one noted the schema "has no
# freshman value" - it does). The quote wins over the parsed label, so these
# overrides realign the label with the firm's own quoted words:
#   freshman-enhancement-program      "Freshman Enhancement Program" (Morgan Stanley)
#   goldman-sachs-possibilities-series  "First year undergraduate students..."
#   amazon-future-engineer-scholarship  "Be a high school senior in the U.S. ..."
#   consulting-kickstart              "We welcome first-year (freshman) undergraduate students..."
AUDIENCE_OVERRIDES = {
    "freshman-enhancement-program": "freshman",
    "goldman-sachs-possibilities-series": "freshman",
    "amazon-future-engineer-scholarship": "high_school",
    "consulting-kickstart": "freshman",
}

# Tracker rows whose recorded sentence was checked against the live page and
# NOT FOUND there. Refuted quotes must not keep circulating as pending claims;
# each entry names the evidence. Verified on 2026-07-29.
REFUTED_ROWS = {
    ("Hudson River Trading", "hrt-swe-intern-2027-summer-2027"):
        "Recorded sentence 'Eligible for full-time roles in 2028.' does not appear "
        "in the live posting (Greenhouse job 8052083 read in full: no occurrence of "
        "'2028' or 'eligib'). Superseded by the current posting's stated criterion.",
}

# URL-less tracker watch rows made fully redundant by later sourced rows for
# the same firm — nothing refuted, just no residual information: no quote, no
# URL, and every role they name now has its own sourced row.
REDUNDANT_WATCH_ROWS = {
    ("Aquatic Capital", "aquatic-capital-swe-qr-2027-summer-2027"):
        "Combined SWE/QR watch row; both roles recorded as sourced rows "
        "(Greenhouse 8489186002, 8489233002) on 2026-07-29.",
}
FIELD_KEYS = ("class_year", "sponsorship", "process", "compensation")
FIELD_ALLOWED = {"state", "tier", "quote", "source_url", "source_status",
                 "checked", "summary_note", "parsed"}
COOLING_ALLOWED = FIELD_ALLOWED | {"notes"}
PARSED_ALLOWED = {"trigger", "duration_months", "scope", "resets_allowed",
                  "restrictive", "application_cap"}

# A cooling-off row must be about applying again, sitting an assessment again,
# waiting, or a cap on applications. If none of this vocabulary appears, it is
# not a cooling-off rule. (Season-exclusivity clauses like Akuna's "you will
# not be considered for other ... roles ... this recruiting season" are caps.)
REAPPLY_RE = re.compile(
    r"re-?appl|reappl|new application|apply again|retake|re-?take|"
    r"waiting period|wait\b|refrain|back to back|back-to-back|each year|"
    r"future program year|attempt|cooling|recruiting season|"
    r"one application|multiple applications|per role|not be considered for other",
    re.I,
)

# A recommendation is not a lockout. Jane Street "usually recommend[s] waiting
# ... at least a year"; rendering that as a hard 12-month clock in the lockout
# view would assert more than the firm said. Hedged rules keep their quote and
# their parsed duration, but restrictive stays null: the reader reads the quote.
HEDGED_RULE_RE = re.compile(r"\brecommend|usually|encourage|suggest\b", re.I)

# A stated one-application rule IS a cap of one, derivable from the quote alone.
ONE_APP_RE = re.compile(
    r"one application per role|not be considered for other .{0,40}roles?"
    r".{0,40}(this )?recruiting season|do not allow multiple applications|"
    r"only apply to one",
    re.I,
)

moved, dropped, deduped = [], [], []


def slug(text):
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")) or "unnamed"


def clean_audience(value):
    v = (value or "").strip().lower()
    for a in AUDIENCE:
        if v.startswith(a):
            return a
    for a in AUDIENCE:
        if a in v:
            return a
    return "unknown"


def clean_field(field, allowed=FIELD_ALLOWED):
    out = {}
    note = (field.get("note") or "").strip()
    for k, v in field.items():
        if k in allowed:
            out[k] = v

    quote = (out.get("quote") or "").strip()
    if quote:
        out["quote"] = quote
    else:
        out.pop("quote", None)

    if not (out.get("source_url") or "").strip():
        out["source_url"] = None

    state = out.get("state")
    if state not in ("stated", "silent", "unverified"):
        state = out["state"] = "unverified"

    # A quote is the only thing that licenses "stated".
    if state == "stated" and "quote" not in out:
        out["state"] = state = "unverified"

    # You cannot report that a firm publishes nothing unless you can say which
    # page you read. Silence with no URL is not silence, it is an unchecked box.
    if state == "silent" and out.get("source_url") is None:
        out["state"] = state = "unverified"

    # Explanatory notes are legal only where nothing is being claimed.
    existing = (out.get("summary_note") or "").strip()
    merged = " ".join(x for x in (existing, note) if x).strip()
    if merged and state == "unverified":
        out["summary_note"] = merged
    else:
        out.pop("summary_note", None)

    if "parsed" in out and isinstance(out["parsed"], dict):
        out["parsed"] = {k: v for k, v in out["parsed"].items() if k in PARSED_ALLOWED}

    if out.get("source_url") is None and "quote" in out and not out.get("source_status"):
        out["source_status"] = "url_pending"
    return out


def clean_cooling(cooling, unfiled):
    out = clean_field(cooling, COOLING_ALLOWED)
    notes = (cooling.get("notes") or "").strip()
    if notes:
        out["notes"] = notes
    else:
        out.pop("notes", None)

    quote = out.get("quote")
    if quote and not REAPPLY_RE.search(quote):
        unfiled.append({
            "quote": quote,
            "source_url": out.get("source_url"),
            "source_status": out.get("source_status") or "ok",
        })
        moved.append(quote[:70])
        out.pop("quote", None)
        out.pop("source_status", None)
        out["state"] = "silent" if out.get("source_url") else "unverified"
        prior = out.get("notes", "")
        out["notes"] = (
            "A quote originally filed here was moved to unfiled_quotes because it "
            "does not concern reapplying, waiting, or retaking an assessment. " + prior
        ).strip()

    parsed = {k: v for k, v in (out.get("parsed") or {}).items() if v != ""}
    if out.get("state") == "stated":
        quote2 = out.get("quote") or ""
        if ONE_APP_RE.search(quote2) and not parsed.get("application_cap"):
            parsed["application_cap"] = 1
        # Derived only from what the firm itself stated. Never guessed, and a
        # hedged recommendation is never promoted to a hard constraint.
        if HEDGED_RULE_RE.search(quote2):
            parsed["restrictive"] = None
        elif parsed.get("duration_months") is not None:
            parsed["restrictive"] = True
        elif parsed.get("resets_allowed") is False or parsed.get("application_cap"):
            parsed["restrictive"] = True
        else:
            parsed["restrictive"] = None
    if parsed:
        out["parsed"] = parsed
    else:
        out.pop("parsed", None)
    return out


def normalise(rec):
    programs = []
    for prog in rec.get("programs") or []:
        source = dict(prog.get("source") or {})
        source = {k: v for k, v in source.items()
                  if k in {"url", "checked", "check_method", "content_hash", "status", "note"}}
        if not (source.get("url") or "").strip():
            source["url"] = None

        # If the researcher could not even locate the program, it is not a row.
        if source.get("status") == "dead" and source["url"] is None:
            dropped.append(f"{rec.get('firm')}: {prog.get('name','?')[:50]}")
            continue

        if source.get("status") not in ("ok", "url_pending", "blocked", "dead"):
            source["status"] = "ok" if source["url"] else "url_pending"
        if source["url"] is None and not (source.get("note") or "").strip():
            source["note"] = "No source URL was recorded by the researcher."

        unfiled = list(prog.get("unfiled_quotes") or [])
        fields = prog.get("fields") or {}
        pid = slug(prog.get("name") or "program")[:80].strip("-")
        out = {
            "id": pid,
            "name": prog.get("name") or "Unnamed program",
            "audience": next((v for k, v in AUDIENCE_OVERRIDES.items()
                              if pid.startswith(k)),
                             clean_audience(prog.get("audience"))),
            "source": source,
            "fields": {k: clean_field(dict(fields.get(k) or {"state": "unverified"}))
                       for k in FIELD_KEYS},
            "cooling_off": clean_cooling(dict(prog.get("cooling_off") or {"state": "unverified"}), unfiled),
        }
        for key in ("cycle", "location", "status", "opens", "closes"):
            if (prog.get(key) or "").strip():
                out[key] = prog[key].strip()
        if unfiled:
            out["unfiled_quotes"] = [
                {"quote": u["quote"], "source_url": u.get("source_url") or None,
                 "source_status": u.get("source_status") or "ok"}
                for u in unfiled if (u.get("quote") or "").strip()
            ]
        programs.append(out)

    seen = {}
    for p in programs:  # ids must be unique within a firm file
        base = p["id"]
        if base in seen:
            seen[base] += 1
            p["id"] = f"{base}-{seen[base]}"
        else:
            seen[base] = 1

    # Research files are raw output and still carry the original sector
    # spellings; the schema renamed big_tech/big_law to plain names.
    sector = {"big_tech": "technology", "big_law": "law"}.get(
        rec.get("sector"), rec.get("sector"))
    return {
        "firm": (rec.get("firm") or "").replace("&amp;", "&").strip(),
        "sector": sector if sector in SECTORS else "other",
        "programs": programs,
        "provenance": {
            "origin": "per-firm web research, one agent per firm",
            "transcribed": "2026-07-29",
            "note": "Quotes were copied from the firm's own pages by the researching "
                    "agent and passed through normalisation untouched. Rows the "
                    "researcher could not locate were dropped, not guessed.",
        },
    }


def main():
    src = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "research")
    dst = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "data")
    dst.mkdir(parents=True, exist_ok=True)
    n = p = merged_in = 0
    for path in sorted(src.glob("*.json")):
        rec = normalise(json.loads(path.read_text()))
        if not rec["programs"]:
            continue
        target = dst / f"{slug(rec['firm'])}.json"

        # A firm may already have rows transcribed from the tracker. Research
        # ADDS to those; it must never silently replace a sourced posting.
        if target.exists():
            existing = json.loads(target.read_text())
            have = {q["id"] for q in rec["programs"]}
            keep = [q for q in existing.get("programs", []) if q["id"] not in have]

            # When both sides cite the SAME posting URL they are the same row
            # twice. Keep whichever carries more verified fields; showing a
            # stale duplicate next to a verified row misinforms twice over.
            def score(p):
                fields = list((p.get("fields") or {}).values()) + [p.get("cooling_off") or {}]
                return sum(1 for f in fields if f.get("state") == "stated")

            def norm(url):
                """Same posting, different slug: ATS URLs carry a numeric job id
                (Google's /jobs/results/<id>-<slug>, Greenhouse's /jobs/<id>).
                Collapse id-led path segments to the id so slug variants match."""
                if not url:
                    return None
                u = re.sub(r"^https?://(www\.)?", "", url.lower()).rstrip("/")
                u = u.split("?")[0]
                # Greenhouse serves one posting from two hosts; collapse both
                # to org/jobs/id so they dedupe as the same posting.
                m = re.match(
                    r"(?:job-boards|boards)\.greenhouse\.io/([^/]+)/jobs/(\d+)"
                    r"|boards-api\.greenhouse\.io/v1/boards/([^/]+)/jobs/(\d+)", u)
                if m:
                    org = m.group(1) or m.group(3)
                    jid = m.group(2) or m.group(4)
                    return f"greenhouse/{org}/{jid}"
                return "/".join(re.match(r"^(\d{8,})", s).group(1)
                                if re.match(r"^(\d{8,})", s) else s
                                for s in u.split("/"))

            research_by_url = {norm(p["source"].get("url")): p for p in rec["programs"]
                               if p["source"].get("url")}

            # A tracker row with a quote but no URL was a verification debt.
            # When research has now read the live posting, the debt is settled
            # either way: a matching quote means the row is superseded by the
            # sourced version; a refuted quote (recorded sentence absent from
            # the live page) must not keep circulating as a pending claim.
            def words(text):
                return set(re.findall(r"[a-z0-9]+", (text or "").lower()))

            def cy_quote(p):
                return (p.get("fields", {}).get("class_year", {}) or {}).get("quote", "")

            research_cy = [cy_quote(p) for p in rec["programs"] if cy_quote(p)]

            def superseded(q):
                if q["source"].get("url"):
                    return False
                pending = cy_quote(q)
                if not pending:
                    return False
                pw = words(pending)
                for rq in research_cy:
                    rw = words(rq)
                    low_p, low_r = pending.lower().strip(". "), rq.lower()
                    if low_p in low_r or (pw and len(pw & rw) / len(pw | rw) >= 0.6):
                        return True
                return False

            deduped_keep = []
            for q in keep:
                reason = REFUTED_ROWS.get((rec["firm"], q["id"]))
                if reason:
                    deduped.append(f"{rec['firm']}: row {q['id']} DROPPED, quote refuted against the live page — {reason[:80]}...")
                    continue
                if superseded(q):
                    deduped.append(f"{rec['firm']}: pending-quote row {q['id']} superseded by a sourced research row")
                    continue
                if (rec["firm"], q["id"]) in REDUNDANT_WATCH_ROWS:
                    deduped.append(f"{rec['firm']}: watch row {q['id']} redundant — "
                                   + REDUNDANT_WATCH_ROWS[(rec["firm"], q["id"])])
                    continue
                rival = research_by_url.get(norm(q["source"].get("url")))
                if rival is None:
                    deduped_keep.append(q)
                elif score(q) > score(rival):
                    rec["programs"].remove(rival)   # tracker row is the better one
                    deduped_keep.append(q)
                    deduped.append(f"{rec['firm']}: research row was the weaker duplicate of {q['id']}")
                else:
                    deduped.append(f"{rec['firm']}: tracker row was the weaker duplicate of {rival['id']}")
            keep = deduped_keep

            merged_in += len(keep)
            rec["programs"] = rec["programs"] + keep
            prov = existing.get("provenance", {}).get("note", "")
            rec["provenance"]["note"] += " Merged with rows transcribed from a private posting tracker." if prov else ""

        target.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n")
        n += 1
        p += len(rec["programs"])
    if merged_in:
        print(f"  merged in {merged_in} pre-existing tracker rows rather than overwriting them")
    print(f"normalised {n} firms, {p} programs -> {dst}/")
    for m in moved:
        print(f"  MOVED out of cooling_off (not a reapplication rule): {m}...")
    for d in dropped:
        print(f"  DROPPED (program could not be located): {d}")
    for d in deduped:
        print(f"  DEDUPED (same posting recorded twice): {d}")


if __name__ == "__main__":
    main()
