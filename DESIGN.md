# Design system

The rules the interface follows. New surfaces — including the screener — must build
from these tokens and components rather than introducing parallel ones. The tokens
live as CSS custom properties in `tools/template.html`; this file is their contract.

Parts of this contract were adopted from the sibling project's design system
(`mental-math/DESIGN.md`), which documents what transfers and what must not. The
boundary matters more than the imports: that project's accent is green and its warn
colour is amber, and neither colour value may travel here, because here green
uniquely means *stated* and amber uniquely means *publishes nothing* (principle 2).
A shared aesthetic is worth less than an unambiguous state colour.

## Principles, in priority order

1. **The quote is the interface.** Everything else — pills, filters, parsed chips —
   is navigation toward a firm's own sentence. If a derived label and a quote could
   disagree, the quote must be on screen.
2. **Silence never looks like an answer.** `silent` is never a green tick, never a
   red cross, never blank. It always renders as the words "publishes nothing" in its
   own muted-amber treatment.
3. **Derived labels only where the firm stated a constraint.** Parsed trigger/scope
   chips appear only when `parsed.restrictive` is true. A permissive sentence gets no
   chips; the quote speaks alone.
4. **One self-contained file.** No frameworks, no external requests, no build step
   beyond `tools/build.py`. Links out (sources, calendar templates) are user
   navigation, not resource loading.
5. **Nothing personal leaves the page.** Screener inputs are never stored, never
   transmitted, never written to the URL. Browse filters may live in the URL hash;
   personal attributes may not.
6. **Formal register.** Schema vocabulary in the interface ("unverified", "stated"),
   plain descriptions elsewhere. No insider shorthand as user-facing labels.

## Color tokens

Semantic roles, defined once per theme (light and dark via `prefers-color-scheme`):

| Token | Role |
|---|---|
| `--bg` / `--fg` | page ground and primary text |
| `--card` | raised surface (cards, tiles, controls) |
| `--line` | hairline borders |
| `--muted` | secondary text, labels, metadata |
| `--accent` | firm names, links, interactive affordances |
| `--stated` / `--stated-bg` | the firm said it, quote present (green) |
| `--silent` / `--silent-bg` | publishes nothing (amber — deliberately neither go nor stop) |
| `--unver` / `--unver-bg` | not yet verified (grey) |
| `--warn` / `--warn-bg` | caution: lockout rules, missing sources, the read-this-first notice |
| `--accent-soft` | filled hover/selected wash for interactive surfaces (blue-tinted, so it can never be mistaken for a state) |

The three record states map one-to-one to the three state color pairs and nowhere
else. Do not reuse state colors decoratively. The accent stays blue
(`#1f4f82` / `#8fb8e8`) precisely so that no interactive affordance shares a hue
with any record state.

Neutrals are warm on purpose (`#fbfbfa` ground, `#14150f` dark ground), matching
the sibling project's warm-neutral rule without importing its palette.

## Type scale

| Step | Size | Use |
|---|---|---|
| XL | 1.7rem, -0.02em tracking | page title only |
| L | 1.05rem | search input on home |
| M | 0.95–1rem | body, tile titles, card summary titles |
| S | 0.88–0.9rem | quotes, controls, drawer body |
| XS | 0.82–0.85rem | metadata, counts, notes. **Floor for readable text is 0.82rem.** |
| Label | 0.7rem uppercase, +0.07em tracking | field labels only |
| Pill | 0.68rem uppercase | state pills only |

Section headers on home are the Label step at 0.8rem, muted.

**Monospace is for digits that must line up in a column, never for words.** The
`.num` helper (system mono stack, tabular numerals) applies to the home stat
numbers. It does not apply to dates inside sentences, durations, headings, labels,
or quotes — a date in a quote is part of a phrase, not a column. Small uppercase
field labels and state pills are kept deliberately: they are conventional in a
dense data table (the sibling project removed uppercase for its own reasons; that
was a judgement call there, not a rule here).

## Spacing and shape

Base unit 4px. Common paddings: 12–16px inside cards and tiles, 9–13px inside
controls and stats. Radii are tokens: `--r-sm: 8px` (controls, field boxes, stats,
banner), `--r-md: 12px` (cards, tiles, the home search), `--r-pill: 999px` (pills
and quick chips). Page column max-width 1180px; long prose blocks (banner, footer)
max 80ch.

## Components

- **Notice banner** — warn-tinted, 4px left rule. One per page, home only.
- **Stat** — clickable count tile: bold number over muted label. Navigates to a view.
- **Sector tile** — bold name over muted "N firms · N programs". Navigates.
- **Quick chip** — pill-shaped view shortcut. Plain descriptions, no slang.
- **Controls bar** — sticky; back button, selects, search. First option of each
  select doubles as its label; each select also carries an `aria-label`.
- **Card (`<details>`)** — collapsed summary row: firm (accent) — program, then
  **labelled** state pills for class year and sponsorship, warn pill if a
  reapplication rule is stated, muted audience/cycle. Cycle text over 28
  characters stays in the drawer. **The summary must carry the record's state,
  named** — a bare "stated" pill answers "what state?" but not "state of what?",
  and a collapsed card that hides its states forces a reader to open every
  drawer. (Adopted from the sibling project's disclosure rule: the summary
  carries the current value.)
- **Drawer** — meta line, source note if any, calendar line if a date parses,
  2×2 field grid, cooling-off block, unfiled quotes.
- **Field box** — label + state pill, then exactly one of: a quote (green left
  rule), "The firm publishes nothing on this.", or a summary note explicitly
  marked as not the firm's wording.
- **Cooling-off block** — full-width, warn left rule when a rule is stated;
  parsed chips only when restrictive.
- **Calendar line** — only when a date parses from opens/closes; estimated dates
  carry a warn "estimate" pill and the word "(estimated)" inside the event title.

## Screener rules (binding for the feature)

Inputs: expected graduation month and year; work-authorization situation. Nothing
else, all client-side. Output is three groups, in this order and with these
semantics:

1. **Stated criteria that include your answers** — every entry shows which parsed
   window or sponsorship statement matched, and the quote is one click away.
2. **Stated criteria that exclude your answers** — same treatment. The word is
   "exclude", never "ineligible".
3. **Not decidable from the parsed record** — silent, unverified, or stated only in
   prose that was not machine-parsed. This is usually the largest group and its size
   is shown, not hidden.

The screener never uses the words "eligible", "qualified", or "fit". A disclaimer
above the results repeats that this is criteria matching against a dated snapshot,
not an eligibility determination.

## Interaction rules

- **Selected and hovered interactive surfaces fill, they do not hint.** Stat
  tiles, sector tiles, quick chips and the back button take an `--accent-soft`
  fill with an accent border on hover and keyboard focus — never a one-pixel
  border change alone.
- **A control is always rendered; a media query may only restyle it, never
  create it.** A media query must not be the only thing standing between a
  reader and a working control.
- **Stat labels reserve two lines** so the numbers above them share a baseline
  regardless of label length.
