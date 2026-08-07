#!/usr/bin/env python3
"""Phase 2: detect the moment a watched program actually opens.

Contract (PHASE2.md): per active row run its detector, compare against stored
state, print one of OPENED / CHANGED / QUIET / BLOCKED / SEEDED / MANUAL, and
exit 0 always — alerts are work to route, not errors. State lives in
tools/openings_state.json, committed by the workflow so history shows exactly
when each page moved.

The monitor records what firms STATE: evidence is the page's own text, quoted;
a page we cannot read is BLOCKED, never "closed". No verdicts, ever.

Usage: python3 tools/check_openings.py [YYYY-MM]
           [--targets PATH] [--state PATH] [--no-write]
"""

import difflib
import hashlib
import html
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location("vq", HERE / "verify_quotes.py")
vq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vq)  # reuse UA, norm(), TAG, CHALLENGE — one fetch culture

TEXT_CAP = 30_000  # stored page text per row; enough for a readable diff
LOG_CAP = 200      # newest-first entries kept in openings_log.json


def append_log(events, log_path, date):
    """Prepend OPENED/CHANGED events to the site-facing update log.

    The log is the application's own update channel: build.py embeds it in
    index.html and export_json.py ships it to the app, so an alert reaches
    readers without anyone opening the repo. Same register as everything
    else: what the page now shows, dated, with a link — never a verdict.
    """
    if not events:
        return False
    log = json.loads(log_path.read_text()) if log_path.exists() else []
    log = [{"date": date, **e} for e in events] + log
    log_path.write_text(json.dumps(log[:LOG_CAP], indent=1, ensure_ascii=False) + "\n")
    return True


def fetch_text(url):
    """(status, raw_text, norm_text): tag-stripped page text, original case
    plus vq.norm()'d. Mirrors verify_quotes.fetch()'s curl profile; kept
    separate because keyword evidence must be quoted in the page's own case,
    and fetch() lowercases. Tests monkeypatch this function."""
    try:
        raw = subprocess.run(
            ["curl", "-sL", "--compressed", "-m", "30", "-A", vq.UA,
             "-H", "Accept-Language: en-US,en", url],
            capture_output=True, timeout=40).stdout.decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 — any network failure is BLOCKED
        return ("blocked", f"{type(e).__name__}: {e}", "")
    text = vq.TAG.sub(" ", html.unescape(raw))
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(ln.strip() for ln in text.splitlines() if ln.strip())
    normed = vq.norm(text)
    if len(normed) < 2000 or (len(normed) < 20000 and vq.CHALLENGE.search(normed)):
        return ("blocked", f"page text only {len(normed)} chars", normed)
    return ("ok", text[:TEXT_CAP], normed)


def fetch_json(url):
    """(status, parsed) for board APIs. Tests monkeypatch this too."""
    try:
        raw = subprocess.run(
            ["curl", "-sL", "--compressed", "-m", "30", "-A", vq.UA,
             "-H", "Accept: application/json", url],
            capture_output=True, timeout=40).stdout
        return ("ok", json.loads(raw))
    except Exception as e:  # noqa: BLE001
        return ("blocked", f"{type(e).__name__}: {e}")


def json_titles(node, pattern, out):
    """Collect matching title-ish strings anywhere in an API payload."""
    if isinstance(node, dict):
        for key in ("title", "name"):
            v = node.get(key)
            if isinstance(v, str) and pattern.search(v):
                ident = node.get("id") or node.get("jobId") or node.get("positionId") or ""
                out.add(f"{ident}|{v}" if ident else v)
        for v in node.values():
            json_titles(v, pattern, out)
    elif isinstance(node, list):
        for v in node:
            json_titles(v, pattern, out)


def sentence_around(text, phrase):
    """The sentence containing phrase, in the page's own words."""
    i = vq.norm(text).find(vq.norm(phrase))
    if i < 0:
        return ""
    # map roughly back: search original case-insensitively for first phrase word
    m = re.search(re.escape(phrase.split()[0]), text, re.I)
    start = m.start() if m else 0
    lo = max(0, start - 200)
    return re.sub(r"\s+", " ", text[lo:start + 300]).strip()


# ----------------------------- detectors -----------------------------------
# each returns (verdict, evidence, new_state) — verdict None means seeded

