<script setup lang="ts">
import type { TocNode } from "../types";

defineProps<{ nodes: TocNode[]; activeEid: string | null }>();
const emit = defineEmits<{ select: [eid: string] }>();
</script>

<template>
  <ul class="toc-list">
    <li v-for="node in nodes" :key="node.eid">
      <button
        v-if="node.children.length === 0"
        type="button"
        class="toc-leaf"
        :class="{ active: node.eid === activeEid }"
        @click="emit('select', node.eid)"
      >{{ node.heading }}</button>
      <template v-else>
        <button
          type="button"
          class="toc-branch"
          :class="{ active: node.eid === activeEid }"
          @click="emit('select', node.eid)"
        >{{ node.heading }}</button>
        <ActToc :nodes="node.children" :active-eid="activeEid" @select="emit('select', $event)" />
      </template>
    </li>
  </ul>
</template>

<style scoped>
.toc-list { list-style: none; padding-left: var(--s-3); }
.toc-list:first-of-type { padding-left: 0; }

.toc-branch {
  display: block;
  width: 100%;
  text-align: left;
  font-family: var(--font-ui);
  font-size: 0.75rem;
  font-weight: 600;
  padding: var(--s-1) var(--s-2);
  margin-top: var(--s-2);
  border: none;
  background: none;
  color: var(--color-ink-2);
  cursor: pointer;
  border-radius: var(--radius-sm);
}

.toc-branch:hover { background: var(--color-surface-hover); color: var(--color-ink); }
.toc-branch.active { background: var(--color-surface-active); color: var(--color-ink); }

.toc-leaf {
  display: block;
  width: 100%;
  text-align: left;
  font-family: var(--font-ui);
  font-size: 0.8125rem;
  padding: var(--s-1) var(--s-2);
  border: none;
  background: none;
  color: var(--color-ink-2);
  cursor: pointer;
  border-radius: var(--radius-sm);
}

.toc-leaf:hover { background: var(--color-surface-hover); color: var(--color-ink); }
.toc-leaf.active { background: var(--color-surface-active); color: var(--color-ink); font-weight: 600; }
</style>
