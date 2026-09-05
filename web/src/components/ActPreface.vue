<script setup lang="ts">
import type { ActBundle } from "../types";
defineProps<{ bundle: ActBundle }>();
</script>

<template>
  <div v-if="bundle.preface" class="act-preface">
    <!-- long_title / enacting are pre-escaped HTML strings from the build
         pipeline (build.stylemap._render_inline -> html.escape on every text
         and attribute value -- see stylemap.py's module docstring). v-html
         here follows the same escaping-trust contract SectionContent.vue
         relies on for section.html; no new escaping logic belongs here. -->
    <p class="act-preface-long-title" v-html="bundle.preface.long_title"></p>
    <p
      v-if="bundle.preface.enacting"
      class="act-preface-enacting"
      v-html="bundle.preface.enacting"
    ></p>
  </div>
</template>

<style scoped>
.act-preface { margin-bottom: var(--s-4); }
.act-preface-long-title { font-size: 0.9375rem; line-height: 1.6; color: var(--color-ink); }
.act-preface-enacting { margin-top: var(--s-2); font-size: 0.8125rem; font-style: italic; color: var(--color-ink-2); }
.act-preface :deep(em) { font-style: italic; }
.act-preface :deep(strong) { font-weight: 600; }
</style>
