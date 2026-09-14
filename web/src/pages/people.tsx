/**
 * Kategoriyalar and Kuryerlar — two small screens with one rule each.
 *
 * **Xodimlar has left this file.** It was a hand-rolled list of unstyled
 * panels whose only control was five role buttons that fired on a single
 * click, and it read `/admin/users`, which answers with every account in the
 * shop. It is now `pages/staff.tsx`, on the house table, against the door
 * that answers with colleagues only.
 *
 * **A category is a slug and a name.** The tree is shallow on purpose: the
 * catalogue is one shop's, and a five-level taxonomy is a taxonomy nobody
 * files anything under.
 *
 * **The name can be corrected and the row thrown away; the code cannot.** A
 * category is written in a hurry — beside an open sack, by somebody filing a
 * card that had nowhere to go — so a typo in it is the ordinary case, and
 * until now it was permanent: the screen could only add. The slug stays fixed
 * because it is what every filed card and every link in the phone app points
 * at. Deleting is the server's to refuse, and the row says in advance why it
 * would: a category with cards in it, or with categories under it, is holding
 * something up.
 *
 * Both screens used to write `rounded-panel border border-line bg-surface
 * shadow-panel p-3` out by hand, in four places. That string is `Panel`, and
 * `Panel` no longer carries a border or a shadow: a card is told apart from
 * the page by being lighter than it, and three devices doing one job is what
 * made a screen of panels read as a form full of boxes.
 */

import { Loader2, Pencil, Trash2 } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router-dom"

import { Empty, PageHeader, Panel, Problem, Waiting } from "@/components/page"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { groups } from "@/lib/format"
import {
  useCategories,
  useCouriers,
  useDeleteCategory,
  useEditCategory,
  useWriteCategory,
} from "@/lib/queries"
import type { AdminCategory } from "@/lib/types"

// ---------------------------------------------------------------- categories

