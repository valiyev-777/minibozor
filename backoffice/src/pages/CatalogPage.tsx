import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { ChevronDown, ChevronRight, Plus, Search, Store } from "lucide-react"
import { api } from "@/api/client"
import type {
  AdminProduct,
  AdminProductPage,
  Brand,
  Category,
  ProductStatus,
} from "@/api/types"
import { DataTable, type Column } from "@/components/DataTable"
import { Page } from "@/components/Layout"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Hint, Input, Label, Select } from "@/components/ui/field"
import { Tabs } from "@/components/ui/tabs"
import { PRODUCT_STATUS, PRODUCT_TONE } from "@/lib/labels"
import { cn, mediaSrc, money, when } from "@/lib/utils"

const KEY = ["staff", "catalog"]
const PAGE_SIZE = 30

type Tab = "products" | "categories" | "brands"

const STATUSES: ProductStatus[] = [
  "draft",
  "moderating",
  "published",
  "rejected",
  "archived",
]

export function CatalogPage() {
  const navigate = useNavigate()
  const [tab, setTab] = React.useState<Tab>("products")

  return (
    <Page
      title="Katalog"
      hint="Kartochkani tahrirlash — qatordagi tugma. Narx, qoldiq va holat u yerda emas, va nega emasligi yozilgan."
      actions={
        tab === "products" ? (
          <Button variant="primary" onClick={() => navigate("/catalog/products/new")}>
            <Plus />
            Yangi kartochka
          </Button>
        ) : null
      }
    >
      <div className="mb-3">
        <Tabs
          value={tab}
          onChange={setTab}
          items={[
            { value: "products", label: "Mahsulotlar" },
            { value: "categories", label: "Turkumlar" },
            { value: "brands", label: "Brendlar" },
          ]}
        />
      </div>

      {tab === "products" ? <ProductsTab /> : null}
      {tab === "categories" ? <CategoriesTab /> : null}
      {tab === "brands" ? <BrandsTab /> : null}
    </Page>
  )
}

// ----------------------------------------------------------------- products

