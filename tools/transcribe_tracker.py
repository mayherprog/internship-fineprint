#!/usr/bin/env python3
"""Transcribe a private posting tracker (.xlsx) into the public record schema.

The point of doing this in code rather than by hand: a script cannot mistype a
firm's sentence. Every `quote` in the output is a byte-for-byte substring of a
quoted span in the spreadsheet. Nothing is rewritten, shortened or smoothed.

Anything in the spreadsheet that is NOT inside quotation marks is the tracker
author's own summary. It is never written to a `quote` field. It goes to
`summary_note` with the field marked `unverified`, which is what it is.

The source spreadsheet is personal and is not published. This script documents
how the public rows were derived; run it yourself against your own tracker.

Usage:
    python3 tools/transcribe_tracker.py path/to/tracker.xlsx [--out data]
"""

import argparse
import json
import pathlib
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

# Quotation marks the tracker actually uses, straight and curly.
QUOTE_RE = re.compile(r'[""“”"]([^""“”"]{8,})[""“”"]')

SPONSORSHIP_KEYS = (
    "sponsor", "visa", "work authoriz", "work authoris", "cpt", "opt",
    "citizen", "permanent resident", "green card", "clearance",
    "right to work", "immigration",
)
CLASS_YEAR_KEYS = (
    "graduat", "class of", "standing", "rising", "pursuing", "degree",
    "junior", "senior", "sophomore", "freshman", "first-year", "second-year",
    "credit hour", "enrolled", "returning to school", "academic year",
    "final year", "year remaining", "completion of at least", "bachelor",
    "master", "phd", "undergraduate",
)
PROCESS_KEYS = (
    "interview", "assessment", "onsite", "superday", "hirevue", "video",
    "online test", "case study", "screening", "round",
)

SECTOR_MAP = {
    "swe": "technology",
    "finance/quant": "quant_trading",
    "swe/quant": "quant_trading",
    "quant": "quant_trading",
    "finance": "banking_finance",
    "consulting": "consulting",
    "law": "law",
}

