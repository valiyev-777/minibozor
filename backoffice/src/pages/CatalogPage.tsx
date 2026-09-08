import * as React from "react"
import { Plus, Trash2 } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Brand, Category, ProductPage } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Hint, Input, Label, Select } from "@/ui/field"
import { Async, Empty } from "@/ui/states"
import { Panel, Row } from "@/components/Panel"
import { PageTitle } from "@/components/Shell"
import { useAction } from "@/lib/mutate"
import { num } from "@/lib/format"
import { productStatus, t } from "@/lib/labels"

/**
 * The catalogue's vocabulary, and the cards waiting on a batch.
 *
 * Three panels on one screen because they are one job: an admin comes here to
 * tidy the words a seller files a product under, and to look at the products
 * that were filed. Splitting them into three menu rows would be three clicks
 * for one sitting.
 *
 * **Nothing here publishes anything, and nothing here edits a seller's card.**
 * The list of cards waiting on a batch is a list, and that is all it is:
 * receiving the goods is what puts one in the shop, in the warehouse's hands,
 * and the words and photographs belong to the seller who wrote them. An admin
 * used to be able to rewrite them from here, which is somebody at head office
 * editing a shopkeeper's own shop; a seller who mistypes a name fixes it in
 * their own cabinet now.
 *
 * What is left for an admin is the vocabulary — the categories and brands a
 * seller files a product *under* — because those are the shop's shelving
 * rather than anybody's goods.
 */
export function CatalogPage() {
  return (
    <>
      <PageTitle>{t.catalog}</PageTitle>
      <Moderation />
      <div className="grid gap-[var(--gap-page)] lg:grid-cols-2">
        <Categories />
        <Brands />
      </div>
    </>
  )
}

function Moderation() {
  const products = useQuery({
    queryKey: ["products", "moderating"],
    queryFn: () =>
      api<ProductPage>("/staff/catalog/products", {
        query: { status: "moderating", page_size: 30 },
      }),
  })

  return (
    <Panel title={t.productsWaiting}>
      <p className="px-5 pb-2 text-[length:var(--text-small)] text-ink-soft">
        {t.editHint}
      </p>
      <Async query={products} lines={4}>
        {(page) =>
          page.items.length === 0 ? (
            <Empty
              title="Sanoq kutayotgan kartochka yo'q"
              hint="Sotuvchi tovar topshirsa, kartochkasi shu yerda ko'rinadi."
            />
          ) : (
            <>
              {page.items.map((product) => (
                <Row key={product.id} className="sm:flex-nowrap">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-ink">{product.title}</p>
                    <p className="truncate text-[length:var(--text-micro)] text-ink-faint">
                      {product.sku} · {product.proposed_by?.name ?? "—"}
                    </p>
                  </div>
                  <span className="tabular w-20 text-right text-ink-soft">
                    {num(product.image_count)} rasm
                  </span>
                  <span className="tabular w-24 text-right text-ink-soft">
                    {num(product.variant_count)} variant
                  </span>
                  <Badge tone="warn">
                    {productStatus[product.status] ?? product.status}
                  </Badge>
                </Row>
              ))}
            </>
          )
        }
      </Async>
    </Panel>
  )
}

