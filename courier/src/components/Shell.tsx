import * as React from "react"
import { Outlet } from "react-router-dom"
import { Download, Package, WifiOff } from "lucide-react"
import { Button } from "@/ui/button"
import { useCourier, useSession } from "@/auth/session"
import { t } from "@/lib/labels"

/**
 * A header and nothing else. No navigation, because there is nowhere to go.
 *
 * Three screens and two of them are opened by tapping a row on the first one,
 * so a menu would be one row long. The back arrow lives on the screens that
 * have somewhere to go back to.
 *
 * Two things do live here: the install prompt, and the offline banner.
 */
export function Shell() {
  const session = useSession()
  const courier = useCourier()
  const online = useOnline()
  const install = useInstall()

  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-20 border-b border-line bg-surface/95 backdrop-blur">
        <div className="flex items-center gap-3 px-[var(--gap-page)] py-3">
          <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-[var(--radius-control)] bg-brand-soft text-brand-deep">
            <Package className="size-5" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate font-semibold text-ink">{t.app}</p>
            <p className="truncate text-[length:var(--text-micro)] text-ink-soft">
              {courier.full_name || courier.phone}
            </p>
          </div>
          {install ? (
            <Button size="sm" onClick={install}>
              <Download />
              {t.install}
            </Button>
          ) : null}
          <Button variant="ghost" size="sm" onClick={() => void session.signOut()}>
            {t.signOut}
          </Button>
        </div>

        {/* Said out loud, because there is no outbox in this version: a write
            that cannot reach the server fails, and a courier who knows the
            phone is offline will not spend five minutes wondering why the
            button does nothing. */}
        {online ? null : (
          <p
            role="status"
            className="flex items-center gap-2 bg-warn-soft px-[var(--gap-page)] py-2
                       text-[length:var(--text-small)] font-medium text-warn-ink"
          >
            <WifiOff className="size-4 shrink-0" />
            Internet yo'q — yozib bo'lmaydi. Signal qaytganda qayta bosing.
          </p>
        )}
      </header>

      <main className="flex-1 pb-safe">
        <Outlet />
      </main>
    </div>
  )
}

/** Whether the phone thinks it has a network, which is the best we can know. */
function useOnline(): boolean {
  const [online, setOnline] = React.useState(
    typeof navigator === "undefined" ? true : navigator.onLine,
  )
  React.useEffect(() => {
    const up = () => setOnline(true)
    const down = () => setOnline(false)
    window.addEventListener("online", up)
    window.addEventListener("offline", down)
    return () => {
      window.removeEventListener("online", up)
      window.removeEventListener("offline", down)
    }
  }, [])
  return online
}

/**
 * The install button, and only when the browser has offered one.
 *
 * `beforeinstallprompt` fires once, before the page can ask for it, so the
 * event is captured and held — calling `prompt()` later is what turns a
 * button press into the browser's own dialogue. A browser that never fires it
 * (every iOS one) gets no button rather than a button that does nothing:
 * there, installing is "Share → Add to Home Screen" and a button we render
 * cannot reach it.
 */
type InstallEvent = Event & { prompt: () => Promise<void> }

function useInstall(): (() => void) | null {
  const [event, setEvent] = React.useState<InstallEvent | null>(null)

  React.useEffect(() => {
    const capture = (raw: Event) => {
      raw.preventDefault()
      setEvent(raw as InstallEvent)
    }
    window.addEventListener("beforeinstallprompt", capture)
    // Once it is installed the button is noise, so it goes.
    const installed = () => setEvent(null)
    window.addEventListener("appinstalled", installed)
    return () => {
      window.removeEventListener("beforeinstallprompt", capture)
      window.removeEventListener("appinstalled", installed)
    }
  }, [])

  if (!event) return null
  return () => {
    void event.prompt()
    setEvent(null)
  }
}