# The tracker's "Firm / Program" column mixes firm names with posting titles
# ("Five Rings QT Intern 2027" is a posting, not a firm). Splitting heuristics
# alone produced duplicate firm files and titles-as-firms. This table maps a
# recognised prefix to the canonical firm name and its sector. Longest prefix
# wins, so "two sigma freshman" is checked before "two sigma".
CANON = {
    "sig / five rings": ("SIG / Five Rings / Optiver (trader development)", "quant_trading"),
    "two sigma freshman": ("Two Sigma / Jane Street / Goldman Sachs (freshman programs)", "quant_trading"),
    "hrt witti": ("HRT / Virtu (women's programs)", "quant_trading"),
    "amazon future": ("Amazon", "technology"),
    "bank junior": ("Multiple banks (junior-cycle programs)", "banking_finance"),
    "barclays": ("Barclays / Deutsche Bank / UBS / Jefferies / HSBC", "banking_finance"),
    "d. e. shaw": ("D. E. Shaw", "quant_trading"),
    "chicago trading": ("Chicago Trading Company", "quant_trading"),
    "cubist": ("Cubist Systematic Strategies (Point72)", "quant_trading"),
    "voloridge": ("Voloridge Investment Management", "quant_trading"),
    "susquehanna": ("Susquehanna (SIG)", "quant_trading"),
    "arrowstreet": ("Arrowstreet Capital", "asset_management"),
    "bank of america": ("Bank of America", "banking_finance"),
    "bofa": ("Bank of America", "banking_finance"),
    "citi": ("Citi", "banking_finance"),
    "citadel": ("Citadel / Citadel Securities", "quant_trading"),
    "goldman": ("Goldman Sachs", "banking_finance"),
    "morgan stanley": ("Morgan Stanley", "banking_finance"),
    "jpmc": ("JPMorgan Chase", "banking_finance"),
    "wells fargo": ("Wells Fargo", "banking_finance"),
    "capital one": ("Capital One", "banking_finance"),
    "ny fed": ("Federal Reserve Bank of New York", "government"),
    "bridgewater": ("Bridgewater Associates", "asset_management"),
    "girls who invest": ("Girls Who Invest", "asset_management"),
    "seo": ("SEO (Sponsors for Educational Opportunity)", "other"),
    "drw": ("DRW", "quant_trading"),
    "virtu": ("Virtu Financial", "quant_trading"),
    "old mission": ("Old Mission", "quant_trading"),
    "walleye": ("Walleye Capital", "quant_trading"),
    "imc": ("IMC Trading", "quant_trading"),
    "optiver": ("Optiver", "quant_trading"),
    "five rings": ("Five Rings", "quant_trading"),
    "hrt": ("Hudson River Trading", "quant_trading"),
    "two sigma": ("Two Sigma", "quant_trading"),
    "akuna": ("Akuna Capital", "quant_trading"),
    "point72": ("Point72", "quant_trading"),
    "aquatic": ("Aquatic Capital", "quant_trading"),
    "jane street": ("Jane Street", "quant_trading"),
    "jump": ("Jump Trading", "quant_trading"),
    "tower": ("Tower Research Capital", "quant_trading"),
    "schonfeld": ("Schonfeld", "quant_trading"),
    "anthelion": ("Anthelion Capital", "quant_trading"),
    "stevens capital": ("Stevens Capital Management", "quant_trading"),
    "flow traders": ("Flow Traders", "quant_trading"),
    "pdt": ("PDT Partners", "quant_trading"),
    "google": ("Google", "technology"),
    "microsoft": ("Microsoft", "technology"),
    "amazon": ("Amazon", "technology"),
    "apple": ("Apple", "technology"),
    "meta": ("Meta", "technology"),
    "nvidia": ("NVIDIA", "technology"),
    "palantir": ("Palantir", "technology"),
    "uber": ("Uber", "technology"),
    "linkedin": ("LinkedIn", "technology"),
    "dropbox": ("Dropbox", "technology"),
    "salesforce": ("Salesforce", "technology"),
    "duolingo": ("Duolingo", "technology"),
    "deepgram": ("Deepgram", "technology"),
    "epic": ("Epic Systems", "technology"),
    "neuralink": ("Neuralink", "technology"),
    "western digital": ("Western Digital", "technology"),
    "the trade desk": ("The Trade Desk", "technology"),
    "podium": ("Podium", "technology"),
    "appian": ("Appian", "technology"),
}
_CANON_KEYS = sorted(CANON, key=len, reverse=True)


def canon(raw, default_sector="other"):
    """Canonical (firm, sector) for a raw firm-ish string from the tracker."""
    low = (raw or "").strip().lower()
    for key in _CANON_KEYS:
        if low.startswith(key):
            return CANON[key]
    return raw.strip(), default_sector


def slug(text):
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return re.sub(r"-{2,}", "-", text) or "unnamed"


def col_index(ref):
    letters = re.match(r"([A-Z]+)", ref or "A").group(1)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


class Workbook:
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        self.shared = []
        if "xl/sharedStrings.xml" in self.z.namelist():
            root = ET.fromstring(self.z.read("xl/sharedStrings.xml"))
            for si in root.iter(NS + "si"):
                self.shared.append("".join(t.text or "" for t in si.iter(NS + "t")))
        self.names = re.findall(r'<sheet name="([^"]+)"', self.z.read("xl/workbook.xml").decode("utf8"))

    def sheet(self, index):
        """Return (rows, hyperlinks_by_cell_ref) for 1-based sheet index."""
        root = ET.fromstring(self.z.read(f"xl/worksheets/sheet{index}.xml"))
        rows = []
        for row in root.iter(NS + "row"):
            cells = {}
            for c in row.iter(NS + "c"):
                i = col_index(c.get("r"))
                if c.get("t") == "inlineStr":
                    val = "".join(t.text or "" for t in c.iter(NS + "t"))
                else:
                    v = c.find(NS + "v")
                    val = "" if v is None else (v.text or "")
                    if c.get("t") == "s" and val:
                        val = self.shared[int(val)]
                cells[i] = val or ""
            if cells:
                rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
            else:
                rows.append([])

        links = {}
        rels_path = f"xl/worksheets/_rels/sheet{index}.xml.rels"
        if rels_path in self.z.namelist():
            rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(self.z.read(rels_path))}
            for h in root.iter(NS + "hyperlink"):
                target = rels.get(h.get(RNS + "id"))
                if target:
                    links[h.get("ref")] = target
        return rows, links


