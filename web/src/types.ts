/** The record model. Mirrors schema/program.schema.json; the Python
 * validator is the authority, these types are the front end's contract. */

export type RecordState = "stated" | "silent" | "unverified";

interface BaseField {
  state: RecordState;
  tier?: number;
  quote?: string;
  source_url?: string;
  source_status?: string;
  checked?: string;
  summary_note?: string;
  notes?: string;
}

export interface FieldRecord extends BaseField {
  parsed?: ClassYearParse & SponsorshipParse;
}

export interface ClassYearParse {
  graduates_between?: [string, string];
  graduates_from?: string;
  graduates_by?: string;
}

export interface SponsorshipParse {
  sponsors?: boolean;
  cpt_ok?: boolean;
  cpt_refused?: boolean;
  no_future_sponsorship?: boolean;
  us_work_auth_required?: boolean;
}

export interface CoolingOff extends BaseField {
  parsed?: {
    trigger?: string;
    duration_months?: number | null;
    scope?: string;
    resets_allowed?: boolean | null;
    application_cap?: string;
    restrictive?: boolean | null;
  };
}

export interface Source {
  url?: string | null;
  checked?: string;
  status?: string;
  note?: string;
}

export interface Apply {
  url: string;
  kind: "posting" | "program_page" | "careers_hub";
  checked?: string;
  note?: string;
}

export const APPLY_KIND_LABEL: Record<Apply["kind"], string> = {
  posting: "posting",
  program_page: "program page",
  careers_hub: "careers site",
};

export interface Program {
  firm: string;
  sector: string;
  id: string;
  name: string;
  audience: string;
  cycle: string;
  location: string;
  opens: string;
  closes: string;
  source: Source;
  apply?: Apply;
  fields: Record<string, FieldRecord>;
  cooling_off: CoolingOff;
  unfiled: { label?: string; quote: string; source_url?: string }[];
}

// The legal sector values live in schema/program.schema.json and nowhere else.
// This map only supplies display names, which the schema cannot: the browser
// has no way to read the schema, so the keys are hand-written here and then
// checked. `python3 tools/export_json.py` — which CI runs immediately before
// `npm run build` — fails if these keys are not exactly the schema enum, or if
// a label disagrees with the one tools/build.py renders into TABLE.md.
// Adding a sector means: schema first, then this map and tools/build.py.
export const SECTOR_LABEL: Record<string, string> = {
  quant_trading: "Quantitative trading",
  technology: "Technology",
  banking_finance: "Banking & finance",
  consulting: "Consulting",
  law: "Law",
  private_equity: "Private equity",
  venture_capital: "Venture capital",
  asset_management: "Asset management",
  government: "Government",
  other: "Other",
};

export const AUDIENCE_LABEL: Record<string, string> = {
  undergraduate: "Undergraduate",
  sophomore: "Sophomore/2nd year",
  freshman: "First year",
  law_student_jd: "Law student (JD)",
  graduate: "Graduate",
  phd: "PhD",
  paralegal: "Paralegal",
  high_school: "High school",
  all: "All",
  unknown: "Not stated",
};

export const FIELD_LABEL: Record<string, string> = {
  class_year: "Class year",
  sponsorship: "Sponsorship",
  process: "Process",
  compensation: "Compensation",
};
