<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from "vue";
import { useRoute } from "vue-router";
import ActSearch from "../components/ActSearch.vue";
import ActToc from "../components/ActToc.vue";
import ActHeader from "../components/ActHeader.vue";
import SectionContent from "../components/SectionContent.vue";
import SourceTrustPanel from "../components/SourceTrustPanel.vue";
import type { ActBundle, SectionEntry, TocNode } from "../types";
import { track } from "../lib/analytics";

const route = useRoute();
const bundle = ref<ActBundle | null>(null);
const activeSection = ref<string | null>(null);
const activeTopLevelEid = ref<string | null>(null);
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
  activeTopLevelEid.value = null;
  currentSlug.value = slug;
  loadedPartEid.value = null;
  try {
    const data = await fetchJson<ActBundle>(`/data/${slug}.json`);
    bundle.value = data;
    track("act_opened", { slug });
    const firstTopLevelEid = data.toc[0]?.eid ?? null;
    if (data.split_by_part) {
      if (firstTopLevelEid) await loadPart(slug, firstTopLevelEid);
    } else {
      activeTopLevelEid.value = firstTopLevelEid;
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Failed to load Act";
    track("act_load_error", { slug, error: error.value });
  }
}

async function loadPart(slug: string, partEid: string) {
  try {
    const partData = await fetchJson<ActBundle>(`/data/${slug}/${partEid}.json`);
    if (bundle.value) {
      bundle.value = { ...bundle.value, sections: partData.sections, definitions: partData.definitions };
    }
    loadedPartEid.value = partEid;
    activeTopLevelEid.value = partEid;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Failed to load Act";
    bundle.value = null;
  }
}

// AKN eId convention: a node's owning top-level TOC group (Part, or the
// node itself for an Act with no Part wrapper) is the first
// "__"-delimited segment (e.g. "part-II__dvs-1__sec-6AA" -> "part-II"),
// matching lex-au-graph's containment-prefix derivation in resolver.py.
// A top-level node's own eid (e.g. "part-II") has no "__" at all, so it
// is already its own group.
function ownerPartEid(eid: string): string {
  // String.split always returns at least one element; the fallback is
  // unreachable but satisfies noUncheckedIndexedAccess.
  return eid.split("__", 1)[0] ?? eid;
}

function flattenLeafEids(node: TocNode): string[] {
  if (node.children.length === 0) return [node.eid];
  const eids: string[] = [];
  for (const child of node.children) eids.push(...flattenLeafEids(child));
  return eids;
}

// All sections belonging to the currently active top-level TOC group, in
// document order -- the content pane shows a whole group at once (e.g.
// every section under "Preliminary") rather than one section in
// isolation, so a sidebar click on a specific section only needs to
// scroll to it, not replace the pane.
const visibleSections = computed((): { eid: string; section: SectionEntry }[] => {
  if (!bundle.value || !activeTopLevelEid.value) return [];
  const topNode = bundle.value.toc.find((n) => n.eid === activeTopLevelEid.value);
  if (!topNode) return [];
  const result: { eid: string; section: SectionEntry }[] = [];
  for (const eid of flattenLeafEids(topNode)) {
    const section = bundle.value.sections[eid];
    if (section) result.push({ eid, section });
  }
  return result;
});

async function scrollToSection(eid: string) {
  await nextTick();
  if (eid === activeTopLevelEid.value) {
    document.querySelector(".content-pane")?.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  document.getElementById(eid)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function selectSection(eid: string) {
  activeSection.value = eid;
  track("toc_navigate", { slug: currentSlug.value, eid });
  const targetGroup = ownerPartEid(eid);
  if (!bundle.value?.split_by_part) {
    activeTopLevelEid.value = targetGroup;
    await scrollToSection(eid);
    return;
  }
  if (targetGroup === loadedPartEid.value) {
    activeTopLevelEid.value = targetGroup;
    await scrollToSection(eid);
    return;
  }
  if (currentSlug.value) {
    await loadPart(currentSlug.value, targetGroup);
    await scrollToSection(eid);
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
        <ActHeader :bundle="bundle" />
        <SourceTrustPanel :bundle="bundle" />
        <div v-for="s in visibleSections" :key="s.eid" :id="s.eid" class="section-anchor">
          <SectionContent :section="s.section" :definitions="bundle.definitions" />
        </div>
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

.section-anchor { scroll-margin-top: var(--s-4); }
.section-anchor + .section-anchor { margin-top: var(--s-5); padding-top: var(--s-5); border-top: 1px solid var(--color-border); }
</style>
