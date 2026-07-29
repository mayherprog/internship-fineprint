#!/usr/bin/env python3
"""Generate the published views from data/: TABLE.md and index.html.

Two rules drive every rendering decision here, and they are the reason this
file is longer than a table generator needs to be:

  1. Silence never looks like an answer. A firm that publishes nothing about
     sponsorship is not a green tick and not a red cross. It gets its own
     muted treatment and the words "publishes nothing".
  2. The quote is the authority; everything else is navigation. Parsed values
     exist to let you filter. Whenever they disagree with the quote, the quote
     wins, so the quote is always on screen next to the claim.

Usage:  python3 tools/build.py [data_dir]
"""

import html
import json
import pathlib
import sys
from collections import Counter

SECTOR_LABEL = {
    "big_tech": "Big tech", "banking_finance": "Banking & finance",
    "quant_trading": "Quant & trading", "consulting": "Consulting",
    "big_law": "Big law", "asset_management": "Asset management",
    "government": "Government", "other": "Other",
}
AUDIENCE_LABEL = {
    "undergraduate": "Undergraduate", "sophomore": "Sophomore/2nd year",
    "freshman": "First year", "law_student_jd": "Law student (JD)",
    "graduate": "Graduate", "phd": "PhD", "paralegal": "Paralegal",
    "all": "All", "unknown": "Not stated",
}
FIELD_LABEL = {
    "class_year": "Class year", "sponsorship": "Sponsorship",
    "process": "Process", "compensation": "Compensation",
}


def load(data_dir):
    rows = []
    for path in sorted(pathlib.Path(data_dir).glob("*.json")):
        rec = json.loads(path.read_text())
        for prog in rec["programs"]:
            rows.append({
                "firm": rec["firm"], "sector": rec["sector"],
                "id": prog["id"], "name": prog["name"],
                "audience": prog.get("audience", "unknown"),
                "cycle": prog.get("cycle", ""), "location": prog.get("location", ""),
                "source": prog["source"], "fields": prog["fields"],
                "cooling_off": prog["cooling_off"],
                "unfiled": prog.get("unfiled_quotes", []),
            })
    rows.sort(key=lambda r: (r["firm"].lower(), r["name"].lower()))
    return rows


def cooling_summary(co):
    """One short phrase for a table cell. Never asserts more than the data does."""
    state = co.get("state")
    if state != "stated":
        return {"silent": "publishes nothing", "unverified": "not checked yet"}.get(state, "not checked yet")
    p = co.get("parsed") or {}
    months = p.get("duration_months")
    if months:
        n = int(months) if float(months).is_integer() else months
        return f"{n} months stated"
    return "rule stated, no duration given"


def field_summary(field):
    state = field.get("state")
    if state == "stated":
        return field["quote"]
    if state == "silent":
        return "publishes nothing"
    return field.get("summary_note") or "not checked yet"


# --------------------------------------------------------------------------
# TABLE.md — the dataset is useful with no interface at all.
# --------------------------------------------------------------------------

def build_markdown(rows):
    counts = Counter(r["cooling_off"]["state"] for r in rows)
    firms = len({r["firm"] for r in rows})
    out = [
        "# Internship eligibility — the published record",
        "",
        "Generated from `data/` by `tools/build.py`. Do not edit by hand.",
        "",
        f"**{len(rows)} programs across {firms} firms.** "
        f"Cooling-off: {counts.get('stated', 0)} stated, "
        f"{counts.get('silent', 0)} publish nothing, "
        f"{counts.get('unverified', 0)} not yet checked.",
        "",
        "Every quote is the firm's own wording. **A firm's current page is always the "
        "authority** — these rows are a dated snapshot and firms rewrite pages without notice.",
        "",
        "`publishes nothing` is a fact about the public record, not a statement that a "
        "firm has no such policy. Silence is not permission and not prohibition.",
        "",
    ]
    by_sector = {}
    for r in rows:
        by_sector.setdefault(r["sector"], []).append(r)

    for sector in sorted(by_sector, key=lambda s: SECTOR_LABEL.get(s, s)):
        out += [f"## {SECTOR_LABEL.get(sector, sector)}", "",
                "| Firm | Program | For | Class year (firm's words) | Cooling-off | Checked | Source |",
                "|---|---|---|---|---|---|---|"]
        for r in by_sector[sector]:
            cy = r["fields"]["class_year"]
            words = field_summary(cy).replace("|", "\\|")
            if len(words) > 150:
                words = words[:147] + "…"
            if cy.get("state") == "stated":
                words = f'"{words}"'
            url = r["source"].get("url")
            status = r["source"].get("status")
            link = f"[link]({url})" if url else {
                "url_pending": "_no URL yet_", "blocked": "_blocked_",
                "dead": "_dead link_"}.get(status, "_none_")
            out.append(
                f"| {r['firm']} | {r['name'][:70]} | {AUDIENCE_LABEL.get(r['audience'], r['audience'])} "
                f"| {words} | {cooling_summary(r['cooling_off'])} "
                f"| {r['source'].get('checked', '')} | {link} |")
        out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# index.html — one self-contained file. No build step, no framework, no backend.
