/**
 * The screen's name, said once.
 *
 * On a desktop a screen carries its title twice on purpose: the top bar says
 * where you are (a breadcrumb) and the page's own header card says what this
 * is, next to the controls that act on it. On a 390px phone that is the same
 * two or three words printed twice and about a fifth of the window spent
 * before any content — and on `/ishlarim` the content was two sentences.
 *
 * So on a phone the page header stops drawing its title and the top bar draws
 * it instead. Which means the top bar has to know a title it cannot work out:
 * `Terish` is the menu's word for the screen, but the screen a picker is
 * actually on is `MB-000412`, and the line under it — `4 qator · 2 qoldi` — is
 * the thing they are reading. The nav label is a fallback, not the answer.
 *
 * Hence this: `PageHeader` publishes what it was given, the top bar reads it.
 * The publish is keyed on the value rather than on the route, so navigating
 * from one titled screen to another never blanks the bar for a frame — the
 * outgoing header only clears the title if it is still the one showing.
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react"

export type PageTitle = { title: string; subtitle?: string }

type Publish = (what: PageTitle) => () => void

const Reading = createContext<PageTitle | null>(null)
const Writing = createContext<Publish | null>(null)

export function PageTitleProvider({ children }: { children: React.ReactNode }) {
  const [what, setWhat] = useState<PageTitle | null>(null)

  const publish = useCallback<Publish>((next) => {
    setWhat(next)
    return () => setWhat((now) => (now === next ? null : now))
  }, [])

  return (
    <Writing.Provider value={publish}>
      <Reading.Provider value={what}>{children}</Reading.Provider>
    </Writing.Provider>
  )
}

/** Called by `PageHeader`. Outside the shell (the sign-in screen) it is a
 *  no-op rather than a crash — a component that only works in one frame is a
 *  component somebody eventually moves. */
export function usePublishTitle(title: string, subtitle?: string) {
  const publish = useContext(Writing)
  useEffect(() => {
    if (!publish) return
    return publish({ title, subtitle })
  }, [publish, title, subtitle])
}

/** Called by the top bar. `null` until a screen with a header has rendered. */
export function usePageTitle(): PageTitle | null {
  return useContext(Reading)
}
