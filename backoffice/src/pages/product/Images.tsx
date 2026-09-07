import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { ImagePlus, Trash2 } from "lucide-react"
import { api, upload } from "@/api/client"
import type { AdminImage, MediaOut } from "@/api/types"
import { orderChanged, SortableList } from "@/components/SortableList"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Hint } from "@/components/ui/field"
import { useAction } from "@/lib/mutate"
import { mediaSrc } from "@/lib/utils"

/**
 * The gallery, and the order it is shown in.
 *
 * Two requests to add one photograph, and they are different jobs. `POST
 * /staff/media` takes the bytes, decodes them to prove they are a picture,
 * shrinks the phone-sized ones and writes a file under a name of its own;
 * `POST .../images` attaches the path it hands back to this card. So a file
 * that is not an image, or is too big, is refused before the card is touched.
 *
 * The order matters more than it looks. The first photograph is the cover —
 * it is what every tile in the shop shows — so this is not decoration, it is
 * choosing the picture the product is sold by.
 */
export function Images({ productId }: { productId: number }) {
  const key = ["staff", "catalog", "images", productId]
  const [draft, setDraft] = React.useState<AdminImage[] | null>(null)
  const input = React.useRef<HTMLInputElement>(null)

  const query = useQuery({
    queryKey: key,
    queryFn: () =>
      api<AdminImage[]>(`/staff/catalog/products/${productId}/images`),
  })

  const rows = query.data ?? []
  const shown = draft ?? rows
  const dirty =
    draft !== null && orderChanged(rows.map((r) => r.id), draft.map((r) => r.id))

  const add = useAction<File, string[]>({
    run: async (file) => {
      // Two requests, two jobs: the first proves the bytes are a picture and
      // stores it under a name of ours, the second hangs that path on this
      // card. A file that is not an image never reaches the card at all.
      const stored = await upload<MediaOut>("/staff/media", file)
      // The write endpoint answers with bare URLs; the ids come from the read
      // that `invalidate` triggers next.
      return api<string[]>(`/staff/catalog/products/${productId}/images`, {
        method: "POST",
        json: { url: stored.media_url, sort: rows.length },
      })
    },
    invalidate: [key, ["staff", "catalog"]],
    success: "Rasm qo'shildi",
    onDone: () => setDraft(null),
  })

  const saveOrder = useAction<void, AdminImage[]>({
    run: () =>
      api<AdminImage[]>(`/staff/catalog/products/${productId}/images/order`, {
        method: "PUT",
        json: { ids: shown.map((row) => row.id) },
      }),
    invalidate: [key, ["staff", "catalog"]],
    success: "Tartib saqlandi",
    onDone: () => setDraft(null),
  })

  const remove = useAction<AdminImage, unknown>({
    run: (row) =>
      api(`/staff/catalog/products/${productId}/images/${row.id}`, {
        method: "DELETE",
      }),
    invalidate: [key, ["staff", "catalog"]],
    success: "Rasm o'chirildi",
    onDone: () => setDraft(null),
  })

  return (
    <section className="overflow-hidden rounded-lg border border-line bg-surface">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3 py-2">
        <div>
          <h2 className="text-[13px] font-medium text-ink">Rasmlar</h2>
          <Hint>
            Birinchisi muqova — do'kondagi har bir katakchada o'sha ko'rinadi.
            Sudrab yoki tugmalar bilan almashtiring.
          </Hint>
        </div>
        <div className="flex items-center gap-1.5">
          {dirty ? (
            <>
              <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>
                Bekor qilish
              </Button>
              <Button
                size="sm"
                variant="primary"
                disabled={saveOrder.isPending}
                onClick={() => saveOrder.mutate()}
              >
                {saveOrder.isPending ? "Yuborilmoqda…" : "Tartibni saqlash"}
              </Button>
            </>
          ) : null}
          <input
            ref={input}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0]
              // Cleared straight away so choosing the same file twice in a row
              // still fires a change event.
              event.target.value = ""
              if (file) add.mutate(file)
            }}
          />
          <Button
            size="sm"
            disabled={add.isPending}
            onClick={() => input.current?.click()}
          >
            <ImagePlus />
            {add.isPending ? "Yuklanmoqda…" : "Rasm yuklash"}
          </Button>
        </div>
      </header>

      {query.isPending ? (
        <div className="px-3 py-6">
          <span className="block h-3 w-40 animate-pulse rounded bg-line" />
        </div>
      ) : shown.length === 0 ? (
        <div className="px-3 py-8 text-center">
          <p className="text-[13px] text-ink-faint">Hali rasm yo'q</p>
          <Hint>
            Har qanday formatdagi surat bo'ladi — server o'zi WebP qilib
            kichraytiradi, uzun tomonini 1600 px gacha.
          </Hint>
        </div>
      ) : (
        <SortableList
          rows={shown}
          rowKey={(row) => row.id}
          onOrderChange={setDraft}
          disabled={saveOrder.isPending}
          renderRow={(row, index) => (
            <div className="flex items-center gap-2">
              <img
                src={mediaSrc(row.url)}
                alt=""
                className="size-10 shrink-0 rounded border border-line object-cover"
              />
              <div className="min-w-0 flex-1">
                <p className="tabular truncate text-[12px] text-ink-soft">{row.url}</p>
                {index === 0 ? <Badge tone="accent">Muqova</Badge> : null}
              </div>
              <Button
                size="icon"
                variant="ghost"
                aria-label="Rasmni o'chirish"
                disabled={remove.isPending}
                onClick={() => remove.mutate(row)}
              >
                <Trash2 />
              </Button>
            </div>
          )}
        />
      )}

      {dirty ? (
        <p className="border-t border-line bg-warn-soft px-3 py-2 text-[12px] text-ink-soft">
          Tartib hali yuborilmadi. Butun ro'yxat bir so'rovda ketadi — yarim
          holat bo'lmaydi.
        </p>
      ) : null}
    </section>
  )
}
