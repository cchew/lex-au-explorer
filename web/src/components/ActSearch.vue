<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import type { IndexEntry } from "../types";

const SHORTCUTS = ["privacy-act-1988", "fair-work-act-2009", "corporations-act-2001"];

const emit = defineEmits<{ select: [slug: string] }>();

const index = ref<IndexEntry[]>([]);
const query = ref("");

onMounted(async () => {
  const res = await fetch("/data/index.json");
  index.value = await res.json();
});

const shortcuts = computed(() => index.value.filter((e) => SHORTCUTS.includes(e.slug)));

const matches = computed(() => {
  const q = query.value.trim().toLowerCase();
  if (!q) return [];
  return index.value.filter((e) => e.title.toLowerCase().includes(q)).slice(0, 20);
});

function select(slug: string) {
  emit("select", slug);
  query.value = "";
}
</script>

<template>
  <div class="act-search">
    <label for="act-search-input" class="visually-hidden">Search for an Act</label>
    <input
      id="act-search-input"
      v-model="query"
      type="text"
      placeholder="Search legislation by title..."
      class="search-input"
      autocomplete="off"
    />
    <ul v-if="matches.length" class="results">
      <li
        v-for="m in matches"
        :key="m.slug"
        data-testid="search-option"
        class="result"
        @click="select(m.slug)"
      >{{ m.title }}</li>
    </ul>
    <nav v-else class="shortcuts" aria-label="Shortcut Acts">
      <button
        v-for="s in shortcuts"
        :key="s.slug"
        type="button"
        class="shortcut-btn"
        @click="select(s.slug)"
      >{{ s.title }}</button>
    </nav>
  </div>
</template>

<style scoped>
.search-input {
  width: 100%;
  font-family: var(--font-ui);
  font-size: 0.875rem;
  padding: var(--s-2) var(--s-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-ink);
}

.results { list-style: none; margin-top: var(--s-2); border: 1px solid var(--color-border); border-radius: var(--radius-sm); overflow: hidden; }
.result { padding: var(--s-2) var(--s-3); font-size: 0.8125rem; cursor: pointer; }
.result:hover { background: var(--color-surface-hover); }

.shortcuts { display: flex; flex-wrap: wrap; gap: var(--s-1); margin-top: var(--s-3); }
.shortcut-btn {
  font-family: var(--font-ui);
  font-size: 0.75rem;
  font-weight: 500;
  padding: var(--s-1) var(--s-3);
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-ink-2);
  cursor: pointer;
}
.shortcut-btn:hover { background: var(--color-surface-hover); border-color: var(--color-ink-3); }

.visually-hidden {
  position: absolute; width: 1px; height: 1px; overflow: hidden;
  clip: rect(0, 0, 0, 0); white-space: nowrap;
}
</style>
