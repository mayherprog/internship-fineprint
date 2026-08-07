import { useEffect, useMemo, useState } from "react";
import type { Program, UpdateEntry } from "./types";
import { AUDIENCE_LABEL, SECTOR_LABEL } from "./types";
import { judge, type Profile, type Verdict } from "./judge";
import { ProgramCard, Pill } from "./components";

type View = "home" | "browse" | "match";

interface Filters {
  sector: string;
  audience: string;
  cool: string;
  spon: string;
  q: string;
}
const NO_FILTERS: Filters = { sector: "", audience: "", cool: "", spon: "", q: "" };

const MNAMES = ["January","February","March","April","May","June",
  "July","August","September","October","November","December"];

function searchable(r: Program): string {
  const bits = [r.firm, r.name, r.cycle, r.location];
  for (const f of Object.values(r.fields)) bits.push(f.quote ?? "", f.summary_note ?? "");
  bits.push(r.cooling_off.quote ?? "", r.cooling_off.notes ?? "",
    (r.unfiled ?? []).map((u) => u.quote).join(" "), r.source.note ?? "");
  return bits.join(" ").toLowerCase();
}

function coolMatch(r: Program, c: string): boolean {
  if (!c) return true;
  if (c === "restrictive") return r.cooling_off.parsed?.restrictive === true;
  return r.cooling_off.state === c;
}

/* Manual choice persists and overrides the OS preference in both directions;
   a device preference is not personal data. */
function useTheme() {
  const [theme, setTheme] = useState<string | null>(() => {
    try { return localStorage.getItem("fineprint-theme"); } catch { return null; }
  });
  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme;
  }, [theme]);
  const dark = theme
    ? theme === "dark"
    : typeof matchMedia !== "undefined" && matchMedia("(prefers-color-scheme: dark)").matches;
  const toggle = () => {
    const next = dark ? "light" : "dark";
    setTheme(next);
    try { localStorage.setItem("fineprint-theme", next); } catch { /* private mode */ }
  };
  return { dark, toggle };
}

