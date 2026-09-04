import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Toaster } from "sonner"
import { App } from "@/App"
import { SessionProvider } from "@/auth/session"
import "@/index.css"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A queue is worked from, not watched. Refetching on every window focus
      // would move rows under an operator's cursor.
      refetchOnWindowFocus: false,
      staleTime: 15_000,
      // 401 is handled in the client, which refreshes and retries once; a
      // second failure means the session is over, and retrying would only
      // delay the login screen.
      retry: false,
    },
  },
})

const root = document.getElementById("root")
if (!root) throw new Error("#root missing")

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
        <Toaster
          position="bottom-right"
          toastOptions={{ style: { fontSize: "13px", borderRadius: "6px" } }}
        />
      </SessionProvider>
    </QueryClientProvider>
  </StrictMode>,
)
