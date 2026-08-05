<script setup lang="ts">
import type { ActBundle } from "../types";
import { track } from "../lib/analytics";
const props = defineProps<{ bundle: ActBundle }>();

function trackSourceLink(type: "legislation_gov_au" | "raw_xml") {
  track("source_link_click", { type, slug: props.bundle.title_id });
}
</script>

<template>
  <div class="trust-panel">
    <a
      :href="bundle.legislation_url"
      target="_blank"
      rel="noopener"
      class="trust-link"
      @click="trackSourceLink('legislation_gov_au')"
    >
      View on legislation.gov.au ↗
    </a>
    <span class="trust-meta mono">Compilation {{ bundle.comp_id }} — effective {{ bundle.effective_date }}</span>
    <a
      :href="bundle.raw_xml_url"
      target="_blank"
      rel="noopener"
      class="trust-link-secondary"
      @click="trackSourceLink('raw_xml')"
    >Raw AKN XML ↗</a>
  </div>
</template>

<style scoped>
.trust-panel {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--s-3);
  padding: var(--s-3) var(--s-4);
  margin-bottom: var(--s-4);
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
}

.trust-link { color: var(--color-ink); font-weight: 500; text-decoration: none; }
.trust-link:hover { text-decoration: underline; }

.trust-meta { color: var(--color-ink-3); }

.trust-link-secondary { color: var(--color-ink-2); text-decoration: underline; text-underline-offset: 2px; margin-left: auto; }
</style>