def quotes_in(text):
    """Every quoted span, verbatim. Order preserved, duplicates dropped."""
    seen, out = set(), []
    for m in QUOTE_RE.finditer(text or ""):
        q = m.group(1).strip()
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return out


def classify(quote):
    low = quote.lower()
    if any(k in low for k in SPONSORSHIP_KEYS):
        return "sponsorship"
    if any(k in low for k in CLASS_YEAR_KEYS):
        return "class_year"
    if any(k in low for k in PROCESS_KEYS):
        return "process"
    return None


def blank(state="unverified"):
    return {"state": state}


def make_field(quote, url, checked, source_status):
    """A field with a verbatim quote. `stated` requires the quote to exist."""
    field = {"state": "stated", "tier": 1, "quote": quote, "checked": checked}
    field["source_url"] = url
    field["source_status"] = source_status
    return field


# A private tracker is written about its author. A public record is not. Any
# clause naming the author is a personal verdict ("Master's - Mayher is BS"),
# not a fact about the firm, and it must never reach data/.
REDACT_NAMES = ("mayher",)
redacted = []


def scrub(text):
    """Drop clauses that talk about the tracker's author rather than the firm."""
    if not text:
        return ""
    clauses = re.split(r"(?<=[.;])\s+|\s+[—–]\s+", text)
    kept = [c for c in clauses if not any(n in c.lower() for n in REDACT_NAMES)]
    if len(kept) != len(clauses):
        redacted.append(text.strip()[:70])
    out = " ".join(k.strip() for k in kept if k.strip())
    # A bare fragment left behind after redaction says nothing useful.
    return out if len(out) > 12 else ""


def unverified_field(summary, checked):
    """No verbatim sentence was recorded, so nothing may be claimed as stated."""
    field = {"state": "unverified", "checked": checked}
    summary = scrub(summary)
    if summary:
        field["summary_note"] = summary.strip()
    return field


def build_program(name, cycle, location, audience, url, checked, cells, status):
    source_status = "ok" if url else "url_pending"
    prog = {
        "id": slug(f"{name}-{cycle}") if cycle else slug(name),
        "name": name,
        "audience": audience,
        "source": {
            "url": url,
            "checked": checked,
            "check_method": "static" if url else "manual",
            "status": source_status,
        },
        "fields": {},
        "cooling_off": blank(),
        "unfiled_quotes": [],
    }
    if cycle:
        prog["cycle"] = cycle
    if location:
        prog["location"] = location
    if status:
        prog["status"] = status
    if not url:
        prog["source"]["note"] = (
            "Verbatim quote recorded from the source posting, but the URL was not "
            "captured at the time. Not independently citable until re-sourced."
        )

    filed = {}
    unfiled = []
    for raw in cells:
        for q in quotes_in(raw):
            key = classify(q)
            if key and key not in filed:
                filed[key] = make_field(q, url, checked, source_status)
            elif key is None:
                unfiled.append({"quote": q, "source_url": url, "source_status": source_status})

    for key in ("class_year", "sponsorship", "process", "compensation"):
        prog["fields"][key] = filed.get(key, blank())
    if unfiled:
        prog["unfiled_quotes"] = unfiled
    else:
        prog.pop("unfiled_quotes")
    return prog


