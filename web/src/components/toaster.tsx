/**
 * The one place the app says "done" and "no".
 *
 * ------------------------------------------------------------------- why
 *
 * Every write in this app was silent when it worked and inline when it did
 * not. A warehouse worker pressed **Yig'ishga o'tkazish**, the button went
 * quiet for a moment, the row redrew, and nothing anywhere said the order had
 * moved — so the honest thing to do was press it again. A refusal fared
 * slightly better: a red sentence appeared inside whatever panel the mutation
 * happened to belong to, which on a long screen is a sentence nobody sees.
 *
 * Feedback for an action belongs where the eye already is, in front of the
 * page rather than inside it, and it belongs to the *action* rather than to
 * the panel that started it.
 *
 * ---------------------------------------------------------------- the toast
 *
 * Dark pill, one line, an icon square on the left in the meaning's own
 * colour — the same three meanings this system uses everywhere. It is dark in
 * both themes on purpose: a toast is not part of the page, and a white card
 * floating over white panels has to draw a border to prove it.
 *
 * Bottom right, because that is the corner furthest from the rail and from
 * the thing that was just pressed, and close enough to the primary action of
 * a form — which sits bottom-right too — that the eye is already there.
 */

import { Toaster as Sonner } from "sonner"

import { useTheme } from "@/lib/theme"

export function Toaster() {
  const { resolved } = useTheme()

  return (
    <Sonner
      theme={resolved}
      position="bottom-right"
      // Long enough to read a sentence in a second language, short enough not
      // to stack up while somebody books in a sack of forty.
      duration={4000}
      gap={8}
      offset={16}
      toastOptions={{
        unstyled: true,
        classNames: {
          toast:
            "flex w-full items-center gap-3 rounded-panel bg-ink px-3 py-2.5 text-surface shadow-raised",
          title: "text-small font-medium",
          description: "text-micro opacity-75",
          actionButton:
            "ml-auto rounded-control bg-white/15 px-2 py-1 text-micro font-medium",
          closeButton: "ml-auto opacity-60 hover:opacity-100",
        },
      }}
      icons={{
        success: <Square tone="bg-good" glyph="✓" />,
        error: <Square tone="bg-danger" glyph="!" />,
        warning: <Square tone="bg-warn" glyph="!" />,
        info: <Square tone="bg-brand" glyph="i" />,
      }}
    />
  )
}

/** The meaning, as a solid square. A tinted glyph on a dark pill disappears. */
function Square({ tone, glyph }: { tone: string; glyph: string }) {
  return (
    <span
      aria-hidden
      className={`grid size-6 shrink-0 place-items-center rounded-control text-small font-bold text-white ${tone}`}
    >
      {glyph}
    </span>
  )
}
