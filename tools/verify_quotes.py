#!/usr/bin/env python3
"""Mechanically verify that every stated quote appears on its cited page.

For each field with state="stated", fetch source_url and assert the quote is a
substring of the page text after whitespace/entity normalization. No model sits
in this loop: a quote either occurs on the page or it does not. This catches
the failure mode that overturned the project's founding fact — a paraphrase or
truncation promoted into a "verbatim" quote.

Outcomes per quote:
  OK       — quote found verbatim on the fetched page
  FAIL     — page fetched and readable, quote NOT present (investigate: the
             page changed, or the quote was never verbatim)
  BLOCKED  — page unreachable or JS-rendered shell (needs the browser pass;
             says nothing about the quote either way)

A FAIL is not automatically a lie: pages change between the agent's read and
this check. But every FAIL must be re-verified by hand or browser before the
row keeps its "stated" state.

Usage:  python3 tools/verify_quotes.py [data_dir] [--only firm-slug]
"""

import html
import json
import pathlib
import re
import subprocess
import sys
import time

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# Pages whose body only arrives via JavaScript; a fetch returning a shell is
# expected, not evidence. Matched against the URL.
KNOWN_JS_HOSTS = re.compile(
    r"myworkdayjobs\.com|jobs\.ashbyhq\.com|careers\.duolingo\.com"
    r"|metacareers\.com|talent\.wellsfargojobs\.com|careers\.sig\.com"
    r"|kpmguscareers\.com|imc\.com/us/careers/jobs"
    # Microsoft moved applications to an Eightfold portal (2026-08): job pages
    # render entirely client-side, curl gets a navigation shell
    r"|apply\.careers\.microsoft\.com"
    # career sites embedding Greenhouse via ?gh_jid= load the posting body
    # with JavaScript: the marketing shell fetches fine, the job text never
    # arrives, so "quote absent" proves nothing
    r"|[?&]gh_jid=|google\.com/about/careers", re.I)

# Bot-challenge interstitials are short pages full of these markers; a real
# page can mention them incidentally, so the marker only counts when the page
# is challenge-sized.
CHALLENGE = re.compile(
    r"just a moment|cf-chl|access denied|captcha|incapsula|radware"
    r"|pardon our interruption", re.I)

TAG = re.compile(r"<script\b.*?</script>|<style\b.*?</style>|<[^>]+>", re.S | re.I)
WS = re.compile(r"\s+")

_cache = {}


def norm(text):
    """Whitespace/entity/quote-mark normalization applied to both sides."""
    text = html.unescape(text)
    text = (text.replace("’", "'").replace("‘", "'")
                .replace("“", '"').replace("”", '"')
                .replace("–", "-").replace("—", "-")
                .replace(" ", " "))
    text = WS.sub(" ", text)
    # markup boundaries leave spaces before punctuation ("office , with");
    # strip them on both sides of the comparison
    text = re.sub(r"\s+([.,;:!?)])", r"\1", text)
    return text.strip().lower()


def json_strings(node, out):
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for v in node.values():
            json_strings(v, out)
    elif isinstance(node, list):
        for v in node:
            json_strings(v, out)


def fetch(url):
    """Return (status, haystacks): normalized text variants to search.

    curl rather than urllib: several careers sites serve real content only to
    clients that negotiate compression and redirects the way browsers do, and
    a false FAIL from a crippled fetch is worse than no check at all.
    """
    if url in _cache:
        return _cache[url]
    try:
        raw = subprocess.run(
            ["curl", "-sL", "--compressed", "-m", "30", "-A", UA,
             "-H", "Accept-Language: en-US,en", url],
            capture_output=True, timeout=40).stdout.decode("utf-8", "replace")
        haystacks = []
        # JSON responses (Greenhouse boards-api): search every string value,
        # unescaped twice because descriptions are HTML-escaped HTML.
        try:
            strings = []
            json_strings(json.loads(raw), strings)
            joined = html.unescape(html.unescape(" ".join(strings)))
            haystacks.append(norm(TAG.sub(" ", joined)))
        except (json.JSONDecodeError, ValueError):
            pass
        # HTML path: strip tags after entity-unescape.
        haystacks.append(norm(TAG.sub(" ", html.unescape(raw))))
        # Raw fallback: content embedded in script JSON (Next.js job pages)
        # survives here once JSON string escapes are flattened.
        haystacks.append(norm(raw.replace("\\n", " ").replace("\\r", " ")
                                 .replace("\\t", " ").replace('\\"', '"')
                                 .replace("\\u0026", "&").replace("\\/", "/")))
        result = ("ok", haystacks)
    except Exception as e:  # noqa: BLE001 - any network failure is BLOCKED
        result = ("error", f"{type(e).__name__}: {e}")
    _cache[url] = result
    time.sleep(0.5)
    return result


