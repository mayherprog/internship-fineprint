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

import html
import json
import pathlib
import re
import sys
from collections import Counter

SECTOR_LABEL = {
    "technology": "Technology", "banking_finance": "Banking & finance",
    "quant_trading": "Quantitative trading", "consulting": "Consulting",
    "law": "Law", "asset_management": "Asset management",
    "government": "Government", "other": "Other",
}
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


def load(data_dir):
    rows = []
    for path in sorted(pathlib.Path(data_dir).glob("*.json")):
        rec = json.loads(path.read_text())
        for prog in rec["programs"]:
            rows.append({
                "firm": rec["firm"], "sector": rec["sector"],
                "id": prog["id"], "name": prog["name"],
                "audience": prog.get("audience", "unknown"),
                "cycle": prog.get("cycle", ""), "location": prog.get("location", ""),
                "opens": prog.get("opens", ""), "closes": prog.get("closes", ""),
                "source": prog["source"], "fields": prog["fields"],
                "cooling_off": prog["cooling_off"],
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

    for sector in sorted(by_sector, key=lambda s: SECTOR_LABEL.get(s, s)):
        out += [f"## {SECTOR_LABEL.get(sector, sector)}", "",
                "| Firm | Program | For | Class year (firm's words) | Cooling-off | Checked | Source |",
                "|---|---|---|---|---|---|---|"]
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
            out.append(
                f"| {r['firm']} | {r['name'][:70]} | {AUDIENCE_LABEL.get(r['audience'], r['audience'])} "
                f"| {words} | {cooling_summary(r['cooling_off'])} "
                f"| {r['source'].get('checked', '')} | {link} |")
        out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# index.html — one self-contained file. No build step, no framework, no backend.
# --------------------------------------------------------------------------

# The page template lives beside this script so markup edits do not require
# touching Python. It is still one self-contained output file: the template
# has no external references and the data is inlined at build time.
PAGE = (pathlib.Path(__file__).parent / "template.html").read_text()


def build_html(rows, built):
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
            .replace("__BUILT__", built)
            .replace("__N__", str(len(rows))))


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    rows = load(data_dir)
    pathlib.Path("TABLE.md").write_text(build_markdown(rows) + "\n")
    pathlib.Path("index.html").write_text(build_html(rows, "2026-07-29"))
    counts = Counter(r["cooling_off"]["state"] for r in rows)
    print(f"TABLE.md and index.html: {len(rows)} programs, "
          f"{len({r['firm'] for r in rows})} firms")
    print(f"  cooling-off: {counts['stated']} stated, {counts['silent']} silent, "
          f"{counts['unverified']} unverified")


if __name__ == "__main__":
    main()
