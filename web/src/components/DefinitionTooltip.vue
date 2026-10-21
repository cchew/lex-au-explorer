<script setup lang="ts">
import { computed } from "vue";
import { actAlikeUrl } from "../lib/links";
import { scopeLabel, normaliseDef } from "../lib/scopeLabel";

const props = defineProps<{
  text: string;
  sectionEid: string;
  term?: string;
  actAlike?: boolean;
  scope?: string;
  actWide?: { text: string; eid: string; term: string };
  via?: { actTitle: string; sectionEid?: string; resolved: boolean };
}>();

const href = computed(() => (props.term ? actAlikeUrl(props.term) : ""));
const scopeInfo = computed(() => (props.scope ? scopeLabel(props.scope) : null));
const differs = computed(
  () => !!props.actWide && normaliseDef(props.actWide.text) !== normaliseDef(props.text),
);
</script>

<template>
  <div class="definition-tooltip" role="tooltip">
    <p v-if="via?.resolved" class="definition-via mono">
      via {{ via.actTitle }}<span v-if="via.sectionEid"> &middot; {{ via.sectionEid }}</span>
    </p>
    <p v-else-if="via" class="definition-via">
      defined by reference to {{ via.actTitle || "another Act" }} (not in this corpus)
    </p>
    <template v-if="scopeInfo">
      <p class="definition-text"><strong v-if="term">{{ term }}</strong> {{ text }}</p>
      <p class="definition-scope">
        <span class="definition-pill">Local definition</span>
        <span class="definition-scope-phrase">{{ scopeInfo.phrase }}</span>
      </p>
      <div v-if="actWide && differs" class="definition-actwide">
        <p class="definition-actwide-label">Differs from the Act-wide definition:</p>
        <p class="definition-text">
          <strong v-if="actWide.term">{{ actWide.term }}</strong> {{ actWide.text }}
          <span class="definition-actwide-ref mono">{{ scopeLabel(actWide.eid).text }}</span>
        </p>
      </div>
    </template>
    <template v-else>
      <p class="definition-text">{{ text }}</p>
      <p class="definition-citation mono">{{ sectionEid }}</p>
    </template>
    <a
      v-if="actAlike && term && !scopeInfo"
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
.definition-scope {
  display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2);
  margin-top: var(--s-2); font-size: 0.6875rem; color: var(--color-ink-2);
}
.definition-pill {
  padding: 1px var(--s-2); border-radius: var(--radius-sm);
  background: var(--pill-local-bg); color: var(--pill-local-text);
  font-weight: 600;
}
.definition-actwide {
  margin-top: var(--s-3); padding-top: var(--s-2); border-top: 1px solid var(--color-border);
}
.definition-actwide-label { font-size: 0.6875rem; color: var(--color-ink-2); margin-bottom: var(--s-1); }
.definition-actwide-ref { margin-left: var(--s-2); font-size: 0.6875rem; color: var(--color-ink-3); }
.definition-actalike {
  display: inline-block; margin-top: var(--s-2); font-size: 0.6875rem;
  color: var(--color-link); text-decoration: underline;
}
</style>
