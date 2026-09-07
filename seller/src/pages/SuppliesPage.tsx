import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Minus, Plus, Truck, TriangleAlert } from "lucide-react"
import { api } from "@/api/client"
import type { Offer, Supply } from "@/api/types"
import { Empty, Failed, Loading, Panel } from "@/components/Card"
import { PageHead } from "@/components/Shell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogClose, DialogPanel } from "@/components/ui/dialog"
import { Hint, Input, Label, Select, Textarea } from "@/components/ui/field"
import { SUPPLY_STATUS, SUPPLY_TONE } from "@/lib/labels"
import { useAction } from "@/lib/mutate"
import { joined, said, when } from "@/lib/utils"

export const SUPPLIES = ["supplies"]

/**
 * Batches: what I say I am bringing, and what the warehouse actually counted.
 *
 * A supply is declared before it arrives, which is the whole point of it — the
 * warehouse knows a pallet is coming and what should be on it, so receiving
 * becomes checking rather than guessing. Then the counted figure lands beside
 * the declared one and the difference is a fact both sides can see.
 *
 * That difference is the screen's reason for existing. A seller who sent
 * fifty and was credited forty-eight needs to know before they read it in a
 * payout, and needs to see it per line rather than as a total.
 */
export function SuppliesPage() {
  const [declaring, setDeclaring] = React.useState(false)

  const query = useQuery({
    queryKey: SUPPLIES,
    queryFn: () => api<Supply[]>("/staff/supplies"),
  })

  const rows = query.data ?? []
  const waiting = rows.filter((row) => row.status === "declared")

  return (
    <>
      <PageHead
        title="Partiyalar"
        hint="Tovar keltirishdan oldin e'lon qilinadi — ombor nima kutayotganini bilsa, qabul qilish tekshirishga aylanadi."
        actions={
          <Button variant="primary" onClick={() => setDeclaring(true)}>
            <Plus />
            Partiya e'lon qilish
          </Button>
        }
      />

      {waiting.length ? (
        <Panel className="mb-5 border-warn/30 bg-warn-soft px-5 py-4">
          <p className="flex items-center gap-2 text-[15px] text-ink">
            <Truck className="size-4 shrink-0 text-warn" />
            <span>
              <span className="font-semibold">{waiting.length} ta partiya</span>{" "}
              omborga yetib kelishini kutmoqda. Qabul qilinmagunicha javondagi
              son o'zgarmaydi.
            </span>
          </p>
        </Panel>
      ) : null}

      <Panel title={`${rows.length} ta partiya`}>
        {query.isPending ? <Loading /> : null}
        {query.error ? (
          <Failed error={query.error} onRetry={() => void query.refetch()} />
        ) : null}
        {!query.isPending && !query.error && rows.length === 0 ? (
          <Empty
            title="Hali partiya yo'q"
            hint="Partiya — «shuncha tovar keltiraman» degan e'lon. Ombor qabul qilganda javondagi son o'sadi."
          />
        ) : null}

        {rows.map((supply) => (
          <SupplyCard key={supply.id} supply={supply} />
        ))}
      </Panel>

      {declaring ? <Declare onClose={() => setDeclaring(false)} /> : null}
    </>
  )
}

