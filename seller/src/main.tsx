import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Toaster } from "sonner"
import { App } from "./App"
import { SessionProvider } from "./auth/session"
import "./index.css"

/**
 * One query client, and two defaults worth stating.
 *
 * **No retries.** The backend's 4xx answers are sentences a person is meant
 * to read — "Bu sizning tovaringiz emas" — and retrying one three times
 * before showing it delays the answer without changing it. A network failure
 * has a retry button on the screen instead, which is the retry somebody
 * actually wants: the one they can see.
 *
 * **Fresh for ten seconds.** These screens are read in bursts — a seller
 * opens their returns, looks at three, goes back to the list — and a refetch
 * per navigation inside one burst is a flicker for no new information.
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, staleTime: 10_000, refetchOnWindowFocus: false },
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
