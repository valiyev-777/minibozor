import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Plus, Trash2 } from "lucide-react"
import { api } from "@/api/client"
import type { AdminBanner, AdminPromo, AdminSection, Category } from "@/api/types"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { DataTable, type Column } from "@/components/DataTable"
import { Page } from "@/components/Layout"
import { orderChanged, SortableList } from "@/components/SortableList"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Hint, Input, Label, Select } from "@/components/ui/field"
import { Tabs } from "@/components/ui/tabs"
import { useAction } from "@/lib/mutate"
import { money } from "@/lib/utils"

const BANNERS = ["staff", "showcase", "banners"]
const SECTIONS = ["staff", "showcase", "sections"]
const PROMOS = ["staff", "showcase", "promos"]

type Tab = "banners" | "sections" | "promos"

export function ShowcasePage() {
  const [tab, setTab] = React.useState<Tab>("banners")

  return (
    <Page
      title="Vitrina"
      hint="Katalogdan mustaqil: bu yerda hech qanday kartochka yaratilmaydi va tahrirlanmaydi — faqat joylashuv."
    >
      <div className="mb-3">
        <Tabs
          value={tab}
          onChange={setTab}
          items={[
            { value: "banners", label: "Bannerlar" },
            { value: "sections", label: "Bosh sahifa bloklari" },
            { value: "promos", label: "Promo-kodlar" },
          ]}
        />
      </div>

      {tab === "banners" ? <BannersTab /> : null}
      {tab === "sections" ? <SectionsTab /> : null}
      {tab === "promos" ? <PromosTab /> : null}
    </Page>
  )
}

/**
 * A card holding an arrangement, with one Save for the whole of it.
 *
 * Both ordered lists work the same way and the backend insists on it: the
 * `.../order` endpoints take every id and refuse a list that repeats a row or
 * leaves one out. So the order is held here while somebody arranges it, and
 * `ids` goes complete or not at all.
 */
function Arrangement<T extends { id: number }>({
  title,
  hint,
  rows,
  loading,
  error,
  onRetry,
  path,
  invalidate,
  renderRow,
  actions,
  emptyTitle,
}: {
  title: string
  hint: string
  rows: T[] | undefined
  loading: boolean
  error: unknown
  onRetry: () => void
  path: string
  invalidate: string[]
  renderRow: (row: T) => React.ReactNode
  actions?: React.ReactNode
  emptyTitle: string
}) {
  const [draft, setDraft] = React.useState<T[] | null>(null)

  // The server's order is the truth until somebody starts arranging. Once
  // they have, a background refetch must not pull the rows out from under
  // their hands — so the draft wins while it exists.
  const shown = draft ?? rows ?? []
  const saved = (rows ?? []).map((row) => row.id)
  const dirty = draft !== null && orderChanged(saved, draft.map((row) => row.id))

  const save = useAction<void, T[]>({
    run: () =>
      api<T[]>(path, { method: "POST", json: { ids: shown.map((row) => row.id) } }),
    invalidate: [invalidate],
    success: "Tartib saqlandi",
    onDone: () => setDraft(null),
  })

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3 py-2">
        <div>
          <p className="text-[13px] font-medium text-ink">{title}</p>
          <Hint>{hint}</Hint>
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
                disabled={save.isPending}
                onClick={() => save.mutate()}
              >
                {save.isPending ? "Yuborilmoqda…" : "Tartibni saqlash"}
              </Button>
            </>
          ) : null}
          {actions}
        </div>
      </div>

      {error ? (
        <div className="flex items-center justify-between gap-3 bg-danger-soft px-3 py-2.5">
          <p className="text-[12px] font-medium text-danger">Ro'yxat olinmadi.</p>
          <Button size="sm" onClick={onRetry}>
            Qayta urinish
          </Button>
        </div>
      ) : null}

      {loading && !rows ? (
        <div className="px-3 py-6">
          <span className="block h-3 w-48 animate-pulse rounded bg-line" />
        </div>
      ) : shown.length === 0 ? (
        <p className="px-3 py-8 text-center text-[13px] text-ink-faint">{emptyTitle}</p>
      ) : (
        <SortableList
          rows={shown}
          rowKey={(row) => row.id}
          renderRow={renderRow}
          onOrderChange={setDraft}
          disabled={save.isPending}
        />
      )}

      {dirty ? (
        <p className="border-t border-line bg-warn-soft px-3 py-2 text-[12px] text-ink-soft">
          Tartib hali yuborilmadi. Saqlangunicha ilovada eski tartib turadi — butun
          ro'yxat bir so'rovda ketadi, yarim holat bo'lmaydi.
        </p>
      ) : null}
    </div>
  )
}

