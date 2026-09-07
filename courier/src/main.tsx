import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router-dom"
import { Toaster } from "sonner"
import App from "./App"
import { SessionProvider } from "./auth/session"
import "./index.css"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <SessionProvider>
        <App />
        {/*
          Top, not bottom. The bottom of the screen is where every primary
          action in this app lives, and a toast landing on the button somebody
          is reaching for is a toast that gets tapped through.
        */}
        <Toaster position="top-center" richColors closeButton toastOptions={{ duration: 5000 }} />
      </SessionProvider>
    </BrowserRouter>
  </StrictMode>,
)
