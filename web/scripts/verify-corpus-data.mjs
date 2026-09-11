#!/usr/bin/env node
// web/public/data/ doubles as both the real-corpus staging dir (gitignored,
// written by `npm run predeploy`) and 4 git-tracked E2E fixture files
// (index.json among them, 2 fake Acts). Whichever last touched the
// directory determines what `vite build` bakes into dist/ -- with no
// warning either way. This gate catches the fixture set before it ships.
import { readFileSync } from "node:fs";

export const MIN_ACTS = 500; // real corpus is 3,000+; the E2E fixture set is 2

export function checkCorpus(index) {
  const count = Array.isArray(index) ? index.length : 0;
  return { ok: Array.isArray(index) && count >= MIN_ACTS, count };
}

function main() {
  const indexPath = new URL("../public/data/index.json", import.meta.url);
  let index;
  try {
    index = JSON.parse(readFileSync(indexPath, "utf8"));
  } catch (err) {
    console.error(`Couldn't read web/public/data/index.json: ${err.message}`);
    console.error("Run 'npm run predeploy' to generate the corpus first.");
    process.exit(1);
  }

  const { ok, count } = checkCorpus(index);
  if (!ok) {
    console.error(
      `web/public/data/index.json has ${count} Acts (expected >= ${MIN_ACTS}). ` +
        "This looks like the E2E fixture set, not the real corpus.",
    );
    console.error("Run 'npm run predeploy' first, then build again.");
    process.exit(1);
  }
  console.log(`Corpus check OK: ${count} Acts in web/public/data/index.json.`);
}

if (import.meta.url === `file://${process.argv[1]}`) main();
