/**
 * Light, dark, or whatever the machine says.
 *
 * Three states rather than two, and the third is the reason this is a store
 * at all. `prefers-color-scheme` alone would repaint the office at whatever
 * hour the operating system decides the sun set — a desk screen that goes
 * dark mid-afternoon in winter is not a feature, it is a bug somebody
 * reports. So the class on `<html>` is written by this module and nothing
 * else, and "follow the system" is one of the things a person can choose
 * rather than the thing that happens to them.
 *
 * The choice is remembered in `localStorage` under one key, and it is read
 * *before* React paints — see the inline script in `index.html` — so nobody
 * gets a white flash on the way to a dark screen.
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react"

export type ThemeMode = "light" | "dark" | "system"

const KEY = "mb:theme"

type ThemeState = {
  mode: ThemeMode
  /** What is actually on screen right now, system resolved. */
  resolved: "light" | "dark"
  setMode: (mode: ThemeMode) => void
}

const ThemeContext = createContext<ThemeState | null>(null)

function stored(): ThemeMode {
  const value = localStorage.getItem(KEY)
  return value === "light" || value === "dark" || value === "system" ? value : "light"
}

function systemPrefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(stored)
  const [systemDark, setSystemDark] = useState(systemPrefersDark)

  // Only listened to while the mode is `system`; a person who has picked a
  // side does not want their screen changing under them at dusk.
  useEffect(() => {
    if (mode !== "system") return
    const query = window.matchMedia("(prefers-color-scheme: dark)")
    const onChange = () => setSystemDark(query.matches)
    query.addEventListener("change", onChange)
    return () => query.removeEventListener("change", onChange)
  }, [mode])

  const resolved: "light" | "dark" =
    mode === "system" ? (systemDark ? "dark" : "light") : mode

  useEffect(() => {
    document.documentElement.classList.toggle("dark", resolved === "dark")
    // The browser chrome around the page — the address bar on a phone — is
    // told too, or the app ends up in a dark window with a bright hat on.
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", resolved === "dark" ? "#090e14" : "#2585ff")
  }, [resolved])

  const setMode = useCallback((next: ThemeMode) => {
    localStorage.setItem(KEY, next)
    setModeState(next)
  }, [])

  return (
    <ThemeContext.Provider value={{ mode, resolved, setMode }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme(): ThemeState {
  const value = useContext(ThemeContext)
  if (!value) throw new Error("useTheme outside a ThemeProvider")
  return value
}
