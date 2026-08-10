#!/usr/bin/env python3
"""Fetch-first candidate harvester. No model sits in this loop.

Given firm domains, find the student/campus careers pages, pull the sentences
that could plausibly answer this database's five questions, and prove each one
is a literal normalised substring of the live page BEFORE any of it is offered
for recording. That last step is the whole point: it is what stops a quote
landing as a FAIL row in tools/verify_quotes.py three commits later.

Stages, per EXPANSION.md 6.3:
  1. probe a small set of guessed careers paths per domain   (free)
  2. grep the returned HTML for student/campus/early-career links (free)
  3. fetch those pages                                        (free)
  4. split to sentences, keep only eligibility-shaped ones    (free)
  5. re-verify every candidate against the live page via verify_quotes.norm

A domain that answers 403 to every probe is recorded as `blocked`, not as
`nothing found`. Those two look identical in a summary line and are opposite
facts: 403 is a user-agent filter hiding a page that a browser renders fine,
and EXPANSION.md 6.2b notes the blocked set skews toward the marquee names.

Usage: python3 tools/harvest.py firms.json out.json
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import html
import json
import pathlib
import re
import subprocess
import sys
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from verify_quotes import TAG, json_strings, norm  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# Careers paths worth guessing. A 404 costs nothing, and the student page is
# the one that carries the FAQ, so student paths are probed before the hub.
SEED_PATHS = (
    "/careers/students", "/careers/campus", "/careers/early-careers",
    "/careers/university", "/careers/students-graduates", "/early-careers",
    "/careers", "/en/careers", "/about/careers", "/who-we-are/careers",
    "/people/careers", "/join-us", "/company/careers", "/careers/internships",
)

# A link worth following from a careers hub.
STUDENT_LINK = re.compile(
    r"student|campus|universit|early.?career|internship|intern\b|graduate"
    r"|analyst.program|summer.analyst|undergrad|emerging.talent|new.grad"
    r"|\bfaq\b|frequently.asked", re.I)

# Machine endpoints that answer 200 with content that is not a page.
NOT_A_PAGE = re.compile(r"/wp-json/|oembed|\.(xml|rss|json|pdf|jpg|png|svg)(\?|$)"
                        r"|/feed/?$|/wp-admin|/tag/|/author/", re.I)

HREF = re.compile(r'href=["\']([^"\'#>]+)', re.I)

# Sentences that could answer one of the five fields. Generous on purpose:
# recall matters here, precision is the model's job downstream. The one place
# that generosity was actively harmful is `sponsor` -- in this corpus most
# occurrences are "financial sponsors", the private-equity sense, so the
# sponsorship pattern requires visa/authorisation language instead.
FIELD_PATTERNS = {
    "sponsorship": re.compile(
        r"\bsponsorship\b|\bvisa\b|work authoriz|work authoris|\bCPT\b|\bOPT\b"
        r"|right to work|immigration|permanent resident|legally authoriz"
        r"|legally authoris|(eligible|authorized|authorised) to work"
        r"|citizenship (status|requirement)|require sponsor|sponsor an?\b"
        r"|\bH-?1B\b|\bF-?1\b|international student", re.I),
    "class_year": re.compile(
        r"graduat|class of|rising (junior|senior|sophomore)|penultimate"
        r"|undergraduate|sophomore|freshman|first.year|second.year|third.year"
        r"|final year|degree program|currently enrolled|matriculat"
        r"|pursuing a (bachelor|master)|year of study", re.I),
    "cooling_off": re.compile(
        r"reappl|re-appl|only (one|1|a single) applicat|one applicat"
        r"|per (recruiting )?(cycle|season|year)|maximum of \w+ applicat"
        r"|may (only )?apply|cannot apply|not be able to apply|wait \w+ months"
        r"|\b(6|six|12|twelve) months\b|multiple applicat|apply to (more than|up to)"
        r"|another applicat|previously applied|declin(e|ed|ing) an offer"
        r"|withdraw your applicat|single applicat|limit .{0,20}applicat", re.I),
    "process": re.compile(
        r"application (process|opens|closes|deadline)|interview|assessment"
        r"|online test|hirevue|first round|superday|rolling basis"
        r"|applications (open|close|are reviewed)|deadline|offer is extended", re.I),
    "compensation": re.compile(
        r"\$[\d,]+|per hour|hourly|salary|stipend|compensation|paid internship"
        r"|housing (stipend|allowance)|relocation", re.I),
}

# Sentences that match a pattern but say nothing a database can record: legal
# boilerplate, cookie banners, and the navigation chrome that survives tag
# stripping on a marketing site.
NOISE = re.compile(
    r"cookie|privacy polic|newsletter|subscribe|©|all rights reserved"
    r"|equal opportunit|equal employment|without regard to|regardless of race"
    r"|reasonable accommodation|affirmative action"
    r"|follow us|linkedin\.com|twitter\.com|javascript"
    r"|skip to (main )?content|search menu|menu navigation|toggle |breadcrumb"
    r"|^\s*(home|about|contact|explore)\b.{0,40}$", re.I)

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def curl(url: str, timeout: int = 25) -> tuple[int, str]:
    """Return (http_status, body). Never raises: a dead URL is data."""
    try:
        proc = subprocess.run(
            ["curl", "-sL", "--compressed", "-m", str(timeout), "-A", UA,
             "-H", "Accept-Language: en-US,en",
             "-w", "\n__STATUS__%{http_code}", url],
            capture_output=True, timeout=timeout + 10)
        body = proc.stdout.decode("utf-8", "replace")
        head, _, code = body.rpartition("\n__STATUS__")
        return (int(code) if code.strip().isdigit() else 0), head
    except Exception:  # noqa: BLE001 - unreachable is a result, not an error
        return 0, ""


def haystacks(raw: str) -> list[str]:
    """The same normalised search surfaces verify_quotes.fetch builds.

    Sharing the construction is what makes the substring assertion in stage 5
    predictive of what the verifier will conclude later, rather than a second
    opinion that happens to agree today.
    """
    out = []
    try:
        strings: list[str] = []
        json_strings(json.loads(raw), strings)
        joined = html.unescape(html.unescape(" ".join(strings)))
        out.append(norm(TAG.sub(" ", joined)))
    except (json.JSONDecodeError, ValueError):
        pass
    out.append(norm(TAG.sub(" ", html.unescape(raw))))
    out.append(norm(raw.replace("\\n", " ").replace("\\r", " ")
                       .replace("\\t", " ").replace('\\"', '"')
                       .replace("\\u0026", "&").replace("\\/", "/")))
    return out


def readable_text(raw: str) -> str:
    """Visible prose, with accordion bodies included.

    Reads the markup rather than rendered text on purpose: FAQ answers live in
    collapsed <details>/aria-hidden panels that are present in the HTML and
    absent from innerText, and those answers are exactly the material worth
    recording.
    """
    text = html.unescape(html.unescape(raw))
    text = re.sub(r"<script\b.*?</script>|<style\b.*?</style>|<nav\b.*?</nav>",
                  " ", text, flags=re.S | re.I)
    # keep block boundaries so sentences do not weld together across markup
    text = re.sub(r"</(p|div|li|h[1-6]|td|section|dd|dt)>", ". ", text, flags=re.I)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    text = TAG.sub(" ", text)
    return re.sub(r"\s+", " ", text)


def candidate_sentences(text: str) -> list[dict]:
    """Eligibility-shaped sentences, tagged with the fields they might serve."""
    seen, out = set(), []
    for sent in SENT_SPLIT.split(text):
        sent = sent.strip(" .·|-")
        if not (40 <= len(sent) <= 400) or NOISE.search(sent):
            continue
        fields = [f for f, pat in FIELD_PATTERNS.items() if pat.search(sent)]
        if not fields:
            continue
        key = norm(sent)
        if key in seen:
            continue
        seen.add(key)
        out.append({"quote": sent, "fields": fields})
    return out


def discover(domain: str) -> tuple[list[tuple[str, str]], list[int]]:
    """((url, body) for real careers pages, every HTTP status seen).

    Returning the statuses too is what lets the caller tell "this firm
    publishes nothing" apart from "this firm 403s curl", which is the
    difference between dropping a candidate and queueing a browser pass.
    """
    base = f"https://{domain}"
    pages: dict[str, str] = {}
    bodies: dict[str, str] = {}      # content hash -> url, to drop /x and /x/
    hubs: list[tuple[str, str]] = []
    statuses: list[int] = []

    def take(url: str, body: str) -> bool:
        digest = hashlib.sha1(readable_text(body).encode()).hexdigest()
        if digest in bodies or url in pages:
            return False
        bodies[digest] = url
        pages[url] = body
        return True

    for path in SEED_PATHS:
        url = base + path
        status, body = curl(url)
        statuses.append(status)
        if status == 200 and len(body) > 1500 and take(url, body):
            hubs.append((url, body))
        if len(pages) >= 3:
            break

    for hub_url, body in hubs:
        for href in HREF.findall(body)[:400]:
            if not STUDENT_LINK.search(href) or NOT_A_PAGE.search(href):
                continue
            target = urljoin(hub_url, href)
            host = urlparse(target).netloc.split(":")[0]
            bare = domain.removeprefix("www.")
            if host not in (bare, f"www.{bare}"):
                continue
            if target in pages or len(pages) >= 8:
                continue
            status, sub = curl(target)
            statuses.append(status)
            if status == 200 and len(sub) > 1500:
                take(target, sub)
    return list(pages.items()), statuses


def harvest(firm: dict) -> dict:
    """Everything found for one firm, with every quote re-verified in place."""
    result = {**firm, "pages": [], "note": ""}
    try:
        pages, statuses = discover(firm["domain"])
    except Exception as e:  # noqa: BLE001
        result["note"] = f"discovery failed: {type(e).__name__}: {e}"
        return result
    if not pages:
        blocked = sum(1 for s in statuses if s in (401, 403, 429))
        result["note"] = (
            f"BLOCKED: {blocked}/{len(statuses)} probes refused (403/429) -- "
            "needs a browser pass, says nothing about what the firm publishes"
            if blocked else "no careers page answered 200 on any guessed path")
        return result

    for url, raw in pages:
        cands = candidate_sentences(readable_text(raw))
        if not cands:
            continue
        # Stage 5. A candidate that cannot be found on the page it came from is
        # an extraction artefact (welded markup, mangled entity) and is dropped
        # here rather than surviving to become a FAIL row later.
        hay = haystacks(raw)
        verified = [c for c in cands if any(norm(c["quote"]) in h for h in hay)]
        if verified:
            result["pages"].append({
                "url": url, "chars": len(raw), "candidates": verified,
                "dropped_unverifiable": len(cands) - len(verified)})
    if not result["pages"]:
        result["note"] = "pages fetched, no eligibility-shaped sentence found"
    return result


def main() -> None:
    firms = json.loads(pathlib.Path(sys.argv[1]).read_text())
    out_path = pathlib.Path(sys.argv[2])
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(harvest, firms))
    out_path.write_text(json.dumps(results, indent=1))

    def count(r: dict) -> int:
        return sum(len(p["candidates"]) for p in r["pages"])

    hit = [r for r in results if r["pages"]]
    blocked = [r for r in results if r["note"].startswith("BLOCKED")]
    print(f"{len(hit)}/{len(results)} firms yielded candidate sentences; "
          f"{len(blocked)} blocked and queued for a browser pass\n")
    for r in sorted(results, key=lambda r: -count(r)):
        print(f"  {r['firm'][:28]:30} {count(r):4} candidates "
              f"over {len(r['pages'])} pages  {r['note'][:60]}")


if __name__ == "__main__":
    main()