// ------------------------------------------------------------------ banners

function BannersTab() {
  const [creating, setCreating] = React.useState(false)
  const [editing, setEditing] = React.useState<AdminBanner | null>(null)
  const [removing, setRemoving] = React.useState<AdminBanner | null>(null)

  const query = useQuery({
    queryKey: BANNERS,
    queryFn: () => api<AdminBanner[]>("/staff/showcase/banners"),
  })

  return (
    <>
      <Arrangement<AdminBanner>
        title="Bannerlar"
        hint="Yuqoridagisi ilovada birinchi ko'rinadi. Sudrab yoki tugmalar bilan."
        rows={query.data}
        loading={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        path="/staff/showcase/banners/order"
        invalidate={BANNERS}
        emptyTitle="Banner yo'q"
        actions={
          <Button size="sm" variant="primary" onClick={() => setCreating(true)}>
            <Plus />
            Banner
          </Button>
        }
        renderRow={(row) => (
          <div className="flex items-center gap-2">
            <span
              className="size-7 shrink-0 rounded"
              style={{
                background: `linear-gradient(135deg, ${row.gradient_from}, ${row.gradient_to})`,
              }}
              aria-hidden
            />
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-medium text-ink">{row.title}</p>
              <p className="truncate text-[12px] text-ink-faint">
                {[row.kicker, row.subtitle].filter(Boolean).join(" · ") || "—"}
              </p>
            </div>
            <span className="hidden shrink-0 text-[12px] text-ink-faint sm:block">
              {row.target_type}
              {row.target_value ? `: ${row.target_value}` : ""}
            </span>
            {row.active ? null : <Badge tone="neutral">O'chiq</Badge>}
            <Button size="sm" onClick={() => setEditing(row)}>
              Tahrirlash
            </Button>
            <Button
              size="icon"
              variant="ghost"
              aria-label="O'chirish"
              onClick={() => setRemoving(row)}
            >
              <Trash2 />
            </Button>
          </div>
        )}
      />

      {creating ? <BannerForm onClose={() => setCreating(false)} /> : null}
      {editing ? (
        <BannerForm banner={editing} onClose={() => setEditing(null)} />
      ) : null}
      {removing ? (
        <DeleteRow
          title="Bannerni o'chirish"
          description={removing.title}
          path={`/staff/showcase/banners/${removing.id}`}
          invalidate={BANNERS}
          onClose={() => setRemoving(null)}
        />
      ) : null}
    </>
  )
}

const TARGETS = ["category", "product", "url", "none"]

function BannerForm({ banner, onClose }: { banner?: AdminBanner; onClose: () => void }) {
  const [form, setForm] = React.useState({
    kicker: banner?.kicker ?? "",
    title: banner?.title ?? "",
    subtitle: banner?.subtitle ?? "",
    cta: banner?.cta ?? "Ko'rish",
    image_url: banner?.image_url ?? "",
    gradient_from: banner?.gradient_from ?? "#2E5AAC",
    gradient_to: banner?.gradient_to ?? "#7CA0E8",
    target_type: banner?.target_type ?? "category",
    target_value: banner?.target_value ?? "",
    active: banner?.active ?? true,
  })

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  const save = useAction<void, AdminBanner>({
    run: () =>
      banner
        ? api<AdminBanner>(`/staff/showcase/banners/${banner.id}`, {
            method: "PATCH",
            json: form,
          })
        : api<AdminBanner>("/staff/showcase/banners", { method: "POST", json: form }),
    invalidate: [BANNERS],
    success: banner ? "Banner saqlandi" : "Banner qo'shildi",
    onDone: onClose,
  })

  return (
    <ConfirmDialog
      open
      onOpenChange={(next) => !next && onClose()}
      title={banner ? "Bannerni tahrirlash" : "Banner qo'shish"}
      confirmLabel="Saqlash"
      disabled={!form.title.trim() || !form.image_url.trim()}
      pending={save.isPending}
      onConfirm={() => save.mutate()}
    >
      <div className="space-y-3">
        <div className="flex gap-2">
          <div className="w-36 space-y-1">
            <Label htmlFor="b-kicker">Kicker</Label>
            <Input
              id="b-kicker"
              value={form.kicker}
              placeholder="YANGI"
              onChange={(event) => set("kicker", event.target.value)}
            />
          </div>
          <div className="flex-1 space-y-1">
            <Label htmlFor="b-title">Sarlavha</Label>
            <Input
              id="b-title"
              autoFocus
              value={form.title}
              onChange={(event) => set("title", event.target.value)}
            />
          </div>
        </div>

        <div className="space-y-1">
          <Label htmlFor="b-subtitle">Izoh</Label>
          <Input
            id="b-subtitle"
            value={form.subtitle}
            onChange={(event) => set("subtitle", event.target.value)}
          />
        </div>

        <div className="flex gap-2">
          <div className="w-36 space-y-1">
            <Label htmlFor="b-cta">Tugma matni</Label>
            <Input
              id="b-cta"
              value={form.cta}
              onChange={(event) => set("cta", event.target.value)}
            />
          </div>
          <div className="flex-1 space-y-1">
            <Label htmlFor="b-image">Rasm yo'li</Label>
            <Input
              id="b-image"
              value={form.image_url}
              placeholder="banners/yozgi.png"
              onChange={(event) => set("image_url", event.target.value)}
            />
          </div>
        </div>

        <div className="flex gap-2">
          <div className="flex-1 space-y-1">
            <Label htmlFor="b-target">Nimaga olib boradi</Label>
            <Select
              id="b-target"
              value={form.target_type}
              onChange={(event) => set("target_type", event.target.value)}
            >
              {TARGETS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex-1 space-y-1">
            <Label htmlFor="b-target-value">Qiymati</Label>
            <Input
              id="b-target-value"
              value={form.target_value}
              placeholder="krossovkalar"
              onChange={(event) => set("target_value", event.target.value)}
            />
          </div>
        </div>

        <div className="flex items-end gap-2">
          <div className="flex-1 space-y-1">
            <Label htmlFor="b-from">Gradient — boshi</Label>
            <Input
              id="b-from"
              value={form.gradient_from}
              onChange={(event) => set("gradient_from", event.target.value)}
            />
          </div>
          <div className="flex-1 space-y-1">
            <Label htmlFor="b-to">Gradient — oxiri</Label>
            <Input
              id="b-to"
              value={form.gradient_to}
              onChange={(event) => set("gradient_to", event.target.value)}
            />
          </div>
          <span
            className="mb-0.5 size-8 shrink-0 rounded border border-line"
            style={{
              background: `linear-gradient(135deg, ${form.gradient_from}, ${form.gradient_to})`,
            }}
            aria-hidden
          />
        </div>

        <label className="flex items-center gap-2 text-[13px] text-ink">
          <input
            type="checkbox"
            checked={form.active}
            onChange={(event) => set("active", event.target.checked)}
          />
          Ilovada ko'rinsin
        </label>
      </div>
    </ConfirmDialog>
  )
}

// -------------------------------------------------------------------- rails

function SectionsTab() {
  const [creating, setCreating] = React.useState(false)
  const [editing, setEditing] = React.useState<AdminSection | null>(null)
  const [removing, setRemoving] = React.useState<AdminSection | null>(null)

  const query = useQuery({
    queryKey: SECTIONS,
    queryFn: () => api<AdminSection[]>("/staff/showcase/sections"),
  })

  return (
    <>
      <Arrangement<AdminSection>
        title="Bosh sahifa bloklari"
        hint="Ilovaning bosh ekranidagi qatorlar, yuqoridan pastga."
        rows={query.data}
        loading={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        path="/staff/showcase/sections/order"
        invalidate={SECTIONS}
        emptyTitle="Blok yo'q"
        actions={
          <Button size="sm" variant="primary" onClick={() => setCreating(true)}>
            <Plus />
            Blok
          </Button>
        }
        renderRow={(row) => (
          <div className="flex items-center gap-2">
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-medium text-ink">{row.title}</p>
              <p className="tabular truncate text-[12px] text-ink-faint">
                {row.key}
                {row.category_slug ? ` → ${row.category_slug}` : ""}
              </p>
            </div>
            <Badge tone="neutral">{row.layout}</Badge>
            {row.active ? null : <Badge tone="neutral">O'chiq</Badge>}
            <Button size="sm" onClick={() => setEditing(row)}>
              Tahrirlash
            </Button>
            <Button
              size="icon"
              variant="ghost"
              aria-label="O'chirish"
              onClick={() => setRemoving(row)}
            >
              <Trash2 />
            </Button>
          </div>
        )}
      />

      {creating ? <SectionForm onClose={() => setCreating(false)} /> : null}
      {editing ? (
        <SectionForm section={editing} onClose={() => setEditing(null)} />
      ) : null}
      {removing ? (
        <DeleteRow
          title="Blokni o'chirish"
          description={removing.title}
          path={`/staff/showcase/sections/${removing.key}`}
          invalidate={SECTIONS}
          onClose={() => setRemoving(null)}
        />
      ) : null}
    </>
  )
}

const LAYOUTS = ["rail", "grid", "banner"]

function SectionForm({
  section,
  onClose,
}: {
  section?: AdminSection
  onClose: () => void
}) {
  const categories = useQuery({
    queryKey: ["categories", "roots"],
    queryFn: () => api<Category[]>("/categories"),
  })

  const [form, setForm] = React.useState({
    key: section?.key ?? "",
    title: section?.title ?? "",
    subtitle: section?.subtitle ?? "",
    category_slug: section?.category_slug ?? "",
    layout: section?.layout ?? "rail",
    active: section?.active ?? true,
  })

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  const save = useAction<void, AdminSection>({
    run: () => {
      const body = {
        title: form.title.trim(),
        subtitle: form.subtitle,
        category_slug: form.category_slug || null,
        layout: form.layout,
        active: form.active,
      }
      return section
        ? api<AdminSection>(`/staff/showcase/sections/${section.key}`, {
            method: "PATCH",
            json: body,
          })
        : api<AdminSection>("/staff/showcase/sections", {
            method: "POST",
            json: { ...body, key: form.key.trim() },
          })
    },
    invalidate: [SECTIONS],
    success: section ? "Blok saqlandi" : "Blok qo'shildi",
    onDone: onClose,
  })

  return (
    <ConfirmDialog
      open
      onOpenChange={(next) => !next && onClose()}
      title={section ? "Blokni tahrirlash" : "Blok qo'shish"}
      confirmLabel="Saqlash"
      disabled={!form.title.trim() || (!section && !form.key.trim())}
      pending={save.isPending}
      onConfirm={() => save.mutate()}
    >
      <div className="space-y-3">
        {section ? null : (
          <div className="space-y-1">
            <Label htmlFor="s-key">Kalit</Label>
            <Input
              id="s-key"
              autoFocus
              value={form.key}
              placeholder="yangi-kelganlar"
              onChange={(event) => set("key", event.target.value)}
            />
            <Hint>O'zgarmas nom — keyin tahrirlanmaydi, ilova shunga tayanadi.</Hint>
          </div>
        )}

        <div className="space-y-1">
          <Label htmlFor="s-title">Sarlavha</Label>
          <Input
            id="s-title"
            value={form.title}
            onChange={(event) => set("title", event.target.value)}
          />
        </div>

        <div className="space-y-1">
          <Label htmlFor="s-subtitle">Izoh</Label>
          <Input
            id="s-subtitle"
            value={form.subtitle}
            onChange={(event) => set("subtitle", event.target.value)}
          />
        </div>

        <div className="flex gap-2">
          <div className="flex-1 space-y-1">
            <Label htmlFor="s-category">Turkum</Label>
            <Select
              id="s-category"
              value={form.category_slug}
              onChange={(event) => set("category_slug", event.target.value)}
            >
              <option value="">— turkumsiz —</option>
              {(categories.data ?? []).map((category) => (
                <option key={category.slug} value={category.slug}>
                  {category.name}
                </option>
              ))}
            </Select>
            <Hint>Yo'q turkumga ishora qilgan blok ilovada bo'sh ko'rinadi.</Hint>
          </div>
          <div className="w-32 space-y-1">
            <Label htmlFor="s-layout">Ko'rinishi</Label>
            <Select
              id="s-layout"
              value={form.layout}
              onChange={(event) => set("layout", event.target.value)}
            >
              {LAYOUTS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </Select>
          </div>
        </div>

        <label className="flex items-center gap-2 text-[13px] text-ink">
          <input
            type="checkbox"
            checked={form.active}
            onChange={(event) => set("active", event.target.checked)}
          />
          Bosh sahifada ko'rinsin
        </label>
      </div>
    </ConfirmDialog>
  )
}

// -------------------------------------------------------------- promo codes

function PromosTab() {
  const [creating, setCreating] = React.useState(false)
  const [editing, setEditing] = React.useState<AdminPromo | null>(null)
  const [removing, setRemoving] = React.useState<AdminPromo | null>(null)

  const query = useQuery({
    queryKey: PROMOS,
    queryFn: () => api<AdminPromo[]>("/staff/showcase/promos"),
  })

  const columns: Column<AdminPromo>[] = [
    {
      key: "code",
      header: "Kod",
      sortValue: (row) => row.code,
      cell: (row) => <span className="tabular font-medium text-ink">{row.code}</span>,
    },
    {
      key: "discount",
      header: "Chegirma",
      cell: (row) =>
        row.percent_off ? `${row.percent_off}%` : row.amount_off ? money(row.amount_off) : "—",
    },
    {
      key: "min",
      header: "Eng kam savat",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.min_total,
      cell: (row) => (row.min_total ? money(row.min_total) : "—"),
    },
    {
      key: "active",
      header: "Holat",
      sortValue: (row) => String(row.active),
      cell: (row) =>
        row.active ? <Badge tone="good">Ishlaydi</Badge> : <Badge tone="neutral">O'chiq</Badge>,
    },
    {
      key: "actions",
      header: "",
      headClassName: "text-right",
      className: "text-right",
      cell: (row) => (
        <div className="flex justify-end gap-1.5">
          <Button size="sm" onClick={() => setEditing(row)}>
            Tahrirlash
          </Button>
          <Button
            size="icon"
            variant="ghost"
            aria-label="O'chirish"
            onClick={() => setRemoving(row)}
          >
            <Trash2 />
          </Button>
        </div>
      ),
    },
  ]

  return (
    <>
      <DataTable
        rows={query.data}
        columns={columns}
        rowKey={(row) => row.id}
        loading={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        emptyTitle="Promo-kod yo'q"
        toolbar={
          <>
            <Button size="sm" variant="primary" onClick={() => setCreating(true)}>
              <Plus />
              Promo-kod
            </Button>
            <Hint>
              Ishlatilgan kod o'chirilmaydi — o'chirib qo'yiladi, keyingi yil yodidan
              yozib chiqmaslik uchun.
            </Hint>
          </>
        }
      />

      {creating ? <PromoForm onClose={() => setCreating(false)} /> : null}
      {editing ? <PromoForm promo={editing} onClose={() => setEditing(null)} /> : null}
      {removing ? (
        <DeleteRow
          title="Promo-kodni o'chirish"
          description={removing.code}
          path={`/staff/showcase/promos/${removing.code}`}
          invalidate={PROMOS}
          onClose={() => setRemoving(null)}
        />
      ) : null}
    </>
  )
}

function PromoForm({ promo, onClose }: { promo?: AdminPromo; onClose: () => void }) {
  const [code, setCode] = React.useState(promo?.code ?? "")
  const [percent, setPercent] = React.useState(String(promo?.percent_off ?? 0))
  const [amount, setAmount] = React.useState(String(promo?.amount_off ?? 0))
  const [minTotal, setMinTotal] = React.useState(String(promo?.min_total ?? 0))
  const [active, setActive] = React.useState(promo?.active ?? true)

  const save = useAction<void, AdminPromo>({
    run: () => {
      const body = {
        percent_off: Number(percent) || 0,
        amount_off: Number(amount) || 0,
        min_total: Number(minTotal) || 0,
        active,
      }
      return promo
        ? api<AdminPromo>(`/staff/showcase/promos/${promo.code}`, {
            method: "PATCH",
            json: body,
          })
        : api<AdminPromo>("/staff/showcase/promos", {
            method: "POST",
            json: { ...body, code: code.trim().toUpperCase() },
          })
    },
    invalidate: [PROMOS],
    success: promo ? "Promo-kod saqlandi" : "Promo-kod qo'shildi",
    onDone: onClose,
  })

  const both = Number(percent) > 0 && Number(amount) > 0

  return (
    <ConfirmDialog
      open
      onOpenChange={(next) => !next && onClose()}
      title={promo ? `Promo-kod ${promo.code}` : "Promo-kod qo'shish"}
      confirmLabel="Saqlash"
      disabled={(!promo && !code.trim()) || both}
      pending={save.isPending}
      onConfirm={() => save.mutate()}
    >
      <div className="space-y-3">
        {promo ? null : (
          <div className="space-y-1">
            <Label htmlFor="p-code">Kod</Label>
            <Input
              id="p-code"
              autoFocus
              className="tabular uppercase"
              value={code}
              placeholder="YOZ25"
              onChange={(event) => setCode(event.target.value)}
            />
          </div>
        )}

        <div className="flex gap-2">
          <div className="flex-1 space-y-1">
            <Label htmlFor="p-percent">Foiz</Label>
            <Input
              id="p-percent"
              type="number"
              min={0}
              max={100}
              value={percent}
              onChange={(event) => setPercent(event.target.value)}
            />
          </div>
          <div className="flex-1 space-y-1">
            <Label htmlFor="p-amount">Yoki summa (so'm)</Label>
            <Input
              id="p-amount"
              type="number"
              min={0}
              step={1000}
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
            />
          </div>
        </div>
        {both ? (
          <p className="text-[12px] font-medium text-danger">
            Foiz va summa birga bo'lmaydi — bittasini 0 qiling.
          </p>
        ) : null}

        <div className="space-y-1">
          <Label htmlFor="p-min">Eng kam savat (so'm)</Label>
          <Input
            id="p-min"
            type="number"
            min={0}
            step={1000}
            value={minTotal}
            onChange={(event) => setMinTotal(event.target.value)}
          />
          <Hint>Savat shu summadan past bo'lsa kod qo'llanmaydi.</Hint>
        </div>

        <label className="flex items-center gap-2 text-[13px] text-ink">
          <input
            type="checkbox"
            checked={active}
            onChange={(event) => setActive(event.target.checked)}
          />
          Kod ishlasin
        </label>
      </div>
    </ConfirmDialog>
  )
}

// ----------------------------------------------------------------- deleting

/**
 * One delete for all three.
 *
 * The refusals are the backend's: a promo code that has been redeemed answers
 * 409 with the sentence saying so, and that sentence is what the toast shows.
 * Guessing here which rows are deletable would be a second copy of a rule that
 * lives in `showcase.py`.
 */
function DeleteRow({
  title,
  description,
  path,
  invalidate,
  onClose,
}: {
  title: string
  description: string
  path: string
  invalidate: string[]
  onClose: () => void
}) {
  const remove = useAction<void, { message: string }>({
    run: () => api<{ message: string }>(path, { method: "DELETE" }),
    invalidate: [invalidate],
    success: (result) => result.message,
    onDone: onClose,
  })

  return (
    <ConfirmDialog
      open
      onOpenChange={(next) => !next && onClose()}
      title={title}
      description={description}
      confirmLabel="O'chirish"
      destructive
      pending={remove.isPending}
      onConfirm={() => remove.mutate()}
    >
      <p className="text-[13px] text-ink-soft">
        Ishlatilgan yozuvni server o'chirtirmaydi — o'rniga uni o'chirib qo'ying.
      </p>
    </ConfirmDialog>
  )
}
