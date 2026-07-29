# Internship eligibility, in the firms' own words

A sourced, dated record of what firms **actually state** about who may apply to their
internship and early-career programs: class year, sponsorship and work authorisation,
process stages, and above all **cooling-off periods** — the rules about reapplying and
retaking assessments that quietly cost candidates an entire recruiting cycle.

Every row is a sentence a firm published, quoted exactly, with a link and the date it was
read. Firms that publish nothing are recorded as publishing nothing.

```bash
python3 tools/validate.py     # 4,016 assertions over 132 programs, 0 failures
```

**[Browse the data →](TABLE.md)** &nbsp;·&nbsp; **[Interactive view →](index.html)**

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

132 programs across 68 firms, spanning technology, banking and finance, quantitative
trading, consulting and law. Of those, **11 state a cooling-off rule, 30 publish nothing
on it, and 91 have not been checked yet.** The unchecked majority is the honest state of this dataset today, not
a rounding error, and it is visible in the interface rather than hidden.

Known gaps, all recorded in the data rather than papered over:

- **32 rows carry a verbatim quote but no source URL.** They were transcribed from a
  private posting tracker whose links were not captured. They are flagged `url_pending`
  and render as *source link missing*. They are not independently citable until re-sourced.
- **16 rows are `blocked`** — the page is JavaScript-rendered or refuses automated reads.
  Google's careers site, Amazon's FAQ accordions, Skadden's app shell and all of
  mckinsey.com fall here. These need a browser, not a fetch.
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
