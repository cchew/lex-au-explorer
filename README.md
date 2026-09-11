# Lex AU Explorer

Showcase site and tools for [lex-au](https://github.com/cchew/lex-au), [lex-au-search](https://github.com/cchew/lex-au-search) and [lex-au-graph](https://github.com/cchew/lex-au-graph).

Current features:

1. Browse Commonwealth legislation with hover-definitions for defined terms
2. Source-fidelity panel with a build-time currency check against legislation.gov.au ("verified DATE: current compilation" / "a newer compilation now exists" / "repealed since this snapshot")

## Versions

- v0.4.1: defined-term tooltip now anchors near the hovered term and clamps to the viewport, instead of a fixed offset that could render off-screen on long sections. The tooltip stays open when the mouse moves onto it, so the "Open in Act Alike" link is reachable. Generic STOPLIST terms (act, corporation, etc.) no longer highlight at all, not just after their first occurrence per section.
- v0.4.0: defined terms are now highlighted where they are *used* in operative provisions, not only at their point of definition. A browser-runtime pass (`web/src/lib/termHighlight.ts`, gated by a reader toggle) builds a surface-form matcher from the Act's body-used terms and wraps matches per rendered section; when a term is defined more than once in an Act the correct definition is chosen client-side by the resolver's nearest-enclosing-scope rule. One-hop cross-Act pointer definitions ("has the same meaning as in the X Act") are inlined in the tooltip with a "via {Act}" line and resolve to an in-corpus section where the target Act is held (about 59% of pointer defs; the rest show the raw pointer text). Terms defined across a comparable number of Acts get an "Open in Act Alike" deep link. The build replaces the per-section `bundle.definitions` map with a `bundle.terms[]` array carrying every defined term the graph has for the Act (about 29% of Acts carry defined terms; bundle size +1.5%). The lex-au AKN corpus is unchanged.
- v0.3.0: schedules now render in the reader in every shape (numbered clause/subclause units, loose `<paragraph>`/`<table>`/prose runs grouped into synthetic units, clause eId collisions disambiguated with a `~N` suffix, each labelled "Schedule N"). Act long title and enacting words extracted from `<preface>` (heuristic; ~5% of Acts have no extractable long title and show none). Part/Chapter/Division-level introductory text ("head-notes") rendered. Multi-line table cells keep their line breaks (`<br>`). Figures now embed the real image with width/height where the raster exists (the vector-heavy giant tax Acts still placehold where upstream vector-to-raster conversion timed out). Large Acts lazy-load each schedule as a separate file and the reader merges section maps instead of replacing them. Raw AKN XML is served from the `cchew/lex-au` HuggingFace dataset instead of being bundled, reducing `web/dist` from 1.2G to 589M (the 3,076 raw XML copies are no longer written). ref-tally: this run resolved 105,492 of 246,880 ref attempts; the denominator grew by ~100k newly-surfaced schedule cross-references (most unresolved by the suffix-match index), so the ratio is not comparable to prior body-only runs. Residual carve-out: schedule table `<th>` header styling is lost (text intact), schedule Part/Division grouping is flattened (a few labels use the corpus ordinal, not the gazetted number), VML-only images are undetected, and some vector figures are placeheld.
- v0.2.0: rendering split into a semantic IR (`build/ir.py`, `build/parse.py`) and a swappable style map (`build/stylemap.py`; `--style-map` to override, `--emit-ir` to inspect). Fidelity: inline italic/bold preserved as em/strong, `<def>`/`<date>`/`<quantity>` text no longer dropped, Schedule clause/subclause numbering modelled in the semantic IR (schedule bodies are not yet rendered in the reader), tab-wrapped embedded subsection numbers normalised, AKN tables and blockLists rendered, figures shown or placeheld (never blank), cross-references resolved to the target provision in-reader (unambiguous only; ambiguous refs render as plain text and are counted in `ref-tally.json`), example and penalty blocks distinguished, hanging-indent numbering matching the source. DOCX text-parity golden tests added.
- v0.1.4: Umami analytics live (per-environment Website ID via Vite). Adds `search_no_results` and an entry-method (`typed`/`shortcut`/`direct`) on `act_opened`; `definition_hover` now carries the Act slug; `toc_navigate` reports a coarse position bucket instead of a raw eid.
- v0.1.3: `verification.json` records only exceptions (stale/repealed) plus a completed-run date, instead of one entry per Act.
- v0.1.2: source-fidelity panel now carries a build-time currency check against legislation.gov.au, refreshed out-of-band by `lex-au-explorer-verify` (no network access in the build).
- v0.1.1: fixes section rendering to include subsection/paragraph/authorial-note body text, not just a section's own top-level content (52% of Privacy Act 1988 sections were rendering under 30 chars of body text). Reader now shows a whole TOC group's sections at once with scroll-to-anchor navigation, plus an Act key-info header (title, No., year). Rebranded shell, Umami analytics wired (dormant pending a Website ID).
- v0.1.0: shell + legislation reader with hover-definitions, section-scoped hover tooltips, source-fidelity panel. Real corpus build verified (3,078 Acts, zero failures).

## Deploy

Netlify does not run the build: its build container has neither the sibling
`lex-au`/`lex-au-graph` repos nor a Python venv, so the pipeline must be run
locally and the resulting `web/dist/` (with the real corpus baked in via
Vite bundling `public/`) deployed as a pre-built directory.

    cd web
    npm run predeploy          # runs the Python build pipeline, writes web/public/data
    npm run build               # vue-tsc + vite build; bakes public/data into dist/
    netlify deploy --prod --dir=dist   # deploys the pre-built dist/, no remote build

Reader data is served from `web/public/data` (dev) and `web/dist/data` (prod); there is no `web/data/` - if it exists it is a stale hand-run, delete it.

## Source-fidelity verification

`web/verification.json` records the Acts whose corpus copy is behind
legislation.gov.au (or has been repealed), plus the date the last full run
completed (`generated_at`). The build reads that file and bakes a status into
each Act bundle -- listed Acts get the exception, every unlisted Act is
current as of `generated_at`, and if no run has completed (`generated_at`
null) the panel shows nothing. **The build itself never touches the network.**
Refresh the file when you want a fresh "verified" claim in the reader,
typically just before a deploy:

    lex-au-explorer-verify --corpus-dir ../../lex-au/repo/corpus

One bulk "what changed since the corpus was built" query, then a targeted
check per changed Act. Failed per-Act checks keep the previous observation
rather than losing it, and an interrupted run leaves `generated_at` null so a
partial exception list is never treated as authoritative -- either way it is
safe to re-run. `--delay` (default 1.5s) paces calls to the government API.

Known limitation: repeal is only detected for Acts that also had a compilation
change; a repealed Act with no final compilation still reads as current until
the next corpus re-ingest drops it.

## Known limitations

Schedule labels ("Schedule N") number schedules by their position in the
corpus XML, not by the Act's gazetted schedule number. These agree for
almost every Act; a small number of Acts number their gazetted schedules
non-sequentially or omit one, so the corpus ordinal can drift from the
gazette. Fixing this needs a lex-au-side follow-up (carrying the gazetted
number through the corpus rather than deriving it at build time).

## License
MIT
