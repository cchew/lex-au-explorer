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

export interface DefinitionEntry {
  text: string;
  section_eid: string;
}

export interface ActBundle {
  frbr_uri: string;
  title: string;
  title_id: string;
  legislation_url: string;
  comp_id: string;
  effective_date: string;
  toc: TocNode[];
  sections: Record<string, SectionEntry>;
  definitions: Record<string, DefinitionEntry>;
  raw_xml_url: string;
  split_by_part: boolean;
}
