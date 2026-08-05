<script setup lang="ts">
import type { ActBundle } from "../types";
defineProps<{ bundle: ActBundle }>();
</script>

<template>
  <div class="act-header">
    <h2>{{ bundle.title }}</h2>
    <div class="act-meta">
      <span class="act-badge">No. {{ bundle.number }} of {{ bundle.year }}</span>
    </div>
  </div>
</template>

<style scoped>
.act-header { margin-bottom: var(--s-3); }
.act-header h2 { font-size: 1.25rem; color: var(--color-ink); margin-bottom: var(--s-2); }
.act-meta { display: flex; gap: var(--s-2); flex-wrap: wrap; }

.act-badge {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  padding: 2px var(--s-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-ink-2);
}
</style>
