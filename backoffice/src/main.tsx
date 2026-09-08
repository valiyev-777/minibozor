import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Toaster } from "sonner"
import { App } from "./App"
import { SessionProvider } from "./auth/session"
import "./index.css"

/**
 * One query client, and three defaults worth stating.
 *
 * **No retries.** The backend's 4xx answers are sentences somebody is meant
 * to read — "Bu ariza allaqachon tekshirilgan" — and retrying one three times
 * before showing it delays the answer without changing it. A network failure
 * has a retry button on the screen instead, which is the retry somebody
 * actually wants: the one they can see.
 *
 * **Fresh for five seconds.** Shorter than the seller cabinet's ten. These
 * are queues that two or three people work at once, so a batch somebody else
 * has just received should stop being on your list quickly; the seller's own
 * screens have one reader and change when they change them.
 *
 * **Refetch on focus.** A picker leaves the queue open, goes to a shelf and
 * comes back. That is the one place a stale list costs something real, and it
 * is exactly what window focus means here.
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, staleTime: 5_000, refetchOnWindowFocus: true },
  },
})

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <App />
        <Toaster position="top-center" richColors closeButton />
      </SessionProvider>
    </QueryClientProvider>
  </StrictMode>,
)
