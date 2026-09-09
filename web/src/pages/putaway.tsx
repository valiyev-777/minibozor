/**
 * Joylashtirish — carrying what is in the receiving area to a shelf.
 *
 * The queue is the receiving area itself. There is no task list beside it,
 * because being in `QABUL` *is* the state of not having been shelved, and a
 * second list would be a second answer that can disagree with the shelf.
 *
 * **Oldest first, with the age in words.** "2 soat 10 daqiqa" is the reason
 * anybody works this screen; a timestamp makes the reader do the subtraction.
 *
 * **The cell code is typed.** Market goods have no usable code of their own
 * and the phone cameras read codes badly, so this is a text input — one that
 * keeps working unchanged when a scanner gun is plugged in later, because a
 * gun types the code and presses Enter, which is what the form already does.
 *
 * **The cell's current fill is shown before confirming**, so nobody overfills
 * a cell by accident and finds out when the pile falls over.
 */

import { ArrowRight, Check } from "lucide-react"
import { useState } from "react"

import { Empty, Fill, PageHeader, Problem, Waiting } from "@/components/page"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { age, groups, units } from "@/lib/format"
import { useLocation, usePutAway, usePutawayQueue } from "@/lib/queries"
import type { PutawayLine } from "@/lib/types"

export function PutawayPage() {
  const queue = usePutawayQueue()
  const [open, setOpen] = useState<number | null>(null)

  return (
    <div className="space-y-4">
      <PageHeader
        title="Joylashtirish"
        subtitle="Qabulda turgan tovarlarni javonga olib qo'yish"
      />
      <Problem error={queue.error} />
      {queue.isLoading ? <Waiting what="Navbat" /> : null}

      {queue.data?.length === 0 ? (
        <Empty what="Qabul bo'sh — hammasi javonda." />
      ) : null}

      <ul className="space-y-2">
        {(queue.data ?? []).map((line) => (
          <li key={line.variant_id}>
            <Line
              line={line}
              open={open === line.variant_id}
              onToggle={() =>
                setOpen((was) => (was === line.variant_id ? null : line.variant_id))
              }
              onDone={() => setOpen(null)}
            />
          </li>
        ))}
      </ul>
    </div>
  )
}

function Line({
  line,
  open,
  onToggle,
  onDone,
}: {
  line: PutawayLine
  open: boolean
  onToggle: () => void
  onDone: () => void
}) {
  return (
    <div className="rounded-panel border bg-surface">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-3 p-3 text-left"
      >
        <div className="min-w-0 flex-1">
          {/* The thing leads. The place is where you walk to; the thing is
              what you must not get wrong. */}
          <div className="truncate text-body font-semibold">{line.product_title}</div>
          <div className="text-small text-ink-soft">{line.variant_label}</div>
          <div className="text-micro text-ink-faint">
            {age(line.minutes_here)} qabulda · {line.barcode}
          </div>
        </div>
        <div className="shrink-0 text-right">
          <div className="figure">{groups(line.qty)}</div>
          <div className="text-micro text-ink-faint">dona</div>
        </div>
        <ArrowRight className="size-4 shrink-0 text-ink-faint" />
      </button>

      {open ? <Form line={line} onDone={onDone} /> : null}
    </div>
  )
}

function Form({ line, onDone }: { line: PutawayLine; onDone: () => void }) {
  const [code, setCode] = useState(line.suggestion)
  const [qty, setQty] = useState(String(line.qty))
  const put = usePutAway()
  // The cell as it stands *now*, so nobody fills one they cannot see.
  const cell = useLocation(code.trim().length >= 3 ? code.trim().toUpperCase() : null)

  function submit(event: React.FormEvent) {
    event.preventDefault()
    put.mutate(
      { variant_id: line.variant_id, qty: Number(qty), code: code.trim() },
      { onSuccess: onDone },
    )
  }

  return (
    <form onSubmit={submit} className="space-y-3 border-t p-3">
      <div className="flex flex-wrap gap-2">
        <label className="flex-1">
          <span className="mb-1 block text-micro text-ink-soft">Katak kodi</span>
          <Input
            autoFocus
            value={code}
            onChange={(event) => setCode(event.target.value.toUpperCase())}
            placeholder="A-02-03"
            // A scanner gun types the code and presses Enter. Nothing here has
            // to know that; the form submits on Enter like any other form.
            className="h-control-lg tabular text-body"
            aria-label="Katak kodi"
          />
        </label>
        <label className="w-28">
          <span className="mb-1 block text-micro text-ink-soft">Nechta</span>
          <Input
            value={qty}
            onChange={(event) => setQty(event.target.value.replace(/\D/g, ""))}
            inputMode="numeric"
            className="h-control-lg tabular text-body"
            aria-label="Nechta"
          />
        </label>
      </div>

      {line.suggestion ? (
        <p className="text-micro text-ink-soft">
          Bu model {line.suggestion} katagida turibdi — bir model bitta katakda.
        </p>
      ) : null}

      {cell.data ? (
        <div className="rounded-control bg-canvas p-2">
          <div className="flex items-baseline justify-between text-micro">
            <span className="tabular font-medium">{cell.data.code}</span>
            <span className="text-ink-soft">
              {units(cell.data.units)}
              {cell.data.capacity ? ` / ${groups(cell.data.capacity)}` : ""} ·{" "}
              {cell.data.products} xil
            </span>
          </div>
          <div className="mt-1">
            <Fill percent={cell.data.fill_percent} />
          </div>
        </div>
      ) : null}

      <Problem error={put.error || cell.error} />

      <Button
        type="submit"
        disabled={put.isPending || !code.trim() || !Number(qty)}
        className="h-control-lg w-full gap-2 text-body"
      >
        <Check className="size-5" />
        {put.isPending ? "..." : "Joylashtirish"}
      </Button>
    </form>
  )
}
