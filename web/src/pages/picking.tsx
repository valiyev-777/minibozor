/**
 * Terish — fetching one order off the shelves.
 *
 * **The variant leads, not the cell.** The cell is where you walk to; the
 * variant is the thing you must not get wrong. So a line is the model, then
 * the colour and size in the largest type on the screen, then the code, then
 * the quantity — in that order, at that weight, deliberately.
 *
 * **A mixed cell says so.** A picker reaching into a cell of black and white
 * shoes needs to be told to look, and the server already knows whether the
 * cell holds more than one thing.
 *
 * **One tap confirms a line.** This is the screen a scanner gun will pay for
 * later — the picker scans the item and the system refuses the wrong
 * colour — and the shape of the row is already the shape that will take it.
 *
 * **The board fills itself.** Above the tasks are the orders nobody has begun
 * — `GET /warehouse/pick/waiting` — and starting one is a tap. It used to be
 * that a task only existed once somebody pressed "Terishga qo'yish" on the
 * office's Buyurtmalar screen, which the warehouse role cannot even open: so
 * an order came in from a telephone, sat in `placed`, and this board stayed
 * empty saying "Terish uchun buyurtma yo'q" until the owner went through them
 * one at a time. The queue is the thing that decides the order of work; it
 * cannot also need a person to load it.
 */

import { Check, MapPin, TriangleAlert } from "lucide-react"
import { useState } from "react"

import { Empty, PageHeader, Panel, Problem, Waiting } from "@/components/page"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/cn"
import { age, groups } from "@/lib/format"
import {
  useCompleteTask,
  usePickLine,
  usePickQueue,
  usePickTask,
  usePickWaiting,
  useStartPicking,
  useTakeTask,
} from "@/lib/queries"
import type { PickTask } from "@/lib/types"

export function PickingPage() {
  const [openId, setOpenId] = useState<number | null>(null)
  if (openId) return <Task id={openId} onBack={() => setOpenId(null)} />
  return <Queue onOpen={setOpenId} />
}

