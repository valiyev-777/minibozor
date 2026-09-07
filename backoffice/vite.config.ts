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
    // with the other two panels. Preserved rather than resolved so that a
    // module inside it looks for `clsx` in *this* app's node_modules, which is
    // what makes a symlink cheaper than a workspace package: no workspace, no
    // build step, no version to keep in step. The three builds stay exactly as
    // separate as they were.
    preserveSymlinks: true,
  },
  server: {
    port: 5173,
    // The API is on another origin, so every request is cross-site and carries
    // the refresh cookie. That is why the backend names this origin instead of
    // answering with a wildcard: a browser refuses a wildcard together with
    // credentials. Proxying would hide the problem in dev and leave it in
    // production, so we do not.
    strictPort: true,
  },
})
