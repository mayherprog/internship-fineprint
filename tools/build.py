#!/usr/bin/env python3
"""Generate the published views from data/: TABLE.md and index.html.

Two rules drive every rendering decision here, and they are the reason this
file is longer than a table generator needs to be:

  1. Silence never looks like an answer. A firm that publishes nothing about
     sponsorship is not a green tick and not a red cross. It gets its own
     muted treatment and the words "publishes nothing".
  2. The quote is the authority; everything else is navigation. Parsed values
     exist to let you filter. Whenever they disagree with the quote, the quote
     wins, so the quote is always on screen next to the claim.

Usage:  python3 tools/build.py [data_dir]
"""

import datetime
import html
import json
import pathlib
import re
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import validate  # noqa: E402  -- README counts come from the validator itself
from sectors import SECTORS, assert_labels_cover_schema  # noqa: E402

# Display names are the one thing the schema cannot supply: "banking_finance"
# only becomes "Banking & finance" because a human decided so. So this map is
# hand-written, and check_sector_labels() below makes an incomplete one a build
# failure -- a sector with no label would otherwise render as a heading reading
# `private_equity`, which looks like a bug in the data rather than a gap here.
SECTOR_LABEL = {
    "technology": "Technology", "banking_finance": "Banking & finance",
    "quant_trading": "Quantitative trading", "consulting": "Consulting",
    "law": "Law", "private_equity": "Private equity",
    "venture_capital": "Venture capital",
    "asset_management": "Asset management",
    "government": "Government", "other": "Other",
}


def check_sector_labels():
    """Run before any rendering. Deliberately a function rather than an
    import-time statement: importing this module for its helpers must not be
    able to abort an unrelated test session before it collects."""
    assert_labels_cover_schema(SECTOR_LABEL, "tools/build.py SECTOR_LABEL")


AUDIENCE_LABEL = {
    "undergraduate": "Undergraduate", "sophomore": "Sophomore/2nd year",
    "freshman": "First year", "law_student_jd": "Law student (JD)",
    "graduate": "Graduate", "phd": "PhD", "paralegal": "Paralegal",
    "high_school": "High school", "all": "All", "unknown": "Not stated",
}
FIELD_LABEL = {
    "class_year": "Class year", "sponsorship": "Sponsorship",
    "process": "Process", "compensation": "Compensation",
}
APPLY_KIND_LABEL = {
    "posting": "posting", "program_page": "program page",
    "careers_hub": "careers site",
}


# `opens`/`closes` in data/ sometimes carry a pipeline status marker
# ("unverified - no close date found in extracted page data") instead of
# anything a firm said. Those are maintainer-side facts about the extraction,
# not dates, and rendering one puts pipeline-ese in the deadline slot.
STATUS_MARKER_RE = re.compile(r"^\s*(?:unverified|unstated)\b|^\s*[—–-]\s*$")


def deadline_display(raw):
    """A status marker renders as the words "not stated"; a date or any
    firm-stated phrase (including "Rolling") passes through verbatim. The
    raw string stays untouched in data/, where the maintainer reads it."""
    if not raw:
        return ""
    return "not stated" if STATUS_MARKER_RE.match(raw) else raw


def load(data_dir):
    check_sector_labels()
    rows = []
    for path in sorted(pathlib.Path(data_dir).glob("*.json")):
        rec = json.loads(path.read_text())
        # The label map covering the schema is only half of it: a record could
        # still carry a sector the schema never allowed. That would render as a
        # raw slug heading, and .github/workflows/pages.yml deploys this build
        # without running validate.py first, so nothing else would catch it.
        if rec.get("sector") not in SECTORS:
            raise SystemExit(
                f"{path.name}: sector {rec.get('sector')!r} is not in "
                f"schema/program.schema.json; run tools/validate.py")
        for prog in rec["programs"]:
            rows.append({
                "firm": rec["firm"], "sector": rec["sector"],
                "id": prog["id"], "name": prog["name"],
                "audience": prog.get("audience", "unknown"),
                "cycle": prog.get("cycle", ""), "location": prog.get("location", ""),
                "opens": deadline_display(prog.get("opens", "")),
                "closes": deadline_display(prog.get("closes", "")),
                # source.note is maintainer provenance — how the page was
                # fetched, which user-agent got through, whether the answers
                # sat in a collapsed accordion. It stays in data/ for auditing
                # and is deliberately NOT shipped: this payload is served to
                # readers, so anything left in it lands on the page and in the
                # search index. The quote is the interface; scraping mechanics
                # are not.
                "source": {k: v for k, v in prog["source"].items() if k != "note"},
                # apply.note is the same case: the drawer renders only the
                # apply URL and its kind, so the note was pure payload weight
                # a reader could still read in view-source.
                "apply": ({k: v for k, v in prog["apply"].items() if k != "note"}
                          if prog.get("apply") else None),
                "fields": prog["fields"],
                # cooling_off.notes is maintainer provenance too — re-read
                # reminders, capture caveats, follow-up instructions. The
                # schema's note-like fields are source.note, apply.note,
                # cooling_off.notes and provenance.note (never loaded here);
                # summary_note is the one deliberate exception, rendered as
                # an explicitly-not-the-firm's-wording summary.
                "cooling_off": {k: v for k, v in prog["cooling_off"].items()
                                if k != "notes"},
                "unfiled": prog.get("unfiled_quotes", []),
            })
    rows.sort(key=lambda r: (r["firm"].lower(), r["name"].lower()))
    return rows


