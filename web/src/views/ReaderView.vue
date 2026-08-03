<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";
import ActSearch from "../components/ActSearch.vue";
import ActToc from "../components/ActToc.vue";
import SectionContent from "../components/SectionContent.vue";
import SourceTrustPanel from "../components/SourceTrustPanel.vue";
import type { ActBundle } from "../types";

const route = useRoute();
const bundle = ref<ActBundle | null>(null);
const activeSection = ref<string | null>(null);
const error = ref<string | null>(null);

async function selectAct(slug: string) {
  error.value = null;
  bundle.value = null;
  activeSection.value = null;
  try {
    const res = await fetch(`/data/${slug}.json`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = await res.text();
    try {
      const data: ActBundle = JSON.parse(text);
      bundle.value = data;
      if (data.split_by_part) {
        const firstPartEid = data.toc[0]?.eid;
        if (firstPartEid) await loadPart(slug, firstPartEid);
      } else {
        activeSection.value = Object.keys(data.sections)[0] ?? null;
      }
    } catch (jsonError) {
      throw new Error(`HTTP 404`);
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Failed to load Act";
  }
}

async function loadPart(slug: string, partEid: string) {
  const res = await fetch(`/data/${slug}/${partEid}.json`);
  if (!res.ok) {
    error.value = `HTTP ${res.status}`;
    bundle.value = null;
    return;
  }
  const partData: ActBundle = await res.json();
  if (bundle.value) {
    bundle.value = { ...bundle.value, sections: partData.sections, definitions: partData.definitions };
  }
  activeSection.value = Object.keys(partData.sections)[0] ?? null;
}

function selectSection(eid: string) {
  activeSection.value = eid;
}

onMounted(() => {
  const slug = route.params.slug;
  if (typeof slug === "string") selectAct(slug);
});
</script>

<template>
  <div class="reader">
    <ActSearch v-if="!bundle" @select="selectAct" />
    <p v-if="error" class="load-error">{{ error }}</p>
    <div v-if="bundle" class="reader-layout">
      <aside class="toc-sidebar">
        <ActToc :nodes="bundle.toc" :active-eid="activeSection" @select="selectSection" />
      </aside>
      <div class="content-pane">
        <SourceTrustPanel :bundle="bundle" />
        <SectionContent
          v-if="activeSection && bundle.sections[activeSection]"
          :section="bundle.sections[activeSection]!"
          :definitions="bundle.definitions"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.load-error { color: var(--color-ink-2); font-size: 0.875rem; }

.reader-layout { display: grid; grid-template-columns: 260px 1fr; gap: var(--s-5); margin-top: var(--s-4); }

.toc-sidebar {
  border-right: 1px solid var(--color-border);
  padding-right: var(--s-4);
  max-height: calc(100vh - 200px);
  overflow-y: auto;
  position: sticky;
  top: var(--s-4);
}

.content-pane { min-width: 0; }
</style>
