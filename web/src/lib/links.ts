// Act Alike deep link. Scheme + base confirmed against term-comparison's
// permalink.ts (`termToPath`, `TERM_PATH_RE`): the frontend route is a path
// segment `/term/<term>`, not a `?term=` query param.
export const ACT_ALIKE_BASE = "https://act-alike.netlify.app";

export function actAlikeUrl(displayTerm: string): string {
  return `${ACT_ALIKE_BASE}/term/${encodeURIComponent(displayTerm)}`;
}