def cooling_summary(co):
    """One short phrase for a table cell. Never asserts more than the data does."""
    state = co.get("state")
    if state != "stated":
        return {"silent": "publishes nothing", "unverified": "not checked yet"}.get(state, "not checked yet")
    p = co.get("parsed") or {}
    months = p.get("duration_months")
    if months:
        n = int(months) if float(months).is_integer() else months
        return f"{n} months stated"
    return "rule stated, no duration given"


def field_summary(field):
    state = field.get("state")
    if state == "stated":
        return field["quote"]
    if state == "silent":
        return "publishes nothing"
    return field.get("summary_note") or "not checked yet"


# --------------------------------------------------------------------------
# TABLE.md — the dataset is useful with no interface at all.
# --------------------------------------------------------------------------

def build_markdown(rows):
    counts = Counter(r["cooling_off"]["state"] for r in rows)
    firms = len({r["firm"] for r in rows})
    out = [
        "# Internship eligibility — the published record",
        "",
        "Generated from `data/` by `tools/build.py`. Do not edit by hand.",
        "",
        f"**{len(rows)} programs across {firms} firms.** "
        f"Cooling-off: {counts.get('stated', 0)} stated, "
        f"{counts.get('silent', 0)} publish nothing, "
        f"{counts.get('unverified', 0)} not yet checked.",
        "",
        "Every quote is the firm's own wording. **A firm's current page is always the "
        "authority** — these rows are a dated snapshot and firms rewrite pages without notice.",
        "",
        "`publishes nothing` is a fact about the public record, not a statement that a "
        "firm has no such policy. Silence is not permission and not prohibition.",
        "",
    ]
    by_sector = {}
    for r in rows:
        by_sector.setdefault(r["sector"], []).append(r)

    # Indexed, not .get(s, s): load() has already refused any sector the schema
    # does not allow, so a KeyError here means that guarantee was removed.
    for sector in sorted(by_sector, key=lambda s: SECTOR_LABEL[s]):
        out += [f"## {SECTOR_LABEL[sector]}", "",
                "| Firm | Program | For | Class year (firm's words) | Cooling-off | Checked | Source | Apply |",
                "|---|---|---|---|---|---|---|---|"]
        for r in by_sector[sector]:
            cy = r["fields"]["class_year"]
            words = field_summary(cy).replace("|", "\\|")
            if len(words) > 150:
                words = words[:147] + "…"
            if cy.get("state") == "stated":
                words = f'"{words}"'
            url = r["source"].get("url")
            status = r["source"].get("status")
            link = f"[link]({url})" if url else {
                "url_pending": "_no URL yet_", "blocked": "_blocked_",
                "dead": "_dead link_"}.get(status, "_none_")
            ap = r.get("apply") or {}
            apply_cell = (f"[{APPLY_KIND_LABEL.get(ap.get('kind'), 'apply')}]({ap['url']})"
                          if ap.get("url") else "_none_")
            out.append(
                f"| {r['firm']} | {r['name'][:70]} | {AUDIENCE_LABEL.get(r['audience'], r['audience'])} "
                f"| {words} | {cooling_summary(r['cooling_off'])} "
                f"| {r['source'].get('checked', '')} | {link} | {apply_cell} |")
        out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# README.md — every count in it is injected between <!-- GEN:name --> markers,
# the same way TABLE.md is regenerated, so the README can never again claim
# totals the data has outgrown. Prose is hand-written (here, as templates);
# numbers are always computed.
# --------------------------------------------------------------------------

def sector_phrase(rows):
    c = Counter(r["sector"] for r in rows)
    labels = [SECTOR_LABEL[s].lower().replace(" & ", " and ")
              for s, _ in c.most_common() if s != "other"]
    if "other" in c:
        labels.append("others")
    return ", ".join(labels[:-1]) + " and " + labels[-1]