# --------------------------------------------------------------------------

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Internship eligibility, in the firms' own words</title>
<meta name="description" content="A sourced, dated record of what firms actually state about internship eligibility, sponsorship, class year and cooling-off periods.">
<style>
:root{
  --bg:#fbfbfa; --fg:#1a1a19; --muted:#6b6b66; --line:#e2e1dc; --card:#fff;
  --stated:#1c6b3f; --stated-bg:#e8f3ec; --silent:#7a6a2f; --silent-bg:#f6f1e0;
  --unver:#6b6b66; --unver-bg:#efeeea; --warn:#8a3324; --warn-bg:#f9ebe8; --accent:#1f4f82;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#14150f; --fg:#eceade; --muted:#9d9b8e; --line:#2d2e26; --card:#1b1c15;
    --stated:#7fc79b; --stated-bg:#17301f; --silent:#d4bd6a; --silent-bg:#302a14;
    --unver:#9d9b8e; --unver-bg:#26261f; --warn:#e8a396; --warn-bg:#3a1d17; --accent:#8fb8e8;
  }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
  font:16px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 80px}
h1{font-size:1.7rem;margin:0 0 6px;letter-spacing:-.02em}
.sub{color:var(--muted);margin:0 0 20px;max-width:70ch}
.banner{border:1px solid var(--line);border-left:4px solid var(--warn);background:var(--warn-bg);
  padding:12px 16px;border-radius:8px;margin:0 0 22px;font-size:.9rem;max-width:80ch}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 22px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:9px 13px;font-size:.85rem}
.stat b{font-size:1.15rem;display:block;line-height:1.2}
.controls{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 8px;position:sticky;top:0;
  background:var(--bg);padding:10px 0;z-index:5;border-bottom:1px solid var(--line)}
select,input{font:inherit;font-size:.9rem;padding:7px 10px;border:1px solid var(--line);
  border-radius:7px;background:var(--card);color:var(--fg)}
input{flex:1;min-width:190px}
.count{color:var(--muted);font-size:.85rem;margin:10px 0 16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:0 0 12px}
.card h3{margin:0 0 2px;font-size:1.02rem}
.card .firm{color:var(--accent);font-weight:600}
.meta{color:var(--muted);font-size:.82rem;margin:0 0 12px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(255px,1fr));gap:10px}
.f{border:1px solid var(--line);border-radius:8px;padding:10px 12px;background:var(--bg)}
.f .lbl{font-size:.7rem;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:5px}
.q{font-size:.88rem}
.q.quote{border-left:3px solid var(--stated);padding-left:9px}
.pill{display:inline-block;font-size:.68rem;text-transform:uppercase;letter-spacing:.05em;
  padding:2px 7px;border-radius:20px;margin-left:6px;vertical-align:1px;font-weight:600}
.s-stated{background:var(--stated-bg);color:var(--stated)}
.s-silent{background:var(--silent-bg);color:var(--silent)}
.s-unverified{background:var(--unver-bg);color:var(--unver)}
.s-warn{background:var(--warn-bg);color:var(--warn)}
.none{color:var(--muted);font-style:italic;font-size:.88rem}
.cool{margin-top:11px;border:1px solid var(--line);border-left:4px solid var(--muted);
  border-radius:8px;padding:11px 13px;background:var(--bg)}
.cool.has{border-left-color:var(--warn)}
.notes{color:var(--muted);font-size:.79rem;margin-top:7px}
a{color:var(--accent)}
footer{margin-top:44px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);font-size:.84rem;max-width:80ch}
table{width:100%;border-collapse:collapse}
.tablewrap{overflow-x:auto}
</style>
</head>
<body>
<div class="wrap">
<h1>Internship eligibility, in the firms' own words</h1>
<p class="sub">Every row is a sentence a firm published about who may apply, quoted exactly, with a
link and the date it was read. Firms that say nothing are recorded as saying nothing.</p>

