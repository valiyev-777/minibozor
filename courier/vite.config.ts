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
    // `src/ui` is a symlink to ../../shared/ui — see the other two panels.
    preserveSymlinks: true,
  },
  server: {
    port: 5175,
    strictPort: true,
    // A courier's phone is not this laptop, so the dev server has to answer on
    // the network address as well as on localhost. `dev.sh` does not pass
    // --host; `npm run dev -- --host` is the way to put it on a handset.
    host: true,
  },
})
