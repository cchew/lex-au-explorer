<script setup lang="ts">
const appVersion = __APP_VERSION__;
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="app-title">
        <h1>Lex AU Explorer</h1>
        <p class="subtitle">
          Showcase site and tools for
          <a href="https://github.com/cchew/lex-au" target="_blank" rel="noopener">lex-au</a>,
          <a href="https://github.com/cchew/lex-au-search" target="_blank" rel="noopener">lex-au-search</a>
          and
          <a href="https://github.com/cchew/lex-au-graph" target="_blank" rel="noopener">lex-au-graph</a>.
        </p>
      </div>
      <nav class="top-nav">
        <router-link to="/" class="nav-link">Home</router-link>
        <router-link to="/reader" class="nav-link">Legislation Reader</router-link>
        <a href="https://clause-kit.netlify.app" target="_blank" rel="noopener" class="nav-link">Clause Kit</a>
        <a href="https://act-alike.netlify.app" target="_blank" rel="noopener" class="nav-link">Act Alike</a>
      </nav>
    </header>
    <main>
      <router-view />
    </main>
    <footer class="disclaimer">
      <span>Not an official government service. AI-generated content may be inaccurate.</span>
      <span class="version">v{{ appVersion }}</span>
    </footer>
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
.subtitle a { color: var(--color-ink-2); }
.subtitle a:hover { color: var(--color-ink); }

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
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--s-4);
  margin-top: var(--s-5);
  padding-top: var(--s-4);
  border-top: 1px solid var(--color-border);
  font-size: 0.75rem;
  color: var(--color-ink-3);
}

.disclaimer .version { font-family: var(--font-mono); white-space: nowrap; }
</style>
