# Lex AU Explorer

Showcase site and tools for [lex-au](https://github.com/cchew/lex-au), [lex-au-search](https://github.com/cchew/lex-au-search) and [lex-au-graph](https://github.com/cchew/lex-au-graph).

Current features:

1. Browse Commonwealth legislation with hover-definitions for defined terms

## Versions

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

## License
MIT
