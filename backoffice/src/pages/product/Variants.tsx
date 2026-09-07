import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Ban, Plus, Trash2 } from "lucide-react"
import { api } from "@/api/client"
import type { AdminVariant, AdminVariants, VariantKind } from "@/api/types"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Hint, Input, Label } from "@/components/ui/field"
import { useAction } from "@/lib/mutate"

/**
 * Colours, and the sizes of each colour.
 *
 * Two things here cannot be done, and the point of this screen is that it says
 * so *before* somebody tries rather than after.
 *
 * - A variant a movement or an order line names cannot be deleted. It is part
 *   of a record: the ledger would stop explaining its own totals and an old
 *   order would point at a row that is not there.
 * - A colour with stock against it cannot take its first size. The shelf is
 *   counted on the leaves, and adding a size moves where the leaves are —
 *   every existing count would sit a level above where the ledger looks, with
 *   nothing to say how a colour's twelve divides between the new sizes.
 *
 * Neither rule is written here. `GET .../variants` answers with `can_delete`,
 * `can_add_size` and the sentence explaining each, produced by the very
 * functions the write endpoints refuse with. A copy of those rules in this
 * file would be a second copy to keep in step, and it would be the one that
 * was wrong.
 */
export function Variants({ productId }: { productId: number }) {
  const key = ["staff", "catalog", "variants", productId]
  const [adding, setAdding] = React.useState<
    { kind: VariantKind; parent: AdminVariant | null } | null
  >(null)
  const [removing, setRemoving] = React.useState<AdminVariant | null>(null)

  const query = useQuery({
    queryKey: key,
    queryFn: () => api<AdminVariants>(`/staff/catalog/products/${productId}/variants`),
  })

  const tree = query.data
  const rows = tree?.variants ?? []
  const colours = rows.filter((row) => row.kind === "color")
  const loose = rows.filter((row) => row.kind === "size" && row.parent_id === null)

  return (
    <section className="overflow-hidden rounded-lg border border-line bg-surface">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3 py-2">
        <div>
          <h2 className="text-[13px] font-medium text-ink">Variantlar</h2>
          <Hint>
            Rang → o'lcham. Javon eng pastki qatlamda sanaladi: o'lchamlari bor
            bo'lsa o'lchamlarda, aks holda ranglarda.
          </Hint>
        </div>
        <div className="flex items-center gap-1.5">
          <Button size="sm" onClick={() => setAdding({ kind: "color", parent: null })}>
            <Plus />
            Rang
          </Button>
          {colours.length === 0 ? (
            <Button size="sm" onClick={() => setAdding({ kind: "size", parent: null })}>
              <Plus />
              O'lcham
            </Button>
          ) : null}
        </div>
      </header>

      {query.isPending ? (
        <div className="px-3 py-6">
          <span className="block h-3 w-40 animate-pulse rounded bg-line" />
        </div>
      ) : rows.length === 0 ? (
        <div className="px-3 py-8 text-center">
          <p className="text-[13px] text-ink-faint">Varianti yo'q</p>
          <Hint>
            Variantsiz kartochka bitta narsa sifatida sotiladi va bitta joyda
            sanaladi — bu ham to'g'ri holat.
          </Hint>
        </div>
      ) : (
        <ul className="divide-y divide-line-soft">
          {colours.map((colour) => (
            <li key={colour.id}>
              <Row
                variant={colour}
                onRemove={() => setRemoving(colour)}
                swatch
                action={
                  <Button
                    size="sm"
                    disabled={!tree?.can_add_size}
                    title={tree?.size_blocked_reason || undefined}
                    onClick={() => setAdding({ kind: "size", parent: colour })}
                  >
                    <Plus />
                    O'lcham
                  </Button>
                }
              />
              <ul>
                {rows
                  .filter((row) => row.parent_id === colour.id)
                  .map((size) => (
                    <li key={size.id} className="border-t border-line-soft bg-canvas/60">
                      <Row
                        variant={size}
                        onRemove={() => setRemoving(size)}
                        indent
                      />
                    </li>
                  ))}
              </ul>
            </li>
          ))}
          {loose.map((size) => (
            <li key={size.id}>
              <Row variant={size} onRemove={() => setRemoving(size)} />
            </li>
          ))}
        </ul>
      )}

      {/* The guard, stated once where it applies rather than in every row. */}
      {tree && !tree.can_add_size && colours.length > 0 ? (
        <p className="flex items-start gap-2 border-t border-line bg-warn-soft px-3 py-2 text-[12px] text-ink-soft">
          <Ban className="mt-0.5 size-3.5 shrink-0 text-warn" />
          <span>
            {tree.size_blocked_reason} Javondagi qoldiqni chiqarib, keyin
            o'lcham qo'shing — yoki o'lchamlarni qoldiq kelishidan oldin
            kiriting.
          </span>
        </p>
      ) : null}

      {adding ? (
        <AddVariant
          productId={productId}
          kind={adding.kind}
          parent={adding.parent}
          invalidate={key}
          onClose={() => setAdding(null)}
        />
      ) : null}
      {removing ? (
        <RemoveVariant
          productId={productId}
          variant={removing}
          invalidate={key}
          onClose={() => setRemoving(null)}
        />
      ) : null}
    </section>
  )
}

