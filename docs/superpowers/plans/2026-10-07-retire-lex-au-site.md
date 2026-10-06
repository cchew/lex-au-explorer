# Retire lex-au.netlify.app in favour of lex-au-explorer

Goal: lex-au.netlify.app (body-only renderer: no schedules, preface, tables, figures) becomes a redirect stub to lex-au-explorer. Old per-Act URLs and `source.xml` links keep working.

## Feature gap (verified 2026-10-07)

Explorer already has: raw XML link (SourceTrustPanel, HF-hosted), legislation.gov.au link, search, TOC, preface, schedules, tables, figures, term tooltips.
Only gap: FRBR Work URI not displayed (bundle already carries `frbr_uri`).

## Changes

### A. lex-au-explorer (frontend only)
1. ActHeader: show `FRBR /akn/au/act/{year}/{number}` as a mono badge beside "No. X of Y". Test in ActHeader.spec.ts.
2. Version 0.4.6 (package.json, README versions), tag v0.4.6.
3. Deploy: `npm run predeploy` (real corpus; data dir currently holds fixtures) then `npm run build` then `netlify deploy --prod --dir=dist`. Restore 4 fixture files after.

### B. lex-au (redirect stub)
1. `scripts/gen_redirects.py`: reads corpus index, reuses `_assign_site_paths`, writes `redirects/_redirects` + `redirects/index.html`.
   - `{site_path}` -> `https://lex-au-explorer.netlify.app/reader/{slug}` 301
   - `{site_path}source.xml` -> HF `xml/{slug}.xml` 301
   - `/akn/*` and `/*` -> explorer home 301 (after specific rules; first match wins)
   - slugs percent-encoded; slugs absent from the explorer index fall through to the catch-all
2. Remove "Build static site" + "Deploy to Netlify" steps and netlify inputs from publish-corpus action and both workflows. REQUIRED: otherwise the next corpus change overwrites the stub with the old body-only site.
3. README + hf-readme: point to the explorer; mark `lexau site` as local-preview only.
4. Deploy `redirects/` once to the existing Netlify site (id in `.netlify/state.json`).

## Review: risks and checks

| Risk | Mitigation / check |
|---|---|
| CI redeploys old site over the stub | B2, grep workflows for `netlify` afterwards |
| Redirect target Act missing from explorer | gen script filters on explorer `index.json`; report count |
| Rule order (catch-all shadows specifics) | specifics first; curl-test 5 samples incl. a disambiguated path, a parenthesised slug, source.xml |
| Large `_redirects` file | curl-test after deploy; rollback = redeploy `site/` |
| Explorer deploy ships fixture data (v0.4.1 incident) | `npm run build` size gate; confirm 3,076 Acts live after deploy |
| Old `#eId` anchors lost | accepted; explorer has no equivalent anchor scheme |
| Search engines / links | 301 permanent |

## UX review

- FRBR badge: same style as the existing No./year badge, wraps in the flex row, selectable text, `title` explains the term. Short string (never disambiguated), so no mobile overflow.
- Old-URL visitors land on the right Act in the reader; unknown paths land on explorer home, not a 404.
- Verify by Playwright screenshot at desktop and 390px width before deploy.