function ProductsTab() {
  const navigate = useNavigate()
  const [term, setTerm] = React.useState("")
  const [q, setQ] = React.useState("")
  const [status, setStatus] = React.useState<"" | ProductStatus>("")
  const [page, setPage] = React.useState(1)

  const query = useQuery({
    queryKey: [...KEY, "products", q, status, page],
    queryFn: () =>
      api<AdminProductPage>("/staff/catalog/products", {
        query: { q, status, page, page_size: PAGE_SIZE },
      }),
  })

  function search(event: React.FormEvent) {
    event.preventDefault()
    setPage(1)
    setQ(term.trim())
  }

  const columns: Column<AdminProduct>[] = [
    {
      key: "title",
      header: "Kartochka",
      sortValue: (row) => row.title,
      cell: (row) => (
        <div className="max-w-72">
          <span className="block truncate font-medium text-ink">{row.title}</span>
          <span className="tabular block truncate text-[12px] text-ink-faint">
            {row.sku}
          </span>
        </div>
      ),
    },
    {
      key: "status",
      header: "Holat",
      sortValue: (row) => row.status,
      cell: (row) => (
        <>
          <Badge tone={PRODUCT_TONE[row.status]}>{PRODUCT_STATUS[row.status]}</Badge>
          {row.moderation_note ? (
            <span className="mt-0.5 block max-w-40 truncate text-[12px] text-danger">
              {row.moderation_note}
            </span>
          ) : null}
        </>
      ),
    },
    {
      key: "where",
      header: "Turkum · brend",
      sortValue: (row) => row.category_slug,
      cell: (row) => (
        <div className="max-w-40">
          <span className="block truncate text-ink-soft">{row.category_slug}</span>
          <span className="block truncate text-[12px] text-ink-faint">
            {row.brand_slug || "brendsiz"}
          </span>
        </div>
      ),
    },
    {
      key: "proposer",
      header: "Kim yozgan",
      sortValue: (row) => row.proposed_by?.name ?? "",
      cell: (row) =>
        row.proposed_by ? (
          <span className="inline-flex items-center gap-1.5 text-ink-soft">
            <Store className="size-3.5 shrink-0 text-ink-faint" />
            {row.proposed_by.name}
          </span>
        ) : (
          <span className="text-ink-faint">Mini Bozor</span>
        ),
    },
    {
      key: "price",
      header: "Narx",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.price,
      cell: (row) => (
        <>
          <span className="block text-ink">{money(row.price)}</span>
          {/* The figure on the card is a cache of the winning offer. With no
              offers behind it, it is the number the card was written with. */}
          <span className="block text-[12px] text-ink-faint">
            {row.offer_count ? `${row.offer_count} taklif` : "taklifsiz"}
          </span>
        </>
      ),
    },
    {
      key: "stock",
      header: "Javonda",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.stock_left,
      cell: (row) =>
        row.stock_left > 0 ? (
          row.stock_left
        ) : (
          <span className="font-medium text-danger">0</span>
        ),
    },
    {
      key: "content",
      header: "To'ldirilgan",
      className: "tabular text-[12px] text-ink-soft",
      cell: (row) => `${row.image_count} rasm · ${row.variant_count} variant`,
    },
    {
      key: "created",
      header: "Yozilgan",
      sortValue: (row) => row.created_at,
      cell: (row) => <span className="tabular text-ink-soft">{when(row.created_at)}</span>,
    },
    {
      key: "actions",
      header: "",
      headClassName: "text-right",
      className: "text-right",
      cell: (row) => (
        <Button size="sm" onClick={() => navigate(`/catalog/products/${row.id}`)}>
          Tahrirlash
        </Button>
      ),
    },
  ]

  return (
    <DataTable
      rows={query.data?.items}
      columns={columns}
      rowKey={(row) => row.id}
      loading={query.isPending}
      error={query.error}
      onRetry={() => void query.refetch()}
      emptyTitle={q ? "Bunday kartochka topilmadi" : "Katalog bo'sh"}
      emptyHint={q ? "Nom yoki SKU bo'yicha qidiriladi." : undefined}
      server={{
        page: query.data?.page ?? page,
        pageSize: query.data?.page_size ?? PAGE_SIZE,
        total: query.data?.total ?? 0,
        onPageChange: setPage,
      }}
      toolbar={
        <>
          <form onSubmit={search} className="flex items-center gap-1.5">
            <Label htmlFor="cat-q" className="sr-only">
              Nom yoki SKU
            </Label>
            <Input
              id="cat-q"
              className="w-56"
              value={term}
              placeholder="Nom yoki SKU"
              onChange={(event) => setTerm(event.target.value)}
            />
            <Button size="sm" type="submit">
              <Search />
              Qidirish
            </Button>
          </form>
          <div className="flex items-center gap-1.5">
            <Label htmlFor="cat-status">Holat</Label>
            <Select
              id="cat-status"
              className="w-44"
              value={status}
              onChange={(event) => {
                setPage(1)
                setStatus(event.target.value as "" | ProductStatus)
              }}
            >
              <option value="">Hammasi</option>
              {STATUSES.map((value) => (
                <option key={value} value={value}>
                  {PRODUCT_STATUS[value]}
                </option>
              ))}
            </Select>
          </div>
          <Hint>{query.data?.total ?? 0} ta kartochka</Hint>
        </>
      }
    />
  )
}

// --------------------------------------------------------------- categories

/**
 * The catalogue tree, opened a level at a time.
 *
 * `/categories` answers with the roots and `?parent=` with one row's children,
 * which is the shape the apps read it in. Fetching the whole tree up front
 * would mean a request per branch anyway — so a branch is fetched when
 * somebody opens it, and never again while the screen is up.
 */
