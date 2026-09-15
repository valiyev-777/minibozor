/**
 * The barcode, drawn in the browser.
 *
 * A barcode is a picture of a string, so drawing it here means no image to
 * store, no font to install on a server, and a reprint that cannot drift from
 * the code it claims to be.
 *
 * It lives on its own because two screens print it — the label roll and the
 * reprint screen — and two drawings of one barcode is one of them being
 * subtly wrong: a different bar width, a different quiet zone, and a scanner
 * that reads the sticker off one screen and not off the other.
 */

import bwipjs from "bwip-js/browser"
import { useEffect, useMemo, useRef } from "react"

import { cn } from "@/lib/cn"

/** What bwip-js is asked for, on screen and on the roll. A thermal head is
 *  203 dpi and its bars are printed at whatever width they are drawn, so the
 *  picture that goes on a sticker is drawn larger and then scaled down by the
 *  page box — a bar rounded up from too few pixels is a bar a gun misreads. */
const SCREEN = { scale: 2, height: 10 }
const STICKER = { scale: 4, height: 9 }

function paint(
  canvas: HTMLCanvasElement,
  value: string,
  look: { scale: number; height: number },
) {
  bwipjs.toCanvas(canvas, {
    bcid: "code128",
    text: value,
    includetext: true,
    textxalign: "center",
    ...look,
  })
}

/** The barcode as a live canvas — for the screen, where it is a preview. */
export function Barcode({ value, className }: { value: string; className?: string }) {
  const canvas = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (!canvas.current || !value) return
    try {
      paint(canvas.current, value, SCREEN)
    } catch {
      // A code that will not encode is a code somebody has to look at, and a
      // thrown error here would take the whole sheet down with it.
    }
  }, [value])

  return <canvas ref={canvas} className={cn("my-1 w-full", className)} aria-label={value} />
}

/**
 * The barcode as a PNG data URL — for the roll.
 *
 * Twenty stickers of one shoe carry one barcode, so the picture is drawn once
 * and the twenty pages point an `<img>` at it. Twenty canvases would be twenty
 * encodings of the same string, and a browser asked to lay out and print a
 * few hundred canvases takes long enough that somebody presses the button
 * again.
 */
export function useStickerBarcode(value: string): string {
  return useMemo(() => {
    if (!value) return ""
    try {
      const canvas = document.createElement("canvas")
      paint(canvas, value, STICKER)
      return canvas.toDataURL("image/png")
    } catch {
      return ""
    }
  }, [value])
}