export default function App() {
  const [data, setData] = useState<Program[] | null>(null);
  const [updates, setUpdates] = useState<UpdateEntry[]>([]);
  const [view, setView] = useState<View>("home");
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [meMonth, setMeMonth] = useState("5");
  const [meYear, setMeYear] = useState("2029");
  const [meAuth, setMeAuth] = useState<Profile["auth"]>("citizen");
  const { dark, toggle } = useTheme();

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data.json`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData([]));
    fetch(`${import.meta.env.BASE_URL}updates.json`)
      .then((r) => r.json())
      .then(setUpdates)
      .catch(() => setUpdates([]));
  }, []);

  // Deep links restore browse filters; screener answers are deliberately
  // excluded from the URL, so a shared link can never carry someone's profile.
  useEffect(() => {
    const boot = new URLSearchParams(location.hash.slice(1));
    if ([...boot.keys()].length) {
      setFilters({
        sector: boot.get("sector") ?? "", audience: boot.get("audience") ?? "",
        cool: boot.get("cool") ?? "", spon: boot.get("spon") ?? "", q: boot.get("q") ?? "",
      });
      setView("browse");
    }
  }, []);

  useEffect(() => {
    if (view !== "browse") return;
    const h = new URLSearchParams();
    (Object.entries(filters) as [string, string][]).forEach(([k, v]) => v && h.set(k, v));
    history.replaceState(null, "",
      h.toString() ? `#${h.toString()}` : location.pathname + location.search);
  }, [filters, view]);

  const searchIndex = useMemo(
    () => new Map((data ?? []).map((r) => [r.id, searchable(r)])),
    [data],
  );

  if (data === null) return <div className="wrap"><p className="none">Loading…</p></div>;

  const go = (patch: Partial<Filters>) => {
    setFilters({ ...NO_FILTERS, ...patch });
    setView("browse");
    window.scrollTo(0, 0);
  };
  const home = () => {
    history.replaceState(null, "", location.pathname + location.search);
    setView("home");
    window.scrollTo(0, 0);
  };

  const rows = data.filter((r) =>
    (!filters.sector || r.sector === filters.sector) &&
    (!filters.audience || r.audience === filters.audience) &&
    coolMatch(r, filters.cool) &&
    (!filters.spon || (r.fields.sponsorship ?? { state: "" }).state === filters.spon) &&
    (!filters.q || (searchIndex.get(r.id) ?? "").includes(filters.q.trim().toLowerCase())));

  const sectors = [...new Set(data.map((r) => r.sector))]
    .map((s) => ({
      s,
      firms: new Set(data.filter((r) => r.sector === s).map((r) => r.firm)).size,
      programs: data.filter((r) => r.sector === s).length,
    }))
    .sort((a, b) => b.programs - a.programs);

  const groups: Record<1 | 2 | 3, [Program, Verdict][]> = { 1: [], 2: [], 3: [] };
  if (profile) data.forEach((r) => { const v = judge(r, profile); groups[v.group].push([r, v]); });

  return (
    <div className="wrap">
      <header className="top">
        <div>
          <h1 className="wordmark" onClick={home} title="Home">Fineprint</h1>
          <div className="tagline">Internship eligibility, in the firms&apos; own words</div>
        </div>
        {view !== "home" ? (
          <input className="gsearch" type="search" value={filters.q}
            placeholder="Search firms, programs, quoted text…" aria-label="Search programs"
            onChange={(e) => { setFilters({ ...filters, q: e.target.value }); setView("browse"); }} />
        ) : null}
        <button className={`theme${view === "home" ? " solo" : ""}`} onClick={toggle}
          aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}>
          {dark ? "☀" : "☾"}
        </button>
      </header>

      {view === "home" ? (
        <section>
          <p className="hero-line">
            Search <b>{data.length}</b> programs at <b>{new Set(data.map((r) => r.firm)).size}</b> firms.
          </p>
          <HomeSearch onGo={(q) => go({ q })} />
          <h2>Browse by sector</h2>
          <div className="tiles">
            {sectors.map(({ s, firms, programs }) => (
              <button key={s} className="tile" onClick={() => go({ sector: s })}>
                <b>{SECTOR_LABEL[s] ?? s}</b>
                <span>{firms} firm{firms === 1 ? "" : "s"} · {programs} program{programs === 1 ? "" : "s"}</span>
              </button>
            ))}
          </div>
          <h2>Quick views</h2>
          <div className="quick">
            <button onClick={() => go({})}>View all programs</button>
            <button onClick={() => go({ cool: "restrictive" })}>Reapplication lockouts</button>
            <button onClick={() => go({ audience: "sophomore" })}>Programs for sophomores</button>
            <button onClick={() => go({ audience: "freshman" })}>Programs for first-year students</button>
            <button onClick={() => go({ spon: "stated" })}>Stated sponsorship terms</button>
          </div>
          {updates.length ? (
            <>
              <h2>Recent changes</h2>
              {updates.slice(0, 8).map((u, i) => (
                <div className="upd" key={i}>
                  <span className="d">{u.date}</span> · <span className="v">{u.verdict}</span> ·{" "}
                  <strong>{u.firm}</strong> — {u.program} ·{" "}
                  <a href={u.url} rel="noopener nofollow">page</a>
                  <p>{u.evidence}</p>
                </div>
              ))}
            </>
          ) : null}
          <h2>Match against stated criteria</h2>
          <div className="screener">
            <select value={meMonth} onChange={(e) => setMeMonth(e.target.value)}
              aria-label="Expected graduation month">
              {MNAMES.map((m, i) => <option key={m} value={String(i + 1)}>{m}</option>)}
            </select>
            <select value={meYear} onChange={(e) => setMeYear(e.target.value)}
              aria-label="Expected graduation year">
              {["2026","2027","2028","2029","2030","2031"].map((y) => <option key={y}>{y}</option>)}
            </select>
            <select value={meAuth} onChange={(e) => setMeAuth(e.target.value as Profile["auth"])}
              aria-label="Work authorization situation">
              <option value="citizen">U.S. citizen or permanent resident</option>
              <option value="cpt">F-1 student — can work via CPT/OPT, no employer sponsorship needed</option>
              <option value="sponsor">Will need employer visa sponsorship</option>
            </select>
            <button onClick={() => {
              setProfile({ grad: `${meYear}-${meMonth.padStart(2, "0")}`, auth: meAuth });
              setView("match");
              window.scrollTo(0, 0);
            }}>Match</button>
          </div>
          <p className="notes">
            Your answers stay on this page — nothing is stored, sent, or written to the address
            bar. Matching compares your answers with criteria firms have stated, in a dated
            snapshot. It is not an eligibility determination.
          </p>
        </section>
      ) : null}

      {view === "browse" ? (
        <section>
          <div className="controls">
            <button className="back" onClick={home}>← Home</button>
            <FilterSelect value={filters.sector} label="Sector" map={SECTOR_LABEL}
              values={[...new Set(data.map((r) => r.sector))].sort()}
              onChange={(sector) => setFilters({ ...filters, sector })} />
            <FilterSelect value={filters.audience} label="Class year" map={AUDIENCE_LABEL}
              values={[...new Set(data.map((r) => r.audience))].sort()}
              onChange={(audience) => setFilters({ ...filters, audience })} />
            <select className={filters.cool ? "on" : ""} value={filters.cool}
              aria-label="Cooling-off filter"
              onChange={(e) => setFilters({ ...filters, cool: e.target.value })}>
              <option value="">Cooling-off: any</option>
              <option value="restrictive">States a waiting period or cap</option>
              <option value="stated">States any reapplication rule</option>
              <option value="silent">Publishes nothing</option>
              <option value="unverified">Not yet verified</option>
            </select>
            <select className={filters.spon ? "on" : ""} value={filters.spon}
              aria-label="Sponsorship filter"
              onChange={(e) => setFilters({ ...filters, spon: e.target.value })}>
              <option value="">Sponsorship: any</option>
              <option value="stated">States something</option>
              <option value="silent">Publishes nothing</option>
              <option value="unverified">Not yet verified</option>
            </select>
          </div>
          <div className="count">
            {rows.length} of {data.length} programs — select a row for quotes and sources
          </div>
          {rows.length ? (
            rows.map((r) => <ProgramCard key={r.id} r={r} open={rows.length <= 3} />)
          ) : (
            <p className="none">No programs match. Try clearing a filter.</p>
          )}
        </section>
      ) : null}

      {view === "match" && profile ? (
        <section>
          <div className="controls">
            <button className="back" onClick={home}>← Home</button>
            <span className="count">
              Graduating {MNAMES[+profile.grad.slice(5) - 1]} {profile.grad.slice(0, 4)}
            </span>
          </div>
          <p className="sub">
            These groups compare your answers with criteria firms have <strong>stated</strong>,
            as recorded on the dates shown — not a verdict about you, and the firm&apos;s current
            page is always the authority. The largest group is usually the unread one: treat it
            as unread, not unavailable.
          </p>
          <MatchGroup title="Stated criteria that include your answers"
            pill={<Pill state="stated" />} list={groups[1]} />
          <MatchGroup title="Stated criteria that exclude your answers"
            pill={<span className="pill s-warn">stated</span>} list={groups[2]} />
          <MatchGroup title="Not decidable from the parsed record"
            pill={<span className="pill s-unverified">unread</span>} list={groups[3]} />
        </section>
      ) : null}

      <details className="about">
        <summary>About</summary>
        <div className="body">
          <p>
            Every row is a sentence a firm published about who may apply, quoted exactly, with a
            link and the date it was read. Firms that say nothing are recorded as saying nothing.
          </p>
          <p>
            This is a dated snapshot, not advice, and not a verdict about you.{" "}
            <strong>The firm&apos;s own current page is always the authority</strong> — pages get
            rewritten without notice, and several postings recorded here have already been taken
            down since they were read.
          </p>
          <p>
            &ldquo;Publishes nothing&rdquo; is a fact about the public record only: it does not
            mean a firm has no such policy, and silence is neither permission nor prohibition.
            &ldquo;Not yet verified&rdquo; means exactly that — nobody has read the page yet.
          </p>
          <p>
            Every quote rests only on a firm&apos;s own pages or a university career service,
            never on aggregators or test-prep sites.
          </p>
        </div>
      </details>
      <footer>
        <p>
          Generated from <code>data/</code>, one JSON file per firm, validated by{" "}
          <code>tools/validate.py</code>. Quoted material belongs to the firms that wrote it, is
          reproduced for identification and reference, and is not relicensed.
        </p>
      </footer>
    </div>
  );
}

