# lex-au-explorer

Public showcase site for the AU Legislative Intelligence Stack. Static
build-time pipeline (Python, `build/`) generates per-Act JSON bundles from
lex-au's corpus and lex-au-graph's definition graph; a Vue 3 + Vite frontend
(`web/`) serves them with no live backend.

## Stack position

Corpus: lex-au (`../lex-au/repo/`) -- AKN 3.0 XML corpus + `corpus/index.json`
Retrieval: lex-au-graph (`../lex-au-graph/repo/`) -- definition graph, installed editable
Applications: this repo -- the first public-facing showcase surface for the stack

## Build pipeline

    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"
    lex-au-explorer-build --corpus-dir ../../lex-au/repo/corpus --graph ../../lex-au-graph/repo/graph.json --out web/data

`build/verification.py` + `lex-au-explorer-verify` do an out-of-band currency
check against legislation.gov.au's OData API, writing `web/verification.json`.
The build reads that file (no network); it does not call the API itself.

## Frontend

    cd web && npm install && npm run dev

## Tests

    pytest                    # build pipeline
    cd web && npm run test    # unit
    cd web && npm run test:e2e  # Playwright, needs data/ built first
