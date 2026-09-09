/**
 * The photograph step — the one people will skip if you let them.
 *
 * Market goods arrive with no pictures, so the only ones that will ever exist
 * are taken here, at the receiving desk, while the sack is open. A colour
 * without one keeps the whole card out of the shop, and the form says so, at
 * the moment it happens, naming the colour.
 *
 * **Three ways in.** The phone camera, a file from the gallery, and **paste
 * from the clipboard** — because the wholesaler's picture is usually already
 * sitting in Telegram and Ctrl+V is the fastest path there is.
 *
 * **A square guide frame and one line of instruction.** Consistency across a
 * catalogue matters far more than the quality of any single shot, and a guide
 * frame is what buys it. The server pads the result onto a white square on
 * top of that, so a portrait photo and a landscape one become the same tile.
 *
 * There is no background removal here and there will not be: the goods are
 * shot against a sheet of white paper. `rembg` and friends mean onnxruntime
 * and a 150MB model for a problem a 15,000 so'm sheet of paper already solves.
 */

import { Camera, Check, Clipboard, ImagePlus, Loader2 } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { Problem } from "@/components/page"
import { Button } from "@/components/ui/button"
import { tokens } from "@/lib/api"
import { cn } from "@/lib/cn"
import type { Media } from "@/lib/types"

const GUIDE = "oq fonda · bitta tavar · qo'l ko'rinmasin"

export function PhotoStep({
  colours,
  taken,
  onTaken,
}: {
  colours: string[]
  taken: Record<string, string>
  onTaken: (colour: string, url: string) => void
}) {
  const [colour, setColour] = useState(colours[0] ?? "")
  const missing = colours.filter((one) => !taken[one])

  useEffect(() => {
    if (!colours.includes(colour)) setColour(colours[0] ?? "")
  }, [colours, colour])

  return (
    <div className="space-y-3">
      {colours.length > 1 ? (
        <div className="flex flex-wrap gap-1">
          {colours.map((one) => (
            <button
              key={one}
              type="button"
              onClick={() => setColour(one)}
              className={cn(
                "h-control rounded-control border px-3 text-small",
                one === colour && "border-brand bg-brand-soft text-brand-deep",
                taken[one] && "border-good",
              )}
            >
              {one}
              {taken[one] ? " ✓" : ""}
            </button>
          ))}
        </div>
      ) : null}

      <Capture colour={colour} current={taken[colour]} onTaken={onTaken} />

      {missing.length ? (
        <p className="rounded-control bg-warn-soft p-2 text-micro text-warn-ink">
          Rasmsiz rang: <b>{missing.join(", ")}</b>. Rasm qo'yilmaguncha karta
          sotuvga chiqmaydi — omborda turadi, sanaladi, lekin ilovada
          ko'rinmaydi.
        </p>
      ) : (
        <p className="rounded-control bg-good-soft p-2 text-micro text-good">
          Hamma rangning rasmi bor — karta sotuvga chiqishi mumkin.
        </p>
      )}
    </div>
  )
}

function Capture({
  colour,
  current,
  onTaken,
}: {
  colour: string
  current: string | undefined
  onTaken: (colour: string, url: string) => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const camera = useRef<HTMLInputElement>(null)
  const gallery = useRef<HTMLInputElement>(null)
  const area = useRef<HTMLDivElement>(null)

  async function send(file: File | null | undefined) {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const form = new FormData()
      form.append("file", file)
      // Not through `api()`: this one posts a multipart body rather than JSON,
      // and a helper that handles both is a helper with a branch in it for
      // the sake of one caller.
      const response = await fetch(
        `${import.meta.env.VITE_API_URL ?? "http://localhost:8000"}/api/v1/media?square=true`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${tokens.access() ?? ""}` },
          body: form,
        },
      )
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as { detail?: string } | null
        throw new Error(body?.detail ?? "Rasm yuklanmadi")
      }
      const media = (await response.json()) as Media
      onTaken(colour, media.media_url)
    } catch (problem) {
      setError(problem)
    } finally {
      setBusy(false)
    }
  }

  // Paste, because the wholesaler's picture is already in Telegram.
  useEffect(() => {
    const node = area.current
    if (!node) return
    const onPaste = (event: ClipboardEvent) => {
      const file = [...(event.clipboardData?.items ?? [])]
        .find((item) => item.type.startsWith("image/"))
        ?.getAsFile()
      if (file) {
        event.preventDefault()
        void send(file)
      }
    }
    node.addEventListener("paste", onPaste)
    return () => node.removeEventListener("paste", onPaste)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [colour])

  return (
    <div
      ref={area}
      tabIndex={0}
      className="space-y-2 rounded-panel border border-dashed p-3 focus:outline-none focus:ring-2 focus:ring-brand"
    >
      <div className="relative mx-auto aspect-square w-full max-w-56 overflow-hidden rounded-control bg-canvas">
        {current ? (
          <img
            src={mediaUrl(current)}
            alt={colour}
            className="size-full object-contain"
          />
        ) : (
          <>
            {/* The guide frame. Consistency across the catalogue is worth more
                than the quality of any single shot. */}
            <div className="absolute inset-4 rounded-control border-2 border-dashed border-line" />
            <div className="grid size-full place-items-center text-micro text-ink-faint">
              {colour || "rasm"}
            </div>
          </>
        )}
        {busy ? (
          <div className="absolute inset-0 grid place-items-center bg-white/70">
            <Loader2 className="size-6 animate-spin text-brand" />
          </div>
        ) : null}
        {current && !busy ? (
          <span className="absolute right-2 top-2 grid size-6 place-items-center rounded-full bg-good text-good-ink">
            <Check className="size-4" />
          </span>
        ) : null}
      </div>

      <p className="text-center text-micro text-ink-faint">{GUIDE}</p>

      <div className="flex flex-wrap justify-center gap-2">
        <Button
          type="button"
          variant="secondary"
          className="h-control gap-2"
          onClick={() => camera.current?.click()}
        >
          <Camera className="size-4" />
          Kamera
        </Button>
        <Button
          type="button"
          variant="secondary"
          className="h-control gap-2"
          onClick={() => gallery.current?.click()}
        >
          <ImagePlus className="size-4" />
          Fayl
        </Button>
        <span className="inline-flex h-control items-center gap-2 rounded-control border px-3 text-small text-ink-soft">
          <Clipboard className="size-4" />
          yoki Ctrl+V
        </span>
      </div>

      {/* `capture` asks the phone for the back camera directly. On a desktop
          it is an ordinary file input, which is the right fallback. */}
      <input
        ref={camera}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(event) => void send(event.target.files?.[0])}
      />
      <input
        ref={gallery}
        type="file"
        accept="image/*"
        hidden
        onChange={(event) => void send(event.target.files?.[0])}
      />

      <Problem error={error} />
    </div>
  )
}

/** Media paths are stored relative, so each client prefixes its own host. */
export function mediaUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path
  const base = import.meta.env.VITE_API_URL ?? "http://localhost:8000"
  return `${base}/media/${path.replace(/^\/+/, "")}`
}
