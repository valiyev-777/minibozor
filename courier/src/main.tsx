import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Toaster } from "sonner"
import { App } from "./App"
import { SessionProvider } from "./auth/session"
import "./index.css"

/**
 * One query client, tuned for a phone in a stairwell.
 *
 * **No retries.** The backend's 4xx answers are sentences somebody standing at
 * a door is meant to read — "Naqd 240 000 bo'lishi kerak, 230 000 berildi" —
 * and retrying one three times before showing it delays the answer without
 * changing it. A network failure has a retry button on the screen instead.
 *
 * **The round is refetched on focus and on reconnect.** A courier looks at the
 * phone, walks up four flights, and looks again; and the signal comes back in
 * the street. Both are exactly when the list should be asked again — and both
 * are cheap, because the round is one request.
 *
 * There is no offline outbox in this version. The plan says so, and the
 * consequence is stated on the screen rather than hidden: a write that cannot
 * reach the server fails visibly and the courier presses the button again.
 * Queueing writes needs a store and a replay order, and half of one is worse
 * than none — it loses things silently.
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      staleTime: 10_000,
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
    },
  },
})

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <App />
        {/* Bottom, and not top: the top of this screen is where the address
            is, and a toast over an address is a toast over the thing being
            read. */}
        <Toaster position="bottom-center" richColors closeButton />
      </SessionProvider>
    </QueryClientProvider>
  </StrictMode>,
)
