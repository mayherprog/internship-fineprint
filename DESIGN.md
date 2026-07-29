# Design system

The rules the interface follows. New surfaces — including the screener — must build
from these tokens and components rather than introducing parallel ones. The tokens
live as CSS custom properties in `tools/template.html`; this file is their contract.

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

The three record states map one-to-one to the three state color pairs and nowhere
else. Do not reuse state colors decoratively.

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

## Spacing and shape

Base unit 4px. Common paddings: 12–16px inside cards and tiles, 9–13px inside
controls and stats. Radii: 7px controls, 8px field boxes and stats, 10px cards and
tiles, 20px pills and quick chips. Page column max-width 1180px; long prose blocks
(banner, footer) max 80ch.

## Components

- **Notice banner** — warn-tinted, 4px left rule. One per page, home only.
- **Stat** — clickable count tile: bold number over muted label. Navigates to a view.
- **Sector tile** — bold name over muted "N firms · N programs". Navigates.
- **Quick chip** — pill-shaped view shortcut. Plain descriptions, no slang.
- **Controls bar** — sticky; back button, selects, search. First option of each
  select doubles as its label; each select also carries an `aria-label`.
- **Card (`<details>`)** — collapsed summary row: firm (accent) — program, state
  pill for class year, warn pill if a reapplication rule is stated, muted audience/
  cycle. Cycle text over 28 characters stays in the drawer.
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
