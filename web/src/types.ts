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
  fields: Record<string, FieldRecord>;
  cooling_off: CoolingOff;
  unfiled: { label?: string; quote: string; source_url?: string }[];
}

export const SECTOR_LABEL: Record<string, string> = {
  quant_trading: "Quantitative trading",
  technology: "Technology",
  banking_finance: "Banking & finance",
  consulting: "Consulting",
  law: "Law",
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
