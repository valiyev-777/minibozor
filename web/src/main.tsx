import {
  MutationCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query"
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router-dom"
import { toast } from "sonner"

import { App } from "@/App"
import { Toaster } from "@/components/toaster"
import { SessionProvider } from "@/lib/session"
import { ThemeProvider } from "@/lib/theme"
import "./index.css"

/**
 * Every write answers, and it answers from here.
 *
 * A refusal is worth saying **always** — there is no write in this app whose
 * failure is not worth knowing about, and forty-seven mutations each
 * remembering to say so is forty-seven chances to forget. So the cache says
 * it, once, for all of them.
 *
 * A confirmation is the opposite: worth saying only where the screen does not
 * already show the answer. Booking a pile in redraws the whole panel with the
 * labels to write on the box — a toast saying "saqlandi" over the top of that
 * is noise. Moving an order along changes one word in one row, and *that* is
 * worth a sentence. So success is opt-in, by the mutation declaring
 * `meta: { done: "…" }` beside itself.
 */
const mutations = new MutationCache({
  onSuccess: (_data, _variables, _context, mutation) => {
    const done = mutation.meta?.done
    if (typeof done === "string" && done) toast.success(done)
  },
  onError: (error) => {
    toast.error(error instanceof Error ? error.message : "Nimadir noto'g'ri ketdi.")
  },
})

// Server state is TanStack Query's and nothing else's: a warehouse screen is
// a view of a room several people are changing at once, and a `useState` copy
// of it is a screen that is quietly out of date while somebody works from it.
const queries = new QueryClient({
  mutationCache: mutations,
  defaultOptions: {
    queries: {
      // A shelf figure is worth re-reading when a screen comes back into
      // focus — somebody has been putting things away in the meantime.
      refetchOnWindowFocus: true,
      staleTime: 10_000,
      retry: 1,
    },
  },
})

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queries}>
        <SessionProvider>
          <BrowserRouter>
            <App />
            <Toaster />
          </BrowserRouter>
        </SessionProvider>
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
)
