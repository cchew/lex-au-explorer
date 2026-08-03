# lex-au-explorer

Public showcase site for the [AU Legislative Intelligence Stack](https://github.com/cchew/lex-au) --
browse Commonwealth legislation with hover-definitions for defined terms,
correctly scoped to the section you're reading.

Static site, no live backend -- a build-time pipeline joins
[lex-au](https://github.com/cchew/lex-au)'s corpus with
[lex-au-graph](https://github.com/cchew/lex-au-graph)'s definition graph into
per-Act JSON bundles, served from Netlify.

## Deploy

Netlify does not run the build: its build container has neither the sibling
`lex-au`/`lex-au-graph` repos nor a Python venv, so the pipeline must be run
locally and the resulting `web/dist/` (with the real corpus baked in via
Vite bundling `public/`) deployed as a pre-built directory.

    cd web
    npm run predeploy          # runs the Python build pipeline, writes web/public/data
    npm run build               # vue-tsc + vite build; bakes public/data into dist/
    netlify deploy --prod --dir=dist   # deploys the pre-built dist/, no remote build

## Versions

- v0.1.0: shell + legislation reader with hover-definitions, section-scoped hover tooltips, source-fidelity panel. Real corpus build verified (3,078 Acts, zero failures). Not yet deployed.

MIT licensed.
