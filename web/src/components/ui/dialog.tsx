/**
 * The modal, in three bands with a hairline between them.
 *
 * Header, body, footer — `border-line` between each, rather than the three
 * being separated by whitespace inside one padded box. It is the house shape
 * and it earns itself the moment the body is a form: a scrolling body under a
 * fixed title needs a line to scroll *under*, or the title floats over the
 * fields and the modal looks broken halfway through a scroll.
 *
 * So `DialogContent` has no padding of its own. Header and footer bring
 * theirs; the body between them wants `DialogBody`, which is here for exactly
 * that reason — a bare `<div>` between the two bands is the one place this
 * shape is easy to get wrong.
 *
 * The footer's buttons are full-width and split. Two equal buttons at
 * opposite ends of a confirmation are hard to mis-click, which is the whole
 * point of asking.
 *
 * ------------------------------------------------------------ and the sheet
 *
 * This file is also where the **side** sheet gets its bands. There is one
 * overlay in this application and one set of header/body/footer, and
 * `components/ui/sheet.tsx` imports them from here rather than keeping a
 * second copy that drifts — which is exactly what had happened: the sheet's
 * body was padded `p-4` against the modal's `p-5`, its footer could not
 * carry a cancel button, and it faded in over half a second while the modal
 * took a seventh of one. Two shapes, one behaviour: the only difference
 * between a dialog and a sheet is where the box is anchored.
 */

import * as React from "react"
import { XIcon } from "lucide-react"
import { Dialog as DialogPrimitive } from "radix-ui"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/cn"

function Dialog({ ...props }: React.ComponentProps<typeof DialogPrimitive.Root>) {
  return <DialogPrimitive.Root data-slot="dialog" {...props} />
}

