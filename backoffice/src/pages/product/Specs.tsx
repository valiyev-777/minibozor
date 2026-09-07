import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Languages, Plus, Trash2 } from "lucide-react"
import { api } from "@/api/client"
import type { AdminSpec, SpecOut } from "@/api/types"
import { Button } from "@/components/ui/button"
import { Hint, Input, Label } from "@/components/ui/field"
import { useAction } from "@/lib/mutate"

/**
 * The spec table, replaced whole.
 *
 * `PUT .../specs` takes the entire list and rewrites it, which is why this is
 * edited as a block with one Save rather than row by row. The order is the
 * order it is read in on the product page, so it is part of the content.
 *
 * The translations do not survive a rewrite by accident — they cannot. The
 * rows are deleted and written again, and SQLite hands the old ids straight
 * back out, so the backend drops each old row's translations with it and this
 * form has to send the Russian and English along with the row it belongs to.
 * That is why they are edited here and not behind a separate screen.
 */

type Draft = {
  key: string
  value: string
  ru_key: string
  ru_value: string
  en_key: string
  en_value: string
}

const BLANK: Draft = { key: "", value: "", ru_key: "", ru_value: "", en_key: "", en_value: "" }

function toDraft(row: AdminSpec): Draft {
  const ru = row.translations["ru"] ?? {}
  const en = row.translations["en"] ?? {}
  return {
    key: row.key,
    value: row.value,
    ru_key: ru["key"] ?? "",
    ru_value: ru["value"] ?? "",
    en_key: en["key"] ?? "",
    en_value: en["value"] ?? "",
  }
}

export function Specs({ productId }: { productId: number }) {
  const key = ["staff", "catalog", "specs", productId]
  const [rows, setRows] = React.useState<Draft[] | null>(null)
  const [showing, setShowing] = React.useState(false)

  const specs = useQuery({
    queryKey: key,
    queryFn: () => api<AdminSpec[]>(`/staff/catalog/products/${productId}/specs`),
  })

  // The server's rows become the draft once, when they arrive. After that the
  // draft is what is on screen: a refetch must not overwrite half-typed rows.
  const loaded = specs.data
  React.useEffect(() => {
    if (loaded && rows === null) setRows(loaded.map(toDraft))
  }, [loaded, rows])

  const shown = rows ?? []

  const save = useAction<void, SpecOut[]>({
    run: () =>
      api<SpecOut[]>(`/staff/catalog/products/${productId}/specs`, {
        method: "PUT",
        json: {
          specs: shown
            .filter((row) => row.key.trim() && row.value.trim())
            .map((row) => ({
              key: row.key.trim(),
              value: row.value.trim(),
              translations: {
                ru: { key: row.ru_key.trim(), value: row.ru_value.trim() },
                en: { key: row.en_key.trim(), value: row.en_value.trim() },
              },
            })),
        },
      }),
    invalidate: [key, ["staff", "catalog"]],
    success: "Xususiyatlar saqlandi",
    // Redrawn from what came back rather than from what was typed: the PUT
    // answers with key and value only, so the translations are re-read by the
    // invalidation above and land through `loaded`.
    onDone: () => setRows(null),
  })

  function set(index: number, patch: Partial<Draft>) {
    setRows((list) =>
      (list ?? []).map((row, i) => (i === index ? { ...row, ...patch } : row)),
    )
  }

  return (
    <section className="overflow-hidden rounded-lg border border-line bg-surface">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3 py-2">
        <div>
          <h2 className="text-[13px] font-medium text-ink">Xususiyatlar</h2>
          <Hint>
            Mahsulot sahifasidagi jadval, shu tartibda. Butun ro'yxat birdan
            almashtiriladi.
          </Hint>
        </div>
        <div className="flex items-center gap-1.5">
          <Button size="sm" variant="ghost" onClick={() => setShowing((was) => !was)}>
            <Languages />
            {showing ? "Tarjimani yashirish" : "Tarjima"}
          </Button>
          <Button
            size="sm"
            variant="primary"
            disabled={save.isPending || rows === null}
            onClick={() => save.mutate()}
          >
            {save.isPending ? "Yuborilmoqda…" : "Saqlash"}
          </Button>
        </div>
      </header>

      {specs.isPending ? (
        <div className="px-3 py-6">
          <span className="block h-3 w-40 animate-pulse rounded bg-line" />
        </div>
      ) : (
        <div className="space-y-2 px-3 py-2">
          {shown.map((row, index) => (
            <div key={index} className="rounded border border-line p-2">
              <div className="flex items-end gap-2">
                <div className="flex-1 space-y-1">
                  {index === 0 ? <Label>Nomi</Label> : null}
                  <Input
                    value={row.key}
                    placeholder="Material"
                    onChange={(event) => set(index, { key: event.target.value })}
                  />
                </div>
                <div className="flex-1 space-y-1">
                  {index === 0 ? <Label>Qiymati</Label> : null}
                  <Input
                    value={row.value}
                    placeholder="Zamsh"
                    onChange={(event) => set(index, { value: event.target.value })}
                  />
                </div>
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label="Qatorni olib tashlash"
                  onClick={() =>
                    setRows((list) => (list ?? []).filter((_, i) => i !== index))
                  }
                >
                  <Trash2 />
                </Button>
              </div>

              {showing ? (
                <div className="mt-2 grid grid-cols-2 gap-2 border-t border-line-soft pt-2">
                  <Input
                    value={row.ru_key}
                    placeholder={`${row.key || "Nomi"} — ruscha`}
                    onChange={(event) => set(index, { ru_key: event.target.value })}
                  />
                  <Input
                    value={row.ru_value}
                    placeholder={`${row.value || "Qiymati"} — ruscha`}
                    onChange={(event) => set(index, { ru_value: event.target.value })}
                  />
                  <Input
                    value={row.en_key}
                    placeholder={`${row.key || "Nomi"} — inglizcha`}
                    onChange={(event) => set(index, { en_key: event.target.value })}
                  />
                  <Input
                    value={row.en_value}
                    placeholder={`${row.value || "Qiymati"} — inglizcha`}
                    onChange={(event) => set(index, { en_value: event.target.value })}
                  />
                </div>
              ) : null}
            </div>
          ))}

          {shown.length === 0 ? (
            <p className="py-4 text-center text-[13px] text-ink-faint">
              Xususiyat yo'q
            </p>
          ) : null}

          <Button size="sm" onClick={() => setRows((list) => [...(list ?? []), BLANK])}>
            <Plus />
            Qator
          </Button>
        </div>
      )}

      {showing ? (
        <p className="border-t border-line px-3 py-2 text-[12px] text-ink-faint">
          Tarjima qatorning o'zi bilan birga yuboriladi. Jadval to'liq qayta
          yozilganda eski qatorlarning tarjimasi ular bilan ketadi — shuning
          uchun u alohida ekranda emas, shu yerda.
        </p>
      ) : null}
    </section>
  )
}
