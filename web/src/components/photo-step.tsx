/**
 * Every photograph on a card, in one place — the strip a colour owns.
 *
 * Market goods arrive with no pictures, so the only ones that will ever exist
 * are taken here. A colour without one keeps that colour out of the shop, and
 * the reason is written on the strip itself, at the moment somebody is looking
 * at it — not in a paragraph they have to connect to a colour themselves.
 *
 * **Why this is one component and not two.** It used to be two, stacked: a row
 * of colour tiles that showed one picture per colour, and underneath it a
 * gallery that listed every picture with its own delete buttons and its own
 * `muqova` badges. On a card with four colours and nine photographs that is
 * two different answers to "what has this card got" on one screen, and the two
 * disagreed — the tiles showed the *last* photograph of a colour while the
 * gallery called the *first* one the cover. So: one strip per colour, the
 * cover at the front of it, and everything a person can do to a photograph
 * done on the photograph.
 *
 * **One strip answers all five questions.** Which picture the customer sees
 * (the first tile, ringed, captioned `muqova`), what else there is (the rest
 * of the strip), how to add (the dashed tile at the end, or camera / file /
 * Ctrl+V / a file dropped anywhere on the strip), how to promote (`muqova
 * qilish` under any tile that is not the cover), how to remove (the bin on the
 * tile). The sentence this replaces — *"delete the ones in front of it"* — was
 * a workaround for a missing endpoint, and the endpoint exists now.
 *
 * **Adding to a colour that already has one is the quiet mistake.** The person
 * means "use this picture instead" and the server appends, so the shot they
 * just took becomes the fifth photograph of a colour and the customer never
 * sees it. The new tile lands where they can see it and the strip asks, once,
 * whether they meant to change the cover.
 *
 * The upload is shown as it happens — the local file appears instantly under a
 * spinner — because a photograph that arrives three seconds later reads as a
 * failure.
 *
 * There is no background removal here and there will not be: the goods are
 * shot against a sheet of white paper. `rembg` and friends mean onnxruntime
 * and a 150MB model for a problem a 15,000 so'm sheet of paper already solves.
 */

import { Camera, Check, Clipboard, ImagePlus, Loader2, Trash2 } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { Problem } from "@/components/page"
import { Button } from "@/components/ui/button"
import { tokens } from "@/lib/api"
import { cn } from "@/lib/cn"
import type { AdminImage, Media } from "@/lib/types"

const GUIDE = "oq fonda · bitta tovar · qo'l ko'rinmasin"

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

/** The colour's own name, or the word for a card that has only one of them. */
const name = (colour: string) => colour || "umumiy"

/** A photograph on its way up, held locally until the server's copy lands. */
type Pending = {
  colour: string
  /** The object URL of the chosen file — the tile shown under the spinner. */
  local: string
  /** How many photographs this colour had when the shutter clicked. The
   *  moment the server answers with more than that, the real tile is on
   *  screen and this one is dropped. */
  was: number
}