function DialogTrigger({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Trigger>) {
  return <DialogPrimitive.Trigger data-slot="dialog-trigger" {...props} />
}

function DialogPortal({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Portal>) {
  return <DialogPrimitive.Portal data-slot="dialog-portal" {...props} />
}

function DialogClose({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Close>) {
  return <DialogPrimitive.Close data-slot="dialog-close" {...props} />
}

function DialogOverlay({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Overlay>) {
  return (
    <DialogPrimitive.Overlay
      data-slot="dialog-overlay"
      className={cn(
        // `rail` rather than a hex: the near-black the sidebar is painted in
        // is the one dark this system owns, and an overlay written as a
        // literal is an overlay that stops matching the day the rail moves.
        "fixed inset-0 z-50 bg-rail/60 backdrop-blur-[2px]",
        "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0",
        className,
      )}
      {...props}
    />
  )
}

/**
 * Put focus back where it came from when the panel closes.
 *
 * Radix restores focus to its own `Trigger` and to nothing else, and not one
 * overlay in this application uses one: a cell on the map, a row in a table
 * and a button in a page header all open a panel by setting a piece of state.
 * So every single one of them dropped focus on `<body>` when it closed —
 * `Esc` out of a customer and the next `Tab` started again at the top of the
 * rail, which on a screen with ninety cells is a long way back to the cell
 * you were looking at. Radix's own focus scope remembers the right element
 * and would restore it; `Dialog` overrides that to reach for a trigger, and
 * with no trigger the override lands nowhere.
 *
 * **When** the answer is read is the whole difficulty, and both of the
 * obvious moments are wrong. This wrapper is in the tree the entire time its
 * screen is, closed as well as open, so a first render answers with whatever
 * had focus when the page loaded. And `onOpenAutoFocus` is already too late:
 * a panel whose first field carries `autoFocus` — the appoint form, the cell's
 * reason — has had React focus that field during the commit, so the answer is
 * a control inside the panel, which is gone by the time it is needed.
 *
 * So it is read during the render pass in which the panel mounts, by a
 * component that only exists then: after the click that opened it, before any
 * of it reaches the DOM.
 */
function useReturnFocus(onCloseAutoFocus?: (event: Event) => void) {
  const opener = React.useRef<Element | null>(null)

  return {
    /** Rendered inside the portal, which React mounts only while open. */
    capture: <CaptureOpener into={opener} />,
    onCloseAutoFocus: React.useCallback(
      (event: Event) => {
        onCloseAutoFocus?.(event)
        // A caller with its own idea where focus should land wins.
        if (event.defaultPrevented) return
        const back = opener.current
        opener.current = null
        if (back instanceof HTMLElement && back.isConnected && back !== document.body) {
          // Preventing the default is what stops Radix's own handler running
          // afterwards and focusing a trigger that does not exist.
          event.preventDefault()
          back.focus()
        }
      },
      [onCloseAutoFocus],
    ),
  }
}

function CaptureOpener({ into }: { into: React.RefObject<Element | null> }) {
  React.useState(() => {
    into.current = document.activeElement
    return null
  })
  return null
}

function DialogContent({
  className,
  children,
  showCloseButton = true,
  onCloseAutoFocus,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content> & {
  showCloseButton?: boolean
}) {
  const focus = useReturnFocus(onCloseAutoFocus)
  return (
    <DialogPortal data-slot="dialog-portal">
      {focus.capture}
      <DialogOverlay />
      <DialogPrimitive.Content
        data-slot="dialog-content"
        onCloseAutoFocus={focus.onCloseAutoFocus}
        className={cn(
          "fixed top-1/2 left-1/2 z-50 flex max-h-[calc(100dvh-4rem)] w-full max-w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col",
          "overflow-hidden rounded-panel border border-line bg-surface text-ink shadow-raised outline-none sm:max-w-lg",
          "duration-150 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
          className,
        )}
        {...props}
      >
        {children}
        {showCloseButton && <DialogCornerClose />}
      </DialogPrimitive.Content>
    </DialogPortal>
  )
}

/**
 * The one close affordance, top right, in both shapes.
 *
 * Exported so the sheet can use the same object rather than a second one
 * that is three pixels along — the corner cross is the thing a person's eye
 * goes to first, and it has to be in the same corner at the same size
 * whichever way the box came in.
 */
function DialogCornerClose() {
  return (
    <DialogPrimitive.Close
      data-slot="dialog-close"
      className="absolute top-3 right-3 grid size-8 place-items-center rounded-control text-ink-faint transition-colors hover:bg-line-soft hover:text-ink focus-visible:ring-2 focus-visible:ring-brand/40 focus:outline-none [&_svg]:size-4"
    >
      <XIcon />
      <span className="sr-only">Yopish</span>
    </DialogPrimitive.Close>
  )
}

function DialogHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="dialog-header"
      className={cn(
        "flex shrink-0 flex-col gap-1 border-b border-line px-4 py-3 pr-12",
        className,
      )}
      {...props}
    />
  )
}

/** The scrolling middle. A modal whose body is a form scrolls; its title and
 *  its two buttons do not go with it. */
function DialogBody({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="dialog-body"
      className={cn("min-h-0 flex-1 overflow-y-auto p-5", className)}
      {...props}
    />
  )
}

function DialogFooter({
  className,
  showCloseButton = false,
  children,
  ...props
}: React.ComponentProps<"div"> & { showCloseButton?: boolean }) {
  return (
    <div
      data-slot="dialog-footer"
      className={cn(
        "flex shrink-0 items-center gap-3 border-t border-line p-4 [&>*]:flex-1",
        className,
      )}
      {...props}
    >
      {showCloseButton && (
        <DialogPrimitive.Close asChild>
          <Button variant="secondary">Bekor qilish</Button>
        </DialogPrimitive.Close>
      )}
      {children}
    </div>
  )
}

function DialogTitle({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title
      data-slot="dialog-title"
      className={cn("text-body leading-tight font-semibold", className)}
      {...props}
    />
  )
}

function DialogDescription({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description
      data-slot="dialog-description"
      className={cn("text-small text-ink-soft", className)}
      {...props}
    />
  )
}

export {
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogCornerClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
  useReturnFocus,
}
