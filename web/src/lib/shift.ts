/**
 * "Am I taking work right now?" — and the honest answer about where it lives.
 *
 * The design has an online switch on the home screen and an "go offline"
 * button on the profile, and the server has **no shift**. `app/routers/courier`
 * says so in its first paragraph and means it: there is no open, no close, no
 * cash total to count against, and no column anywhere that records whether a
 * courier is available. The board is open to every courier all the time and
 * taking a parcel is the only fact the system holds.
 *
 * So this is a **local preference and nothing more**, and it is written down
 * here rather than dressed up as state the server knows about. What it does is
 * real, though, and worth having:
 *
 *   - it stops the free board polling every minute in the background while
 *     somebody is off shift, which on a phone is battery;
 *   - it puts the home screen's one big action where it belongs — "come back
 *     on" rather than "take a load" — so the screen matches what the person
 *     is doing.
 *
 * What it explicitly does **not** do is hide work from an operator or stop
 * anything arriving. A courier who is "offline" here and takes a parcel in the
 * warehouse has taken a parcel; the switch is a note to themselves. Both
 * screens that show it say as much, because a switch that looks like it tells
 * the office something and does not is worse than no switch.
 */

import { useCallback, useEffect, useState } from "react"

const KEY = "mb:kuryer:shift"

/** Anybody who has not said otherwise is on. The alternative — starting a
 *  fresh install offline — greets a courier with a screen that has nothing on
 *  it and an explanation they did not ask for. */
function read(): boolean {
  try {
    return localStorage.getItem(KEY) !== "off"
  } catch {
    // Private mode, or a locked-down webview. On, and carry on.
    return true
  }
}

export function useOnShift(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(read)

  // Two tabs, or the profile screen and the home screen in the same tab: the
  // switch is one fact and both have to show it.
  useEffect(() => {
    const listen = () => setOn(read())
    window.addEventListener("storage", listen)
    window.addEventListener("mb:shift", listen)
    return () => {
      window.removeEventListener("storage", listen)
      window.removeEventListener("mb:shift", listen)
    }
  }, [])

  const set = useCallback((next: boolean) => {
    try {
      localStorage.setItem(KEY, next ? "on" : "off")
    } catch {
      // Nothing to remember it with. The switch still works for this session.
    }
    setOn(next)
    window.dispatchEvent(new Event("mb:shift"))
  }, [])

  return [on, set]
}