function CategoriesTab() {
  const roots = useQuery({
    queryKey: ["categories", "roots"],
    queryFn: () => api<Category[]>("/categories"),
  })

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface">
      <div className="border-b border-line px-3 py-2">
        <p className="text-[13px] font-medium text-ink">Turkumlar</p>
        <Hint>
          Ichkarisini ochish uchun qatorni bosing. Ichida mahsulot yoki ichki turkum bor
          turkumni server o'chirtirmaydi.
        </Hint>
      </div>

      {roots.isPending ? (
        <div className="px-3 py-6">
          <span className="block h-3 w-48 animate-pulse rounded bg-line" />
        </div>
      ) : roots.error ? (
        <div className="flex items-center justify-between gap-3 bg-danger-soft px-3 py-2.5">
          <p className="text-[12px] font-medium text-danger">Turkumlar olinmadi.</p>
          <Button size="sm" onClick={() => void roots.refetch()}>
            Qayta urinish
          </Button>
        </div>
      ) : (roots.data ?? []).length === 0 ? (
        <p className="px-3 py-8 text-center text-[13px] text-ink-faint">Turkum yo'q</p>
      ) : (
        <ul className="divide-y divide-line-soft">
          {(roots.data ?? []).map((category) => (
            <CategoryRow key={category.slug} category={category} depth={0} />
          ))}
        </ul>
      )}
    </div>
  )
}

function CategoryRow({ category, depth }: { category: Category; depth: number }) {
  const [open, setOpen] = React.useState(false)
  const expandable = category.has_children ?? false

  const children = useQuery({
    queryKey: ["categories", "children", category.slug],
    queryFn: () => api<Category[]>("/categories", { query: { parent: category.slug } }),
    enabled: open && expandable,
  })

  return (
    <li>
      <div
        className={cn(
          "flex items-center gap-2 px-3 py-2",
          expandable && "cursor-pointer hover:bg-accent-soft/50",
        )}
        style={{ paddingLeft: `${0.75 + depth * 1.25}rem` }}
        onClick={expandable ? () => setOpen((was) => !was) : undefined}
      >
        {expandable ? (
          open ? (
            <ChevronDown className="size-3.5 shrink-0 text-ink-faint" />
          ) : (
            <ChevronRight className="size-3.5 shrink-0 text-ink-faint" />
          )
        ) : (
          <span className="size-3.5 shrink-0" />
        )}

        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] text-ink">{category.name}</p>
          <p className="tabular truncate text-[12px] text-ink-faint">
            {category.slug}
            {category.subtitle ? ` · ${category.subtitle}` : ""}
          </p>
        </div>

        <span className="shrink-0 text-[12px] text-ink-faint">{category.icon}</span>
        {/* The picture itself rather than a badge saying there is one: every
            category has an image, so the badge was always lit and said
            nothing. What an admin actually wants to know is which picture. */}
        {category.image_url ? (
          <img
            src={mediaSrc(category.image_url)}
            alt=""
            className="size-7 shrink-0 rounded border border-line object-cover"
          />
        ) : (
          <span className="size-7 shrink-0 rounded border border-dashed border-line" />
        )}
      </div>

      {open && expandable ? (
        children.isPending ? (
          <p
            className="py-1.5 text-[12px] text-ink-faint"
            style={{ paddingLeft: `${2.25 + depth * 1.25}rem` }}
          >
            Yuklanmoqda…
          </p>
        ) : (
          <ul className="divide-y divide-line-soft border-t border-line-soft">
            {(children.data ?? []).map((child) => (
              <CategoryRow key={child.slug} category={child} depth={depth + 1} />
            ))}
          </ul>
        )
      ) : null}
    </li>
  )
}

// ------------------------------------------------------------------- brands

function BrandsTab() {
  const query = useQuery({
    queryKey: ["brands"],
    queryFn: () => api<Brand[]>("/brands"),
  })

  const columns: Column<Brand>[] = [
    {
      key: "name",
      header: "Nomi",
      sortValue: (row) => row.name,
      cell: (row) => <span className="font-medium text-ink">{row.name}</span>,
    },
    {
      key: "slug",
      header: "Slug",
      sortValue: (row) => row.slug,
      cell: (row) => <span className="tabular text-ink-soft">{row.slug}</span>,
    },
  ]

  return (
    <DataTable
      rows={query.data}
      columns={columns}
      rowKey={(row) => row.id}
      loading={query.isPending}
      error={query.error}
      onRetry={() => void query.refetch()}
      emptyTitle="Brend yo'q"
      clientPageSize={40}
      toolbar={
        <Hint>
          {query.data?.length ?? 0} ta brend. Brendda nechta mahsulot borligini bu
          endpoint sanamaydi — u faqat listing filtrida hisoblanadi.
        </Hint>
      }
    />
  )
}