function HomeSearch({ onGo }: { onGo: (q: string) => void }) {
  const [q, setQ] = useState("");
  return (
    <div className="bigsearch">
      <input type="search" value={q} onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") onGo(q.trim()); }}
        placeholder="Search firms, programs, quoted text — try a firm name or “CPT”" />
      <button onClick={() => onGo(q.trim())}>Search</button>
    </div>
  );
}

function FilterSelect({ value, label, map, values, onChange }: {
  value: string; label: string; map: Record<string, string>;
  values: string[]; onChange: (v: string) => void;
}) {
  return (
    <select className={value ? "on" : ""} value={value} aria-label={label}
      onChange={(e) => onChange(e.target.value)}>
      <option value="">{label}: all</option>
      {values.map((v) => <option key={v} value={v}>{map[v] ?? v}</option>)}
    </select>
  );
}

function MatchGroup({ title, pill, list }: {
  title: string; pill: React.ReactNode; list: [Program, Verdict][];
}) {
  if (!list.length) return null;
  return (
    <>
      <div className="matchgroup">
        {title} {pill}{" "}
        <span className="summeta">{list.length} program{list.length === 1 ? "" : "s"}</span>
      </div>
      {list.map(([r, v]) => <ProgramCard key={r.id} r={r} why={v.why} />)}
    </>
  );
}
