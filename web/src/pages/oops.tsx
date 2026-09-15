/**
 * The two screens nobody plans and everybody eventually sees.
 *
 * ------------------------------------------------------------------- why
 *
 * A mistyped address used to be **redirected home, silently**. That is the
 * worst of the options: the person asked for a page, got a different one
 * without being told, and now believes the link they were sent is the
 * dashboard. A wrong address is information — say it, and offer the way back.
 *
 * A render that throws was worse still: React unmounts the tree and the
 * window goes white. A white screen is indistinguishable from a network that
 * died, from a laptop that went to sleep, and from the app never having
 * loaded — so the report that comes back is "it broke", with nothing in it.
 * The boundary keeps the chrome, says which screen fell over, and puts the
 * message somewhere it can be copied into a message.
 *
 * Neither page is decorated. An illustration on an error screen is a picture
 * of a thing that did not work.
 */

import { AlertTriangle, ArrowLeft, Home, Lock, RotateCw } from "lucide-react"
import { Component, type ReactNode } from "react"
import { Link, useLocation } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { roleWord, rolesFor } from "@/lib/nav"

/**
 * A wrong address — said, not silently corrected.
 *
 * And **two different wrong addresses**, because the router cannot tell them
 * apart on its own: it builds a route table per role, so a warehouse worker
 * opening `/mahsulotlar` and anybody opening `/mahsulotla` both land here.
 * Telling the first one "Bunday sahifa yo'q" is a lie — the page exists, it
 * is the owner's — and the person who read it goes and reports a broken link
 * instead of asking for the screen. `rolesFor` is what knows the difference.
 */
export function NotFound({ home }: { home: string }) {
  const where = useLocation()
  const owners = rolesFor(where.pathname)

  if (owners.length) {
    return (
      <Shape
        tone="quiet"
        icon={Lock}
        code="403"
        title="Bu sahifa sizning rolingizga ochiq emas"
        what={
          <>
            {owners.map((role) => roleWord(role)).join(", ")} ochadi:{" "}
            <code className="rounded-control bg-line-soft px-1.5 py-0.5 text-micro">
              {where.pathname}
            </code>
          </>
        }
      >
        <Button variant="secondary" onClick={() => window.history.back()}>
          <ArrowLeft />
          Orqaga
        </Button>
        <Button asChild variant="primary">
          <Link to={home}>
            <Home />
            Bosh sahifa
          </Link>
        </Button>
      </Shape>
    )
  }

  return (
    <Shape
      code="404"
      title="Bunday sahifa yo'q"
      what={
        <>
          Manzil noto'g'ri yoki sahifa ko'chirilgan:{" "}
          <code className="rounded-control bg-line-soft px-1.5 py-0.5 text-micro">
            {where.pathname}
          </code>
        </>
      }
    >
      <Button variant="secondary" onClick={() => window.history.back()}>
        <ArrowLeft />
        Orqaga
      </Button>
      <Button asChild variant="primary">
        <Link to={home}>
          <Home />
          Bosh sahifa
        </Link>
      </Button>
    </Shape>
  )
}

/**
 * The fallback the boundary draws.
 *
 * Reload rather than "try again": the component that threw is not going to
 * render differently for being asked twice, and a button that pretends
 * otherwise costs somebody a minute before they reload anyway.
 */
function Broken({ error, home }: { error: Error; home: string }) {
  return (
    <Shape
      code="500"
      title="Bu ekranda nimadir buzildi"
      what="Ish yo'qolmadi — oxirgi saqlangan holat serverda turibdi. Sahifani yangilab ko'ring; takrorlansa, quyidagi matnni yuboring."
    >
      <Button variant="secondary" onClick={() => window.location.reload()}>
        <RotateCw />
        Yangilash
      </Button>
      <Button asChild variant="primary">
        <Link to={home}>
          <Home />
          Bosh sahifa
        </Link>
      </Button>
      <pre className="mt-4 max-h-48 w-full overflow-auto rounded-control bg-line-soft p-3 text-start text-micro text-ink-soft">
        {error.message}
        {error.stack ? `\n\n${error.stack.split("\n").slice(1, 6).join("\n")}` : ""}
      </pre>
    </Shape>
  )
}

function Shape({
  code,
  title,
  what,
  children,
  tone = "bad",
  icon: Face = AlertTriangle,
}: {
  code: string
  title: string
  what: ReactNode
  children: ReactNode
  /** A door that is somebody else's is not a fault. Nothing broke, nothing
   *  was mistyped, and a red triangle over it reads as one. */
  tone?: "bad" | "quiet"
  icon?: typeof AlertTriangle
}) {
  return (
    <div className="grid min-h-[60vh] place-items-center">
      <div className="w-full max-w-lg rounded-panel border border-panel-edge bg-surface p-8 text-center">
        <div
          className={
            tone === "quiet"
              ? "mx-auto grid size-12 place-items-center rounded-panel bg-line-soft text-ink-soft"
              : "mx-auto grid size-12 place-items-center rounded-panel bg-danger-soft text-danger"
          }
        >
          <Face className="size-6" />
        </div>
        <p className="mt-4 text-micro font-semibold tracking-widest text-ink-faint">
          {code}
        </p>
        <h1 className="mt-1 text-xl font-semibold tracking-tight">{title}</h1>
        <p className="mx-auto mt-2 max-w-sm text-small text-ink-soft">{what}</p>
        <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
          {children}
        </div>
      </div>
    </div>
  )
}

/**
 * One boundary around the screen, not around the chrome.
 *
 * Inside the shell on purpose: the rail and the top bar did not throw, and a
 * person whose screen fell over still wants the menu — the next thing they do
 * is go somewhere else. `key` is the path, so navigating away resets it; a
 * boundary that stays broken after you leave the broken page is a boundary
 * that has trapped you.
 */
export class ScreenBoundary extends Component<
  { children: ReactNode; home: string; at: string },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidUpdate(previous: { at: string }) {
    if (previous.at !== this.props.at && this.state.error) {
      this.setState({ error: null })
    }
  }

  componentDidCatch(error: Error, info: { componentStack?: string | null }) {
    // The console is where a developer looks first, and the boundary is not a
    // reason to lose the stack React already assembled.
    console.error("Screen failed:", error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return <Broken error={this.state.error} home={this.props.home} />
    }
    return this.props.children
  }
}