<div class="banner"><strong>Read this first.</strong> This is a dated snapshot, not advice, and not a
verdict about you. <strong>The firm's own current page is always the authority</strong> — pages get
rewritten without notice. &ldquo;Publishes nothing&rdquo; is a fact about the public record only: it
does not mean a firm has no such policy, and silence is neither permission nor prohibition.</div>

<div class="stats" id="stats"></div>

<div class="controls">
  <select id="sector"></select>
  <select id="audience"></select>
  <select id="cool">
    <option value="">Cooling-off: any</option>
    <option value="stated">States a rule</option>
    <option value="silent">Publishes nothing</option>
    <option value="unverified">Not checked yet</option>
  </select>
  <select id="spon">
    <option value="">Sponsorship: any</option>
    <option value="stated">States something</option>
    <option value="silent">Publishes nothing</option>
    <option value="unverified">Not checked yet</option>
  </select>
  <input id="q" type="search" placeholder="Search firms, programs, quoted text…">
</div>
<div class="count" id="count"></div>
<div id="list"></div>

<footer>
<p>Generated from <code>data/</code>, one JSON file per firm, validated by
<code>tools/validate.py</code>. Quoted material belongs to the firms that wrote it, is
reproduced for identification and reference, and is not relicensed.</p>
<p id="gen"></p>
</footer>
</div>

