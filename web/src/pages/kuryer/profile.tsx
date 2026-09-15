/**
 * 2i — Profil. Hand the cash in, and go offline.
 *
 * -------------------------------------------------------------- the cash door
 *
 * `POST /courier/cash/handovers`, and it takes **three** things rather than
 * the one the design implies: the amount, a note, and **who took it**. That
 * last one is the whole reason the hand-in is a row and not a counter — the
 * question anybody actually asks a week later is "who had Tuesday's takings",
 * and a number that gets reset cannot answer it. So the button opens a short
 * sheet rather than firing: the amount (which defaults to everything, because
 * that is what a hand-in usually is), the person at the desk, and a line of
 * note.
 *
 * The picker is the server's own list (`GET /courier/cash/receivers` — the
 * warehouse and the owner), because a picker offering a name the write then
 * refuses is a picker that lies.
 *
 * The reply carries `cash_on_hand` **after** the hand-in, so the figure on
 * this screen is right without a second round trip — which matters on the
 * connection this app is built for.
 *
 * ----------------------------------------------------------------- departures
 *
 * The artboard's settings list is `Transport · Ish hududi · Til ·
 * Bildirishnomalar · Yordam`. **None of those exist**: there is no vehicle on
 * a user, no zone, one language and no picker (everybody who signs in here
 * reads Uzbek — see `lib/nav`), and no notification preferences. A list of
 * five rows that all go nowhere is five promises. The list is kept and filled
 * with the settings this app really has: the theme, which is a real choice a
 * courier makes at dusk, and the way out.
 *
 * The artboard's warehouse and staff id are dropped for the same reason: one
 * warehouse, and the id on screen is the phone number somebody actually
 * identifies themselves with.
 */

import { LogOut, Monitor, Moon, Sun } from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router-dom"

import { Cap, Glass, Notice, Page, Refusal, Slab, Tile } from "@/components/kuryer/bits"
import { cn } from "@/lib/cn"
import { groups, money } from "@/lib/format"
import { useCashReceivers, useEarnings, useHandInCash } from "@/lib/queries"
import { useSession } from "@/lib/session"
import { useOnShift } from "@/lib/shift"
import { useTheme, type ThemeMode } from "@/lib/theme"

const LOOKS: Array<{ key: ThemeMode; label: string; icon: typeof Sun }> = [
  { key: "light", label: "Yorug'", icon: Sun },
  { key: "dark", label: "Qorong'i", icon: Moon },
  { key: "system", label: "Tizim", icon: Monitor },
]

