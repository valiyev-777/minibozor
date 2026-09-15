/**
 * The photograph step — the one people will skip if you let them.
 *
 * Market goods arrive with no pictures, so the only ones that will ever exist
 * are taken here. A colour without one keeps that colour out of the shop, and
 * the reason is written on the tile itself, at the moment somebody is looking
 * at it — not in a paragraph they have to connect to a colour themselves.
 *
 * **A row of colour tiles.** A tile with a photograph shows it; a tile
 * without shows a dashed camera box. Tapping a tile opens the camera (a file
 * dialog on a desk), pasting attaches to the selected tile because the
 * wholesaler's picture is usually already sitting in Telegram, and a file can
 * be dropped straight onto the tile it belongs to. The upload is shown as it
 * happens — the local file appears instantly under a spinner — because a
 * photograph that arrives three seconds later reads as a failure.
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

/** One door for every photograph, shared by the tiles and by `Capture`.
 *  Not through `api()`: this one posts a multipart body rather than JSON, and
 *  a helper that handles both is a helper with a branch in it. */
async function upload(file: File): Promise<Media> {
  const form = new FormData()
  form.append("file", file)
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
  return (await response.json()) as Media
}

export function PhotoStep({
  colours,
  taken,
  onTaken,
}: {
  colours: string[]
  taken: Record<string, string>
  onTaken: (colour: string, url: string) => void
}) {
  // Start on the first colour that still needs a photograph: that is the tile
  // the person opened this for.
  const [colour, setColour] = useState(
    colours.find((one) => !taken[one]) ?? colours[0] ?? "",
  )
  const [busy, setBusy] = useState<Record<string, boolean>>({})
  // The just-taken file as an object URL, per colour. Shown ahead of the
  // server's copy so the tile swaps the moment the shutter clicks.
  const [preview, setPreview] = useState<Record<string, string>>({})
  const [over, setOver] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)
  const camera = useRef<HTMLInputElement>(null)
  const gallery = useRef<HTMLInputElement>(null)
  // Which tile the open file dialog belongs to — set by the click, read by
  // the change event, because state set in between would race the dialog.
  const target = useRef(colour)

  useEffect(() => {
    if (!colours.includes(colour)) setColour(colours[0] ?? "")
  }, [colours, colour])

  async function send(one: string, file: File | null | undefined) {
    if (!file || !file.type.startsWith("image/")) return
    const local = URL.createObjectURL(file)
    setPreview((was) => ({ ...was, [one]: local }))
    setBusy((was) => ({ ...was, [one]: true }))
    setError(null)
    try {
      const media = await upload(file)
      onTaken(one, media.media_url)
    } catch (problem) {
      // Back to what the server has: an optimistic preview of a failed upload
      // would read as success.
      URL.revokeObjectURL(local)
      setPreview((was) => {
        const next = { ...was }
        delete next[one]
        return next
      })
      setError(problem)
    } finally {
      setBusy((was) => ({ ...was, [one]: false }))
    }
  }

  // Paste lands on the selected colour from anywhere on the page — the person
  // is in Telegram, copies, comes back, and must not have to find a box first.
  // Only image items are taken, so pasting text into a price field is unharmed.
  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      const file = [...(event.clipboardData?.items ?? [])]
        .find((item) => item.type.startsWith("image/"))
        ?.getAsFile()
      if (file) {
        event.preventDefault()
        void send(colour, file)
      }
    }
    document.addEventListener("paste", onPaste)
    return () => document.removeEventListener("paste", onPaste)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [colour])

  const name = (one: string) => one || "umumiy"

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {colours.map((one) => {
          const shot = preview[one] ?? (taken[one] ? mediaUrl(taken[one]) : "")
          return (
            <button
              key={one}
              type="button"
              aria-label={`${name(one)} — rasm olish`}
              onClick={() => {
                setColour(one)
                target.current = one
                camera.current?.click()
              }}
              onDragOver={(event) => {
                event.preventDefault()
                setOver(one)
              }}
              onDragLeave={() => setOver((was) => (was === one ? null : was))}
              onDrop={(event) => {
                event.preventDefault()
                setOver(null)
                setColour(one)
                void send(one, event.dataTransfer.files?.[0])
              }}
              className={cn(
                "w-28 overflow-hidden rounded-control border text-left transition-shadow",
                shot ? "border-good" : "border-dashed",
                one === colour && "ring-2 ring-brand/40",
                over === one && "border-brand ring-2 ring-brand",
              )}
            >
              <div className="relative aspect-square w-full bg-canvas">
                {shot ? (
                  <img src={shot} alt={name(one)} className="size-full object-cover" />
                ) : (
                  /* The rule, on the thing it is about: this colour is what
                     stays out of the shop. */
                  <div className="grid size-full place-items-center p-2">
                    <div className="space-y-1 text-center text-micro text-ink-faint">
                      <Camera className="mx-auto size-5" />
                      <div>
                        rasm yo'q — bu rang do'konga chiqmaydi
                      </div>
                    </div>
                  </div>
                )}
                {busy[one] ? (
                  <div className="absolute inset-0 grid place-items-center bg-surface/70">
                    <Loader2 className="size-6 animate-spin text-brand" />
                  </div>
                ) : null}
                {shot && !busy[one] ? (
                  <span className="absolute right-1 top-1 grid size-5 place-items-center rounded-full bg-good text-good-ink">
                    <Check className="size-3" />
                  </span>
                ) : null}
              </div>
              <div
                className={cn(
                  "truncate px-2 py-1 text-center text-micro font-medium",
                  shot ? "text-ink-soft" : "text-warn-ink",
                )}
              >
                {name(one)}
              </div>
            </button>
          )
        })}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="gap-2"
          onClick={() => {
            target.current = colour
            camera.current?.click()
          }}
        >
          <Camera className="size-4" />
          Kamera
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="gap-2"
          onClick={() => {
            target.current = colour
            gallery.current?.click()
          }}
        >
          <ImagePlus className="size-4" />
          Fayl
        </Button>
        <span className="inline-flex items-center gap-1 text-micro text-ink-soft">
          <Clipboard className="size-3.5" />
          yoki Ctrl+V — «{name(colour)}» rangiga
        </span>
      </div>

      <p className="text-micro text-ink-faint">
        {GUIDE} · faylni plitkaning ustiga tashlash ham bo'ladi
      </p>

      {/* `capture` asks the phone for the back camera directly. On a desktop
          it is an ordinary file input, which is the right fallback. */}
      <input
        ref={camera}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(event) => {
          void send(target.current, event.target.files?.[0])
          event.target.value = ""
        }}
      />
      <input
        ref={gallery}
        type="file"
        accept="image/*"
        hidden
        onChange={(event) => {
          void send(target.current, event.target.files?.[0])
          event.target.value = ""
        }}
      />

      <Problem error={error} />
    </div>
  )
}

