import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwind from "@tailwindcss/vite"
import { fileURLToPath, URL } from "node:url"

export default defineConfig({
  plugins: [react(), tailwind()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
    // `src/ui` is a symlink to ../../shared/ui — the one design system, shared
    // with the seller's cabinet and the courier's app. Preserved rather than
    // resolved so a module inside it looks for `clsx` in *this* app's
    // node_modules, which is what makes a symlink cheaper than a workspace
    // package: no workspace, no build step, no version to keep in step.
    preserveSymlinks: true,
  },
  server: {
    // The staff application. Its own port here and its own hostname in
    // production: a seller is not staff, and this bundle has no business
    // being downloaded into their browser.
    port: 5173,
    strictPort: true,
  },
})
