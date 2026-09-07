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
      // Refetched on focus, unlike the backoffice. An operator is working a
      // queue and would lose their place; a seller comes back to this tab
      // after doing something else and wants what is true now.
      refetchOnWindowFocus: true,
      staleTime: 20_000,
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
          position="top-center"
          toastOptions={{ style: { fontSize: "14px", borderRadius: "12px" } }}
        />
      </SessionProvider>
    </QueryClientProvider>
  </StrictMode>,
)
