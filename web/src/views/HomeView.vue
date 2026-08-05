<template>
  <div class="home">
    <p class="intro">
      Click the tiles below to access tools and applications. More features will be added over time.
    </p>
    <div class="cards">
      <router-link to="/reader" class="card">
        <h2>Legislation Reader</h2>
        <p>Browse Acts with defined terms highlighted</p>
      </router-link>
      <div class="card card-disabled" aria-disabled="true">
        <h2>Clause Kit (coming soon)</h2>
        <p>LLM-extracted, citation-verified rules-as-code from legislation.</p>
      </div>
      <div class="card card-disabled" aria-disabled="true">
        <h2>Act Alike (coming soon)</h2>
        <p>Compare how a legal term is defined differently across different Acts.</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.intro { max-width: var(--reading-width); font-size: 0.9375rem; color: var(--color-ink-2); margin-bottom: var(--s-6); }

.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: var(--s-4); }

.card {
  display: block;
  padding: var(--s-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  text-decoration: none;
  color: inherit;
  transition: all 0.12s var(--ease-spring);
}

.card:hover { background: var(--color-surface-hover); border-color: var(--color-ink-3); }
.card h2 { font-size: 1rem; margin-bottom: var(--s-2); color: var(--color-ink); }
.card p { font-size: 0.8125rem; color: var(--color-ink-2); }

.card-disabled { cursor: default; opacity: 0.6; }
.card-disabled:hover { background: var(--color-surface); border-color: var(--color-border); }
</style>
