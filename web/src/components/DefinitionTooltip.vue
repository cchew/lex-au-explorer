<script setup lang="ts">
import { computed } from "vue";
import { actAlikeUrl } from "../lib/links";

const props = defineProps<{
  text: string;
  sectionEid: string;
  term?: string;
  actAlike?: boolean;
  via?: { actTitle: string; sectionEid?: string; resolved: boolean };
}>();

const href = computed(() => (props.term ? actAlikeUrl(props.term) : ""));
</script>

<template>
  <div class="definition-tooltip" role="tooltip">
    <p v-if="via?.resolved" class="definition-via mono">
      via {{ via.actTitle }}<span v-if="via.sectionEid"> &middot; {{ via.sectionEid }}</span>
    </p>
    <p v-else-if="via" class="definition-via">
      defined by reference to {{ via.actTitle || "another Act" }} (not in this corpus)
    </p>
    <p class="definition-text">{{ text }}</p>
    <p class="definition-citation mono">{{ sectionEid }}</p>
    <a
      v-if="actAlike && term"
      class="definition-actalike"
      :href="href"
      target="_blank"
      rel="noopener"
    >Open in Act Alike &#8599;</a>
  </div>
</template>

<style scoped>
.definition-tooltip {
  max-width: 320px;
  padding: var(--s-3);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-md);
}

.definition-text { font-size: 0.8125rem; color: var(--color-ink); line-height: 1.5; }
.definition-via { font-size: 0.6875rem; color: var(--color-ink-3); margin-bottom: var(--s-2); }
.definition-citation { margin-top: var(--s-2); font-size: 0.6875rem; color: var(--color-ink-3); }
.definition-actalike {
  display: inline-block; margin-top: var(--s-2); font-size: 0.6875rem;
  color: var(--color-link); text-decoration: underline;
}
</style>
