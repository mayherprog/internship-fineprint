# Fineprint — internship eligibility, in the firms' own words

[![CI](https://github.com/mayherprog/internship-fineprint/actions/workflows/ci.yml/badge.svg)](https://github.com/mayherprog/internship-fineprint/actions/workflows/ci.yml)
[![Freshness](https://github.com/mayherprog/internship-fineprint/actions/workflows/freshness.yml/badge.svg)](https://github.com/mayherprog/internship-fineprint/actions/workflows/freshness.yml)

**Live: [mayherprog.github.io/internship-fineprint](https://mayherprog.github.io/internship-fineprint/)**
· TypeScript app: [/app/](https://mayherprog.github.io/internship-fineprint/app/)

A sourced, dated record of what firms **actually state** about who may apply to their
internship and early-career programs: class year, sponsorship and work authorisation,
process stages, and above all **cooling-off periods** — the rules about reapplying and
retaking assessments that quietly cost candidates an entire recruiting cycle.

Every row is a sentence a firm published, quoted exactly, with a link and the date it was
read. Firms that publish nothing are recorded as publishing nothing.

```bash
python3 -m unittest discover -s tests   # parser/dedup/scrub/verifier unit tests
python3 tools/validate.py               # 6,508 assertions over 194 programs, 0 failures
python3 tools/verify_quotes.py data     # re-fetch every cited page; quotes must still be there
```

**[Browse the data →](TABLE.md)** &nbsp;·&nbsp; **[Interactive view →](index.html)**

## Architecture

Two languages, one contract. **Python** owns the data: `tools/transcribe_tracker.py`
(spreadsheet → records, with personal-clause redaction) → `tools/ingest_research.py`
(merges researched firms, canonicalizes ATS URLs, dedupes same-posting rows) →
`tools/parse_criteria.py` (annotates stated quotes with machine-readable windows,
refusing hedged or stale sentences) → `tools/validate.py` (thousands of invariant
assertions) → `tools/build.py` (a dependency-free single-file site). **TypeScript**
owns the app in `web/` — React + Vite, consuming the exact JSON the validator passed,
with the screener's rules ported one-to-one from the reference implementation.

Staleness is treated as a first-class failure mode: `tools/verify_quotes.py`
mechanically re-fetches every cited page and asserts each quote is still literally
present (bot walls and PDFs report as blocked, never as refutations), and a weekly
[freshness workflow](.github/workflows/freshness.yml) runs the sweep plus a dated
[watchlist](tools/watchlist.json) of expected application-window openings, opening an
issue when anything needs a human re-read. Failures never auto-demote data — deciding
whether a miss is a page change, a paraphrase, or a fetch artifact takes judgment.

---

## Why this exists

Most eligibility information students act on is folklore. It circulates on forums and
test-prep sites, contradicts itself on the details, and is repeated confidently by people
who never read the firm's page. A related study — [RESEARCH.md in
mayherprog/mental-math](https://github.com/mayherprog/mental-math) — traced one widely
believed assessment "specification" and found it had no firm-published source at any of
the six firms examined.

Cooling-off rules are the worst case. They are rarely aggregated, almost never cited, and
getting one wrong is expensive in both directions: believe a lockout that does not exist
and you sit out a cycle for nothing; miss one that does and you burn an attempt.

This project fixes exactly one thing: it puts the firm's own sentence, its link, and the
date it was read, in one place.

## What a row records — and what it refuses to

A row records **what a firm states**. It never renders a verdict about a particular reader.

"Expected graduation date between December 2027 and June 2028" is the row. It is a closed
door for a 2029 graduate and an open one for a 2028 graduate, and which of those you are
is not the database's business. This matters: the same fact serves opposite readers, so
programs excluded from one person's search still belong here.

## The three rules that make this trustworthy

**1. `quote` is verbatim, or the field does not exist.** Never paraphrased, never tidied,
never truncated to fit. Typos in the source are preserved. `parsed` values exist so you
can filter; whenever `parsed` and `quote` disagree, **the quote wins**.

**2. `state` has three values, and conflating them is how this project would do harm.**

| state | meaning |
|---|---|
| `stated` | the firm says it, and `quote` proves it |
| `silent` | the firm publishes nothing on this **on the page that was read**. A fact about the public record, not about the firm's practice. Silence is neither permission nor prohibition. |
| `unverified` | nobody has successfully checked yet |

The distinction between `silent` and `unverified` is load-bearing. You may only claim a
firm is silent if you can name the page you read — `tools/validate.py` enforces this, and
it is why McKinsey's rows are `unverified`: every route to mckinsey.com returned no body,
so the public record could not be inspected at all.

**3. `tier` records how much weight a source can bear.** Tier 1 is the firm itself, tier 2
university career services, tier 3 aggregated candidate reports — which can establish
*widely reported* and never *true*. **Test-prep vendors are excluded from citation
entirely.** A cooling-off period may never rest on tier 3 alone; the validator rejects it.

## Why cooling-off has its own structure

`trigger` and `scope` decide whether a lockout actually applies to you, and they are the
two things people get wrong.

`trigger` — `assessment_attempt`, `rejection`, `application`, `offer_declined`, `unknown`
`scope` — `this_role`, `this_program`, `all_roles`, `all_offices_all_roles`, `unknown`

A rejection at a résumé screen and an attempted assessment are different events. Being
turned down for one role is not the same as being locked out of a firm. Rows that do not
distinguish these are worse than no rows.

### A worked example of why the wording matters

Optiver's 8-month rule is the fact this project was built around, and checking it properly
changed it. An earlier private note recorded:

> "We only allow candidates to attempt an assessment at Optiver every 8 months, across all
> offices and roles."

That sentence is real Optiver text. But it was cited to a URL that does not carry it, and
it is the **first half** of a two-sentence answer. The second sentence immediately narrows
the scope to "this or a similar role that has the same assessment components." Optiver
states the rule three different ways across three of its own pages, and they do not agree.

Quoting sentence one alone tells a student the clock is broader than Optiver's own
follow-on sentence says. That is precisely the failure this project exists to stop, found
in its own founding fact. The full quote and all three formulations are in
[`data/optiver.json`](data/optiver.json).

## Coverage, stated honestly

194 programs across 69 firms, spanning quantitative trading, technology, banking and
finance, asset management, consulting, law and government. On cooling-off specifically:
**22 state a rule, 94 publish nothing on it, and 74 have not been checked yet.** The
unchecked share is the honest state of this dataset today, not a rounding error, and it is
visible in the interface rather than hidden.

These counts move as the data grows. `tools/build.py` regenerates
[`TABLE.md`](TABLE.md) with a current breakdown at the top, and `tools/validate.py` prints
the same totals; where this section and the generated output disagree, the generated output
is right.

Known gaps, all recorded in the data rather than papered over:

- **19 programs carry a verbatim quote but no source URL.** They were transcribed from a
  private posting tracker whose links were not captured. They are flagged `url_pending`
  and render as *no URL yet*. They are not independently citable until re-sourced.
- **14 programs are `blocked`** — the page is JavaScript-rendered or refuses automated
  reads. Amazon's FAQ accordions, Jane Street, Morgan Stanley, Tower Research and all of
  mckinsey.com fall here. These need a browser, not a fetch.
- **11 programs are `dead`** — the URL returns a non-200 or refuses the connection, in
  nearly every case because the posting or program page was taken down between cycles.
  Citadel Launch, Meta University, Two Sigma's first-year software engineering internship
  and several law-firm 1L programs sit here. Ten of the eleven carry no quote at all, and
  seven are `unverified` on every field, because a page that cannot be read cannot be said
  to publish nothing. The three marked `silent` are silent against a *different* page that
  was read successfully — the firm's general early-careers page — never against the dead
  URL itself.
- **Sponsorship is silent on most rows.** Do not read that as either sponsoring or not.

## Reproducing the data

```bash
python3 tools/transcribe_tracker.py path/to/tracker.xlsx   # private tracker -> data/
python3 tools/ingest_research.py                           # research/ -> data/
python3 tools/parse_criteria.py                            # annotate stated quotes with parses
python3 tools/validate.py                                  # enforce the rules above
python3 tools/build.py                                     # data/ -> TABLE.md + index.html
```

`parse_criteria.py` adds machine-readable graduation windows and sponsorship terms to
quotes that state them, printing every annotation for review. It refuses hedged
language ("typically", "preferred"), stale cycles, and ambiguous dates — a row the
screener cannot decide lands in the honest third bucket rather than in a guess.

`transcribe_tracker.py` extracts quotes programmatically rather than by hand, because a
script cannot mistype a firm's sentence. Text in the spreadsheet that was **not** inside
quotation marks is the tracker author's own summary; it is never written to a `quote`
field, only to `summary_note` on an `unverified` row.

`research/` holds the raw per-firm research output exactly as returned, so any quote in
`data/` can be traced back to the pass that produced it.

## Contributing

A row is only useful if it survives scrutiny. Pull requests must carry, for every claim:
the verbatim quote, the source URL, the tier, and the date checked. `tools/validate.py`
must pass. Rows that summarise a firm's position instead of quoting it will be declined —
not because the summary is wrong, but because a summary cannot be audited.

If a firm's page has changed, open a PR that updates the quote and the `checked` date
rather than deleting the old row; how a firm's language changed over time is itself useful.

## Licence

Code is MIT ([`LICENSE`](LICENSE)). Written material and the compiled dataset are
CC BY 4.0 ([`LICENSE-DOCS`](LICENSE-DOCS)). **Quoted material belongs to the firms that
wrote it, is reproduced for identification and reference, and is not relicensed.** See
[`NOTICE.md`](NOTICE.md) for what each licence covers and what this project does not claim.

## This is not advice

This is a dated snapshot of public pages. **A firm's own current page is always the
authority.** Pages are rewritten without notice, policies differ by region and by role, and
nothing here is legal, immigration, or career advice. Verify before you act.
