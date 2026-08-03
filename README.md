# lex-au-explorer

Public showcase site for the [AU Legislative Intelligence Stack](https://github.com/cchew/lex-au) --
browse Commonwealth legislation with hover-definitions for defined terms,
correctly scoped to the section you're reading.

Static site, no live backend -- a build-time pipeline joins
[lex-au](https://github.com/cchew/lex-au)'s corpus with
[lex-au-graph](https://github.com/cchew/lex-au-graph)'s definition graph into
per-Act JSON bundles, served from Netlify.

## Deploy

    cd web
    npm run predeploy   # runs the Python build pipeline, writes web/public/data
    npm run build        # vue-tsc + vite build
    netlify deploy --prod

## Versions

- v0.1.0 (in development): shell + legislation reader with hover-definitions.

MIT licensed.
