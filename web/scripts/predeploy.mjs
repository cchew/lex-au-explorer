#!/usr/bin/env node
// Builds the real-corpus site data into web/public/data.
//
// The old `predeploy` script defaulted to ../../lex-au/repo/corpus and ../../lex-au-graph/repo/graph.json,
// which are untracked local snapshots that go months stale (the 2026-11 deploy had to bypass it). This
// takes the inputs from the environment and refuses to guess:
//
//   LEXAU_CORPUS_DIR     a restored lex-au corpus (index.json + xml/), e.g. from
//                        lex-au/repo/scripts/restore_corpus_from_hf.py
//   LEXAU_GRAPH_JSON     the published lex-au-graph graph.json (cchew/lex-au-graph on Hugging Face)
//   LEXAU_CORPUS_IMAGES  optional; defaults to $LEXAU_CORPUS_DIR/images
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";

export function resolvePredeploy(env, exists) {
  const errors = [];
  const corpusDir = env.LEXAU_CORPUS_DIR;
  const graphJson = env.LEXAU_GRAPH_JSON;
  if (!corpusDir) errors.push("Set LEXAU_CORPUS_DIR to a restored lex-au corpus (index.json + xml/).");
  if (!graphJson) errors.push("Set LEXAU_GRAPH_JSON to the published lex-au-graph graph.json.");
  if (corpusDir) {
    if (!exists(`${corpusDir}/index.json`)) errors.push(`${corpusDir}/index.json not found.`);
    if (!exists(`${corpusDir}/xml`)) errors.push(`${corpusDir}/xml not found.`);
  }
  if (graphJson && !exists(graphJson)) errors.push(`${graphJson} not found.`);
  if (errors.length) return { ok: false, errors };
  return {
    ok: true,
    errors,
    corpusDir,
    graphJson,
    imagesDir: env.LEXAU_CORPUS_IMAGES || `${corpusDir}/images`,
  };
}

function main() {
  const r = resolvePredeploy(process.env, existsSync);
  if (!r.ok) {
    for (const e of r.errors) console.error(e);
    process.exit(1);
  }
  try {
    const stamp = JSON.parse(readFileSync(join(r.corpusDir, ".hf-sync-stamp.json"), "utf8"));
    console.log(`Corpus: ${r.corpusDir} (cchew/lex-au @ ${stamp.remote_sha})`);
  } catch {
    console.log(`Corpus: ${r.corpusDir} (no .hf-sync-stamp.json; check the revision yourself)`);
  }
  console.log(`Graph:  ${r.graphJson}`);
  const repoRoot = resolve(fileURLToPath(new URL("../..", import.meta.url)));
  const out = spawnSync(
    join(repoRoot, ".venv/bin/lex-au-explorer-build"),
    ["--corpus-dir", r.corpusDir, "--graph", r.graphJson, "--out", "web/public/data", "--corpus-images", r.imagesDir],
    { cwd: repoRoot, stdio: "inherit" },
  );
  process.exit(out.status ?? 1);
}

if (import.meta.url === `file://${process.argv[1]}`) main();