def readme_sections(rows, data_dir):
    """The generated regions of README.md, keyed by marker name."""
    _, programs, passes, fails = validate.run(data_dir)
    assertions = passes + len(fails)
    counts = Counter(r["cooling_off"]["state"] for r in rows)
    status = Counter(r["source"].get("status") for r in rows)
    firms = len({r["firm"] for r in rows})
    dead_rows = [r for r in rows if r["source"].get("status") == "dead"]
    dead_fields = [list(r["fields"].values()) + [r["cooling_off"]] for r in dead_rows]
    dead_no_quote = sum(1 for fs in dead_fields
                        if not any(f.get("quote") for f in fs))
    dead_all_unver = sum(1 for fs in dead_fields
                         if all(f["state"] == "unverified" for f in fs))
    quickstart = (
        "```bash\n"
        "python3 -m unittest discover -s tests   # parser/dedup/scrub/verifier unit tests\n"
        f"python3 tools/validate.py               # {assertions:,} assertions over "
        f"{len(rows)} programs, {len(fails)} failures\n"
        "python3 tools/verify_quotes.py data     # re-fetch every cited page; "
        "quotes must still be there\n"
        "```")
    coverage = (
        f"{len(rows)} programs across {firms} firms, spanning\n"
        f"{sector_phrase(rows)}.\n"
        "On cooling-off specifically:\n"
        f"**{counts.get('stated', 0)} state a rule, {counts.get('silent', 0)} publish "
        f"nothing on it, and {counts.get('unverified', 0)} have not been checked yet.** "
        "The\nunchecked share is the honest state of this dataset today, not a rounding "
        "error, and it is\nvisible in the interface rather than hidden.\n"
        "\n"
        "Known gaps, all recorded in the data rather than papered over:\n"
        "\n"
        f"- **{status.get('url_pending', 0)} programs are `url_pending`** — transcribed "
        "from a private posting tracker whose\n  links were not captured. They render as "
        "*no URL yet* and are not independently citable\n  until re-sourced.\n"
        f"- **{status.get('blocked', 0)} programs are `blocked`** — the page is "
        "JavaScript-rendered or refuses automated\n  reads. These need a browser, "
        "not a fetch.\n"
        f"- **{status.get('dead', 0)} programs are `dead`** — the URL returns a non-200 "
        "or refuses the connection, in\n  nearly every case because the posting or "
        f"program page was taken down between cycles.\n  {dead_no_quote} of the "
        f"{status.get('dead', 0)} carry no quote at all, and {dead_all_unver} are "
        "`unverified` on every field, because a\n  page that cannot be read cannot "
        "be said to publish nothing.")
    return {"quickstart": quickstart, "coverage": coverage}


def inject_readme(rows, data_dir, path=None):
    path = path or pathlib.Path("README.md")
    text = path.read_text()
    for name, content in readme_sections(rows, data_dir).items():
        begin, end = f"<!-- GEN:{name} -->", f"<!-- /GEN:{name} -->"
        if begin not in text or end not in text:
            raise SystemExit(f"README.md is missing the {begin} … {end} markers")
        before, rest = text.split(begin, 1)
        _, after = rest.split(end, 1)
        text = before + begin + "\n" + content + "\n" + end + after
    path.write_text(text)


# --------------------------------------------------------------------------
# index.html — one self-contained file. No build step, no framework, no backend.
# --------------------------------------------------------------------------

# The page template lives beside this script so markup edits do not require
# touching Python. It is still one self-contained output file: the template
# has no external references and the data is inlined at build time.
PAGE = (pathlib.Path(__file__).parent / "template.html").read_text()


def last_checked(rows):
    """The newest source.checked date across every record: the honest
    freshness of the data, as distinct from the date the site was built."""
    return max((r["source"].get("checked") or "" for r in rows), default="")


def build_html(rows, built, checked):
    # The template carries a self-identifying banner so that opening the raw
    # file never impersonates a broken app; the build strips it.
    page = re.sub(r"<!--TEMPLATE-ONLY-->.*?<!--/TEMPLATE-ONLY-->\n?", "", PAGE, flags=re.S)
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    # The payload sits inside a <script> block, so a literal </script> in any
    # quoted sentence would end the block early. Neutralise it.
    payload = payload.replace("</", "<\\/")
    return (page
            .replace("__DATA__", payload)
            .replace("__SECTORS__", json.dumps(SECTOR_LABEL))
            .replace("__AUD__", json.dumps(AUDIENCE_LABEL))
            .replace("__FIELDS__", json.dumps(FIELD_LABEL))
            .replace("__CHECKED__", checked)
            .replace("__BUILT__", built))


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    rows = load(data_dir)
    pathlib.Path("TABLE.md").write_text(build_markdown(rows) + "\n")
    # Two dates, both honest: when the data was last checked (from the
    # records) and when this page was generated (today — the Pages workflow
    # rebuilds on every deploy, so a hardcoded date here would lie).
    pathlib.Path("index.html").write_text(
        build_html(rows, datetime.date.today().isoformat(), last_checked(rows)))
    inject_readme(rows, data_dir)
    counts = Counter(r["cooling_off"]["state"] for r in rows)
    print(f"TABLE.md and index.html: {len(rows)} programs, "
          f"{len({r['firm'] for r in rows})} firms")
    print(f"  cooling-off: {counts['stated']} stated, {counts['silent']} silent, "
          f"{counts['unverified']} unverified")


if __name__ == "__main__":
    main()
