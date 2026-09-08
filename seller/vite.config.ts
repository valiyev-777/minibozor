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
    // Its own port, because it is its own application. In production it is its
    // own hostname too — a seller is not staff, and the backoffice's code has
    // no business being downloaded into their browser.
    //
    // The API has to name this origin: it answers with credentials (the
    // refresh cookie rides on them) and a browser refuses a wildcard
    // alongside credentials. `dev.sh` starts the backend with
    // MB_CORS_ORIGINS including this one.
    port: 5174,
    strictPort: true,
  },
})
