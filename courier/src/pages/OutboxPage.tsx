import * as React from "react"
import { Send, Trash2 } from "lucide-react"
import { Button, Empty, Panel, Pill } from "@/components/ui"
import { useOffline } from "@/offline/OfflineProvider"
import { useSession } from "@/auth/session"
import { sum, waited } from "@/lib/format"
import type { OutboxRow } from "@/offline/outbox"

/**
 * What the courier has done that the server has not heard about.
 *
 * This screen is a requirement rather than a debugging aid. A courier who
 * finishes a round with eleven actions queued and no idea they are queued is a
 * courier who hands the phone back and goes home; the cash on it does not
 * match anything, and nobody finds out until somebody counts. So the count is
 * on every screen in the header, and this is where it is spelled out: what,
 * when, how many tries, and — if the server refused it — the server's own
 * sentence about why.
 *
 * There is one destructive control on it, and it is deliberately only offered
 * for rows the server has already refused. A pending row holds work the
 * courier actually did.
 */
export function OutboxPage() {
  const { rows, sync, syncing, reachable, unsent } = useOffline()
  const session = useSession()

  const pending = rows.filter((row) => !row.blocked)
  const blocked = rows.filter((row) => row.blocked)

  return (
    <div className="mx-auto max-w-xl space-y-4 p-4 pb-safe">
      <h1 className="text-3xl font-bold">
        {unsent.pending === 0 && unsent.blocked === 0
          ? "Navbat bo'sh"
          : `Yuborilmagan ${unsent.pending} amal`}
      </h1>

      <p className="text-base text-muted">
        Bu amallar telefoningizda saqlangan. Tarmoq qaytganda o'zi yuboriladi — ilovani yopsangiz
        ham, telefon o'chsa ham yo'qolmaydi.
      </p>

      {rows.length === 0 ? (
        <Empty>Hammasi yuborilgan.</Empty>
      ) : (
        <Button onClick={() => void sync()} busy={syncing} disabled={!reachable}>
          <Send className="size-6" />
          {reachable ? "Hozir yuborish" : "Tarmoq kutilmoqda"}
        </Button>
      )}

      {pending.length > 0 ? (
        <ul className="space-y-3">
          {pending.map((row) => (
            <RowCard key={row.id} row={row} />
          ))}
        </ul>
      ) : null}

      {blocked.length > 0 ? (
        <>
          <h2 className="pt-4 text-xl font-bold text-bad">Server rad etdi</h2>
          <p className="text-base text-muted">
            Bu amallarni qayta yuborish foyda bermaydi. Operator bilan gaplashing, keyin o'chiring.
          </p>
          <ul className="space-y-3">
            {blocked.map((row) => (
              <RowCard key={row.id} row={row} />
            ))}
          </ul>
        </>
      ) : null}

      <div className="pt-6">
        <Button tone="ghost" onClick={() => void session.signOut()}>
          Chiqish
        </Button>
        {rows.length > 0 ? (
          <p className="mt-2 text-center text-base text-pending">
            Diqqat: navbatda {rows.length} ta amal bor. Chiqishdan oldin ularni yuboring.
          </p>
        ) : null}
      </div>
    </div>
  )
}

function RowCard({ row }: { row: OutboxRow }) {
  const { discard } = useOffline()
  const [confirming, setConfirming] = React.useState(false)

  return (
    <li>
      <Panel tone={row.blocked ? "bad" : "pending"}>
        <div className="flex items-start justify-between gap-2">
          <span className="text-xl font-semibold">{row.label}</span>
          <Pill tone={row.blocked ? "bad" : "pending"}>
            {row.blocked ? "Xato" : "Kutmoqda"}
          </Pill>
        </div>

        <p className="mt-1 text-base text-muted">
          {waited(row.createdAt)}
          {row.attempts > 0 ? ` · ${row.attempts} urinish` : ""}
        </p>

        {row.cash > 0 ? (
          <p className="mt-1 text-lg font-semibold">Naqd: {sum(row.cash)}</p>
        ) : null}

        {row.lastError ? (
          <p className={row.blocked ? "mt-2 text-lg font-semibold text-bad" : "mt-2 text-base text-muted"}>
            {row.lastError}
          </p>
        ) : null}

        {row.blocked && row.id !== undefined ? (
          confirming ? (
            <div className="mt-3 space-y-2">
              <p className="text-base font-semibold">
                O'chirilsinmi? Bu amal serverga yetib bormaydi.
              </p>
              <div className="grid grid-cols-2 gap-2">
                <Button tone="bad" onClick={() => void discard(row.id!)}>
                  O'chirish
                </Button>
                <Button tone="ghost" onClick={() => setConfirming(false)}>
                  Bekor
                </Button>
              </div>
            </div>
          ) : (
            <Button tone="ghost" className="mt-3" onClick={() => setConfirming(true)}>
              <Trash2 className="size-6" />
              Amalni o'chirish
            </Button>
          )
        ) : null}
      </Panel>
    </li>
  )
}
