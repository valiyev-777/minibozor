// `vitest/config` rather than `vite`: same function, plus the `test` block
// below. The queue is the part of this app that must not regress silently, so
// its tests live in the same config as the build.
import { defineConfig } from "vitest/config"
import react from "@vitejs/plugin-react"
import tailwind from "@tailwindcss/vite"
import { VitePWA } from "vite-plugin-pwa"
import { fileURLToPath, URL } from "node:url"

export default defineConfig({
  plugins: [
    react(),
    tailwind(),
    /**
     * The service worker is not a nicety here — it is half the brief.
     *
     * A courier in a basement who reloads the page, or whose browser drops the
     * tab to reclaim memory and restores it later, must get the application
     * back. Without a precached shell they get Chrome's dinosaur, and the
     * queue sitting in IndexedDB behind it is unreachable until they find
     * signal — which is the exact moment they cannot.
     *
     * `autoUpdate` because there is nobody to press "reload to update": a new
     * version installs itself and takes over on the next navigation. Nothing
     * is lost by that — everything unsent lives in IndexedDB, which a new
     * build opens at the same version and reads unchanged.
     *
     * API calls are deliberately **not** cached. A round that is quietly six
     * hours stale is worse than one that is honestly absent: the app reads its
     * own IndexedDB copy and says when it was taken.
     */
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon-192.png", "icon-512.png", "maskable-512.png"],
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg,png,woff2}"],
        navigateFallback: "index.html",
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [],
      },
      manifest: {
        name: "MiniBozor Kuryer",
        short_name: "Kuryer",
        description: "Kuryer reysi, smena va yig'uv — tarmoqsiz ham ishlaydi",
        lang: "uz",
        start_url: "/",
        scope: "/",
        display: "standalone",
        orientation: "portrait",
        background_color: "#ffffff",
        theme_color: "#0b0f14",
        icons: [
          { src: "icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      devOptions: {
        // So the offline path can be exercised in `npm run dev` rather than
        // only in a production build. This is the feature most likely to be
        // broken by a change and least likely to be noticed.
        enabled: true,
        type: "module",
      },
    }),
  ],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    // Its own port: 5173 is the backoffice, 5174 the seller's cabinet.
    //
    // The API must name this origin — it answers with credentials, and a
    // browser refuses a wildcard alongside them. See README.
    port: 5175,
    strictPort: true,
  },
  test: {
    globals: true,
    environment: "node",
  },
})
