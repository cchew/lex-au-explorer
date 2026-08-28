<script setup lang="ts">
import { ref } from "vue";
import DefinitionTooltip from "./DefinitionTooltip.vue";
import type { DefinitionEntry } from "../types";
import { track } from "../lib/analytics";

const props = defineProps<{
  section: { heading: string; html: string };
  definitions: Record<string, DefinitionEntry>;
  slug?: string;
}>();

const activeTerm = ref<string | null>(null);
let showTimer: ReturnType<typeof setTimeout> | null = null;

function onMouseEnter(event: MouseEvent) {
  const target = event.target as HTMLElement;
  const term = target.dataset.term;
  if (!term || !props.definitions[term]) return;
  if (showTimer) clearTimeout(showTimer);
  // Only tracked once the tooltip actually shows (past the 200ms delay),
  // not on every mouseover -- a pass-through hover shouldn't count as a
  // "key interaction."
  showTimer = setTimeout(() => {
    activeTerm.value = term;
    track("definition_hover", props.slug ? { term, slug: props.slug } : { term });
  }, 200);
}

function onMouseLeave() {
  if (showTimer) clearTimeout(showTimer);
  activeTerm.value = null;
}
</script>

<template>
  <div class="section-content">
    <h3>{{ section.heading }}</h3>
    <div
      class="section-html"
      v-html="section.html"
      @mouseover="onMouseEnter"
      @mouseout="onMouseLeave"
    ></div>
    <DefinitionTooltip
      v-if="activeTerm && definitions[activeTerm]"
      :text="definitions[activeTerm]!.text"
      :section-eid="definitions[activeTerm]!.section_eid"
    />
  </div>
</template>

<style scoped>
.section-content { position: relative; max-width: 1200px; }
.section-content h3 { font-size: 1rem; margin-bottom: var(--s-3); color: var(--color-ink); }
.section-html :deep(p) { margin-bottom: var(--s-3); font-size: 0.875rem; line-height: 1.7; color: var(--color-ink); }
.section-html :deep([data-term]) { border-bottom: 1px dashed var(--color-accent-border); cursor: help; }
.section-html :deep(.akn-unit) { padding-left: var(--s-4); border-left: 1px solid var(--color-border); margin-bottom: var(--s-3); }
.section-html :deep(.akn-unit .akn-unit) { margin-bottom: 0; }
.section-html :deep(.akn-num) { font-weight: 500; color: var(--color-ink-2); }
.section-html :deep(.akn-note) { font-size: 0.8125rem; color: var(--color-ink-3); font-style: italic; }
.section-html :deep(.akn-note p) { margin-bottom: var(--s-2); }
</style>