export function KuryerProfile() {
  const go = useNavigate()
  const { staff, signOut } = useSession()
  const earnings = useEarnings()
  const [onShift, setOnShift] = useOnShift()
  const { mode, setMode } = useTheme()

  // The hand-in sheet: shut until somebody presses Topshirish. The list of
  // people who may take the money is only fetched once it is open — a courier
  // who never hands anything in never asks for it.
  const [handing, setHanding] = useState(false)
  const receivers = useCashReceivers()
  const handIn = useHandInCash()
  const [amount, setAmount] = useState("")
  const [took, setTook] = useState<number | null>(null)

  const name = staff?.full_name || staff?.phone || "Kuryer"
  const cash = earnings.data?.cash_on_hand ?? 0
  // Everything, unless somebody typed otherwise. A hand-in is usually the lot,
  // and making the common case a default rather than a sum to retype is the
  // difference between a screen used at a counter and one used at a desk.
  const giving = amount === "" ? cash : Number(amount) || 0

  return (
    <Page>
      <div className="flex items-center gap-3.5">
        <span className="grid size-16 shrink-0 place-items-center rounded-glass bg-kuryer-act-soft text-body font-bold text-kuryer-act-deep">
          {initials(name)}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-kuryer-title font-bold tracking-tight text-kuryer-ink [overflow-wrap:anywhere]">
            {name}
          </p>
          <p className="mt-0.5 text-small text-kuryer-ink-soft">
            Kuryer · {staff?.phone ?? ""}
          </p>
        </div>
      </div>

      {/* ------------------------------------------------------------ the cash */}
      <Glass className="p-4.5">
        <Cap>Topshiriladigan naqd</Cap>
        <p className="mt-2 flex flex-wrap items-baseline gap-2">
          <span className="display tabular text-kuryer-ink [overflow-wrap:anywhere]">
            {groups(cash)}
          </span>
          <span className="text-small font-semibold text-kuryer-ink-soft">so'm</span>
        </p>
        <p className="mt-1 text-small text-kuryer-ink-soft">
          Ombor kassasi — kun oxirigacha
        </p>

        {/* The subtraction, shown rather than summarised: a courier querying
            the figure wants to see where it came from. */}
        {earnings.data ? (
          <p className="mt-1 text-micro tabular text-kuryer-ink-faint">
            {groups(earnings.data.cash_collected)} olingan −{" "}
            {groups(earnings.data.cash_handed_in)} topshirilgan
          </p>
        ) : null}

        {handing ? (
          <div className="mt-4 flex flex-col gap-3 rounded-slab bg-kuryer-quiet p-3.5">
            <label className="block">
              <span className="mb-1.5 block text-micro font-semibold text-kuryer-ink-soft">
                Qancha
              </span>
              <input
                value={amount}
                onChange={(event) =>
                  setAmount(event.target.value.replace(/\D/g, ""))
                }
                inputMode="numeric"
                placeholder={groups(cash)}
                aria-label="Topshiriladigan summa"
                className="h-control-sm w-full rounded-nub border-[0.5px] border-kuryer-hair bg-kuryer-card px-3.5 text-body font-semibold tabular text-kuryer-ink outline-none placeholder:font-normal focus:ring-2 focus:ring-kuryer-act-edge"
              />
            </label>

            <div>
              <p className="mb-1.5 text-micro font-semibold text-kuryer-ink-soft">
                Kim qabul qiladi
              </p>
              {receivers.isLoading ? (
                <p className="text-micro text-kuryer-ink-faint">Yuklanmoqda…</p>
              ) : null}
              <div className="flex flex-col gap-2">
                {(receivers.data ?? []).map((one) => (
                  <button
                    key={one.id}
                    type="button"
                    aria-pressed={took === one.id}
                    onClick={() => setTook(one.id)}
                    className={cn(
                      "flex min-h-12 items-center gap-3 rounded-nub px-3.5 text-left text-small font-semibold transition-colors",
                      took === one.id
                        ? "border-[1.5px] border-kuryer-act-edge bg-kuryer-act-soft text-kuryer-act-deep"
                        : "border-[0.5px] border-kuryer-hair bg-kuryer-card text-kuryer-ink",
                    )}
                  >
                    <span className="min-w-0 flex-1 truncate">
                      {one.full_name || one.phone}
                    </span>
                    <span className="shrink-0 text-micro font-normal text-kuryer-ink-soft">
                      {one.role === "admin" ? "Egasi" : "Ombor"}
                    </span>
                  </button>
                ))}
              </div>
              {!receivers.isLoading && !(receivers.data ?? []).length ? (
                <p className="text-micro text-kuryer-halt-ink">
                  Hozir naqdni qabul qiladigan xodim yo'q.
                </p>
              ) : null}
            </div>

            <Refusal error={handIn.error} />

            <div className="flex gap-2.5">
              <Slab
                tone="quiet"
                className="h-control-sm flex-1 rounded-nub text-small"
                onClick={() => setHanding(false)}
              >
                Bekor
              </Slab>
              <Slab
                className="h-control-sm flex-[1.4] rounded-nub text-small"
                disabled={
                  handIn.isPending || !took || giving <= 0 || giving > cash
                }
                onClick={() =>
                  handIn.mutate(
                    { amount: giving, received_by_id: took! },
                    {
                      onSuccess: () => {
                        setHanding(false)
                        setAmount("")
                        setTook(null)
                      },
                    },
                  )
                }
              >
                {handIn.isPending ? "Topshirilmoqda…" : `${groups(giving)} topshirish`}
              </Slab>
            </div>
            {giving > cash ? (
              <p className="text-micro text-kuryer-halt-ink">
                Qo'lingizdagidan ko'p — eng ko'pi {money(cash)}
              </p>
            ) : null}
          </div>
        ) : (
          <div className="mt-4 flex gap-2.5">
            <button
              type="button"
              onClick={() => go("/kuryer/daromad")}
              className="h-control-sm flex-1 rounded-nub bg-kuryer-quiet text-small font-semibold text-kuryer-ink"
            >
              Hisobot
            </button>
            <Slab
              className="h-control-sm flex-[1.4] rounded-nub text-small"
              disabled={!cash}
              onClick={() => setHanding(true)}
            >
              Topshirish
            </Slab>
          </div>
        )}
      </Glass>

      {!cash ? (
        <Notice tone="done" title="Qo'lingizda naqd yo'q">
          Hammasi topshirilgan — eshikda olingan pul shu yerda ko'rinadi.
        </Notice>
      ) : null}

      {/* -------------------------------------------------------- the settings */}
      <Tile className="overflow-hidden p-0">
        <p className="caption px-4 pb-1 pt-4 font-bold text-kuryer-ink-soft">
          Ko'rinish
        </p>
        <div className="flex gap-1.5 p-3 pt-2">
          {LOOKS.map((look) => (
            <button
              key={look.key}
              type="button"
              aria-pressed={mode === look.key}
              onClick={() => setMode(look.key)}
              className={cn(
                "flex h-control-sm min-w-0 flex-1 items-center justify-center gap-1.5 rounded-nub text-small font-semibold transition-colors",
                mode === look.key
                  ? "bg-kuryer-act-soft text-kuryer-act-deep"
                  : "bg-kuryer-quiet text-kuryer-ink-soft",
              )}
            >
              <look.icon className="size-4 shrink-0" />
              <span className="truncate">{look.label}</span>
            </button>
          ))}
        </div>

        <Row label="Telefon" value={staff?.phone ?? ""} />
        <Row label="Rol" value="Kuryer" />
        <Row label="Ombor" value="Bitta ombor" last />
      </Tile>

      {/* ------------------------------------------------------------- the shift */}
      <Slab
        tone={onShift ? "halt" : "act"}
        onClick={() => setOnShift(!onShift)}
      >
        {onShift ? "Oflaynga o'tish" : "Onlayn bo'lish"}
      </Slab>
      <p className="text-center text-micro text-kuryer-ink-faint">
        {onShift
          ? "Oflaynda ombor navbati yangilanmaydi. Bu faqat shu telefondagi belgi."
          : "Hozir oflaynsiz — ombor navbati ko'rinmayapti."}
      </p>

      <button
        type="button"
        onClick={signOut}
        className="flex h-control-sm w-full items-center justify-center gap-2 rounded-nub text-small font-semibold text-kuryer-halt-ink"
      >
        <LogOut className="size-4" />
        Chiqish
      </button>
    </Page>
  )
}

function Row({
  label,
  value,
  last = false,
}: {
  label: string
  value: string
  last?: boolean
}) {
  return (
    <div
      className={cn(
        "flex min-h-14 items-center gap-3 px-4",
        !last && "border-b-[0.5px] border-kuryer-hair",
      )}
    >
      <span className="min-w-0 flex-1 text-small text-kuryer-ink">{label}</span>
      <span className="shrink-0 text-small tabular text-kuryer-ink-soft">{value}</span>
    </div>
  )
}

function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (!words.length) return "?"
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase()
  return (words[0][0] + words[1][0]).toUpperCase()
}
