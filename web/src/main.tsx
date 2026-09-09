import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router-dom"

import { App } from "@/App"
import { SessionProvider } from "@/lib/session"
import "./index.css"

// Server state is TanStack Query's and nothing else's: a warehouse screen is
// a view of a room several people are changing at once, and a `useState` copy
// of it is a screen that is quietly out of date while somebody works from it.
const queries = new QueryClient({
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
    <QueryClientProvider client={queries}>
      <SessionProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </SessionProvider>
    </QueryClientProvider>
  </StrictMode>,
)
