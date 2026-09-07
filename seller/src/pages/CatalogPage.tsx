import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Check, ImageOff, Lightbulb, Plus, Search, Users } from "lucide-react"
import { api } from "@/api/client"
import type { CatalogCard, CatalogCardPage, Category } from "@/api/types"
import { Empty, Failed, Loading, Panel } from "@/components/Card"
import { PageHead } from "@/components/Shell"
import { Button } from "@/components/ui/button"
import { Hint, Input, Label, Select } from "@/components/ui/field"
import { mediaSrc, money } from "@/lib/utils"
import { NewOffer } from "@/pages/catalog/NewOffer"
import { Propose } from "@/pages/catalog/Propose"

export const CATALOG = ["catalog"]

const PAGE_SIZE = 24

type Owned = "" | "no" | "yes"

/**
 * Finding something to sell.
 *
 * The screen the marketplace was missing. Offering a product needs a
 * `product_id`, and until now the only catalogue listing was the admin's — so
 * a seller could edit the offers somebody had opened for them and could not
 * open one. This is where they arrive, search, and price something.
 *
 * A grid of photographs rather than a table of rows. What a seller does here
 * is *recognise* a product — is this the shoe I have in the van — and a
 * picture answers that faster than a column of titles ever will.
 *
 * The shop price is on every card. It is already public on
 * `GET /products/{id}/offers` with no token at all, so withholding it would
 * protect nothing and only make somebody price blind; what it tells them is
 * the thing they need, which is what this goes for and how many people are
 * already selling it.
 */