function Row({
  variant,
  onRemove,
  action,
  swatch,
  indent,
}: {
  variant: AdminVariant
  onRemove: () => void
  action?: React.ReactNode
  swatch?: boolean
  indent?: boolean
}) {
  return (
    <div className={`flex items-center gap-2 px-3 py-2 ${indent ? "pl-9" : ""}`}>
      {swatch ? (
        <span
          className="size-5 shrink-0 rounded border border-line"
          style={{ background: variant.value }}
          aria-hidden
        />
      ) : null}
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] text-ink">{variant.label}</p>
        <p className="tabular truncate text-[12px] text-ink-faint">{variant.value}</p>
      </div>

      {variant.stock_left === null ? null : (
        <Badge tone={variant.stock_left > 0 ? "neutral" : "danger"}>
          javonda {variant.stock_left}
        </Badge>
      )}

      {action}

      <Button
        size="icon"
        variant="ghost"
        aria-label="Variantni o'chirish"
        disabled={!variant.can_delete}
        // The server's own sentence, so the tooltip and the 409 agree.
        title={variant.blocked_reason || undefined}
        onClick={onRemove}
      >
        <Trash2 />
      </Button>
    </div>
  )
}

function AddVariant({
  productId,
  kind,
  parent,
  invalidate,
  onClose,
}: {
  productId: number
  kind: VariantKind
  parent: AdminVariant | null
  invalidate: (string | number)[]
  onClose: () => void
}) {
  const colour = kind === "color"
  const [label, setLabel] = React.useState("")
  const [value, setValue] = React.useState(colour ? "#000000" : "")
  const [ru, setRu] = React.useState("")
  const [en, setEn] = React.useState("")

  const add = useAction<void, unknown>({
    run: () =>
      api(`/staff/catalog/products/${productId}/variants`, {
        method: "POST",
        json: {
          kind,
          label: label.trim(),
          value: (value || label).trim(),
          ...(parent ? { parent_id: parent.id } : {}),
          translations: { ru: { label: ru.trim() }, en: { label: en.trim() } },
        },
      }),
    invalidate: [invalidate, ["staff", "catalog"]],
    success: colour ? "Rang qo'shildi" : "O'lcham qo'shildi",
    onDone: onClose,
  })

  return (
    <ConfirmDialog
      open
      onOpenChange={(next) => !next && onClose()}
      title={colour ? "Rang qo'shish" : "O'lcham qo'shish"}
      description={parent ? `${parent.label} rangi uchun` : undefined}
      confirmLabel="Qo'shish"
      disabled={!label.trim()}
      pending={add.isPending}
      onConfirm={() => add.mutate()}
    >
      <div className="space-y-3">
        <div className="flex gap-2">
          <div className="flex-1 space-y-1">
            <Label htmlFor="v-label">Nomi</Label>
            <Input
              id="v-label"
              autoFocus
              value={label}
              placeholder={colour ? "Ko'k" : "42"}
              onChange={(event) => setLabel(event.target.value)}
            />
          </div>
          <div className="w-40 space-y-1">
            <Label htmlFor="v-value">{colour ? "Rang kodi" : "Qiymati"}</Label>
            <div className="flex items-center gap-1.5">
              <Input
                id="v-value"
                className="tabular"
                value={value}
                placeholder={colour ? "#2E5AAC" : label || "42"}
                onChange={(event) => setValue(event.target.value)}
              />
              {colour ? (
                <span
                  className="size-7 shrink-0 rounded border border-line"
                  style={{ background: value }}
                  aria-hidden
                />
              ) : null}
            </div>
          </div>
        </div>

        <div className="flex gap-2">
          <div className="flex-1 space-y-1">
            <Label htmlFor="v-ru">Nomi — ruscha</Label>
            <Input
              id="v-ru"
              value={ru}
              placeholder={label}
              onChange={(event) => setRu(event.target.value)}
            />
          </div>
          <div className="flex-1 space-y-1">
            <Label htmlFor="v-en">Nomi — inglizcha</Label>
            <Input
              id="v-en"
              value={en}
              placeholder={label}
              onChange={(event) => setEn(event.target.value)}
            />
          </div>
        </div>
        <Hint>
          Bo'sh qoldirilsa o'zbekchasi ko'rsatiladi. Rang nomlari («Qora»,
          «Ko'k») ilovada tanlagichda o'qiladi, shuning uchun tarjimasi
          arziydi.
        </Hint>

        {colour ? null : (
          <Hint>
            O'lcham qaysi rangga tegishli ekani muhim: javon shu kesishmada
            sanaladi. Rangsiz o'lcham — ranglari yo'q kartochkalar uchun.
          </Hint>
        )}
      </div>
    </ConfirmDialog>
  )
}

function RemoveVariant({
  productId,
  variant,
  invalidate,
  onClose,
}: {
  productId: number
  variant: AdminVariant
  invalidate: (string | number)[]
  onClose: () => void
}) {
  const remove = useAction<void, unknown>({
    run: () =>
      api(`/staff/catalog/products/${productId}/variants/${variant.id}`, {
        method: "DELETE",
      }),
    invalidate: [invalidate, ["staff", "catalog"]],
    success: "Variant o'chirildi",
    onDone: onClose,
  })

  return (
    <ConfirmDialog
      open
      onOpenChange={(next) => !next && onClose()}
      title={`${variant.label} — o'chirish`}
      confirmLabel="O'chirish"
      destructive
      pending={remove.isPending}
      onConfirm={() => remove.mutate()}
    >
      <p className="text-[13px] text-ink-soft">
        Bu variantga hali hech narsa tayanmagan, shuning uchun o'chirish
        mumkin. Sotilgani bo'lsa, o'rniga javondan chiqariladi — buyurtma
        yozuvi yo'q qatorga ishora qilib qolmasligi kerak.
      </p>
    </ConfirmDialog>
  )
}