<script id="payload" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('payload').textContent);
const SECTORS = __SECTORS__, AUD = __AUD__, FIELDS = __FIELDS__;
const esc = s => String(s ?? '').replace(/[&<>"']/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function pill(state){
  const label = {stated:'stated', silent:'publishes nothing', unverified:'not checked'}[state] || state;
  return `<span class="pill s-${esc(state)}">${esc(label)}</span>`;
}
function srcLink(url, status){
  if (url) return `<a href="${esc(url)}" rel="noopener nofollow">source</a>`;
  if (status === 'url_pending') return `<span class="pill s-warn">source link missing</span>`;
  if (status === 'blocked') return `<span class="pill s-warn">page blocks automated reads</span>`;
  if (status === 'dead') return `<span class="pill s-warn">link dead</span>`;
  return '';
}
function fieldHTML(key, f){
  let body;
  if (f.state === 'stated') body = `<div class="q quote">&ldquo;${esc(f.quote)}&rdquo;</div>`;
  else if (f.state === 'silent') body = `<div class="none">The firm publishes nothing on this.</div>`;
  else body = `<div class="none">${f.summary_note ? esc(f.summary_note) + ' — unverified, not the firm\\'s wording'
                                                  : 'Nobody has checked this yet.'}</div>`;
  const tier = f.tier && f.state === 'stated' ? ` &middot; tier ${esc(f.tier)}` : '';
  const link = f.state === 'stated' ? ' &middot; ' + srcLink(f.source_url, f.source_status) : '';
  return `<div class="f"><div class="lbl">${esc(FIELDS[key])}${pill(f.state)}</div>${body}
    <div class="notes">${f.checked ? 'checked ' + esc(f.checked) : ''}${tier}${link}</div></div>`;
}
function coolHTML(co){
  const has = co.state === 'stated';
  let body;
  if (has) body = `<div class="q quote">&ldquo;${esc(co.quote)}&rdquo;</div>`;
  else if (co.state === 'silent') body = `<div class="none">The firm publishes no reapplication or
    assessment-retry rule on the page checked. That is a fact about the public record, not proof
    no rule exists.</div>`;
  else body = `<div class="none">Not checked yet.</div>`;
  const p = co.parsed || {};
  const bits = [];
  // Parsed trigger/scope labels appear ONLY when the firm states an actual
  // constraint (a duration, a cap, an explicit no-resets). Attaching
  // "triggered by rejection" to a permissive sentence like JPMorgan's
  // "you can submit a new application" would imply a lockout the firm
  // never stated. The quote is on screen either way and always wins.
  if (has && p.restrictive === true){
    if (p.duration_months) bits.push(`${p.duration_months} months`);
    if (p.trigger && p.trigger !== 'unknown') bits.push('triggered by ' + p.trigger.replace(/_/g,' '));
    if (p.scope && p.scope !== 'unknown') bits.push('scope: ' + p.scope.replace(/_/g,' '));
    if (p.application_cap) bits.push('cap: ' + p.application_cap);
  }
  return `<div class="cool${has ? ' has' : ''}"><div class="lbl">Cooling-off / reapplying${pill(co.state)}</div>
    ${body}
    ${bits.length ? `<div class="notes">${esc(bits.join(' · '))}</div>` : ''}
    ${co.notes ? `<div class="notes">${esc(co.notes)}</div>` : ''}
    <div class="notes">${co.checked ? 'checked ' + esc(co.checked) + ' &middot; ' : ''}
      ${has ? srcLink(co.source_url, co.source_status) : ''}</div></div>`;
}
function cardHTML(r){
  const meta = [r.cycle, r.location, AUD[r.audience] || r.audience].filter(Boolean).map(esc).join(' &middot; ');
  return `<article class="card">
    <h3><span class="firm">${esc(r.firm)}</span> — ${esc(r.name)}</h3>
    <p class="meta">${meta} &middot; ${SECTORS[r.sector] || r.sector} &middot;
      ${srcLink(r.source.url, r.source.status)}
      ${r.source.checked ? ' &middot; read ' + esc(r.source.checked) : ''}</p>
    ${r.source.note ? `<p class="meta">${esc(r.source.note)}</p>` : ''}
    <div class="grid">${Object.keys(FIELDS).map(k => fieldHTML(k, r.fields[k] || {state:'unverified'})).join('')}</div>
    ${coolHTML(r.cooling_off)}
    ${(r.unfiled && r.unfiled.length) ? `<div class="notes">Other quoted sentences from this source:
      ${r.unfiled.map(u => '&ldquo;' + esc(u.quote) + '&rdquo;').join(' ')}</div>` : ''}
  </article>`;
}

const $ = id => document.getElementById(id);
function fill(sel, map, label){
  $(sel).innerHTML = `<option value="">${label}: all</option>` +
    [...new Set(DATA.map(r => r[sel]))].sort()
      .map(v => `<option value="${esc(v)}">${esc(map[v] || v)}</option>`).join('');
}
fill('sector', SECTORS, 'Sector');
fill('audience', AUD, 'Open to');

function render(){
  const s = $('sector').value, a = $('audience').value, c = $('cool').value,
        sp = $('spon').value, q = $('q').value.trim().toLowerCase();
  const rows = DATA.filter(r =>
    (!s || r.sector === s) && (!a || r.audience === a) &&
    (!c || r.cooling_off.state === c) &&
    (!sp || (r.fields.sponsorship || {}).state === sp) &&
    (!q || JSON.stringify(r).toLowerCase().includes(q)));
  $('count').textContent = `${rows.length} of ${DATA.length} programs`;
  $('list').innerHTML = rows.length ? rows.map(cardHTML).join('')
    : '<p class="none">No programs match. Try clearing a filter.</p>';
}
['sector','audience','cool','spon'].forEach(i => $(i).addEventListener('change', render));
$('q').addEventListener('input', render);

const cs = {stated:0, silent:0, unverified:0};
DATA.forEach(r => cs[r.cooling_off.state]++);
$('stats').innerHTML = [
  ['programs', DATA.length], ['firms', new Set(DATA.map(r => r.firm)).size],
  ['state a cooling-off rule', cs.stated], ['publish nothing on it', cs.silent],
  ['not yet checked', cs.unverified],
].map(([k, v]) => `<div class="stat"><b>${v}</b>${esc(k)}</div>`).join('');
$('gen').textContent = 'Built __BUILT__ from __N__ programs.';
render();
</script>
</body>
</html>
"""


def build_html(rows, built):
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    # The payload sits inside a <script> block, so a literal </script> in any
    # quoted sentence would end the block early. Neutralise it.
    payload = payload.replace("</", "<\\/")
    return (PAGE
            .replace("__DATA__", payload)
            .replace("__SECTORS__", json.dumps(SECTOR_LABEL))
            .replace("__AUD__", json.dumps(AUDIENCE_LABEL))
            .replace("__FIELDS__", json.dumps(FIELD_LABEL))
            .replace("__BUILT__", built)
            .replace("__N__", str(len(rows))))


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    rows = load(data_dir)
    pathlib.Path("TABLE.md").write_text(build_markdown(rows) + "\n")
    pathlib.Path("index.html").write_text(build_html(rows, "2026-07-29"))
    counts = Counter(r["cooling_off"]["state"] for r in rows)
    print(f"TABLE.md and index.html: {len(rows)} programs, "
          f"{len({r['firm'] for r in rows})} firms")
    print(f"  cooling-off: {counts['stated']} stated, {counts['silent']} silent, "
          f"{counts['unverified']} unverified")


if __name__ == "__main__":
    main()
