/**
 * Sanash — recounting one cell.
 *
 * A cell at a time, because a stocktake of the whole warehouse is a day
 * nobody has and a cell is what one person can count without stopping the
 * shop.
 *
 * The screen shows what the system thinks is there and takes what is actually
 * there beside it. **Both are kept.** The difference is the whole point of a
 * count — it becomes an `adjust` movement with the counter's name on it — and
 * a screen that only took the new figure would leave nobody able to say how
 * far the shelf had drifted.
 *
 * **The scanner counts.** One read of a sticker is one unit: the row goes up
 * by one and says its new figure back. That is the whole reason the stickers
 * exist — counting forty pairs by scanning them beats counting them by eye,
 * and the screen never has to be touched with a hand that is holding shoes.
 * A code that is not in this cell is refused loudly, because a shoe in the
 * wrong cell is exactly the finding a count is for.
 */

import { Check } from "lucide-react"
import { useEffect, useState } from "react"

import { Empty, PageHeader, Panel, Problem, Waiting } from "@/components/page"
import { ScanBar, missWords, type ScanAnswer } from "@/components/scan"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/cn"
import { groups } from "@/lib/format"
import { useCount, useStartCount, useSubmitCount } from "@/lib/queries"

export function CountsPage() {
  const [code, setCode] = useState("")
  const [id, setId] = useState<number | null>(null)
  const [said, setSaid] = useState("")
  const start = useStartCount()

  function begin(cellCode: string) {
    setSaid("")
    start.mutate(cellCode.trim().toUpperCase(), {
      onSuccess: (count) => {
        setId(count.id)
        setCode("")
      },
    })
  }

  /** At the door of a cell, the cell label is the way in. A goods sticker
   *  here is somebody a step ahead of the screen, so it is a hint and not a
   *  refusal. */
  function onScan(answer: ScanAnswer) {
    if (answer.kind === "cell" && answer.cell) {
      if (answer.cell.is_active === false) {
        setSaid(`${answer.cell.code} yopilgan yacheyka — sanashga ochilmaydi.`)
        return
      }
      begin(answer.cell.code)
      return
    }
    if (answer.kind === "variant" && answer.variant) {
      setSaid(
        `${answer.variant.product_title} — avval katak yorlig'ini o'qiting, sanash o'sha yerda boshlanadi.`,
      )
      return
    }
    setSaid(missWords(answer.code))
  }

  if (id) return <Counting id={id} onDone={() => setId(null)} />

  return (
    <div className="space-y-4">
      <PageHeader title="Sanash" subtitle="Bitta katakni qayta sanash" />

      <ScanBar
        hint="Katak yorlig'ini o'qiting — sanash o'sha zahoti ochiladi."
        said={said}
        onAnswer={onScan}
        paused={start.isPending}
      />

      <Panel>
        <form
          onSubmit={(event) => {
            event.preventDefault()
            begin(code)
          }}
          className="flex flex-wrap gap-2">
          <Input
            autoFocus
            value={code}
            onChange={(event) => setCode(event.target.value.toUpperCase())}
            placeholder="A-02-03"
            aria-label="Katak kodi"
            className="h-control-lg flex-1 tabular text-body" />
          <Button size="lg" type="submit" disabled={start.isPending || !code.trim()} >
            Sanashni boshlash
          </Button>
        </form>
      </Panel>
      <Problem error={start.error} />
    </div>
  )
}

/**
 * The count itself, and it is **the whole screen** rather than an overlay.
 *
 * Named `Sheet` once, which was the only thing overlay about it: a person
 * counting a cell has a trolley in one hand and is reading a column of
 * figures off a shelf, and the list they are filling in is the screen's
 * entire job — not something laid over the screen they came from. The way
 * back is the page header's own button.
 */
