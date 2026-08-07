# Phase 2 — the sophomore opening monitor

Status: specified 2026-08-07, not yet built.
Owner intent: detect, within a day, the moment a watched sophomore program
actually starts accepting applications, and surface the firm's own sentence
saying so. This document is the build contract.

## What exists already (do not rebuild)

- `tools/watchlist.json` + `tools/check_watchlist.py`: rows with an *expected*
  opening window (`due_from`/`due_to`, YYYY-MM). The weekly freshness workflow
  prints rows whose window covers the current month. This answers "when should
  we start looking?" — it cannot answer "did it open?"
- `tools/verify_quotes.py`: the curl fetch profile, normalization, JS-host and
  bot-challenge classification. Phase 2 reuses `fetch()` and `norm()` verbatim
  (import them; do not copy).
- The freshness workflow (`.github/workflows/freshness.yml`): weekly sweep that
  files a labeled GitHub issue. Phase 2 adds a second, faster loop.

## Binding rules (inherited, non-negotiable)

1. The monitor records what firms STATE. An alert quotes the firm's sentence
   verbatim with URL and timestamp. It never says "eligible", never "apply now".
2. Blocked pages report BLOCKED, never FAIL, never "closed".
3. Every fired alert must be convertible into a normal `data/` row update
   (quote, source_url, checked) through the existing pipeline.

## New pieces

### 1. `tools/openings.json` — the target list

One row per watched program:

```json
{
  "firm": "Microsoft",
  "program_id": "explore-microsoft-program-explore-internship",
  "detector": "ats_search",
  "watch": {
    "endpoint": "eightfold search on apply.careers.microsoft.com",
    "title_pattern": "(?i)explore",
    "location_filter": "United States"
  },
  "active_from": "2026-08",
  "active_to": "2027-01",
  "notes": "Portal migrated 2026-08 (old careers.microsoft.com search URLs 404)."
}
```

`active_from`/`active_to` bound the polling window (seed them from
`watchlist.json` minus one month of early margin). Outside the window a row is
polled weekly by the existing freshness sweep only.

### 2. Detectors, in order of preference

- **`ats_api`** — the board has a public JSON API. Poll it and match new
  postings by title pattern. Known-good today: Greenhouse
  (`boards-api.greenhouse.io/v1/boards/<token>/jobs`, proven with Walleye),
  Ashby posting API, Lever postings API. A new matching posting is the
  strongest possible signal: it carries its own verbatim text.
- **`ats_search`** — JS portals (Eightfold at apply.careers.microsoft.com,
  Workday CXS) whose front end calls a JSON search endpoint. Capture the
  endpoint once in a browser session (network tab), record it in the row, poll
  it like ats_api. If the endpoint churns, fall back to page_diff.
- **`page_diff`** — marketing pages with no API (NY Fed, LinkedIn First Play,
  Bridgewater, Goldman Emerging Leaders, JSIP, Citi Early ID, BofA student
  hub). Fetch with `verify_quotes.fetch()`, strip to text, hash the normalized
  text. Alert on hash change with a unified diff of the text so the human sees
  *what* changed. Noise control: hash only after dropping lines matching a
  per-row `ignore` regex (cookie banners, copyright years, CSRF tokens).
- **`keyword_flip`** — special case of page_diff for pages that publish their
  own state sentence (NY Fed: "Please check back in September 2026"; GWI:
  "The application ... is now open"). The row lists `absent_phrase` and/or
  `present_phrase`; the alert fires on the transition and quotes the new
  sentence verbatim — ready to paste into the data row.
- **`manual`** — bot-walled hosts (Wells Fargo, SIG, Citadel, McKinsey).
  No mechanical polling pretends to work; the row exists so the report prints
  a standing "needs a browser pass this week" line during its active window.

### 3. `tools/check_openings.py` — the runner

Same contract as `check_watchlist.py`: exit 0 always, print a report.
Per active row: run the detector, compare against stored state, print one of
`OPENED` (state transition detected — includes the verbatim evidence),
`CHANGED` (page_diff moved but no phrase matched — includes the diff),
`QUIET`, or `BLOCKED`. State (hashes, last seen posting IDs, last transition)
lives in `tools/openings_state.json`, committed by the workflow with
`[skip ci]` so history shows exactly when each page moved.

### 4. `.github/workflows/openings.yml` — the fast loop

- Cron: daily at 13:00 UTC (US careers pages update on business mornings;
  one run per day keeps the job inside free-tier minutes).
- Steps: checkout → run `check_openings.py` → if any `OPENED` or `CHANGED`
  row, file/append to a GitHub issue labeled `opening` (one issue per firm per
  cycle, not one per run) → commit `openings_state.json`.
- Permissions: `contents: write`, `issues: write` (freshness.yml already has
  the issues pattern to copy).
- GitHub notifications on the `opening` label are the push channel; no new
  notification infrastructure.

### 5. Seed target list (Tier 1, from apply-list-2026-07-30)

| Program | Detector | Why |
|---|---|---|
| Microsoft Explore | ats_search | portal JSON search; title match "Explore" |
| NY Fed Sophomore Career Exploration | keyword_flip | their own "check back September 2026" sentence |
| Duolingo Thrive | ats_api (Ashby) | careers.duolingo.com is Ashby-hosted |
| NVIDIA Ignite | page_diff | Workday; university page is the tell |
| LinkedIn First Play | keyword_flip | page states "opens ~Nov" language |
| Goldman Emerging Leaders | page_diff | page fetches clean (verified 2026-08-07) |
| Citi Early ID | page_diff | jobs.citi.com fetches clean |
| BofA sophomore programs (GBAM, Global Tech) | page_diff | careers.bankofamerica.com fetches clean (verified 2026-08-07) |
| Bridgewater Rising Fellows | page_diff | no API found |
| Jane Street JSIP | page_diff | janestreet.com fetches clean |
| Salesforce Futureforce Launchpad | page_diff | CodePath partner page |
| SEO Career | page_diff | career.seo-usa.org fetches clean |
| Amazon Propel | page_diff | amazon.jobs team page |
| Capital One early-career hub | page_diff | TEIP folded in; hub is the only signal |
| Wells Fargo Sophomore Experience | manual | bot-walled; browser pass only |
| SIG Discovery Days | manual | bot-walled |
| Citadel Discover Citadel | manual | bot-walled |
| McKinsey Sophomore SBA | manual | fully bot-blocked |

GWI Scholars Program is already open (recorded 2026-08-07) and needs no row;
its deadlines (priority 2026-09-15, final 2026-10-15) belong in the data row,
which now carries them.

## Size estimate (labeled estimate, not fact)

`check_openings.py` ~180 lines reusing verify_quotes internals; openings.json
~18 rows; workflow ~45 lines. One session to build and unit-test detectors
against fixture HTML; one browser session to capture the two ats_search
endpoints; then it runs itself.

## Explicit non-goals

- No eligibility verdicts, no scoring, no ranking. The screener's output is a
  quoted sentence and a URL.
- No headless-browser scraping of bot-walled hosts from CI (against those
  sites' defenses and this repo's BLOCKED-not-FAIL ethic); those stay manual.
- No polling more than daily; a program that opens at 9am is caught by 13:00
  UTC next run, which is within the one-day detection target.
