import path from "node:path"

import tailwind from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
import { VitePWA } from "vite-plugin-pwa"

// One app for three roles, on the port the three panels used to share between
// them. `VITE_API_URL` comes from the environment and is never compiled in:
// the API moves between a laptop, a phone on the same wifi and a server, and a
// hostname baked into a bundle is a rebuild every time it does.
export default defineConfig({
  plugins: [
    react(),
    tailwind(),
    VitePWA({
      registerType: "autoUpdate",
      // Installable because half of this app is used standing up, in a
      // warehouse, on a phone — a browser chrome and an address bar are two
      // rows of a screen that wants them for a pick list.
      manifest: {
        name: "Mini Bozor",
        short_name: "Mini Bozor",
        lang: "uz",
        start_url: "/",
        display: "standalone",
        background_color: "#ffffff",
        theme_color: "#0e7bf5",
        icons: [
          { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
        ],
      },
    }),
  ],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    strictPort: true,
    // `shared/theme.css` lives above this app's root, which is the point of
    // it: one file, imported by path, rather than a package with a build step
    // whose only job is to move it around.
    fs: { allow: [".."] },
  },
})