def quotes_in(rec):
    """Yield (program_id, field_name, quote, source_url) for stated fields.

    Tracker-era rows carry their source at the program level only; fall back
    to it so those quotes are verified rather than flagged.
    """
    for prog in rec["programs"]:
        prog_url = prog.get("source", {}).get("url", "")
        for name, field in prog.get("fields", {}).items():
            if field.get("state") == "stated" and field.get("quote"):
                yield (prog["id"], name, field["quote"],
                       field.get("source_url") or prog_url)
        co = prog.get("cooling_off", {})
        if co.get("state") == "stated" and co.get("quote"):
            yield (prog["id"], "cooling_off", co["quote"],
                   co.get("source_url") or prog_url)


def main():
    argv = sys.argv[1:]
    only = None
    if "--only" in argv:
        i = argv.index("--only")
        if i + 1 >= len(argv):
            sys.exit("--only needs a firm slug")
        only = argv[i + 1]
        # Drop the flag AND its value. Leaving the value in the positional list
        # made `verify_quotes.py --only acme` read "acme" as the data directory,
        # glob an empty tree, and exit 0 having verified nothing. A checker that
        # passes loudly while checking nothing is worse than no checker at all.
        argv = argv[:i] + argv[i + 2:]
    args = [a for a in argv if not a.startswith("--")]
    data_dir = pathlib.Path(args[0] if args else "data")
    if not data_dir.is_dir():
        sys.exit(f"{data_dir}: not a directory")

    ok, fail, blocked, nourl, parts = [], [], [], [], []
    for path in sorted(data_dir.glob("*.json")):
        if only and path.stem != only:
            continue
        rec = json.loads(path.read_text())
        for pid, fname, quote, url in quotes_in(rec):
            key = (rec["firm"], pid, fname)
            if not url:
                nourl.append(key)
                continue
            if url.lower().endswith(".pdf"):
                blocked.append((*key, url, "PDF source, no text extraction here"))
                continue
            status, hay = fetch(url)
            if status == "error":
                blocked.append((*key, url, hay))
                continue
            size = max(map(len, hay))
            if any(norm(quote) in h for h in hay):
                ok.append(key)
                continue
            # multi-bullet quotes: every sentence/line verbatim on the page
            # counts, but contiguity is unproven — report separately
            pieces = [s for s in re.split(r"[\n]+|(?<=[.!?])\s+", quote)
                      if len(s.strip()) >= 15]
            if pieces and all(any(norm(s) in h for h in hay) for s in pieces):
                parts.append((*key, url, len(pieces)))
                continue
            if (KNOWN_JS_HOSTS.search(url) or size < 2000
                    or (size < 20000 and CHALLENGE.search(hay[-1]))):
                # a near-empty page is a JS shell and a challenge-sized page
                # full of bot-wall markers is an interstitial: neither refutes
                blocked.append((*key, url, f"page text only {size} chars"
                                if size < 20000 else "JS-rendered host"))
            else:
                fail.append((*key, url, quote[:70]))

    print(f"verified {len(ok)} quotes OK, {len(parts)} OK-by-parts, "
          f"{len(fail)} FAIL, {len(blocked)} BLOCKED, "
          f"{len(nourl)} missing source_url\n")
    if parts:
        print("OK-BY-PARTS — each sentence verbatim on page, contiguity "
              "unproven (review for splice risk):")
        for firm, pid, fname, url, n in parts:
            print(f"  {firm[:22]:24} {fname:12} {n} pieces\n    {url}")
    if fail:
        print("FAIL — quote not on cited page (re-verify before trusting):")
        for firm, pid, fname, url, q in fail:
            print(f"  {firm[:22]:24} {fname:12} \"{q}…\"\n    {url}")
    if blocked:
        print("\nBLOCKED — needs browser pass, proves nothing either way:")
        for firm, pid, fname, url, why in blocked:
            print(f"  {firm[:22]:24} {fname:12} {why[:60]}\n    {url}")
    if nourl:
        print("\nMISSING source_url on a stated quote (schema violation):")
        for firm, pid, fname in nourl:
            print(f"  {firm[:22]:24} {pid[:40]:42} {fname}")
    sys.exit(1 if fail or nourl else 0)


if __name__ == "__main__":
    main()
