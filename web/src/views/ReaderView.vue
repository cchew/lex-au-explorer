<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from "vue";
import { useRoute } from "vue-router";
import ActSearch from "../components/ActSearch.vue";
import ActToc from "../components/ActToc.vue";
import ActHeader from "../components/ActHeader.vue";
import ActPreface from "../components/ActPreface.vue";
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
// Top-level TOC groups (Parts, or Schedules for split_schedules Acts) whose
// section maps have already been fetched and merged into `bundle.value`.
// Revisiting any group in this set must be a genuine no-op -- no re-fetch.
const loadedGroups = ref<Set<string>>(new Set());

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

type OpenSource = "typed" | "shortcut" | "direct";

async function selectAct(slug: string, source: OpenSource = "direct") {
  error.value = null;
  bundle.value = null;
  activeSection.value = null;
  activeTopLevelEid.value = null;
  currentSlug.value = slug;
  loadedGroups.value = new Set();
  try {
    const data = await fetchJson<ActBundle>(`/data/${slug}.json`);
    bundle.value = data;
    track("act_opened", { slug, source });
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
      // Merge, don't replace: a split_by_part Act accumulates Parts as the
      // reader navigates between them, and a split_schedules Act keeps its
      // inline body sections when a Schedule file is pulled in. `visibleSections`
      // still filters to the active top node, so held-but-inactive entries are
      // never mis-rendered. Schedule part files carry only `sections` (no
      // `definitions`); `...undefined` spreads to nothing, so the merge is safe.
      bundle.value = {
        ...bundle.value,
        sections: { ...bundle.value.sections, ...partData.sections },
        definitions: { ...bundle.value.definitions, ...partData.definitions },
      };
    }
    // Reassign (not a bare `.add`) so Vue reactivity fires on the ref.
    loadedGroups.value = new Set(loadedGroups.value).add(partEid);
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

function findTocNode(nodes: TocNode[], eid: string): TocNode | null {
  for (const node of nodes) {
    if (node.eid === eid) return node;
    const found = findTocNode(node.children, eid);
    if (found) return found;
  }
  return null;
}

// Coarse "how far into the Act" bucket for analytics -- a raw eid is
// high-cardinality noise in Umami's event-data view; what's actually
// informative is whether people jump around near the front or read deep.
function sectionPosition(eid: string): "first" | "early" | "mid" | "late" {
  const all = (bundle.value?.toc ?? []).flatMap(flattenLeafEids);
  const i = all.indexOf(eid);
  if (i <= 0 || all.length < 2) return "first";
  const frac = i / (all.length - 1);
  if (frac < 0.34) return "early";
  if (frac < 0.67) return "mid";
  return "late";
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
  const el = document.getElementById(eid);
  if (el) {
    el.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  // Resolved #part-* / #dvs-* links point at a container eid that the DOM
  // renders no `id` for (only sections and provisions get one). Fall back to
  // that container's first descendant leaf section so the reader still moves.
  const node = bundle.value ? findTocNode(bundle.value.toc, eid) : null;
  if (!node) return;
  for (const leafEid of flattenLeafEids(node)) {
    const leafEl = document.getElementById(leafEid);
    if (leafEl) {
      leafEl.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
  }
}

async function selectSection(eid: string) {
  activeSection.value = eid;
  track("toc_navigate", { slug: currentSlug.value, position: sectionPosition(eid) });
  const b = bundle.value;
  if (!b) return;
  const targetGroup = ownerPartEid(eid);

  // (b) The target provision is not in the loaded section map, and this Act
  // splits its content across separate files (`split_by_part` for Parts,
  // `split_schedules` for Schedules). Fetch the owning group's file if it
  // hasn't been loaded, then activate it. This MUST precede the plain-Act
  // path below: a split_schedules Act has `split_by_part === false`, so the
  // old `!split_by_part` early-out would activate the Schedule eid with no
  // sections behind it and render a blank pane.
  //
  // The `split_schedules` disjunct is gated on `targetGroup` being an actual
  // promoted schedule group (the frontend mirror of the build's
  // `_is_schedule_key`: `k.split("__")[0].startswith("schedule-")`). A
  // split_schedules Act keeps its whole body inline, so a click on a bare
  // body container eid (`part-1`, `part-1__dvs-2`) is NOT in `sections` yet
  // must not trigger `loadPart("/data/<slug>/part-1.json")` -- that file does
  // not exist, the fetch 404s, and `loadPart` nulls `bundle.value`, ejecting
  // the reader. Those container clicks fall through to path (a), where
  // `scrollToSection` resolves the container to its first descendant leaf.
  if (
    !(eid in b.sections) &&
    (b.split_by_part || (b.split_schedules && targetGroup.startsWith("schedule-")))
  ) {
    if (!loadedGroups.value.has(targetGroup) && currentSlug.value) {
      await loadPart(currentSlug.value, targetGroup);
    }
    activeTopLevelEid.value = targetGroup;
    await scrollToSection(eid);
    return;
  }

  // (a) The target is already in the section map (a small single-file Act, or
  // an already-loaded Part/Schedule), or it is a container eid that
  // `scrollToSection` resolves to a descendant leaf. Just switch the active
  // group and scroll -- no fetch.
  activeTopLevelEid.value = targetGroup;
  await scrollToSection(eid);
}

// In-app cross-reference navigation: a click on a resolved ref link
// (a.akn-ref[data-eid], emitted by build/stylemap.py) is intercepted and
// routed through selectSection, which loads the owning Part for
// split-by-part Acts and scrolls to the target provision.
function onContentClick(e: MouseEvent) {
  if (!(e.target instanceof HTMLElement)) return;
  const a = e.target.closest("a.akn-ref[data-eid]");
  if (!(a instanceof HTMLElement)) return;
  e.preventDefault();
  const eid = a.dataset.eid;
  if (!eid) return;
  selectSection(eid);
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
      <div class="content-pane" @click="onContentClick">
        <ActHeader :bundle="bundle" />
        <ActPreface :bundle="bundle" />
        <SourceTrustPanel :bundle="bundle" />
        <div v-for="s in visibleSections" :key="s.eid" :id="s.eid" class="section-anchor">
          <SectionContent :section="s.section" :definitions="bundle.definitions" :slug="currentSlug ?? undefined" />
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