export function Capture({
  colour,
  current,
  onTaken,
  guide = GUIDE,
  placeholder,
}: {
  colour: string
  current: string | undefined
  onTaken: (colour: string, url: string) => void
  /** The line under the frame. The catalogue shot wants white paper; the
   *  identification snapshot at the receiving bench wants nothing of the kind. */
  guide?: string
  placeholder?: string
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
      const media = await upload(file)
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
      className="space-y-2 rounded-panel border border-dashed p-3 focus:outline-none focus:ring-2 focus:ring-brand">
      <div className="relative mx-auto aspect-square w-full max-w-56 overflow-hidden rounded-control bg-canvas">
        {current ? (
          <img
            src={mediaUrl(current)}
            alt={colour}
            className="size-full object-contain" />
        ) : (
          <>
            {/* The guide frame. Consistency across the catalogue is worth more
                than the quality of any single shot. */}
            <div className="absolute inset-4 rounded-control border-2 border-dashed border-line" />
            <div className="grid size-full place-items-center text-micro text-ink-faint">
              {placeholder ?? colour ?? "rasm"}
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

      <p className="text-center text-micro text-ink-faint">{guide}</p>

      <div className="flex flex-wrap justify-center gap-2">
        <Button type="button" variant="secondary" className="gap-2" onClick={() => camera.current?.click()}
        >
          <Camera className="size-4" />
          Kamera
        </Button>
        <Button type="button" variant="secondary" className="gap-2" onClick={() => gallery.current?.click()}
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
