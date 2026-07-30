/** The screener. Ported verbatim from the vanilla implementation; the rules
 * are binding (DESIGN.md): three groups, stated criteria only, never the
 * words "eligible", "qualified" or "fit". Group 3 — not decidable — is
 * usually the largest and its size is shown, not hidden. */
import type { Program } from "./types";

export interface Profile {
  /** YYYY-MM expected graduation */
  grad: string;
  auth: "citizen" | "cpt" | "sponsor";
}

export interface Verdict {
  group: 1 | 2 | 3;
  why: string[];
}

export function judge(r: Program, me: Profile): Verdict {
  const inc: string[] = [];
  const exc: string[] = [];

  const cy = r.fields.class_year?.parsed ?? {};
  if (cy.graduates_between) {
    const [a, b] = cy.graduates_between;
    (me.grad >= a && me.grad <= b ? inc : exc).push(
      `stated graduation window ${a} to ${b}`,
    );
  } else if (cy.graduates_from) {
    (me.grad >= cy.graduates_from ? inc : exc).push(
      `stated graduation ${cy.graduates_from} or later`,
    );
  } else if (cy.graduates_by) {
    (me.grad <= cy.graduates_by ? inc : exc).push(
      `stated graduation by ${cy.graduates_by}`,
    );
  }

  const sp = r.fields.sponsorship?.parsed ?? {};
  if (me.auth !== "citizen") {
    if (sp.no_future_sponsorship)
      exc.push("requires authorization without sponsorship now or in the future");
    if (me.auth === "sponsor") {
      if (sp.sponsors === false) exc.push("states it does not sponsor this role");
      if (sp.us_work_auth_required && sp.sponsors !== true)
        exc.push("requires existing U.S. work authorization");
    }
    if (me.auth === "cpt" && sp.cpt_refused)
      exc.push("states it will not support CPT or OPT");
    if (me.auth === "cpt" && sp.cpt_ok)
      inc.push("states F-1 students on CPT/OPT are accepted");
    if (sp.sponsors === true) inc.push("states sponsorship is supported");
  }

  if (exc.length) return { group: 2, why: exc };
  if (inc.length) return { group: 1, why: inc };
  return { group: 3, why: [] };
}
