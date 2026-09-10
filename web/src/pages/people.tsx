/**
 * Xodimlar and Kategoriyalar — two small screens with one rule each.
 *
 * **The last admin cannot be stood down.** A role is granted by an admin, so
 * an admin is the only person who can put one back; demote the last one and
 * the grant is unreachable from inside the running system. The server refuses
 * it, and this screen shows the refusal rather than hiding the button — the
 * person who tried is the likeliest one to need the sentence.
 *
 * **A category is a slug and a name.** The tree is shallow on purpose: the
 * catalogue is one shop's, and a five-level taxonomy is a taxonomy nobody
 * files anything under.
 */

import { useState } from "react"

import { Empty, PageHeader, Problem, Waiting } from "@/components/page"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/cn"
import { date, groups } from "@/lib/format"
import {
  useCategories,
  useCouriers,
  useSetRole,
  useStaff,
  useWriteCategory,
} from "@/lib/queries"
import type { StaffUser } from "@/lib/types"

// Every role there is, or the screen lies twice: the missing one cannot be
// granted, and the person who already holds it shows with nothing selected —
// which reads as an account with no role at all rather than as a shop
// assistant. `seller` was left out when the role came back.
const ROLES = [
  { key: "admin", label: "Administrator" },
  { key: "warehouse", label: "Ombor" },
  { key: "seller", label: "Sotuvchi" },
  { key: "courier", label: "Kuryer" },
  { key: "customer", label: "Mijoz" },
]

export function StaffPage() {
  const people = useStaff()

  return (
    <div className="space-y-4">
      <PageHeader title="Xodimlar" subtitle="Kim nima qila oladi" />
      <Problem error={people.error} />
      {people.isLoading ? <Waiting what="Xodimlar" /> : null}

      <ul className="space-y-2">
        {(people.data?.items ?? []).map((person) => (
          <li key={person.id}>
            <Person person={person} />
          </li>
        ))}
      </ul>
    </div>
  )
}

function Person({ person }: { person: StaffUser }) {
  const setRole = useSetRole(person.id)

  return (
    <div className="rounded-panel border border-line bg-surface shadow-panel p-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <div className="truncate text-small font-medium">
            {person.full_name || person.phone}
          </div>
          <div className="text-micro tabular text-ink-faint">
            {person.phone} · {date(person.created_at)}
          </div>
        </div>
        <div className="flex flex-wrap gap-1">
          {ROLES.map((role) => (
            <button
              key={role.key}
              type="button"
              disabled={setRole.isPending || role.key === person.role}
              onClick={() => setRole.mutate({ role: role.key })}
              className={cn(
                "h-control rounded-control border px-2 text-micro",
                role.key === person.role && "border-brand bg-brand-soft text-brand-deep",
              )}
            >
              {role.label}
            </button>
          ))}
        </div>
      </div>
      <Problem error={setRole.error} />
    </div>
  )
}

// ---------------------------------------------------------------- categories

export function CategoriesPage() {
  const categories = useCategories()
  const write = useWriteCategory()
  const [name, setName] = useState("")

  return (
    <div className="space-y-4">
      <PageHeader title="Kategoriyalar" subtitle="Kataloqning javonlari" />

      <form
        onSubmit={(event) => {
          event.preventDefault()
          write.mutate(
            { slug: slugify(name), name: name.trim() },
            { onSuccess: () => setName("") },
          )
        }}
        className="flex flex-wrap gap-2 rounded-panel border border-line bg-surface shadow-panel p-3">
        <Input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Krossovkalar"
          aria-label="Kategoriya nomi"
          className="h-control flex-1" />
        <Button type="submit" disabled={write.isPending || !name.trim()} >
          Qo'shish
        </Button>
        {name.trim() ? (
          <p className="w-full text-micro text-ink-faint">
            Kodi: <span className="tabular">{slugify(name)}</span>
          </p>
        ) : null}
      </form>

      <Problem error={write.error || categories.error} />
      {categories.isLoading ? <Waiting /> : null}
      {categories.data?.length === 0 ? (
        <Empty what="Hali kategoriya yo'q — birinchisini yozing." />
      ) : null}

      <ul className="space-y-2">
        {(categories.data ?? []).map((category) => (
          <li
            key={category.slug}
            className="flex items-center gap-3 rounded-panel border border-line bg-surface shadow-panel p-3">
            <div className="min-w-0 flex-1">
              <div className="truncate text-small font-medium">{category.name}</div>
              <div className="text-micro tabular text-ink-faint">{category.slug}</div>
            </div>
            <span className="tabular text-small text-ink-soft">
              {groups(category.product_count)}
            </span>
          </li>
        ))}
      </ul>
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
        <Empty what="Kuryer yo'q — Xodimlar ekranidan rol bering." />
      ) : null}

      <ul className="space-y-2">
        {(couriers.data ?? []).map((courier) => (
          <li
            key={courier.id}
            className="flex items-center gap-3 rounded-panel border border-line bg-surface shadow-panel p-3">
            <div className="min-w-0 flex-1">
              <div className="truncate text-small font-medium">
                {courier.full_name || courier.phone}
              </div>
              <div className="text-micro tabular text-ink-faint">{courier.phone}</div>
            </div>
            {/* Where a courier's parcels are is a fact about the room, so it is
                on the shelf map as a tile per bag rather than duplicated here. */}
            <a
              href="/ombor"
              className="text-micro underline underline-offset-2 text-ink-soft">
              Xaritada
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}