function Queue({ onOpen }: { onOpen: (id: number) => void }) {
  const queue = usePickQueue()
  const fresh = usePickWaiting()
  const take = useTakeTask()
  const start = useStartPicking()

  const waiting = (queue.data ?? []).filter((task) => task.status !== "picked")
  const unbegun = fresh.data ?? []
  const nothing = waiting.length === 0 && unbegun.length === 0

  return (
    <div className="space-y-4">
      <PageHeader title="Terish" subtitle="Navbat — eng eskisi birinchi" />
      <Problem error={queue.error || fresh.error || take.error || start.error} />
      {queue.isLoading ? <Waiting what="Navbat" /> : null}
      {queue.data && fresh.data && nothing ? (
        <Empty what="Terish uchun buyurtma yo'q." />
      ) : null}

      {/* New orders first, because they are the ones nobody is holding. A
          picker with an unfinished trolley finds it below; a picker with free
          hands starts at the top. */}
      {unbegun.length > 0 ? (
        <section className="space-y-2">
          <h2 className="text-small font-semibold text-ink-soft">
            Yangi buyurtmalar · {unbegun.length}
          </h2>
          <ul className="space-y-2">
            {unbegun.map((order) => (
              <li key={order.order_id}>
                <Panel>
                  <div className="flex items-center gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="text-body font-semibold tabular">
                        {order.order_code}
                      </div>
                      {/* What to fetch, in one line — the same sentence the
                          office queue prints. */}
                      <div className="truncate text-small text-ink-soft">
                        {order.items_summary}
                      </div>
                      <div className="text-micro text-ink-faint">
                        {order.items_count} dona · {age(order.age_minutes)} kutmoqda
                        {order.delivery_window ? ` · ${order.delivery_window}` : ""}
                      </div>
                    </div>
                    <Button size="lg" disabled={start.isPending} onClick={() =>
                        start.mutate(order.order_id, {
                          onSuccess: (task) => onOpen(task.id),
                        })
                      }
                    >
                      Boshlash
                    </Button>
                  </div>
                </Panel>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {/* Trolleys already on the floor. A heading only when there is something
          above it to tell them apart from. */}
      {waiting.length > 0 && unbegun.length > 0 ? (
        <h2 className="text-small font-semibold text-ink-soft">
          Boshlangan · {waiting.length}
        </h2>
      ) : null}

      <ul className="space-y-2">
        {waiting.map((task) => (
          <li key={task.id}>
            <Panel>
              <div className="flex items-center gap-3">
                <div className="min-w-0 flex-1">
                  <div className="text-body font-semibold tabular">{task.order_code}</div>
                  <div className="text-small text-ink-soft">
                    {task.lines.length} qator · {age(task.age_minutes)}
                  </div>
                  {task.picker ? (
                    <div className="text-micro text-ink-faint">{task.picker} olgan</div>
                  ) : null}
                </div>
                {task.status === "waiting" ? (
                  <Button size="lg" className="gap-2" disabled={take.isPending} onClick={() =>
                      take.mutate(task.id, { onSuccess: () => onOpen(task.id) })
                    }
                  >
                    Olish
                  </Button>
                ) : (
                  <Button size="lg" variant="secondary" onClick={() => onOpen(task.id)}
                  >
                    Davom etish
                  </Button>
                )}
              </div>
            </Panel>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Task({ id, onBack }: { id: number; onBack: () => void }) {
  const task = usePickTask(id)
  const pick = usePickLine(id)
  const complete = useCompleteTask(id)

  if (task.isLoading) return <Waiting what="Vazifa" />
  if (!task.data) return <Problem error={task.error} />

  const left = task.data.lines.filter((line) => line.picked_qty < line.qty).length

  return (
    <div className="space-y-4">
      <PageHeader
        title={task.data.order_code}
        subtitle={`${task.data.lines.length} qator · ${left} qoldi`}
      >
        <Button variant="ghost" onClick={onBack}>
          Navbatga
        </Button>
      </PageHeader>

      <Problem error={pick.error || complete.error} />

      <ol className="space-y-2">
        {task.data.lines.map((line, index) => {
          const done = line.picked_qty >= line.qty
          return (
            <li key={line.id}>
              <Panel className={cn(done && "opacity-60")}>
              <div className="flex items-start gap-3">
                <span className="grid size-7 shrink-0 place-items-center rounded-full bg-canvas text-micro tabular text-ink-soft">
                  {index + 1}
                </span>

                <div className="min-w-0 flex-1">
                  <div className="truncate text-small text-ink-soft">
                    {line.product_title}
                  </div>
                  {/* The largest type on the screen is the thing itself. */}
                  <div className="text-figure font-semibold leading-tight">
                    {line.variant_label || "—"}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-small">
                    <span className="inline-flex items-center gap-1 tabular font-medium">
                      <MapPin className="size-4 text-ink-faint" />
                      {line.location_code}
                    </span>
                    <span className="tabular text-ink-soft">{line.barcode}</span>
                  </div>
                  {line.mixed_cell ? (
                    <p className="mt-2 inline-flex items-center gap-1 rounded-control bg-warn-soft px-2 py-1 text-micro text-warn-ink">
                      <TriangleAlert className="size-3.5" />
                      Bu katakda bir nechta xil bor — diqqat bilan qarang
                    </p>
                  ) : null}
                </div>

                <div className="shrink-0 text-right">
                  <div className="figure">{groups(line.qty)}</div>
                  <div className="text-micro text-ink-faint">dona</div>
                </div>
              </div>

              {!done ? (
                <Button size="lg" className="mt-3 w-full gap-2" disabled={pick.isPending} onClick={() =>
                    pick.mutate({ lineId: line.id, qty: line.qty - line.picked_qty })
                  }
                >
                  <Check className="size-5" />
                  Olindi
                </Button>
              ) : (
                <p className="mt-3 text-center text-small text-good">Olindi</p>
              )}
              </Panel>
            </li>
          )
        })}
      </ol>

      <Button size="lg" className="w-full" disabled={left > 0 || complete.isPending || task.data.status === "picked"}
        onClick={() => complete.mutate(undefined, { onSuccess: onBack })}
      >
        {task.data.status === "picked"
          ? "Yig'ildi"
          : left > 0
            ? `Yana ${left} qator qoldi`
            : "Yig'ishni yakunlash"}
      </Button>
    </div>
  )
}

export type { PickTask }
