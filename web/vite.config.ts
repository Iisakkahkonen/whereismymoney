import { defineConfig } from "vite";

// Relative base: the site works at any path, including /whereismymoney/ on GitHub Pages.
export default defineConfig({
  base: "./",
  build: { target: "es2022", chunkSizeWarningLimit: 1500 },
});
