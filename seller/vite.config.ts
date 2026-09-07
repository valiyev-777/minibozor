import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwind from "@tailwindcss/vite"
import { fileURLToPath, URL } from "node:url"

export default defineConfig({
  plugins: [react(), tailwind()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    // Its own port, because it is its own application. In production it is its
    // own hostname too — a seller is not staff, and the backoffice's code has
    // no business being downloaded into their browser.
    //
    // The API has to name this origin: it answers with credentials (the
    // refresh cookie rides on them) and a browser refuses a wildcard
    // alongside credentials. So the backend is started with
    // MB_CORS_ORIGINS including this one — see README.
    port: 5174,
    strictPort: true,
  },
})