export function CategoriesPage() {
  const categories = useCategories()
  const write = useWriteCategory()
  const [name, setName] = useState("")

  return (
    <div className="space-y-4">
      <PageHeader title="Kategoriyalar" subtitle="Kataloqning javonlari" />

      <Panel title="Yangi kategoriya">
        <form
          onSubmit={(event) => {
            event.preventDefault()
            write.mutate(
              { slug: slugify(name), name: name.trim() },
              { onSuccess: () => setName("") },
            )
          }}
          className="flex flex-wrap gap-2"
        >
          <Input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Krossovkalar"
            aria-label="Kategoriya nomi"
            className="flex-1"
          />
          <Button type="submit" disabled={write.isPending || !name.trim()}>
            Qo'shish
          </Button>
          {name.trim() ? (
            <p className="w-full text-micro text-ink-faint">
              Kodi: <span className="tabular">{slugify(name)}</span>
            </p>
          ) : null}
        </form>
      </Panel>

      <Problem error={write.error || categories.error} />
      {categories.isLoading ? <Waiting /> : null}

      {/* One panel holding rows, not a stack of one-row panels: a list is a
          list, and thirty cards with an edge each reads as thirty objects. */}
      {categories.data?.length === 0 ? (
        <Empty what="Hali kategoriya yo'q — birinchisini yozing." />
      ) : categories.data?.length ? (
        <Panel
          title="Kategoriyalar"
          aside={
            <span className="text-micro text-ink-soft">
              {groups(categories.data.length)} ta
            </span>
          }
          bare
        >
          <ul className="divide-y divide-line">
            {categories.data.map((category) => (
              <li key={category.slug}>
                <CategoryRow category={category} />
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}
    </div>
  )
}

/**
 * One category: read it, correct it, or throw it away.
 *
 * Three states in one row rather than a screen of its own, because a category
 * is three fields and opening a page to change one word is a page nobody
 * opens. Editing replaces the row in place; deleting asks in the button it is
 * about to act on — two taps, the first turning the button into the sentence —
 * rather than in a dialog, which is how the rest of this app asks.
 */
function CategoryRow({ category }: { category: AdminCategory }) {
  const [editing, setEditing] = useState(false)
  const edit = useEditCategory(category.slug)
  const remove = useDeleteCategory(category.slug)
  const [name, setName] = useState(category.name)
  const [subtitle, setSubtitle] = useState(category.subtitle)
  const [asked, setAsked] = useState(false)

  // What the server will refuse, said before anybody presses anything — and
  // said without the figure, which is already in the column beside it: the row
  // reads "3 · kartalari bor" rather than "3 · 3 ta karta shu yerda".
  const holding =
    category.product_count > 0
      ? "kartalari bor"
      : category.child_count > 0
        ? "ichki kategoriyasi bor"
        : ""

  if (editing) {
    return (
      <form
        className="space-y-2 bg-brand-soft/40 px-4 py-3"
        onSubmit={(event) => {
          event.preventDefault()
          if (!name.trim()) return
          edit.mutate(
            { name: name.trim(), subtitle: subtitle.trim() },
            { onSuccess: () => setEditing(false) },
          )
        }}
      >
        <label className="block">
          <span className="mb-1 block text-micro text-ink-soft">
            Nomi — mijoz shuni ko'radi
          </span>
          <Input
            value={name}
            onChange={(event) => setName(event.target.value)}
            aria-label={`${category.slug} — nomi`}
            className="bg-surface"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-micro text-ink-soft">
            Qisqa izoh — bo'lmasa bo'sh qoldiring
          </span>
          <Input
            value={subtitle}
            onChange={(event) => setSubtitle(event.target.value)}
            aria-label={`${category.slug} — qisqa izoh`}
            className="bg-surface"
          />
        </label>

        {/* Said where somebody is about to look for it, because the obvious
            next question on a rename screen is why one field will not take. */}
        <p className="text-micro text-ink-faint">
          Kodi <span className="tabular">{category.slug}</span> — o'zgarmaydi:
          kartalar va ilovadagi havolalar shunga bog'langan.
        </p>

        <Problem error={edit.error} />
        <div className="flex gap-2">
          <Button type="submit" size="sm" disabled={edit.isPending || !name.trim()} >
            {edit.isPending ? <Loader2 className="animate-spin" /> : null}
            Saqlash
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => {
              setName(category.name)
              setSubtitle(category.subtitle)
              setEditing(false)
            }}
          >
            Bekor
          </Button>
        </div>
      </form>
    )
  }

  return (
    <div className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-line-soft">
      <div className="min-w-0 flex-1">
        <div className="truncate text-small font-medium">{category.name}</div>
        <div className="truncate text-micro text-ink-faint">
          <span className="tabular">{category.slug}</span>
          {category.subtitle ? ` · ${category.subtitle}` : ""}
        </div>
        <Problem error={remove.error} />
      </div>

      {asked ? (
        <div className="flex items-center gap-2">
          <span className="text-micro text-danger">{category.name} — o'chirilsinmi?</span>
          <Button
            size="sm"
            variant="danger"
            disabled={remove.isPending}
            onClick={() => remove.mutate(undefined, { onSuccess: () => setAsked(false) })}
          >
            {remove.isPending ? <Loader2 className="animate-spin" /> : "Ha"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setAsked(false)}>
            Yo'q
          </Button>
        </div>
      ) : (
        <>
          <span className="tabular text-small text-ink-soft">
            {groups(category.product_count)}
          </span>
          <Button
            size="sm"
            variant="ghost"
            aria-label={`${category.name} — tahrirlash`}
            onClick={() => setEditing(true)}
          >
            <Pencil className="size-4" />
          </Button>
          {/* Nothing to press and the reason it is not there, rather than a
              button that asks and is refused. */}
          {holding ? (
            <span
              className="w-36 shrink-0 text-right text-micro text-ink-faint"
              title={`Avval ${category.product_count > 0 ? "kartalarni" : "ichki kategoriyalarni"} boshqa joyga o'tkazing`}
            >
              {holding}
            </span>
          ) : (
            <Button
              size="sm"
              variant="ghost"
              className="text-danger"
              aria-label={`${category.name} — o'chirish`}
              onClick={() => setAsked(true)}
            >
              <Trash2 className="size-4" />
            </Button>
          )}
        </>
      )}
    </div>
  )
}

/**
 * A slug from a name, in the alphabet a URL can carry.
 *
 * Uzbek is written in Latin here, so this is mostly lowercasing and hyphens —
 * except for the apostrophes in o' and g', which are the two letters a naive
 * slug turns into rubbish.
 */
function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[''`]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
}

// ------------------------------------------------------------------ couriers

export function CouriersPage() {
  const couriers = useCouriers()

  return (
    <div className="space-y-4">
      <PageHeader title="Kuryerlar" subtitle="Kim ish olishi mumkin" />
      <Problem error={couriers.error} />
      {couriers.isLoading ? <Waiting /> : null}
      {couriers.data?.length === 0 ? (
        <Empty what="Kuryer yo'q — Xodimlar ekranida «Xodim qo'shish» orqali tayinlang." />
      ) : couriers.data?.length ? (
        <Panel
          title="Kuryerlar"
          aside={
            <Button asChild variant="ghost" size="sm">
              <Link to="/xodimlar?role=courier">Xodimlarda</Link>
            </Button>
          }
          bare
        >
          <ul className="divide-y divide-line">
            {couriers.data.map((courier) => (
              <li key={courier.id} className="flex items-center gap-3 px-4 py-2.5">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-small font-medium">
                    {courier.full_name || courier.phone}
                  </div>
                  <div className="text-micro tabular text-ink-soft">{courier.phone}</div>
                </div>
                {/* Where a courier's parcels are is a fact about the room, so
                    it is on the shelf map as a tile per bag rather than
                    duplicated here. */}
                <Button asChild variant="ghost" size="sm">
                  <Link to="/ombor">Xaritada</Link>
                </Button>
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}
    </div>
  )
}