export function Photos({
  colours,
  images,
  live,
  onAdd,
  onCover,
  onDelete,
  covering = false,
  deleting = false,
  cardGallery = false,
}: {
  /** The card's colours, from the grid. A colour with no photograph is the
   *  reason the whole card stays out of the shop, so it gets a strip whether
   *  or not anything has been hung on it. */
  colours: string[]
  /** Every photograph on the card, in the server's order. */
  images: AdminImage[]
  /** On sale: taking the last photograph off a colour drops the card back to
   *  draft, and that deletion is warned about by name. */
  live: boolean
  onAdd: (colour: string, url: string) => void
  /** Promote to cover. Admin only on the server — omit it and the control is
   *  not drawn, rather than drawn and answered with a 403. */
  onCover?: (imageId: number) => void
  onDelete: (imageId: number) => void
  covering?: boolean
  deleting?: boolean
  /** This is the card's own gallery (§5.2 ·8), not a colour's strip. Same
   *  machinery — one list of photographs attached to no colour — but none of
   *  the colour framing applies to it: it has no name, it gates nothing, and
   *  calling it "umumiy" makes the screen claim the card has a colour called
   *  that. Mounted this way by `card-form`; every other caller is colours. */
  cardGallery?: boolean
}) {
  // Grouped by colour in the order the server sent them, which is the order
  // the shop reads: first of a colour is that colour's cover. Not re-sorted
  // here — the promote endpoint renumbers the whole card, and a second set of
  // rules in the browser is how the panel and the shop come to disagree.
  const strips = new Map<string, AdminImage[]>()
  for (const one of colours) strips.set(one, [])
  for (const image of images) {
    const held = strips.get(image.colour)
    if (held) held.push(image)
    // A photograph of a colour the grid no longer has — a size booked in by
    // mistake and taken back out. It still needs a strip, or it can never be
    // deleted.
    else strips.set(image.colour, [image])
  }

  // Every strip on screen, in the order they are drawn, and one string of the
  // same so an effect can depend on the list without depending on the array.
  const drawn = [...strips.keys()]
  const order = drawn.join("\u0000")

  // Which strip Ctrl+V lands on. Starts on the first colour still missing a
  // photograph: that is what the person opened this for.
  const [colour, setColour] = useState(
    colours.find((one) => !(strips.get(one) ?? []).length) ?? colours[0] ?? "",
  )
  const [pending, setPending] = useState<Pending[]>([])
  const [over, setOver] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)
  // The colour a photograph was just appended to, while it already had one.
  // The strip asks whether they meant to change the cover — see the file
  // comment: this is the mistake nobody could see.
  const [appended, setAppended] = useState<string | null>(null)
  const [asked, setAsked] = useState<number | null>(null)
  const camera = useRef<HTMLInputElement>(null)
  const gallery = useRef<HTMLInputElement>(null)
  // Which strip the open file dialog belongs to — set by the click, read by
  // the change event, because state set in between would race the dialog.
  const target = useRef(colour)

  useEffect(() => {
    // Checked against the strips actually drawn, not against the grid's
    // colours. A colourless pile is a strip like any other; measuring the
    // selection against the grid bounced it straight back to the first
    // colour, and since the ref follows the selection, the file chosen from
    // the colourless strip landed on that first colour instead — "I add a
    // photograph at the bottom and it comes out at the top".
    if (!drawn.includes(colour)) setColour(drawn[0] ?? "")
    // `order` rather than `drawn`: a fresh array every render would run this
    // on every render.

  }, [order, colour])

  // And kept level with the selection the rest of the time. The ref was only
  // ever written by a click, so it held whatever the *first* render chose —
  // and the first render happens before the grid has loaded, when the card
  // looks like it has no colours at all and the answer is `""`. A file chosen
  // without touching a tile first then hung itself on a colour called
  // `umumiy`, which satisfies no gate and which nothing on the old panel drew.
  useEffect(() => {
    target.current = colour
  }, [colour])

  // Drop an optimistic tile once the server's own copy is in the list.
  useEffect(() => {
    setPending((was) => {
      const next = was.filter((one) => {
        const now = images.filter((image) => image.colour === one.colour).length
        if (now > one.was) {
          URL.revokeObjectURL(one.local)
          return false
        }
        return true
      })
      return next.length === was.length ? was : next
    })
  }, [images])

  async function send(one: string, file: File | null | undefined) {
    if (!file || !file.type.startsWith("image/")) return
    const had = (strips.get(one) ?? []).length
    const local = URL.createObjectURL(file)
    setPending((was) => [...was, { colour: one, local, was: had }])
    setError(null)
    try {
      const media = await upload(file)
      onAdd(one, media.media_url)
      // Appended, not replaced. Said out loud only when there was something to
      // replace — on the first photograph of a colour there is no question.
      if (had > 0) setAppended(one)
    } catch (problem) {
      // Back to what the server has: an optimistic tile for a failed upload
      // would read as success.
      URL.revokeObjectURL(local)
      setPending((was) => was.filter((entry) => entry.local !== local))
      setError(problem)
    }
  }

  // Paste lands on the selected strip from anywhere on the page — the person
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

  const going = images.find((one) => one.id === asked) ?? null

  function pick(one: string, input: React.RefObject<HTMLInputElement | null>) {
    setColour(one)
    target.current = one
    input.current?.click()
  }

  return (
    <div className="space-y-3">
      {[...strips].map(([one, shots]) => {
        const rising = pending.filter((entry) => entry.colour === one)
        const empty = !shots.length && !rising.length
        // A colourless pile on a card that does have colours: photographs
        // attached to nothing. On a card with no colours at all, the
        // colourless strip *is* the card and is perfectly ordinary.
        const stray = !cardGallery && one === "" && colours.length > 0
        // The last photograph of a colour on a live card is not an ordinary
        // deletion: the server drops the card out of the shop, deliberately.
        const falls = Boolean(going && going.colour === one && shots.length === 1 && live)

        return (
          <div
            key={one}
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
              "rounded-control border p-2 transition-colors",
              over === one
                ? "border-brand bg-brand-soft"
                : empty
                  ? "border-dashed border-warn/40 bg-warn-soft/40"
                  : "border-line",
              one === colour && over !== one && "ring-2 ring-brand/25",
            )}
          >
            <div className="mb-2 flex flex-wrap items-baseline gap-x-2 gap-y-1">
              {cardGallery ? null : (
                <span className="text-small font-medium">{name(one)}</span>
              )}
              {empty && cardGallery ? (
                /* The gallery holds nothing back. A card with no general
                   photograph is publishable; a colour without one is not. */
                <span className="text-micro text-ink-soft">
                  hali rasm yo'q — ixtiyoriy
                </span>
              ) : empty ? (
                /* The rule, on the thing it is about: this colour is what
                   stays out of the shop. */
                <span className="text-micro font-medium text-warn-ink">
                  rasm yo'q — bu rang do'konga chiqmaydi
                </span>
              ) : stray ? (
                /* A pile with no colour on a card that has colours. It counts
                   for no colour's gate, so promising the customer sees it is
                   the screen telling a lie — and "what is the difference
                   between this and the strips above?" is the first thing
                   anybody asks when they meet one. */
                <span className="text-micro text-warn-ink">
                  rangga biriktirilmagan — hech qaysi rang uchun hisoblanmaydi
                </span>
              ) : (
                <span className="text-micro text-ink-soft">
                  {shots.length > 1
                    ? `${shots.length} ta rasm — birinchisini mijoz ko'radi`
                    : "mijoz ko'radigan rasm"}
                </span>
              )}
              {one === colour ? (
                <span className="ml-auto inline-flex items-center gap-1 text-micro text-ink-faint">
                  <Clipboard className="size-3.5" />
                  Ctrl+V shu yerga
                </span>
              ) : null}
            </div>

            <div className="flex flex-wrap items-start gap-2">
              {shots.map((image, at) => (
                <figure key={image.id} className={at === 0 ? "w-24" : "w-20"}>
                  <div
                    className={cn(
                      "relative overflow-hidden rounded-control",
                      at === 0 && "ring-2 ring-brand",
                      asked === image.id && "ring-2 ring-danger",
                    )}
                  >
                    <img
                      src={mediaUrl(image.url)}
                      alt={name(one)}
                      className="aspect-square w-full bg-canvas object-cover"
                    />
                    <button
                      type="button"
                      aria-label={`${name(one)} rasmini o'chirish`}
                      onClick={() => setAsked(asked === image.id ? null : image.id)}
                      className="absolute right-1 top-1 grid size-5 place-items-center rounded-full bg-surface/90 text-ink-soft shadow-panel transition-colors hover:text-danger"
                    >
                      <Trash2 className="size-3" />
                    </button>
                    {at === 0 ? (
                      <span className="absolute left-1 top-1 grid size-5 place-items-center rounded-full bg-brand text-brand-ink">
                        <Check className="size-3" />
                      </span>
                    ) : null}
                  </div>
                  {/* Under the tile rather than over it: a badge inside eighty
                      pixels either covers the goods or gets clipped, and the
                      one thing this label must do is be readable. */}
                  {at === 0 ? (
                    <figcaption className="pt-1 text-center text-micro font-medium text-brand-deep">
                      muqova
                    </figcaption>
                  ) : onCover ? (
                    <button
                      type="button"
                      disabled={covering}
                      onClick={() => {
                        setAppended(null)
                        onCover(image.id)
                      }}
                      className="mt-1 w-full truncate rounded-control py-0.5 text-center text-micro text-ink-soft transition-colors hover:bg-brand-soft hover:text-brand-deep disabled:opacity-50"
                    >
                      muqova qilish
                    </button>
                  ) : (
                    <figcaption className="pt-1 text-center text-micro text-ink-faint">
                      qo'shimcha
                    </figcaption>
                  )}
                </figure>
              ))}

              {rising.map((entry) => (
                <div key={entry.local} className="w-20">
                  <div className="relative overflow-hidden rounded-control">
                    <img
                      src={entry.local}
                      alt=""
                      className="aspect-square w-full bg-canvas object-cover"
                    />
                    <div className="absolute inset-0 grid place-items-center bg-surface/70">
                      <Loader2 className="size-6 animate-spin text-brand" />
                    </div>
                  </div>
                  <div className="pt-1 text-center text-micro text-ink-faint">
                    yuklanmoqda
                  </div>
                </div>
              ))}

              <button
                type="button"
                aria-label={`${name(one)} — rasm qo'shish`}
                onClick={() => pick(one, camera)}
                className="w-20 text-left"
              >
                <div
                  className={cn(
                    "grid aspect-square w-full place-items-center rounded-control border border-dashed bg-canvas text-ink-faint transition-colors hover:border-brand hover:text-brand",
                    empty && "border-warn/60 text-warn-ink",
                  )}
                >
                  {empty ? (
                    <Camera className="size-5" />
                  ) : (
                    <ImagePlus className="size-5" />
                  )}
                </div>
                <div className="truncate pt-1 text-center text-micro text-ink-soft">
                  {empty ? "rasm olish" : "yana"}
                </div>
              </button>
            </div>

            {/* **Every strip has its own pair.** There used to be one Kamera
                and one Fayl at the foot of the whole list, acting on whichever
                strip happened to be selected — so two `Fayl` uploads in a row
                both landed on `Oq`, and the only way to aim at the second
                colour was to click a tile first, which opens the camera. The
                target colour is now always the strip being touched. */}
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="gap-2"
                onClick={() => pick(one, camera)}
              >
                <Camera className="size-4" />
                Kamera
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="gap-2"
                onClick={() => pick(one, gallery)}
              >
                <ImagePlus className="size-4" />
                Fayl
              </Button>
              <span className="text-micro text-ink-soft">
                {cardGallery ? "umumiy rasmlarga" : `«${name(one)}» rangiga`}
              </span>
            </div>

            {/* The quiet mistake, said out loud on the strip it happened to.
                One tap turns "I appended by accident" into "that is the one I
                meant", which is the whole complaint. */}
            {appended === one && onCover && shots.length > 1 ? (
              <div className="mt-2 flex flex-wrap items-center gap-2 rounded-control bg-brand-soft p-2">
                <span className="min-w-40 flex-1 text-micro text-brand-deep">
                  Yangi rasm oxiriga qo'shildi — muqova o'zgargani yo'q. Mijoz
                  shu yangisini ko'rsinmi?
                </span>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={covering}
                  onClick={() => {
                    onCover(shots[shots.length - 1].id)
                    setAppended(null)
                  }}
                >
                  Muqova qilsin
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setAppended(null)}>
                  Yo'q
                </Button>
              </div>
            ) : null}

            {/* Two taps, and the second one is the sentence — the same way the
                card itself is deleted on this screen. */}
            {going && going.colour === one ? (
              <div
                className={cn(
                  "mt-2 flex flex-wrap items-center gap-2 rounded-control border p-2",
                  falls ? "border-danger bg-danger-soft" : "border-panel-edge",
                )}
              >
                <span
                  className={cn(
                    "min-w-40 flex-1 text-micro",
                    falls ? "text-danger" : "text-ink-soft",
                  )}
                >
                  {falls
                    ? `«${name(one)}» rangining oxirgi rasmi. O'chirilsa karta sotuvdan tushadi — rasmsiz rang do'konga chiqmaydi.`
                    : `«${name(one)}» rasmi o'chiriladi — aniqmi?`}
                </span>
                <Button
                  variant="danger"
                  size="sm"
                  disabled={deleting}
                  onClick={() => onDelete(going.id)}
                >
                  {deleting ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : falls ? (
                    "Ha, sotuvdan tushsin"
                  ) : (
                    "Ha"
                  )}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setAsked(null)}>
                  Yo'q
                </Button>
              </div>
            ) : null}
          </div>
        )
      })}

      <p className="text-micro text-ink-faint">
        {GUIDE} · faylni rang qatoriga tashlash ham bo'ladi
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
        {/* The scrim takes the surface token, not a raw white: a hard-coded
            one is invisible over a dark theme's own background. */}
        {busy ? (
          <div className="absolute inset-0 grid place-items-center bg-surface/70">
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
