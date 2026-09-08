export interface IndexEntry {
  title: string;
  slug: string;
  frbr_uri: string;
  split_by_part: boolean;
}

export interface TocNode {
  eid: string;
  heading: string;
  children: TocNode[];
}

export interface SectionEntry {
  heading: string;
  html: string;
}

export interface DefEntry {
  text: string;
  eid: string;
  via?: { actTitle: string; sectionEid?: string; resolved: boolean };
}

export interface TermEntry {
  term: string;
  display: string;
  defs: DefEntry[];
  actAlike?: boolean;
  usedInBody?: boolean;
}

export interface VerificationInfo {
  status: "current" | "stale" | "repealed";
  checked_at: string;
  live_comp_id?: string;
  live_effective_date?: string;
}

export interface PrefaceEntry {
  long_title: string;
  enacting: string;
}

export interface ActBundle {
  frbr_uri: string;
  title: string;
  title_id: string;
  legislation_url: string;
  comp_id: string;
  effective_date: string;
  year: number;
  number: number;
  toc: TocNode[];
  sections: Record<string, SectionEntry>;
  terms: TermEntry[];
  raw_xml_url: string;
  split_by_part: boolean;
  // Emitted by the build only when true (large Acts whose Schedules live in
  // separate /data/<slug>/<schedule-eid>.json files); absent reads as false.
  split_schedules?: boolean;
  verification?: VerificationInfo;
  preface?: PrefaceEntry;
}
