<template>
  <div class="home">
    <p class="intro">
      A public showcase of the AU Legislative Intelligence Stack — an open corpus of Commonwealth
      legislation, a cross-reference definition graph, and tools built on top of both.
    </p>
    <div class="cards">
      <router-link to="/reader" class="card">
        <h2>Legislation Reader</h2>
        <p>Browse Acts with defined terms highlighted — hover to see the definition that applies where you're reading.</p>
      </router-link>
      <a class="card" href="https://clause-kit.netlify.app" target="_blank" rel="noopener">
        <h2>ClauseKit ↗</h2>
        <p>LLM-extracted, citation-verified rules-as-code from Commonwealth legislation.</p>
      </a>
      <a class="card" href="https://act-alike.netlify.app" target="_blank" rel="noopener">
        <h2>Act Alike ↗</h2>
        <p>Compare how a legal term is defined differently across different Acts.</p>
      </a>
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
</style>
