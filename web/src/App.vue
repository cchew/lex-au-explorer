<script setup lang="ts">
const appVersion = "0.1.0";
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="app-title">
        <h1>lex-au-explorer</h1>
        <p class="subtitle">Browse AU Commonwealth legislation with section-correct hover-definitions</p>
      </div>
      <nav class="top-nav">
        <router-link to="/" class="nav-link">Home</router-link>
        <router-link to="/reader" class="nav-link">Legislation Reader</router-link>
        <a href="https://clause-kit.netlify.app" class="nav-link" target="_blank" rel="noopener">ClauseKit ↗</a>
        <a href="https://act-alike.netlify.app" class="nav-link" target="_blank" rel="noopener">Act Alike ↗</a>
      </nav>
    </header>
    <main>
      <router-view />
    </main>
    <footer class="disclaimer">Not an official government service. Independent showcase of the AU Legislative Intelligence Stack.</footer>
  </div>
</template>

<style scoped>
.app-shell {
  max-width: 1600px;
  margin: 0 auto;
  padding: var(--s-6) var(--s-5);
}

.app-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--s-5);
  margin-bottom: var(--s-5);
  padding-bottom: var(--s-4);
  border-bottom: 1px solid var(--color-border);
  flex-wrap: wrap;
}

.app-header h1 { font-size: 1.125rem; color: var(--color-ink); }
.subtitle { font-size: 0.75rem; color: var(--color-ink-3); margin-top: 0.2rem; }

.top-nav { display: flex; gap: var(--s-4); align-items: center; flex-wrap: wrap; }

.nav-link {
  font-family: var(--font-ui);
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--color-ink-2);
  text-decoration: none;
  padding: var(--s-1) var(--s-2);
  border-radius: var(--radius-sm);
}

.nav-link:hover { background: var(--color-surface-hover); color: var(--color-ink); }
.nav-link.router-link-active { color: var(--color-ink); font-weight: 600; }

.disclaimer {
  margin-top: var(--s-5);
  padding-top: var(--s-4);
  border-top: 1px solid var(--color-border);
  font-size: 0.75rem;
  color: var(--color-ink-3);
}
</style>