def run_ats(row, prev):
    status, payload = fetch_json(row["watch"]["endpoint"])
    if status != "ok":
        return "BLOCKED", str(payload)[:120], prev
    pattern = re.compile(row["watch"]["title_pattern"])
    found = set()
    json_titles(payload, pattern, found)
    state = {"postings": sorted(found)}
    if prev is None:
        return None, f"seeded with {len(found)} matching posting(s)", state
    new = found - set(prev.get("postings", []))
    if new:
        return "OPENED", "new matching posting(s): " + "; ".join(sorted(new)), state
    return "QUIET", "", state


def run_keyword_flip(row, prev):
    status, raw, normed = fetch_text(row["watch"]["url"])
    if status != "ok":
        return "BLOCKED", raw[:120], prev
    w = row["watch"]
    flags = {}
    if w.get("absent_phrase"):
        flags["absent_present"] = vq.norm(w["absent_phrase"]) in normed
    if w.get("present_phrase"):
        flags["present_present"] = vq.norm(w["present_phrase"]) in normed
    state = {"flags": flags, "hash": hashlib.sha256(normed.encode()).hexdigest()}
    if prev is None:
        return None, f"seeded flags {flags}", state
    fired = []
    old = prev.get("flags", {})
    if old.get("absent_present") and not flags.get("absent_present", True):
        fired.append(f"the sentinel sentence is gone: \"{w['absent_phrase']}\"")
    if not old.get("present_present", False) and flags.get("present_present"):
        fired.append("page now states: \"" + sentence_around(raw, w["present_phrase"]) + "\"")
    if fired:
        return "OPENED", " / ".join(fired), state
    if state["hash"] != prev.get("hash"):
        return "CHANGED", "page changed but no watched phrase flipped", state
    return "QUIET", "", state


def run_page_diff(row, prev):
    status, raw, normed = fetch_text(row["watch"]["url"])
    if status != "ok":
        return "BLOCKED", raw[:120], prev
    ignore = row["watch"].get("ignore")
    if ignore:
        normed = re.sub(ignore, " ", normed)
    digest = hashlib.sha256(normed.encode()).hexdigest()
    chunks = re.split(r"(?<=[.!?]) ", normed)
    state = {"hash": digest, "chunks": chunks[:800]}
    if prev is None:
        return None, "seeded", state
    if digest == prev.get("hash"):
        return "QUIET", "", state
    diff = [ln for ln in difflib.unified_diff(
        prev.get("chunks", []), chunks, lineterm="", n=0)
        if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---"))]
    return "CHANGED", "\n    ".join(diff[:14]) or "text changed", state


DETECTORS = {
    "ats_api": run_ats,
    "ats_search": run_ats,
    "keyword_flip": run_keyword_flip,
    "page_diff": run_page_diff,
}


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    month = args[0] if args else __import__("datetime").date.today().strftime("%Y-%m")

    def opt(name, default):
        return pathlib.Path(argv[argv.index(name) + 1]) if name in argv else default

    targets_path = opt("--targets", HERE / "openings.json")
    state_path = opt("--state", HERE / "openings_state.json")
    log_path = opt("--log", HERE / "openings_log.json")
    rows = json.loads(targets_path.read_text())["watch"]
    state = json.loads(state_path.read_text()) if state_path.exists() else {}

    counts = {}
    events = []
    for row in rows:
        rid = row["id"]
        label = f"{row['firm']} — {row['program']}"
        if not (row["active_from"] <= month <= row["active_to"]):
            continue
        if row["detector"] == "manual":
            print(f"MANUAL  {label}\n    bot-walled; needs a human browser pass: "
                  f"{row['watch']['url']}")
            counts["MANUAL"] = counts.get("MANUAL", 0) + 1
            continue
        verdict, evidence, new_state = DETECTORS[row["detector"]](row, state.get(rid))
        if verdict is None:
            verdict = "SEEDED"
        if new_state is not None:
            state[rid] = new_state
        counts[verdict] = counts.get(verdict, 0) + 1
        line = f"{verdict:7} {label}"
        if evidence and verdict != "QUIET":
            line += f"\n    {evidence}"
        print(line)
        if verdict in ("OPENED", "CHANGED"):
            events.append({
                "firm": row["firm"], "program": row["program"],
                "verdict": verdict.lower(), "evidence": evidence[:500],
                "url": row["watch"].get("url") or row["watch"].get("endpoint", ""),
            })

    if "--no-write" not in argv:
        state_path.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n")
        append_log(events, log_path, month + "-" +
                   __import__("datetime").date.today().strftime("%d"))
    print("\nopenings:", ", ".join(f"{k.lower()} {v}" for k, v in sorted(counts.items()))
          or f"nothing in its active window in {month}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
