import { Link } from "react-router-dom"
import { ChevronRight } from "lucide-react"
import { Empty, Panel, Pill } from "@/components/ui"
import { useOffline } from "@/offline/OfflineProvider"
import { pickupQueued } from "@/offline/derive"
import { stamp } from "@/lib/format"

/**
 * Collections: goods a customer is sending back, which this courier is to pick
 * up while they are out anyway.
 *
 * A separate list from the round because it is separate work with a separate
 * shape — a run has several doors and each door can go its own way — and
 * folding it into the delivery list would put two different verbs behind the
 * same row.
 */
export function PickupsPage() {
  const { pickups, rows } = useOffline()

  return (
    <div className="mx-auto max-w-xl space-y-4 p-4">
      <h1 className="text-3xl font-bold">Yig'uv reyslari</h1>

      {pickups.data.length === 0 ? (
        <Empty>Yig'uv reysi yo'q.</Empty>
      ) : (
        <ul className="space-y-3">
          {pickups.data.map((run) => {
            const queued = pickupQueued(run, rows)
            return (
              <li key={run.id}>
                <Link to={`/pickups/${run.id}`} className="block">
                  <Panel tone={queued ? "pending" : "plain"}>
                    <div className="flex items-start gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-xl font-bold">{run.code}</span>
                          <Pill tone={run.status === "open" ? "brand" : "plain"}>
                            {statusWord(run.status)}
                          </Pill>
                        </div>
                        <p className="mt-1 text-lg text-muted">
                          {run.lines.length} ta tovar · {stamp(run.created_at)}
                        </p>
                        {queued ? (
                          <p className="mt-1 font-bold text-pending">
                            Topshirildi · yuborilmagan
                          </p>
                        ) : null}
                      </div>
                      <ChevronRight className="mt-1 size-6 shrink-0 text-muted" />
                    </div>
                  </Panel>
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

export function statusWord(status: string): string {
  switch (status) {
    case "open":
      return "Yig'iladi"
    case "collected":
      return "Topshirildi"
    case "received":
      return "Omborda"
    case "cancelled":
      return "Bekor qilingan"
    default:
      return status
  }
}
