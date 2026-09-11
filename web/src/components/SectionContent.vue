<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from "vue";
import DefinitionTooltip from "./DefinitionTooltip.vue";
import type { TermEntry, DefEntry } from "../types";
import type { Matcher } from "../lib/termHighlight";
import { highlightTerms, unhighlightTerms, resolveDef, STOPLIST } from "../lib/termHighlight";
import { track } from "../lib/analytics";

const props = defineProps<{
  section: { heading: string; html: string };
  matcher: Matcher | null;
  termIndex: Map<string, TermEntry>;
  sectionEid: string;
  highlightEnabled: boolean;
  slug?: string;
}>();

const rootRef = ref<HTMLElement | null>(null);
const activeDef = ref<DefEntry | null>(null);
const activeEntry = ref<TermEntry | null>(null);
let showTimer: ReturnType<typeof setTimeout> | null = null;

function applyHighlight() {
  const root = rootRef.value;
  if (!root) return;
  unhighlightTerms(root);
  if (props.highlightEnabled && props.matcher)
    highlightTerms(root, props.matcher, props.sectionEid, { stoplist: STOPLIST });
}

onMounted(() => nextTick(applyHighlight));
watch(
  [() => props.section.html, () => props.highlightEnabled, () => props.matcher],
  () => nextTick(applyHighlight),
);

function pickDef(entry: TermEntry, defEid: string | undefined): DefEntry | undefined {
  if (defEid) return entry.defs.find((d) => d.eid === defEid);
  return resolveDef(entry, props.sectionEid) ?? entry.defs[0];
}

function onActivate(event: Event) {
  const target = event.target as HTMLElement;
  if (!target?.dataset?.term) return;
  const entry = props.termIndex.get(target.dataset.term);
  if (!entry) return;
  if (!target.getAttribute("role")) {
    target.tabIndex = 0;
    target.setAttribute("role", "button");
    target.setAttribute("aria-label", `defined term: ${entry.display}`);
  }
  const defEid = target.dataset.defEid;
  const def = pickDef(entry, defEid);
  if (!def) return;
  if (showTimer) clearTimeout(showTimer);
  // Only tracked once the tooltip actually shows (past the 200ms delay),
  // not on every mouseover -- a pass-through hover shouldn't count as a
  // "key interaction."
  showTimer = setTimeout(() => {
    activeDef.value = def;
    activeEntry.value = entry;
    track("definition_hover", {
      term: entry.term,
      context: defEid ? "body" : "definitions",
      ...(props.slug ? { slug: props.slug } : {}),
    });
  }, 200);
}

function onDismiss() {
  if (showTimer) clearTimeout(showTimer);
  activeDef.value = null;
  activeEntry.value = null;
}

onUnmounted(() => {
  if (showTimer) clearTimeout(showTimer);
});
</script>

<template>
  <div class="section-content">
    <h3>{{ section.heading }}</h3>
    <div
      ref="rootRef"
      class="section-html"
      v-html="section.html"
      @mouseover="onActivate"
      @mouseout="onDismiss"
      @focusin="onActivate"
      @focusout="onDismiss"
    ></div>
    <DefinitionTooltip
      v-if="activeDef"
      :text="activeDef.text"
      :section-eid="activeDef.eid"
      :via="activeDef.via"
      :term="activeEntry?.display"
      :act-alike="activeEntry?.actAlike"
    />
  </div>
</template>

<style scoped>
.section-content { position: relative; max-width: 1200px; }
.section-content h3 { font-size: 1rem; margin-bottom: var(--s-3); color: var(--color-ink); }
.section-html :deep(p) { margin-bottom: var(--s-3); font-size: 0.875rem; line-height: 1.7; color: var(--color-ink); }
.section-html :deep([data-term]) { border-bottom: 1px dashed var(--color-accent-border); cursor: help; }
.section-html :deep([data-term]:focus-visible) { outline: 2px solid var(--color-link); outline-offset: 2px; }

/* Provision levels: CSS-grid hanging indent -- the num sits in a left
   gutter column, the body in the second column. The indent step grows
   one --s-4 per nesting level. */
