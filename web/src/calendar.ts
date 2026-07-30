/** Calendar links for parseable open/close dates. Nearly every date in the
 * dataset is a tracker estimate; a reminder built from one must say so or
 * the calendar entry asserts a deadline nobody stated. */
import type { Program } from "./types";

const MONTHS: Record<string, number> = {
  jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5,
  jul: 6, aug: 7, sep: 8, oct: 9, nov: 10, dec: 11,
};

interface When {
  y: number; mo: number; d: number; exact: boolean; est: boolean;
}

function parseWhen(s: string): When | null {
  if (!s) return null;
  const m = s.match(/([A-Za-z]{3,9})\.?\s*(\d{1,2})?,?\s*(20\d\d)/);
  if (!m) return null;
  const mo = MONTHS[m[1].slice(0, 3).toLowerCase()];
  if (mo === undefined) return null;
  return {
    y: +m[3], mo, d: m[2] ? +m[2] : 1, exact: !!m[2],
    est: /[~≈]|expected|anticipated|late|early|mid|per\s|fall|spring/i.test(s),
  };
}

export interface CalLink {
  kind: string;
  raw: string;
  estimated: boolean;
  google: string;
  icsUri: string;
  icsName: string;
}

const pad = (n: number) => String(n).padStart(2, "0");
const icsEscape = (s: string) =>
  s.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");

export function calendarLink(r: Program): CalLink | null {
  const c = parseWhen(r.closes);
  const o = c ? null : parseWhen(r.opens);
  const w = c || o;
  if (!w) return null;
  const kind = c ? "application deadline" : "application window opens";
  const raw = c ? r.closes : r.opens;
  const estimated = w.est || !w.exact;
  const day1 = `${w.y}${pad(w.mo + 1)}${pad(w.d)}`;
  const next = new Date(Date.UTC(w.y, w.mo, w.d + 1));
  const day2 = `${next.getUTCFullYear()}${pad(next.getUTCMonth() + 1)}${pad(next.getUTCDate())}`;
  const title = `${r.firm} — ${r.name}: ${kind}${estimated ? " (estimated)" : ""}`;
  const details =
    `Recorded ${r.source.checked || "undated"} as: "${raw}". ` +
    (estimated ? "This date is an estimate, not a firm-stated deadline. " : "") +
    `Verify on the firm's own page before relying on it.` +
    (r.source.url ? ` ${r.source.url}` : "");
  const google =
    `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(title)}` +
    `&dates=${day1}/${day2}&details=${encodeURIComponent(details)}`;
  const ics = [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//internship-eligibility//EN", "BEGIN:VEVENT",
    `UID:${r.id}@internship-eligibility`, `DTSTART;VALUE=DATE:${day1}`, `DTEND;VALUE=DATE:${day2}`,
    `SUMMARY:${icsEscape(title)}`, `DESCRIPTION:${icsEscape(details)}`, "END:VEVENT", "END:VCALENDAR",
  ].join("\r\n");
  return {
    kind, raw, estimated, google,
    icsUri: "data:text/calendar;charset=utf-8," + encodeURIComponent(ics),
    icsName: `${r.id}.ics`,
  };
}
