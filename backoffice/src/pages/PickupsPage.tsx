import * as React from "react"
import { PackageCheck, Plus } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Courier, PickupRun, Return } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Hint, Label, Select } from "@/ui/field"
import { Async, Empty } from "@/ui/states"
import { Panel, Row } from "@/components/Panel"
import { PageTitle } from "@/components/Shell"
import { useAction } from "@/lib/mutate"
import { moment } from "@/lib/format"
import { pickupStatus, t } from "@/lib/labels"

/**
 * The van, out and back.
 *
 * `collected` and `received` are two different people's claims and are kept
 * apart on purpose: the courier says they have the goods, the warehouse says
 * they arrived. Collapsing them would make "the courier collected it and it
 * never reached us" unsayable, which is the one case worth being able to say —
 * so the button here is the *warehouse's* half, and it only appears on a run
 * the courier has already closed.
 *
 * Booking a run in deliberately does not put anything on a shelf. Whether
 * returned goods are sellable is the inspection's answer, on the return's own
 * screen; doing it here as well would put the same shirt back twice.
 */
export function PickupsPage() {
  const runs = useQuery({
    queryKey: ["pickups"],
    queryFn: () => api<PickupRun[]>("/staff/pickups"),
  })

  const receive = useAction<number, PickupRun>({
    run: (id) => api<PickupRun>(`/staff/pickups/${id}/receive`, { method: "POST" }),
    invalidate: [["pickups"], ["returns"], ["summary"]],
    success: t.pickupReceived,
  })

  return (
    <>
      <PageTitle action={<NewRun />}>{t.pickups}</PageTitle>

      <Async
        query={runs}
        lines={4}
        empty={
          <Panel>
            <Empty title={t.pickupsEmpty} hint={t.pickupsEmptyHint} />
          </Panel>
        }
      >
        {(rows) => (
          <div className="space-y-[var(--gap-page)]">
            {rows.map((run) => (
              <Panel
                key={run.id}
                title={
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="tabular">{run.code}</span>
                    <Badge
                      tone={
                        run.status === "received"
                          ? "good"
                          : run.status === "cancelled"
                            ? "neutral"
                            : "warn"
                      }
                    >
                      {pickupStatus[run.status] ?? run.status}
                    </Badge>
                    <span className="text-[length:var(--text-small)] font-normal text-ink-soft">
                      {run.courier_name}
                    </span>
                  </span>
                }
                action={
                  run.next_statuses.includes("received") ? (
                    <Button
                      variant="primary"
                      size="sm"
                      disabled={receive.isPending}
                      onClick={() => receive.mutate(run.id)}
                    >
                      <PackageCheck />
                      {t.receivePickup}
                    </Button>
                  ) : (
                    <span className="text-[length:var(--text-small)] text-ink-faint">
                      {moment(run.received_at ?? run.collected_at ?? run.created_at)}
                    </span>
                  )
                }
              >
                {run.lines.map((line) => (
                  <Row key={line.id} className="sm:flex-nowrap">
                    <span className="tabular w-28 shrink-0 text-ink">
                      {line.order_code}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-ink">{line.product_title || "—"}</p>
                      <p className="truncate text-[length:var(--text-micro)] text-ink-faint">
                        {line.customer_name} · {line.address_line}
                      </p>
                    </div>
                    <Badge tone={line.collected ? "good" : "warn"}>
                      {line.collected ? t.collected : pickupStatus.open!}
                    </Badge>
                    {line.note ? (
                      <span className="w-48 truncate text-[length:var(--text-small)] text-ink-soft">
                        {line.note}
                      </span>
                    ) : null}
                  </Row>
                ))}
              </Panel>
            ))}
          </div>
        )}
      </Async>
    </>
  )
}

/**
 * A new run, from the approved requests that are not already on one.
 *
 * The server refuses a request that is not approved and one that is already
 * out — two vans for one parcel is a wasted trip and a courier told the goods
 * are gone — so this form offers only the approved ones and lets the server
 * have the last word on the rest.
 */
function NewRun() {
  const [open, setOpen] = React.useState(false)
  const [courierId, setCourierId] = React.useState("")
  const [picked, setPicked] = React.useState<number[]>([])

  const couriers = useQuery({
    queryKey: ["couriers"],
    queryFn: () => api<Courier[]>("/staff/couriers"),
    enabled: open,
  })
  const approved = useQuery({
    queryKey: ["returns", "approved"],
    queryFn: () => api<Return[]>("/staff/returns", { query: { status: "approved" } }),
    enabled: open,
  })

  const create = useAction<void, PickupRun>({
    run: () =>
      api<PickupRun>("/staff/pickups", {
        method: "POST",
        json: { courier_id: Number(courierId), return_request_ids: picked },
      }),
    invalidate: [["pickups"], ["returns"]],
    success: (run) => `${t.pickupCreated} — ${run.code}`,
    onDone: () => {
      setOpen(false)
      setPicked([])
    },
  })

  if (!open) {
    return (
      <Button variant="primary" size="sm" onClick={() => setOpen(true)}>
        <Plus />
        {t.newPickup}
      </Button>
    )
  }

  return (
    <div className="w-full space-y-3 rounded-[var(--radius-panel)] border border-line bg-surface p-4">
      <div className="space-y-1.5">
        <Label htmlFor="run-courier">{t.courier}</Label>
        <Select
          id="run-courier"
          value={courierId}
          onChange={(event) => setCourierId(event.target.value)}
        >
          <option value="">—</option>
          {(couriers.data ?? []).map((courier) => (
            <option key={courier.id} value={courier.id}>
              {courier.full_name || courier.phone}
            </option>
          ))}
        </Select>
      </div>

      <div className="space-y-1">
        <p className="text-[length:var(--text-small)] font-medium text-ink">
          {t.returns}
        </p>
        {(approved.data ?? []).length === 0 ? (
          <Hint>Tasdiqlangan ariza yo'q.</Hint>
        ) : (
          (approved.data ?? []).map((row) => (
            <label
              key={row.id}
              className="flex items-center gap-2 text-[length:var(--text-small)] text-ink"
            >
              <input
                type="checkbox"
                checked={picked.includes(row.id)}
                onChange={(event) =>
                  setPicked(
                    event.target.checked
                      ? [...picked, row.id]
                      : picked.filter((id) => id !== row.id),
                  )
                }
              />
              <span className="tabular">{row.order_code}</span>
              <span className="truncate text-ink-soft">
                {row.customer_name} · {row.product_title}
              </span>
            </label>
          ))
        )}
      </div>

      <div className="flex gap-2">
        <Button
          variant="primary"
          disabled={!courierId || picked.length === 0 || create.isPending}
          onClick={() => create.mutate()}
        >
          {t.newPickup}
        </Button>
        <Button variant="ghost" onClick={() => setOpen(false)}>
          {t.back}
        </Button>
      </div>
    </div>
  )
}