.section-html :deep(.akn-subsection),
.section-html :deep(.akn-paragraph),
.section-html :deep(.akn-subparagraph),
.section-html :deep(.akn-clause),
.section-html :deep(.akn-subclause) {
  display: grid;
  grid-template-columns: minmax(2.75rem, max-content) 1fr;
  column-gap: var(--s-2);
  margin: var(--s-2) 0;
}
.section-html :deep(.akn-paragraph)    { margin-left: var(--s-4); }
.section-html :deep(.akn-subparagraph) { margin-left: calc(var(--s-4) * 2); }
.section-html :deep(.akn-subclause)    { margin-left: var(--s-4); }
.section-html :deep(.akn-num) {
  font-variant-numeric: tabular-nums;
  color: var(--color-ink-2);
  text-align: left;
}
.section-html :deep(.akn-body > p:first-child) { margin-top: 0; }
.section-html :deep(.akn-provision-heading) {
  font-weight: 600;
  color: var(--color-ink);
  margin-right: 0.35rem;
}

/* blockList: chapeau paragraph plus grid items, indented like a paragraph. */
.section-html :deep(.akn-list) { margin: var(--s-2) 0 var(--s-2) var(--s-4); }
.section-html :deep(.akn-intro) { margin: var(--s-2) 0; }
.section-html :deep(.akn-item) {
  display: grid;
  grid-template-columns: minmax(2.75rem, max-content) 1fr;
  column-gap: var(--s-2);
  margin: var(--s-2) 0;
}

.section-html :deep(em) { font-style: italic; }
.section-html :deep(strong) { font-weight: 600; }

/* <date>/<quantity> text is preserved but carries no visual treatment. */
.section-html :deep(.akn-date),
.section-html :deep(.akn-quantity) { color: inherit; }

/* Cross-references: resolved refs are links; unresolved refs render as
   plain text -- no underline, default cursor. */
.section-html :deep(.akn-ref) {
  color: var(--color-link);
  text-decoration: underline;
  text-underline-offset: 2px;
  cursor: pointer;
}
.section-html :deep(.akn-ref-unresolved) {
  color: var(--color-ink);
  text-decoration: none;
  cursor: default;
}

/* Note: the "Note:" label comes from the HTML (akn-note-label span from the
   Task 4 parser split), not a CSS ::before -- source paragraphs already
   begin "Note:" / "Note 1:", so ::before would double it. */
.section-html :deep(.akn-notetext) {
  display: flow-root;
  font-size: 0.8125rem;
  color: var(--color-ink-2);
  margin: var(--s-2) 0 var(--s-2) var(--s-4);
}
.section-html :deep(.akn-note-label) {
  float: left;
  margin-right: 0.35rem;
  font-weight: 600;
  color: var(--color-ink-2);
}

/* Example: shaded box with a left rule. */
.section-html :deep(.akn-exampletext) {
  background: var(--color-surface-hover);
  border-left: 2px solid var(--color-accent-border);
  padding: var(--s-3);
  margin: var(--s-3) 0;
  font-size: 0.8125rem;
}
.section-html :deep(.akn-exampletext p:last-child) { margin-bottom: 0; }

/* Penalty: its own line, not body-indented. */
.section-html :deep(.akn-penaltytext) {
  margin: var(--s-3) 0;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--color-ink);
}

/* Tables: bordered, shaded header row; a wide table scrolls inside its own
   wrapper rather than pushing the page sideways. The scroll lives on the
   wrapper so the <table> can keep display:table + border-collapse (both inert
   under display:block, which doubled every border). */
.section-html :deep(.akn-table-scroll) {
  overflow-x: auto;
  margin: var(--s-3) 0;
}
.section-html :deep(.akn-table) {
  display: table;
  border-collapse: collapse;
  font-size: 0.8125rem;
  width: 100%;
}
.section-html :deep(.akn-table th),
.section-html :deep(.akn-table td) {
  border: 1px solid var(--color-border);
  padding: var(--s-2) var(--s-3);
  text-align: left;
  vertical-align: top;
}
.section-html :deep(.akn-table thead th) {
  background: var(--color-surface-hover);
  font-weight: 600;
}

/* Figures: a real image fits the column; a missing asset is placeheld with
   a muted dashed box, never left blank. */
.section-html :deep(figure) { margin: var(--s-3) 0; }
.section-html :deep(figure img) { max-width: 100%; height: auto; }
.section-html :deep(.akn-figure-missing) {
  border: 1px dashed var(--color-border);
  padding: var(--s-3);
  color: var(--color-ink-3);
  font-size: 0.8125rem;
  font-style: italic;
}
</style>
