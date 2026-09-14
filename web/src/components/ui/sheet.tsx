/**
 * The same modal, anchored to an edge instead of to the middle.
 *
 * **A sheet is a dialog with a different position and nothing else.** That is
 * the whole of this file now. The overlay, the three bands, the corner cross,
 * the focus trap, `Esc`, the backdrop click — all of it comes from
 * `components/ui/dialog.tsx`, and the only thing declared here is where the
 * box sits and which way it slides in.
 *
 * It used to be a second copy, and it had drifted the way second copies do:
 * the body was padded `p-4` against the modal's `p-5`, the footer had no way
 * to carry the cancel button the modal's footer offers, the panel faded in
 * over half a second where the modal took a seventh of one, and the backdrop
 * was written as a hex in two files at once. None of those were decisions.
 *
 * **When to use which.** A record you read beside its list opens at the side,
 * so the list stays visible and the next row is one click away — a person, a
 * customer, an order, a return. An act or a short form opens in the middle
 * and goes away when it is finished — a confirmation, a window editor, an
 * appointment. That rule is written down in the screens; this file only makes
 * the two look like one family.
 */

import * as React from "react"
import { Dialog as SheetPrimitive } from "radix-ui"

import {
  Dialog,
  DialogBody,
  DialogClose,
  DialogCornerClose,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
  useReturnFocus,
} from "@/components/ui/dialog"
import { cn } from "@/lib/cn"

function SheetContent({
  className,
  children,
  side = "right",
  showCloseButton = true,
  onCloseAutoFocus,
  ...props
}: React.ComponentProps<typeof SheetPrimitive.Content> & {
  side?: "top" | "right" | "bottom" | "left"
  showCloseButton?: boolean
}) {
  const focus = useReturnFocus(onCloseAutoFocus)
  return (
    <DialogPortal>
      {focus.capture}
      <DialogOverlay />
      <SheetPrimitive.Content
        data-slot="sheet-content"
        onCloseAutoFocus={focus.onCloseAutoFocus}
        className={cn(
          "fixed z-50 flex flex-col bg-surface text-ink shadow-raised outline-none",
          // The same 150ms the centred modal takes. A sheet that slides for
          // half a second is a sheet somebody is waiting for.
          "duration-150 data-[state=closed]:animate-out data-[state=open]:animate-in",
          // Nearly the whole phone, and deliberately not all of it. Three
          // quarters of 390px is not a panel anybody can read an order in,
          // but a sheet with no backdrop showing is a sheet with no way out
          // for a thumb — there is no `Esc` key on a phone. The strip that is
          // left is wide enough to hit and dismisses the panel.
          side === "right" &&
            "inset-y-0 right-0 h-full w-[calc(100%-3rem)] border-l border-line data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right sm:w-3/4 sm:max-w-md",
          side === "left" &&
            "inset-y-0 left-0 h-full w-[calc(100%-3rem)] border-r border-line data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left sm:w-3/4 sm:max-w-md",
          side === "top" &&
            "inset-x-0 top-0 h-auto border-b border-line data-[state=closed]:slide-out-to-top data-[state=open]:slide-in-from-top",
          side === "bottom" &&
            "inset-x-0 bottom-0 h-auto border-t border-line data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom",
          className,
        )}
        {...props}
      >
        {children}
        {showCloseButton && <DialogCornerClose />}
      </SheetPrimitive.Content>
    </DialogPortal>
  )
}

export {
  // One root, one trigger, one close, one set of bands — the dialog's.
  Dialog as Sheet,
  DialogTrigger as SheetTrigger,
  DialogClose as SheetClose,
  DialogPortal as SheetPortal,
  DialogOverlay as SheetOverlay,
  DialogHeader as SheetHeader,
  DialogBody as SheetBody,
  DialogFooter as SheetFooter,
  DialogTitle as SheetTitle,
  DialogDescription as SheetDescription,
  SheetContent,
}