function Counting({ id, onDone }: { id: number; onDone: () => void }) {
  const count = useCount(id)
  const submit = useSubmitCount(id)
  const [counted, setCounted] = useState<Record<number, string>>({})
  const [note, setNote] = useState("")
  const [said, setSaid] = useState<{ tone: "good" | "danger"; words: string } | null>(null)
  // The row the last scan touched, lit for a moment: at the shelf the answer
  // has to be findable without reading the whole column.
  const [lit, setLit] = useState<number | null>(null)

  // Seeded with what the system believes, so a cell that is exactly right is
  // one tap. The figures a person changes are the findings.
  useEffect(() => {
    if (!count.data) return
    setCounted(
      Object.fromEntries(
        count.data.lines.map((line) => [line.variant_id, String(line.expected_qty)]),
      ),
    )
  }, [count.data])

  if (count.isLoading) return <Waiting what="Katak" />
  if (!count.data) return <Problem error={count.error} />

  const closed = count.data.status === "closed"
  const lines = count.data.lines
  const here = count.data.location_code

  /** One read of a sticker is one unit. */
  function onScan(answer: ScanAnswer) {
    setLit(null)
    if (closed) {
      setSaid({ tone: "danger", words: "Sanash yakunlangan — endi o'zgarmaydi." })
      return
    }
    if (answer.kind === "cell" && answer.cell) {
      // A cell label mid-count is somebody checking they are at the right
      // shelf, which is worth answering and is not a mistake.
      setSaid(
        answer.cell.code === here
          ? { tone: "good", words: `${here} — shu katak sanalmoqda.` }
          : {
              tone: "danger",
              words: `${answer.cell.code} — boshqa katak. Hozir ${here} sanalmoqda; avval shuni yakunlang.`,
            },
      )
      return
    }
    if (answer.kind === "variant" && answer.variant) {
      const found = answer.variant
      const line = lines.find((row) => row.variant_id === found.variant_id)
      if (!line) {
        // The finding a count exists for: something is standing in a cell the
        // system does not put it in.
        setSaid({
          tone: "danger",
          words: `${found.product_title} ${found.variant_label} — tizimda ${here} ichida yo'q. Qo'lda qo'shib bo'lmaydi: uni xaritada shu katakka ko'chiring.`,
        })
        return
      }
      const next = Number(counted[line.variant_id] ?? line.expected_qty) + 1
      setCounted((was) => ({ ...was, [line.variant_id]: String(next) }))
      setLit(line.variant_id)
      setSaid({
        tone: "good",
        words: `${line.variant_label || line.product_title} — ${groups(next)} ta sanaldi.`,
      })
      return
    }
    setSaid({ tone: "danger", words: missWords(answer.code) })
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title={`${here} — sanash`}
        subtitle={closed ? "Yakunlangan" : "Nechta borligini yozing"}
      >
        <Button variant="ghost" onClick={onDone}>
          Orqaga
        </Button>
      </PageHeader>

      {!closed ? (
        <ScanBar
          hint="Har bir yorliqni o'qiting — o'sha qator bittaga oshadi."
          said={said?.words}
          tone={said?.tone}
          onAnswer={onScan}
          paused={submit.isPending}
        />
      ) : null}

      <Problem error={submit.error} />

      {count.data.lines.length === 0 ? (
        <Empty what="Tizim bu katakni bo'sh deb biladi. Agar ichida narsa bo'lsa, uni mahsulot bo'yicha qidirib qo'shing." />
      ) : null}

      <ul className="space-y-2">
        {count.data.lines.map((line) => {
          const value = counted[line.variant_id] ?? String(line.expected_qty)
          const difference = Number(value || 0) - line.expected_qty
          return (
            <li key={line.variant_id}>
              <Panel className={cn(lit === line.variant_id && "ring-2 ring-brand")}>
                <div className="flex items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-small text-ink-soft">
                      {line.product_title}
                    </div>
                    <div className="text-body font-semibold">{line.variant_label}</div>
                    <div className="text-micro tabular text-ink-faint">{line.barcode}</div>
                  </div>
                  <div className="shrink-0 text-right">
                    <div className="text-micro text-ink-faint">tizimda</div>
                    <div className="tabular text-body">{groups(line.expected_qty)}</div>
                  </div>
                  <div className="w-24 shrink-0">
                    <Input
                      value={value}
                      disabled={closed}
                      inputMode="numeric"
                      aria-label={`${line.variant_label} — sanalgan`}
                      onChange={(event) =>
                        setCounted((was) => ({
                          ...was,
                          [line.variant_id]: event.target.value.replace(/\D/g, ""),
                        }))
                      }
                      className="h-control-lg tabular text-body" />
                    {difference ? (
                      <div
                        className={cn(
                          "mt-1 text-center text-micro tabular",
                          difference > 0 ? "text-good" : "text-danger",
                        )}
                      >
                        {difference > 0 ? "+" : ""}
                        {difference}
                      </div>
                    ) : null}
                  </div>
                </div>
              </Panel>
            </li>
          )
        })}
      </ul>

      {!closed && count.data.lines.length ? (
        <Panel>
          <div className="space-y-2">
            <Input
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Izoh (ixtiyoriy)"
              aria-label="Izoh"
              className="h-control" />
            <Button size="lg" className="w-full gap-2" disabled={submit.isPending} onClick={() =>
                submit.mutate(
                  {
                    lines: count.data.lines.map((line) => ({
                      variant_id: line.variant_id,
                      counted_qty: Number(counted[line.variant_id] ?? line.expected_qty),
                    })),
                    note,
                  },
                  { onSuccess: onDone },
                )
              }
            >
              <Check className="size-5" />
              Sanashni yakunlash
            </Button>
          </div>
        </Panel>
      ) : null}
    </div>
  )
}
