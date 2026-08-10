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
| `--shadow` | card/tile/search elevation; soft double shadow in light, single subtle in dark |

Tokens are defined on `:root` (light), redefined under `prefers-color-scheme:
dark`, then again under `:root[data-theme="light"]` and `:root[data-theme="dark"]`
so the manual toggle overrides the OS preference **in both directions**. The
choice persists in `localStorage` — a device preference, not personal data, so it
does not violate the nothing-personal rule.

The three record states map one-to-one to the three state color pairs and nowhere
else. Do not reuse state colors decoratively. The accent stays blue
(`#1f4f82` / `#8fb8e8`) precisely so that no interactive affordance shares a hue
with any record state.

Neutrals are warm on purpose (`#fbfbfa` ground; dark ground `#23211d`, a warm
dark grey, **not near-black** — near-black is what reads as cinematic), matching
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

**Monospace is for digits that must line up in a column, never for words.** No
current surface qualifies (the stat tiles that did were removed as unnecessary);
if one appears, give it a system mono stack with tabular numerals. The rule does
not apply to dates inside sentences, durations, headings, labels, or quotes — a
date in a quote is part of a phrase, not a column.

**Sentence case everywhere.** Uppercase tracked labels and pills were tried and
reversed on owner feedback: combined with a dark ground and mono digits they read
as a terminal, not a reference. Section headers, field labels, and pills are
sentence case at slightly larger sizes (labels 0.8rem, pills 0.76rem).

## Spacing and shape

Base unit 4px. Common paddings: 12–16px inside cards and tiles, 9–13px inside
controls and stats. Radii are tokens: `--r-sm: 8px` (controls, field boxes, stats,
banner), `--r-md: 12px` (cards, tiles, the home search), `--r-pill: 999px` (pills
and quick chips). Page column max-width 1180px; long prose blocks (banner, footer)
max 80ch.

## Components

- **About disclosure** (`<details class="about">`) — the full caveats (dated
  snapshot, firm's page is the authority, what silence means, source rules) live
  collapsed at the bottom of the page, above the footer, on every view. The
  summary is the single word "About" with a collapse arrow (owner call: a
  summary that restates the caveat is itself noise). The home page opens with
  search, not with a warning. The screener keeps its own short inline
  disclaimer next to the results it qualifies — that one carries the caveat at
  the point of use, which is why the About line can afford to be one word.
- **Header** — sticky on every view: the wordmark "Fineprint" (heavy, tight
  tracking, accent full stop; clicking it goes home) over the tagline, a
  global pill search on the right (hidden on home, where the hero search
  serves), and the theme toggle. The header search drives the browse query
  live and switches to browse if typed into from another view. The product
  has a name; the page title is not a sentence.
- **Hero line** — one sentence above the search box carrying the live counts
  ("Search N programs at N firms."). This is the only place counts appear on
  home.
- **Sector tile** — bold name over muted "N firms · N programs". Navigates.
  Tiles, cards and the search field carry `--shadow`; the reference register is
  a job board (raised white cards on a warm ground), not a terminal.
- **Quick chip** — pill-shaped view shortcut. Plain descriptions, no slang.
- **Controls bar** — back button and filter chips; the search lives in the
  sticky header, so this bar scrolls away with the content. Filters are native
  `<select>` elements restyled as pill chips (custom caret, shadow), keeping
  them keyboard- and screen-reader-native. First option of each select doubles
  as its label; each select also carries an `aria-label`. **An active filter
  fills** (`.on`: accent-soft ground, accent border, semibold) — the filled
  selected-state rule applied to filtering.
- **Card (`<details>`)** — collapsed summary row: firm (accent) — program, then
  **labelled** state pills for class year and sponsorship, warn pill if a
  reapplication rule is stated, muted audience/cycle. Cycle text over 28
  characters stays in the drawer. **The summary must carry the record's state,
  named** — a bare "stated" pill answers "what state?" but not "state of what?",
  and a collapsed card that hides its states forces a reader to open every
  drawer. (Adopted from the sibling project's disclosure rule: the summary
  carries the current value.)
- **Drawer** — meta line, calendar line if a date parses, 2×2 field grid,
  cooling-off block, unfiled quotes. **`source.note` is never rendered and
  never shipped in the payload.** It is maintainer provenance — which
  user-agent got past a 403, whether answers sat in a collapsed accordion,
  which fetch attempt succeeded — and it was reaching readers as a paragraph in
  the drawer *and* as searchable text. That is scraping mechanics on the face
  of a reference work, against principle 1 (the quote is the interface) and
  principle 6 (formal register, no insider shorthand). The note stays in
  `data/` where auditors read it; `tools/build.py` strips it when building the
  payload, so a note can never reach the page again merely by being written
  into a record. Source quality still reaches the reader, through the tier pill
  and the source-status link.
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

- **Selected and hovered interactive surfaces fill, they do not hint.** Sector
  tiles, quick chips and the back button take an `--accent-soft` fill with an
  accent border on hover and keyboard focus — never a one-pixel border change
  alone.
- **A control is always rendered; a media query may only restyle it, never
  create it.** A media query must not be the only thing standing between a
  reader and a working control.
