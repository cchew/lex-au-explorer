import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { readFileSync } from "node:fs";

const pkgUrl = import.meta.url;
const pkg = JSON.parse(readFileSync(new URL("./package.json", pkgUrl), "utf8"));

export default defineConfig({
  plugins: [vue()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  test: {
    environment: "happy-dom",
    globals: true,
    exclude: ["**/e2e.spec.*", "**/a11y.spec.*", "**/node_modules/**"],
  },
});