def transcribe(xlsx_path, out_dir):
    wb = Workbook(xlsx_path)
    firms = {}

    def firm_record(name, sector):
        rec = firms.setdefault(name, {"firm": name, "sector": sector, "programs": []})
        # A firm first seen via a sheet with no sector column stays "other"
        # unless a later, better-informed row upgrades it.
        if rec["sector"] == "other" and sector != "other":
            rec["sector"] = sector
        return rec

    # ---- Active Log: 35 postings, each with a real source URL ----------------
    rows, links = wb.sheet(2)
    for i, row in enumerate(rows[1:], start=2):
        row = row + [""] * (11 - len(row))
        firm, program, sector, elig, pay, opens, closes, _, tag = (
            row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9]
        )
        if not firm:
            continue
        url = links.get(f"I{i}")
        firm, fsector = canon(firm, SECTOR_MAP.get(sector.strip().lower(), "other"))
        rec = firm_record(firm, fsector)
        status = "open" if "open" in opens.lower() else "future"
        prog = build_program(
            program or firm, "Summer 2027", "", "undergraduate", url,
            "2026-07-27", [elig], status,
        )
        if opens:
            prog["opens"] = opens
        if closes:
            prog["closes"] = closes
        # Pay in this tracker is the author's summary, not a quoted sentence.
        if pay and prog["fields"]["compensation"]["state"] == "unverified":
            prog["fields"]["compensation"] = unverified_field(pay, "2026-07-27")
        # If no quote survived, keep the author's summary as an explicit non-quote.
        if prog["fields"]["class_year"]["state"] == "unverified" and elig:
            prog["fields"]["class_year"] = unverified_field(elig, "2026-07-27")
        if tag:
            prog["source"].setdefault("note", "")
        rec["programs"].append(prog)

    # ---- Do Not Log: 32 exact disqualifying sentences, NO source URLs --------
    rows, _ = wb.sheet(4)
    for row in rows[1:]:
        row = row + [""] * (3 - len(row))
        checked, firm_program, reason = row[0], row[1], row[2]
        if not firm_program:
            continue
        firm = re.split(r"\s+[—–-]\s+|\s+\(|\s+SWE|\s+Quant|\s+Software", firm_program)[0].strip()
        firm, fsector = canon(firm or firm_program)
        rec = firm_record(firm, fsector)
        prog = build_program(
            firm_program, "Summer 2027", "", "undergraduate", None,
            checked or "2026-07-27", [reason], "unknown",
        )
        if prog["fields"]["class_year"]["state"] == "unverified" and reason:
            prog["fields"]["class_year"] = unverified_field(reason, checked or "2026-07-27")
        rec["programs"].append(prog)

    # ---- Watch + Manual Checks: URLs present, no quoted eligibility ----------
    rows, links = wb.sheet(3)
    for i, row in enumerate(rows[1:], start=2):
        row = row + [""] * (4 - len(row))
        kind, item, detail = row[0], row[1], row[2]
        # Low-priority rows are leads the tracker itself declined to log as
        # postings; a public record has no business promoting them to rows.
        if not item or "low priority" in kind.lower():
            continue
        url = links.get(f"D{i}")
        firm = re.split(r"\s+[—–-]\s+|\s+\(|\s+SWE|\s+Quant|\s+Software|\s+Campus", item)[0].strip()
        firm, fsector = canon(firm or item)
        rec = firm_record(firm, fsector)
        prog = build_program(item, "", "", "unknown", url, "2026-07-27", [detail], "unknown")
        prog["source"]["status"] = "blocked" if "render" in detail.lower() or "block" in detail.lower() else prog["source"]["status"]
        prog["source"]["check_method"] = "manual"
        if detail:
            prog["source"]["note"] = detail.strip()
        rec["programs"].append(prog)

    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = 0
    for name, rec in sorted(firms.items()):
        rec["provenance"] = {
            "origin": "private posting tracker, transcribed programmatically",
            "transcribed": "2026-07-29",
            "note": "Quotes are byte-for-byte substrings of quoted spans in the source "
                    "spreadsheet. Unquoted text became summary_note on unverified fields, "
                    "never a quote.",
        }
        (out / f"{slug(name)}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n")
        written += 1
    return written, sum(len(r["programs"]) for r in firms.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--out", default="data")
    args = ap.parse_args()
    if not pathlib.Path(args.xlsx).exists():
        sys.exit(f"no such file: {args.xlsx}")
    firms, programs = transcribe(args.xlsx, args.out)
    print(f"wrote {firms} firm files, {programs} programs -> {args.out}/")
    for r in redacted:
        print(f"  REDACTED personal clause from summary_note: {r}...")


if __name__ == "__main__":
    main()
