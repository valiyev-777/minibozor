/**
 * 2e — Tasdiqlash. The photograph and who took the goods.
 *
 * **No SMS code**, which is the design's own note and the server's position
 * too: `DeliverIn` requires `recipient_name` and nothing else. A code needs a
 * network at the door, a customer holding their own phone, and a courier
 * waiting while both work — and what it would prove is already proved better
 * by a name and a doorstep.
 *
 * The photograph is **optional and the name is not**, because that is exactly
 * the trade: a name is one field somebody can always fill in while standing in
 * front of the person who took the goods; an upload needs signal, and a
 * basement has none. The upload happens here rather than at the end so the
 * courier is not holding a parcel while a JPEG crawls up a 3G link — and if it
 * fails, the screen says so and lets them carry on.
 *
 * Nothing is written to the server from this screen. It fills in the draft
 * (`components/kuryer/shell`) and hands over to the payment screen, which is
 * the one that posts the delivery — one write, keyed, at the end of the three
 * screens, so a retry in a lift replays rather than delivering twice.
 */

import { Camera, Check, Loader2 } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"

import { Cap, Glass, Loading, Notice, Refusal, Slab, Title } from "@/components/kuryer/bits"
import { Page } from "@/components/kuryer/bits"
import { useDraft } from "@/components/kuryer/shell"
import { mediaUrl } from "@/components/photo-step"
import { tokens } from "@/lib/api"
import { cn } from "@/lib/cn"
import { time } from "@/lib/format"
import { useMyRound } from "@/lib/queries"
import type { Media } from "@/lib/types"

/**
 * Who opened the door. The name that is actually recorded is the customer's
 * unless somebody else took it, in which case the answer is prefixed onto it —
 * "Qorovul · Malika Rahimova" is a sentence an operator can act on, and
 * "Malika Rahimova" alone when the guard signed for it is not.
 */
export const WHO = [
  { label: "Mijoz o'zi", prefix: "" },
  { label: "Qorovul / resepshn", prefix: "Qorovul" },
  { label: "Qo'shni yoki oila a'zosi", prefix: "Qo'shni" },
]

/** The one string the server records, built once at the moment of the write. */
export function recipientOf(who: number, name: string): string {
  const prefix = WHO[who]?.prefix ?? ""
  const clean = name.trim()
  return prefix ? `${prefix} · ${clean}` : clean
}