function SupplyCard({ supply }: { supply: Supply }) {
  const declared = supply.lines.reduce((sum, line) => sum + line.declared_quantity, 0)
  const received = supply.lines.reduce(
    (sum, line) => sum + (line.received_quantity ?? 0),
    0,
  )
  // Only meaningful once it has been received; before that "0 counted" is not
  // a shortfall, it is a batch that has not arrived.
  const settled = supply.status === "received"
  const gap = settled ? received - declared : 0
  const off = supply.lines.filter(
    (line) => settled && (line.difference ?? 0) !== 0,
  )

  return (
    <div className="border-t border-line-soft">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-4">
        <div className="min-w-[10rem] flex-1">
          <p className="tabular text-[16px] font-medium text-ink">{supply.code}</p>
          <p className="text-[13px] text-ink-faint">
            E'lon qilingan {when(supply.declared_at)}
            {supply.received_at ? ` · qabul ${when(supply.received_at)}` : ""}
          </p>
          {supply.note ? (
            <p className="mt-0.5 text-[13px] text-ink-soft">{supply.note}</p>
          ) : null}
        </div>

        <Badge tone={SUPPLY_TONE[supply.status]}>{SUPPLY_STATUS[supply.status]}</Badge>

        <div className="w-24 text-right">
          <p className="text-[12px] text-ink-faint">E'lon</p>
          <p className="tabular text-[18px] font-medium text-ink">{declared}</p>
        </div>
        <div className="w-24 text-right">
          <p className="text-[12px] text-ink-faint">Sanaldi</p>
          <p className="tabular text-[18px] font-medium text-ink">
            {settled ? received : "—"}
          </p>
        </div>
      </div>

      {/* The difference, and only when there is one. A row saying "0" every
          time trains people to stop reading it. */}
      {settled && gap !== 0 ? (
        <div className="mx-5 mb-4 rounded-lg border border-warn/30 bg-warn-soft px-4 py-3">
          <p className="flex items-start gap-2 text-[14px] text-ink">
            <TriangleAlert className="mt-0.5 size-4 shrink-0 text-warn" />
            <span>
              <span className="font-semibold">
                {gap > 0 ? `${gap} dona ko'p` : `${-gap} dona kam`} sanaldi.
              </span>{" "}
              Hisob-kitobda sanalgan son ishlatiladi — e'lon qilingani emas.
            </span>
          </p>
          <ul className="mt-2 space-y-1">
            {off.map((line) => (
              <li key={line.id} className="flex flex-wrap gap-x-3 text-[13px]">
                <span className="flex-1 text-ink-soft">
                  {joined(line.product_title, line.variant_label)}
                </span>
                <span className="tabular text-ink-faint">
                  {line.declared_quantity} → {line.received_quantity}
                </span>
                <span
                  className={`tabular w-12 text-right font-medium ${
                    (line.difference ?? 0) > 0 ? "text-good" : "text-danger"
                  }`}
                >
                  {(line.difference ?? 0) > 0 ? "+" : ""}
                  {line.difference}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <ul className="mb-3 space-y-1 px-5">
        {supply.lines.map((line) => (
          <li key={line.id} className="flex flex-wrap gap-x-3 text-[13px]">
            <span className="tabular w-24 shrink-0 text-ink-faint">{line.sku}</span>
            <span className="min-w-[8rem] flex-1 text-ink-soft">
              {joined(line.product_title, line.variant_label)}
            </span>
            <span className="tabular w-16 text-right text-ink">
              {line.declared_quantity}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

type Draft = { offerId: string; variantId: string; quantity: string }

const BLANK: Draft = { offerId: "", variantId: "", quantity: "10" }

function Declare({ onClose }: { onClose: () => void }) {
  const [lines, setLines] = React.useState<Draft[]>([BLANK])
  const [note, setNote] = React.useState("")

  const offers = useQuery({
    queryKey: ["offers"],
    queryFn: () => api<Offer[]>("/staff/offers"),
  })
  const rows = offers.data ?? []
  const byId = new Map(rows.map((offer) => [String(offer.id), offer]))

  const create = useAction<void, Supply>({
    run: () =>
      api<Supply>("/staff/supplies", {
        method: "POST",
        json: {
          note: note.trim(),
          lines: lines
            .filter((line) => line.offerId && Number(line.quantity) > 0)
            .map((line) => ({
              offer_id: Number(line.offerId),
              ...(line.variantId ? { variant_id: Number(line.variantId) } : {}),
              quantity: Number(line.quantity),
            })),
        },
      }),
    invalidate: [SUPPLIES, ["dashboard"]],
    success: (row) => `${row.code} e'lon qilindi`,
    onDone: onClose,
  })

  function set(index: number, patch: Partial<Draft>) {
    setLines((all) => all.map((line, i) => (i === index ? { ...line, ...patch } : line)))
  }

  const usable = lines.filter((line) => line.offerId && Number(line.quantity) > 0)
  const total = usable.reduce((sum, line) => sum + Number(line.quantity), 0)

  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogPanel
        className="w-[min(94vw,40rem)]"
        title="Partiya e'lon qilish"
        description="Nima va qancha keltirasiz. Ombor qabul qilib, o'zi sanaydi."
        footer={
          <>
            <DialogClose asChild>
              <Button variant="ghost">Bekor qilish</Button>
            </DialogClose>
            <Button
              variant="primary"
              disabled={!usable.length || create.isPending}
              onClick={() => create.mutate()}
            >
              {create.isPending ? "Yuborilmoqda…" : `E'lon qilish (${total} dona)`}
            </Button>
          </>
        }
      >
        <div className="space-y-4 pb-3">
          {offers.isPending ? <Loading lines={2} /> : null}
          {!offers.isPending && rows.length === 0 ? (
            <p className="rounded-lg bg-warn-soft px-3 py-2.5 text-[14px] text-ink">
              Avval narx kerak: partiya narxga bog'lanadi, chunki qoldiq
              qaysi narxda sotilishini bilishi shart.
            </p>
          ) : null}

          {lines.map((line, index) => {
            const offer = byId.get(line.offerId)
            // Only leaves can be counted: a size where there are sizes, a
            // colour where there are only colours. The API decides; this just
            // offers what the offer carries.
            const variants = offer?.variants ?? []
            return (
              <div key={index} className="rounded-lg border border-line p-3">
                <div className="space-y-1.5">
                  <Label htmlFor={`offer-${index}`}>Mahsulot</Label>
                  <Select
                    id={`offer-${index}`}
                    value={line.offerId}
                    onChange={(event) =>
                      set(index, { offerId: event.target.value, variantId: "" })
                    }
                  >
                    <option value="">— tanlang —</option>
                    {rows.map((row) => (
                      <option key={row.id} value={row.id}>
                        {row.product_title}
                      </option>
                    ))}
                  </Select>
                </div>

                <div className="mt-3 flex flex-wrap items-end gap-3">
                  {variants.length ? (
                    <div className="min-w-[12rem] flex-1 space-y-1.5">
                      <Label htmlFor={`variant-${index}`}>Variant</Label>
                      <Select
                        id={`variant-${index}`}
                        value={line.variantId}
                        onChange={(event) => set(index, { variantId: event.target.value })}
                      >
                        <option value="">— butun mahsulot —</option>
                        {variants.map((variant) => (
                          <option key={variant.variant_id} value={variant.variant_id}>
                            {said(variant.label) || `#${variant.variant_id}`}
                          </option>
                        ))}
                      </Select>
                    </div>
                  ) : null}

                  <div className="w-32 space-y-1.5">
                    <Label htmlFor={`qty-${index}`}>Nechta</Label>
                    <Input
                      id={`qty-${index}`}
                      type="number"
                      min={1}
                      className="tabular"
                      value={line.quantity}
                      onChange={(event) => set(index, { quantity: event.target.value })}
                    />
                  </div>

                  {lines.length > 1 ? (
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label="Qatorni olib tashlash"
                      onClick={() => setLines((all) => all.filter((_, i) => i !== index))}
                    >
                      <Minus />
                    </Button>
                  ) : null}
                </div>
              </div>
            )
          })}

          <Button size="sm" onClick={() => setLines((all) => [...all, BLANK])}>
            <Plus />
            Yana qator
          </Button>

          <div className="space-y-1.5">
            <Label htmlFor="note">Izoh</Label>
            <Textarea
              id="note"
              value={note}
              placeholder="Payshanba kuni yetib boradi · haydovchi +998901234567"
              onChange={(event) => setNote(event.target.value)}
            />
            <Hint>
              Ombor buni qabul qilishda o'qiydi — yetib kelish vaqti yoki
              haydovchi raqami shu yerda foydali.
            </Hint>
          </div>

          <p className="rounded-lg bg-line-soft/70 px-3 py-2.5 text-[13px] text-ink-soft">
            E'lon qilish javondagi sonni oshirmaydi. Ombor tovarni sanaganda
            oshadi — va sanalgani e'lon qilinganidan farq qilsa, shu sahifada
            ko'rinadi.
          </p>
        </div>
      </DialogPanel>
    </Dialog>
  )
}
