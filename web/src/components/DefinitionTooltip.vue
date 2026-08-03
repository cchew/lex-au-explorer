<script setup lang="ts">
defineProps<{ text: string; sectionEid: string }>();
</script>

<template>
  <div class="definition-tooltip" role="tooltip">
    <p class="definition-text">{{ text }}</p>
    <p class="definition-citation mono">{{ sectionEid }}</p>
  </div>
</template>

<style scoped>
.definition-tooltip {
  position: absolute;
  z-index: 20;
  max-width: 320px;
  padding: var(--s-3);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-md);
}

.definition-text { font-size: 0.8125rem; color: var(--color-ink); line-height: 1.5; }
.definition-citation { margin-top: var(--s-2); font-size: 0.6875rem; color: var(--color-ink-3); }
</style>
