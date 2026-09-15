/**
 * §5.2 ·1 — the category, and it comes first because it decides what the rest
 * of the form offers.
 *
 * **Cascading selects, not a chip list.** The four-panel editor this replaces
 * printed every category in the database as a flat row of chips, which reads
 * fine with nine of them and is unusable with ninety — and, worse, it hides
 * the fact that the tree has depth. `Kiyim → Oyoq kiyim
 * → Erkaklar → Krossovka` is four decisions, each one narrowing the next, and
 * the shape that says so is one select per level.
 *
 * **Accept, then collapse.** The selects stay until somebody presses
 * *Tanlash*, and then they become a breadcrumb with *O'zgartirish* beside it.
 * The button used to say *Qabul qilish* — which on a screen whose neighbour is
 * the receiving desk reads as "book these goods in" rather than "this is the
 * category I mean".
 * That is not politeness: the rest of the form only appears once the category
 * is settled, because the category is what decides the sizes and the
 * attributes, and a form that re-offers itself every time a select moves is a
 * form that loses what was typed into it.
 *
 * A category is chosen at any depth. Filing a card under `Kiyim` is a coarse
 * filing, not an invalid one, and refusing it would send somebody to a
 * different menu to invent `Kiyim → Boshqa` before they could book goods in.
 */

import { Loader2, Pencil } from "lucide-react"
import { useEffect, useState } from "react"

import { Problem } from "@/components/page"
import { Button } from "@/components/ui/button"
import { useCategories } from "@/lib/queries"
import type { AdminCategory } from "@/lib/types"

/** The chosen category's ancestors, outermost first — the breadcrumb. */
function trail(all: AdminCategory[], slug: string | null): AdminCategory[] {
  const bySlug = new Map(all.map((one) => [one.slug, one]))
  const path: AdminCategory[] = []
  let at = slug ? bySlug.get(slug) : undefined
  // Bounded by the list's own length: a parent cycle in the data would
  // otherwise hang the form rather than draw a wrong breadcrumb.
  while (at && path.length <= all.length) {
    path.unshift(at)
    at = at.parent_slug ? bySlug.get(at.parent_slug) : undefined
  }
  return path
}

export function CategoryStep({
  value,
  onAccept,
  saving = false,
  error,
}: {
  /** What the card is filed under now, or `null` for a card with nothing. */
  value: string | null
  onAccept: (slug: string) => void
  saving?: boolean
  error?: unknown
}) {
  const categories = useCategories()
  const all = categories.data ?? []

  // Open while nothing is filed; a card that arrives filed opens collapsed.
  const [editing, setEditing] = useState(value === null)
  // One slug per level, outermost first. Choosing at a level drops everything
  // under it — a shoe re-filed from men's to women's must not keep the men's
  // sub-category hanging off it.
  const [picked, setPicked] = useState<string[]>([])

  // Seeded from what is filed, once the tree lands. Not on every render: the
  // selects are being driven by hand from here on and a value reset underneath
  // is the classic form that fights back.
  const [seeded, setSeeded] = useState(false)
  useEffect(() => {
    if (seeded || !categories.data) return
    setPicked(trail(categories.data, value).map((one) => one.slug))
    setSeeded(true)
  }, [categories.data, value, seeded])

  const filed = trail(all, value)

  if (!editing && value) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-small">
          {filed.map((one, at) => (
            <span key={one.slug}>
              {at > 0 ? <span className="mx-1 text-ink-faint">›</span> : null}
              <span className={at === filed.length - 1 ? "font-medium" : "text-ink-soft"}>
                {one.name}
              </span>
            </span>
          ))}
          {filed.length === 0 ? <span className="text-ink-soft">{value}</span> : null}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="gap-1"
          onClick={() => setEditing(true)}
        >
          <Pencil className="size-3.5" />
          O'zgartirish
        </Button>
      </div>
    )
  }

  // One level per already-picked slug, plus the next one — which is only drawn
  // when the last pick actually has children. The tree ends where it ends.
  const levels: { parent: string | null; options: AdminCategory[] }[] = []
  let parent: string | null = null
  for (let depth = 0; ; depth += 1) {
    const options = all.filter((one) => one.parent_slug === parent)
    if (!options.length) break
    levels.push({ parent, options })
    const chosen: string | undefined = picked[depth]
    if (!chosen) break
    parent = chosen
  }

  const chosen = picked[picked.length - 1] ?? ""

  return (
    <div className="space-y-2">
      {levels.map((level, depth) => (
        <select
          key={level.parent ?? "root"}
          value={picked[depth] ?? ""}
          aria-label={depth === 0 ? "Toifa" : `Ichki toifa ${depth}`}
          onChange={(event) => {
            const next = event.target.value
            setPicked((was) =>
              next ? [...was.slice(0, depth), next] : was.slice(0, depth),
            )
          }}
          className="h-control w-full rounded-control border border-transparent bg-line-soft px-3 text-small text-ink outline-none focus-visible:border-brand focus-visible:bg-surface focus-visible:ring-2 focus-visible:ring-brand/25"
        >
          <option value="">
            {depth === 0 ? "Toifani tanlang" : "Aniqrog'i — shart emas"}
          </option>
          {level.options.map((one) => (
            <option key={one.slug} value={one.slug}>
              {one.name}
            </option>
          ))}
        </select>
      ))}

      {categories.isLoading ? (
        <p className="text-micro text-ink-soft">Toifalar yuklanmoqda…</p>
      ) : null}

      <Problem error={categories.error || error} />

      <Button
        type="button"
        className="gap-2"
        disabled={!chosen || saving}
        onClick={() => {
          onAccept(chosen)
          setEditing(false)
        }}
      >
        {saving ? <Loader2 className="size-4 animate-spin" /> : null}
        Tanlash
      </Button>
    </div>
  )
}
