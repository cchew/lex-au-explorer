<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";
import ActSearch from "../components/ActSearch.vue";
import ActToc from "../components/ActToc.vue";
import SectionContent from "../components/SectionContent.vue";
import SourceTrustPanel from "../components/SourceTrustPanel.vue";
import type { ActBundle } from "../types";

const route = useRoute();
const bundle = ref<ActBundle | null>(null);
const activeSection = ref<string | null>(null);
const error = ref<string | null>(null);
const currentSlug = ref<string | null>(null);
const loadedPartEid = ref<string | null>(null);

// Fetch + parse a JSON bundle, distinguishing "not found" from "malformed."
//
// Vite's dev server (and, in production, Netlify's SPA catch-all redirect —
// see netlify.toml, added in Task 14) returns a 200 with the index.html shell
// for any path that doesn't match a real file, including missing /data/*.json
// fixtures. That means `res.ok` is true and `res.json()` fails on the HTML,
// which looks identical to a genuinely corrupt JSON file unless we check
// Content-Type first. A real JSON response has Content-Type: application/json;
// the SPA fallback has Content-Type: text/html. Only the latter means "not
// found" — a JSON-parse failure on a response that *claims* to be JSON is a
// distinct, more concerning bug (truncated/corrupted build output) and should
// not be mislabeled 404.
async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const contentType = res.headers.get("content-type") ?? "";
  const text = await res.text();
  if (!contentType.includes("json")) throw new Error(`HTTP 404`);
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new Error(`Invalid response for ${url}`);
  }
}

async function selectAct(slug: string) {
  error.value = null;
  bundle.value = null;
  activeSection.value = null;
  currentSlug.value = slug;
  loadedPartEid.value = null;
  try {
    const data = await fetchJson<ActBundle>(`/data/${slug}.json`);
    bundle.value = data;
    if (data.split_by_part) {
      const firstPartEid = data.toc[0]?.eid;
      if (firstPartEid) await loadPart(slug, firstPartEid);
    } else {
      activeSection.value = Object.keys(data.sections)[0] ?? null;
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Failed to load Act";
  }
}

async function loadPart(slug: string, partEid: string) {
  try {
    const partData = await fetchJson<ActBundle>(`/data/${slug}/${partEid}.json`);
    if (bundle.value) {
      bundle.value = { ...bundle.value, sections: partData.sections, definitions: partData.definitions };
    }
    loadedPartEid.value = partEid;
    activeSection.value = Object.keys(partData.sections)[0] ?? null;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Failed to load Act";
    bundle.value = null;
  }
}

// AKN eId convention: a section's owning top-level Part is the first
// "__"-delimited segment (e.g. "part-II__dvs-1__sec-6AA" -> "part-II"),
// matching lex-au-graph's containment-prefix derivation in resolver.py.
// The Part node's own eid (e.g. "part-II") has no "__" at all, so it is
// already its own owning Part.
function ownerPartEid(eid: string): string {
  // String.split always returns at least one element; the fallback is
  // unreachable but satisfies noUncheckedIndexedAccess.
  return eid.split("__", 1)[0] ?? eid;
}

async function selectSection(eid: string) {
  if (!bundle.value?.split_by_part) {
    activeSection.value = eid;
    return;
  }
  const targetPart = ownerPartEid(eid);
  if (targetPart === loadedPartEid.value) {
    activeSection.value = eid;
    return;
  }
  if (currentSlug.value) {
    await loadPart(currentSlug.value, targetPart);
    activeSection.value = eid;
  }
}

onMounted(() => {
  const slug = route.params.slug;
  if (typeof slug === "string") selectAct(slug);
});
</script>

<template>
  <div class="reader">
    <ActSearch v-if="!bundle" @select="selectAct" />
    <p v-if="error" class="load-error">{{ error }}</p>
    <div v-if="bundle" class="reader-layout">
      <aside class="toc-sidebar">
        <ActToc :nodes="bundle.toc" :active-eid="activeSection" @select="selectSection" />
      </aside>
      <div class="content-pane">
        <SourceTrustPanel :bundle="bundle" />
        <SectionContent
          v-if="activeSection && bundle.sections[activeSection]"
          :section="bundle.sections[activeSection]!"
          :definitions="bundle.definitions"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.load-error { color: var(--color-ink-2); font-size: 0.875rem; }

.reader-layout { display: grid; grid-template-columns: 260px 1fr; gap: var(--s-5); margin-top: var(--s-4); }

.toc-sidebar {
  border-right: 1px solid var(--color-border);
  padding-right: var(--s-4);
  max-height: calc(100vh - 200px);
  overflow-y: auto;
  position: sticky;
  top: var(--s-4);
}

.content-pane { min-width: 0; }
</style>
