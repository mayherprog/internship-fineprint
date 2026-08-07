import type { FieldRecord, Program } from "./types";
import { APPLY_KIND_LABEL, AUDIENCE_LABEL, FIELD_LABEL, SECTOR_LABEL } from "./types";
import { calendarLink } from "./calendar";

const STATE_LABEL: Record<string, string> = {
  stated: "stated",
  silent: "publishes nothing",
  unverified: "unverified",
};

export function Pill({ state, k }: { state: string; k?: string }) {
  return (
    <span className={`pill s-${state}`}>
      {k ? <span className="k">{k}: </span> : null}
      {STATE_LABEL[state] ?? state}
    </span>
  );
}

function SrcLink({ url, status }: { url?: string; status?: string }) {
  if (url)
    return (
      <a href={url} rel="noopener nofollow">
        source
      </a>
    );
  if (status === "url_pending") return <span className="pill s-warn">source link missing</span>;
  if (status === "blocked") return <span className="pill s-warn">page blocks automated reads</span>;
  if (status === "dead") return <span className="pill s-warn">link dead</span>;
  return null;
}

function FieldBox({ name, f }: { name: string; f: FieldRecord }) {
  let body;
  if (f.state === "stated") body = <div className="q quote">&ldquo;{f.quote}&rdquo;</div>;
  else if (f.state === "silent")
    body = <div className="none">The firm publishes nothing on this.</div>;
  else
    body = (
      <div className="none">
        {f.summary_note
          ? `${f.summary_note} — unverified, not the firm's wording`
          : "Not yet verified."}
      </div>
    );
  return (
    <div className="f">
      <div className="lbl">
        {FIELD_LABEL[name] ?? name}
        <Pill state={f.state} />
      </div>
      {body}
      <div className="notes">
        {f.checked ? `checked ${f.checked}` : ""}
        {f.tier && f.state === "stated" ? <> · tier {f.tier}</> : null}
        {f.state === "stated" ? (
          <>
            {" "}
            · <SrcLink url={f.source_url} status={f.source_status} />
          </>
        ) : null}
      </div>
    </div>
  );
}

function CoolingOffBlock({ r }: { r: Program }) {
  const co = r.cooling_off;
  const has = co.state === "stated";
  const p = co.parsed ?? {};
  const bits: string[] = [];
  // Parsed labels appear ONLY when the firm states an actual constraint;
  // attaching "triggered by rejection" to a permissive sentence would imply
  // a lockout the firm never stated. The quote is on screen and always wins.
  if (has && p.restrictive === true) {
    if (p.duration_months) bits.push(`${p.duration_months} months`);
    if (p.trigger && p.trigger !== "unknown") bits.push(`triggered by ${p.trigger.replace(/_/g, " ")}`);
    if (p.scope && p.scope !== "unknown") bits.push(`scope: ${p.scope.replace(/_/g, " ")}`);
    if (p.application_cap) bits.push(`cap: ${p.application_cap}`);
  }
  return (
    <div className={`cool${has ? " has" : ""}`}>
      <div className="lbl">
        Cooling-off / reapplying <Pill state={co.state} />
      </div>
      {has ? (
        <div className="q quote">&ldquo;{co.quote}&rdquo;</div>
      ) : co.state === "silent" ? (
        <div className="none">
          The firm publishes no reapplication or assessment-retry rule on the page checked. That
          is a fact about the public record, not proof no rule exists.
        </div>
      ) : (
        <div className="none">Not yet verified.</div>
      )}
      {bits.length ? <div className="notes">{bits.join(" · ")}</div> : null}
      {co.notes ? <div className="notes">{co.notes}</div> : null}
      <div className="notes">
        {co.checked ? <>checked {co.checked} · </> : null}
        {has ? <SrcLink url={co.source_url} status={co.source_status} /> : null}
      </div>
    </div>
  );
}

function CalendarLine({ r }: { r: Program }) {
  const cal = calendarLink(r);
  if (!cal) return null;
  return (
    <div className="notes">
      {cal.kind}: {cal.raw}
      {cal.estimated ? (
        <>
          {" "}
          <span className="pill s-warn">estimate</span>
        </>
      ) : null}{" "}
      · <a href={cal.google} rel="noopener">add to Google Calendar</a> ·{" "}
      <a href={cal.icsUri} download={cal.icsName}>download .ics</a>
    </div>
  );
}

export function ProgramCard({ r, why, open }: { r: Program; why?: string[]; open?: boolean }) {
  const cy = r.fields.class_year ?? { state: "unverified" as const };
  const sp = r.fields.sponsorship ?? { state: "unverified" as const };
  const meta = [
    r.cycle,
    r.location,
    AUDIENCE_LABEL[r.audience] ?? r.audience,
    r.opens ? `opens: ${r.opens}` : "",
    r.closes ? `closes: ${r.closes}` : "",
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <details className="card" open={open}>
      <summary>
        <span className="sumtitle">
          <span className="firm">{r.firm}</span> — {r.name}
        </span>{" "}
        <Pill state={cy.state} k="Class year" /> <Pill state={sp.state} k="Sponsorship" />
        {r.cooling_off.state === "stated" ? <span className="pill s-warn">Reapply rule</span> : null}
        <span className="summeta">
          {AUDIENCE_LABEL[r.audience] ?? ""}
          {r.cycle && r.cycle.length <= 28 ? ` · ${r.cycle}` : ""}
        </span>
        {why && why.length ? <span className="why">{why.join("; ")}</span> : null}
      </summary>
      <div className="drawer">
        <p className="meta">
          {meta} · {SECTOR_LABEL[r.sector] ?? r.sector} ·{" "}
          <SrcLink url={r.source.url ?? undefined} status={r.source.status} />
          {r.source.checked ? ` · read ${r.source.checked}` : ""}
          {r.apply?.url ? (
            <>
              {" · "}
              <a href={r.apply.url} rel="noopener nofollow">
                apply ({APPLY_KIND_LABEL[r.apply.kind] ?? "link"})
              </a>
            </>
          ) : null}
        </p>
        {r.source.note ? <p className="meta">{r.source.note}</p> : null}
        <CalendarLine r={r} />
        <div className="grid">
          {Object.entries(r.fields).map(([name, f]) => (
            <FieldBox key={name} name={name} f={f} />
          ))}
        </div>
        <CoolingOffBlock r={r} />
        {(r.unfiled ?? []).map((u, i) => (
          <div className="notes" key={i}>
            {u.label ? `${u.label}: ` : ""}&ldquo;{u.quote}&rdquo;
          </div>
        ))}
      </div>
    </details>
  );
}
