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
    port: 5173,
    // The API is on another origin, so every request is cross-site and carries
    // the refresh cookie. That is why the backend names this origin instead of
    // answering with a wildcard: a browser refuses a wildcard together with
    // credentials. Proxying would hide the problem in dev and leave it in
    // production, so we do not.
    strictPort: true,
  },
})
