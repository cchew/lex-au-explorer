<script setup lang="ts">
import { ref } from "vue";
import DefinitionTooltip from "./DefinitionTooltip.vue";
import type { DefinitionEntry } from "../types";

const props = defineProps<{
  section: { heading: string; html: string };
  definitions: Record<string, DefinitionEntry>;
}>();

const activeTerm = ref<string | null>(null);
let showTimer: ReturnType<typeof setTimeout> | null = null;

function onMouseEnter(event: MouseEvent) {
  const target = event.target as HTMLElement;
  const term = target.dataset.term;
  if (!term || !props.definitions[term]) return;
  if (showTimer) clearTimeout(showTimer);
  showTimer = setTimeout(() => { activeTerm.value = term; }, 200);
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
</style>