function Categories() {
  const rows = useQuery({
    queryKey: ["categories"],
    queryFn: () => api<Category[]>("/staff/catalog/categories"),
  })
  const [slug, setSlug] = React.useState("")
  const [name, setName] = React.useState("")
  const [parent, setParent] = React.useState("")

  const add = useAction<void, unknown>({
    run: () =>
      api("/staff/catalog/categories", {
        method: "POST",
        json: {
          slug: slug.trim(),
          name: name.trim(),
          ...(parent ? { parent_slug: parent } : {}),
        },
      }),
    invalidate: [["categories"]],
    success: t.added,
    onDone: () => {
      setSlug("")
      setName("")
    },
  })

  const remove = useAction<string, unknown>({
    run: (target) =>
      api(`/staff/catalog/categories/${target}`, { method: "DELETE" }),
    invalidate: [["categories"]],
    success: t.removed,
  })

  return (
    <Panel title={t.categories}>
      <form
        className="grid gap-3 border-t border-line-soft px-5 py-4 sm:grid-cols-[1fr_1fr_1fr_auto]"
        onSubmit={(event) => {
          event.preventDefault()
          add.mutate()
        }}
      >
        <div className="space-y-1.5">
          <Label htmlFor="cat-slug">{t.slug}</Label>
          <Input
            id="cat-slug"
            required
            pattern="[a-z0-9-]+"
            value={slug}
            onChange={(event) => setSlug(event.target.value)}
            placeholder="choynaklar"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="cat-name">{t.name}</Label>
          <Input
            id="cat-name"
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Choynaklar"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="cat-parent">{t.parent}</Label>
          <Select
            id="cat-parent"
            value={parent}
            onChange={(event) => setParent(event.target.value)}
          >
            <option value="">—</option>
            {(rows.data ?? []).map((row) => (
              <option key={row.slug} value={row.slug}>
                {row.name}
              </option>
            ))}
          </Select>
        </div>
        <Button type="submit" variant="primary" className="self-end" disabled={add.isPending}>
          <Plus />
          {t.add}
        </Button>
      </form>

      <Async query={rows} lines={5}>
        {(list) => (
          <>
            {list.map((row) => (
              <Row key={row.id} className="sm:flex-nowrap">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-ink">{row.name}</p>
                  <p className="truncate text-[length:var(--text-micro)] text-ink-faint">
                    {row.slug}
                    {row.parent_slug ? ` · ${row.parent_slug}` : ""}
                  </p>
                </div>
                <span className="tabular w-20 text-right text-ink-soft">
                  {num(row.product_count)}
                </span>
                {/* Deleting one with cards in it is refused by the server, and
                    that refusal is the answer — a category with products is
                    load-bearing. So the button is offered and the sentence
                    comes back in a toast rather than being predicted here. */}
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label={`${row.name} ${t.remove}`}
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(row.slug)}
                >
                  <Trash2 />
                </Button>
              </Row>
            ))}
          </>
        )}
      </Async>
    </Panel>
  )
}

function Brands() {
  const rows = useQuery({
    queryKey: ["brands"],
    queryFn: () => api<Brand[]>("/staff/catalog/brands"),
  })
  const [slug, setSlug] = React.useState("")
  const [name, setName] = React.useState("")

  const add = useAction<void, unknown>({
    run: () =>
      api("/staff/catalog/brands", {
        method: "POST",
        json: { slug: slug.trim(), name: name.trim() },
      }),
    invalidate: [["brands"]],
    success: t.added,
    onDone: () => {
      setSlug("")
      setName("")
    },
  })

  const remove = useAction<string, unknown>({
    run: (target) => api(`/staff/catalog/brands/${target}`, { method: "DELETE" }),
    invalidate: [["brands"]],
    success: t.removed,
  })

  return (
    <Panel title={t.brands}>
      <form
        className="grid gap-3 border-t border-line-soft px-5 py-4 sm:grid-cols-[1fr_1fr_auto]"
        onSubmit={(event) => {
          event.preventDefault()
          add.mutate()
        }}
      >
        <div className="space-y-1.5">
          <Label htmlFor="brand-slug">{t.slug}</Label>
          <Input
            id="brand-slug"
            required
            pattern="[a-z0-9-]+"
            value={slug}
            onChange={(event) => setSlug(event.target.value)}
            placeholder="hunarmand"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="brand-name">{t.name}</Label>
          <Input
            id="brand-name"
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Hunarmand"
          />
        </div>
        <Button type="submit" variant="primary" className="self-end" disabled={add.isPending}>
          <Plus />
          {t.add}
        </Button>
      </form>

      <Async query={rows} lines={5}>
        {(list) => (
          <>
            {list.map((row) => (
              <Row key={row.id} className="sm:flex-nowrap">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-ink">{row.name}</p>
                  <p className="truncate text-[length:var(--text-micro)] text-ink-faint">
                    {row.slug}
                  </p>
                </div>
                <span className="tabular w-20 text-right text-ink-soft">
                  {num(row.product_count)}
                </span>
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label={`${row.name} ${t.remove}`}
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(row.slug)}
                >
                  <Trash2 />
                </Button>
              </Row>
            ))}
          </>
        )}
      </Async>
      <Hint className="px-5 pb-4">
        Brend — ixtiyoriy. Kartochkada brend bo'lmasa, u ro'yxatlarda brendsiz
        ko'rinadi.
      </Hint>
    </Panel>
  )
}