export function CatalogPage() {
  const [term, setTerm] = React.useState("")
  const [q, setQ] = React.useState("")
  const [category, setCategory] = React.useState("")
  const [owned, setOwned] = React.useState<Owned>("no")
  const [page, setPage] = React.useState(1)
  const [offering, setOffering] = React.useState<CatalogCard | null>(null)
  const [proposing, setProposing] = React.useState(false)

  const categories = useQuery({
    queryKey: ["categories"],
    queryFn: () => api<Category[]>("/categories"),
    staleTime: 5 * 60_000,
  })

  const query = useQuery({
    queryKey: [...CATALOG, q, category, owned, page],
    queryFn: () =>
      api<CatalogCardPage>("/staff/catalog/browse", {
        query: {
          q,
          category,
          ...(owned === "" ? {} : { mine: owned === "yes" }),
          page,
          page_size: PAGE_SIZE,
        },
      }),
  })

  function search(event: React.FormEvent) {
    event.preventDefault()
    setPage(1)
    setQ(term.trim())
  }

  const rows = query.data?.items ?? []
  const total = query.data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <>
      <PageHead
        title="Katalog"
        hint="Sotmoqchi bo'lgan tovarni toping va o'z narxingizni qo'ying. Katalog platformaniki — kartochka bitta, unga bir nechta sotuvchi taklif qo'yadi."
        actions={
          <Button onClick={() => setProposing(true)}>
            <Lightbulb />
            Yo'q tovarni taklif qilish
          </Button>
        }
      />

      <Panel className="mb-5 px-5 py-4">
        <form onSubmit={search} className="flex flex-wrap items-end gap-3">
          <div className="min-w-[14rem] flex-1 space-y-1.5">
            <Label htmlFor="q">Nomi yoki SKU</Label>
            <Input
              id="q"
              value={term}
              placeholder="Krossovka, MB-1001…"
              onChange={(event) => setTerm(event.target.value)}
            />
          </div>
          <div className="w-52 space-y-1.5">
            <Label htmlFor="category">Turkum</Label>
            <Select
              id="category"
              value={category}
              onChange={(event) => {
                setPage(1)
                setCategory(event.target.value)
              }}
            >
              <option value="">Hammasi</option>
              {(categories.data ?? []).map((row) => (
                <option key={row.slug} value={row.slug}>
                  {row.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="w-52 space-y-1.5">
            <Label htmlFor="owned">Mening takliflarim</Label>
            <Select
              id="owned"
              value={owned}
              onChange={(event) => {
                setPage(1)
                setOwned(event.target.value as Owned)
              }}
            >
              <option value="no">Hali menda yo'q</option>
              <option value="yes">Allaqachon meniki</option>
              <option value="">Hammasi</option>
            </Select>
          </div>
          <Button type="submit" variant="primary">
            <Search />
            Qidirish
          </Button>
        </form>
        <Hint className="mt-2">
          Faqat do'konda turgan kartochkalar. Qoralama va moderatsiyadagilar —
          boshqa odamning tugallanmagan ishi.
        </Hint>
      </Panel>

      {query.isPending ? (
        <Panel>
          <Loading lines={4} />
        </Panel>
      ) : null}
      {query.error ? (
        <Panel>
          <Failed error={query.error} onRetry={() => void query.refetch()} />
        </Panel>
      ) : null}
      {!query.isPending && !query.error && rows.length === 0 ? (
        <Panel>
          <Empty
            title={q || category ? "Bunday tovar topilmadi" : "Kartochka yo'q"}
            hint={
              owned === "no"
                ? "Hammasiga taklif qo'yib bo'lgan bo'lsangiz, «Allaqachon meniki» ni tanlang. Katalogda yo'q tovarni esa taklif qilish mumkin."
                : "Katalogda yo'q tovarni taklif qilsangiz, administrator ko'rib chiqadi."
            }
          />
        </Panel>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {rows.map((card) => (
          <Card key={card.id} card={card} onOffer={() => setOffering(card)} />
        ))}
      </div>

      {total > PAGE_SIZE ? (
        <div className="mt-5 flex items-center justify-between gap-3">
          <Hint>
            {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} / {total}
          </Hint>
          <div className="flex items-center gap-2">
            <Button disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Oldingi
            </Button>
            <span className="tabular text-[14px] text-ink-soft">
              {page} / {pages}
            </span>
            <Button disabled={page >= pages} onClick={() => setPage(page + 1)}>
              Keyingi
            </Button>
          </div>
        </div>
      ) : null}

      {offering ? (
        <NewOffer card={offering} onClose={() => setOffering(null)} />
      ) : null}
      {proposing ? <Propose onClose={() => setProposing(false)} /> : null}
    </>
  )
}

function Card({ card, onOffer }: { card: CatalogCard; onOffer: () => void }) {
  const src = mediaSrc(card.image_url)
  return (
    <Panel className="flex flex-col overflow-hidden">
      <div className="flex aspect-[4/3] items-center justify-center bg-line-soft">
        {src ? (
          <img src={src} alt="" className="size-full object-contain" />
        ) : (
          <ImageOff className="size-8 text-ink-faint" />
        )}
      </div>

      <div className="flex flex-1 flex-col gap-2 px-4 py-3">
        <div className="min-h-[3.25rem]">
          <p className="text-[15px] font-medium text-ink">{card.title}</p>
          {card.subtitle ? (
            <p className="line-clamp-1 text-[13px] text-ink-faint">{card.subtitle}</p>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-ink-soft">
          <span className="tabular">{card.sku}</span>
          <span>{card.category_name}</span>
          {card.brand_name ? <span>{card.brand_name}</span> : null}
        </div>

        <div className="flex items-end justify-between gap-3">
          <div>
            <p className="text-[13px] text-ink-soft">Do'kondagi narx</p>
            <p className="tabular text-[20px] font-semibold text-ink">
              {money(card.price)}
            </p>
          </div>
          <div className="text-right">
            {/* How crowded the card already is: the honest figure for
                somebody deciding whether to be the fourth seller on it. */}
            <p className="flex items-center justify-end gap-1 text-[13px] text-ink-soft">
              <Users className="size-3.5" />
              {card.offer_count} taklif
            </p>
            {card.variant_count ? (
              <p className="text-[13px] text-ink-faint">
                {card.variant_count} variant
              </p>
            ) : null}
          </div>
        </div>

        <div className="mt-auto pt-1">
          {card.mine ? (
            // Not a disabled "add" button: they already sell it, and what
            // they would want from here is the price they set.
            <div className="flex items-center justify-between gap-2 rounded-lg bg-brand-soft px-3 py-2">
              <span className="flex items-center gap-1.5 text-[14px] font-medium text-brand-ink">
                <Check className="size-4" />
                Sizda bor
              </span>
              <span className="tabular text-[14px] font-medium text-brand-ink">
                {card.my_price === null ? "" : money(card.my_price)}
              </span>
            </div>
          ) : (
            <Button variant="primary" className="w-full" onClick={onOffer}>
              <Plus />
              Taklif qo'yish
            </Button>
          )}
        </div>
      </div>

      {card.in_stock ? null : (
        <p className="border-t border-line-soft px-4 py-2 text-[13px] text-ink-soft">
          Hozir hech kimda qoldiq yo'q — kartochka bo'sh turgan.
        </p>
      )}
    </Panel>
  )
}