export function KuryerConfirm() {
  const { id } = useParams()
  const go = useNavigate()
  const orderId = Number(id)
  const round = useMyRound()
  const stop = (round.data ?? []).find((one) => one.id === orderId)
  const { draft, open, set } = useDraft()

  const [busy, setBusy] = useState(false)
  const [trouble, setTrouble] = useState<unknown>(null)
  const [shotAt, setShotAt] = useState<string>("")
  const camera = useRef<HTMLInputElement>(null)

  // Opened as the screen arrives, and idempotent — a re-render must not wipe
  // a photograph that is already up.
  useEffect(() => {
    if (stop) open(stop.id, stop.recipient_name)
  }, [stop, open])

  if (round.isLoading) {
    return (
      <div className="grid h-full place-items-center bg-kuryer-ground">
        <Loading what="Bekat" />
      </div>
    )
  }

  if (!stop) {
    return (
      <Page>
        <Notice tone="halt" title="Bu bekat marshrutda yo'q">
          Yetkazilgan yoki boshqa kuryerga o'tgan bo'lishi mumkin.
        </Notice>
        <Slab onClick={() => go("/kuryer/marshrut")}>Marshrutga qaytish</Slab>
      </Page>
    )
  }

  const mine = draft && draft.orderId === stop.id ? draft : null
  const who = mine?.who ?? 0
  const name = mine?.recipientName ?? stop.recipient_name

  async function send(file: File | null | undefined) {
    if (!file) return
    setBusy(true)
    setTrouble(null)
    try {
      // Not through `api()`: this posts a multipart body, and a helper that
      // handles both is a helper with a branch in it. `square=false` — a
      // doorstep is not a product photograph.
      const form = new FormData()
      form.append("file", file)
      const response = await fetch(
        `${import.meta.env.VITE_API_URL ?? "http://localhost:8000"}/api/v1/media`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${tokens.access() ?? ""}` },
          body: form,
        },
      )
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as {
          detail?: string
        } | null
        throw new Error(body?.detail ?? "Surat yuklanmadi")
      }
      const media = (await response.json()) as Media
      set({ photoUrl: media.media_url })
      setShotAt(time(new Date()))
    } catch (problem) {
      setTrouble(problem)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Page>
      <Title over={`Buyurtma ${stop.code} · ${stop.recipient_name || "Mijoz"}`}>
        Tasdiqlash
      </Title>

      {/* --------------------------------------------------------- 1 · the photo */}
      <Glass>
        <Cap>1 · Yetkazish fotosi</Cap>
        <div className="mt-3 flex gap-2.5">
          <button
            type="button"
            disabled={busy}
            onClick={() => camera.current?.click()}
            className="flex h-28 flex-1 flex-col items-center justify-center gap-2 rounded-slab border-[1.5px] border-dashed border-kuryer-grab bg-kuryer-quiet text-kuryer-ink-soft"
          >
            {busy ? (
              <Loader2 className="size-6 animate-spin text-kuryer-act" />
            ) : (
              <Camera className="size-6" />
            )}
            <span className="text-small font-semibold">
              {busy ? "Yuklanmoqda…" : mine?.photoUrl ? "Qayta olish" : "Surat olish"}
            </span>
          </button>

          <div className="relative h-28 flex-1 overflow-hidden rounded-slab bg-kuryer-quiet">
            {mine?.photoUrl ? (
              <>
                <img
                  src={mediaUrl(mine.photoUrl)}
                  alt="Yetkazish fotosi"
                  className="size-full object-cover"
                />
                <span className="absolute bottom-2 left-2 rounded-lg bg-kuryer-card/85 px-2 py-1 text-micro font-semibold text-kuryer-ink">
                  Eshik oldi{shotAt ? ` · ${shotAt}` : ""}
                </span>
              </>
            ) : (
              <span className="grid size-full place-items-center px-3 text-center text-micro text-kuryer-ink-faint">
                Surat majburiy emas
              </span>
            )}
          </div>
        </div>
        <Refusal error={trouble} />
        {/* `capture` asks the phone for the back camera directly; on a desktop
            it is an ordinary file input, which is the right fallback. */}
        <input
          ref={camera}
          type="file"
          accept="image/*"
          capture="environment"
          hidden
          onChange={(event) => {
            void send(event.target.files?.[0])
            event.target.value = ""
          }}
        />
      </Glass>

      {/* ---------------------------------------------------------- 2 · who took it */}
      <Glass>
        <Cap>2 · Kim qabul qildi</Cap>
        <div className="mt-3 flex flex-col gap-2.5">
          {WHO.map((one, n) => (
            <button
              key={one.label}
              type="button"
              aria-pressed={who === n}
              onClick={() => set({ who: n })}
              className={cn(
                "flex min-h-14 items-center gap-3 rounded-slab px-3.5 text-left transition-colors",
                who === n
                  ? "border-[1.5px] border-kuryer-act-edge bg-kuryer-act-soft"
                  : "border-[0.5px] border-kuryer-hair bg-kuryer-card",
              )}
            >
              <span
                aria-hidden
                className={cn(
                  "grid size-5.5 shrink-0 place-items-center rounded-full border-2",
                  who === n ? "border-kuryer-act" : "border-kuryer-grab",
                )}
              >
                {who === n ? (
                  <span className="size-2.5 rounded-full bg-kuryer-act" />
                ) : null}
              </span>
              <span className="text-small font-semibold text-kuryer-ink">
                {one.label}
              </span>
            </button>
          ))}
        </div>

        {/* The name is the required field, so it is editable rather than
            assumed: the order says who it is for, and the person at the door
            is whoever is at the door. */}
        <label className="mt-3 block">
          <span className="mb-1.5 block text-micro font-semibold text-kuryer-ink-soft">
            Ism · familiya
          </span>
          <input
            value={name}
            onChange={(event) => set({ recipientName: event.target.value })}
            aria-label="Kim qabul qildi"
            className="h-control-sm w-full rounded-nub border-[0.5px] border-kuryer-hair bg-kuryer-card px-3.5 text-small text-kuryer-ink outline-none placeholder:text-kuryer-ink-faint focus:ring-2 focus:ring-kuryer-act-edge"
            placeholder="Kim qabul qildi"
          />
        </label>
      </Glass>

      <Notice tone="done" title="Surat va vaqt avtomatik saqlanadi — dispetcher ko'radi">
        {mine?.photoUrl
          ? "Surat yuklandi"
          : "Suratsiz ham yakunlash mumkin — aloqa bo'lmasa to'xtab qolmang"}
      </Notice>

      <Slab
        tone="done"
        disabled={!name.trim()}
        onClick={() => {
          // Only the name is stored. The prefix is applied once, by the
          // screen that actually posts — see `recipientOf` — because setting
          // it here would stack a second `Qorovul ·` onto the name every time
          // somebody stepped back to change the photograph.
          set({ recipientName: name.trim() })
          go(`/kuryer/marshrut/${stop.id}/tolov`)
        }}
      >
        <Check className="size-5" />
        To'lovga o'tish
      </Slab>
    </Page>
  )
}
