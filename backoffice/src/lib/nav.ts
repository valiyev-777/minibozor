import type { Role } from "@/api/types"
import { t } from "./labels"

/**
 * Which screens exist for which role — the whole of the difference between
 * the three people who work here.
 *
 * One table, and both the menu and the route guard read it. That is the point:
 * a menu built from one list and a guard written from another is how a panel
 * ends up with a row nobody can open, or a screen anybody can reach by typing
 * its path. `docs/rebuild-plan.md` §5 is this table in prose.
 *
 * The admin has everything, and not by being listed on every line — by the
 * rule below. An admin who could not do the operator's job would be an admin
 * who has to hand out a second account to get anything done.
 */
export type Screen = {
  path: string
  label: string
  /** Which roles may open it. The admin is added by `allowed`. */
  roles: readonly Role[]
  /** Shown in the menu. A detail screen is reachable and not listed. */
  menu?: boolean
}

const WAREHOUSE: readonly Role[] = ["warehouse"]
const BOTH: readonly Role[] = ["warehouse", "operator"]
/**
 * Nobody but the admin, and empty rather than `["admin"]` — the admin is
 * added by `allowed`, so listing them here would be the same fact written
 * twice and one of the two would eventually be wrong.
 */
const ADMIN: readonly Role[] = []

// There is deliberately no operator-only list. Both of the operator's screens
// — the queue and the returns — are the warehouse's too, because they are one
// list each with two jobs on them: the warehouse picks an order and the
// operator routes it; the warehouse says what arrived in a parcel and the
// operator decides the money. Splitting either would mean neither of them can
// see whose turn it is.

export const SCREENS: readonly Screen[] = [
  // The admin's own landing: four numbers and nothing else.
  { path: "/", label: t.overview, roles: ADMIN, menu: true },

  // The warehouse's day, in the order it happens.
  { path: "/supplies", label: t.supplies, roles: WAREHOUSE, menu: true },
  { path: "/supplies/:id", label: t.supply, roles: WAREHOUSE },
  { path: "/orders", label: t.orders, roles: BOTH, menu: true },
  { path: "/orders/:id", label: t.order, roles: BOTH },
  { path: "/pickups", label: t.pickups, roles: WAREHOUSE, menu: true },
  { path: "/removals", label: t.removals, roles: WAREHOUSE, menu: true },
  { path: "/stock", label: t.stock, roles: WAREHOUSE, menu: true },

  // Returns: the operator decides the money, the warehouse says what arrived.
  // One screen, because it is one row and hiding half of it from each of them
  // would mean neither can see whose turn it is.
  { path: "/returns", label: t.returns, roles: BOTH, menu: true },
  { path: "/returns/:id", label: t.return_, roles: BOTH },

  // The admin's.
  { path: "/sellers", label: t.sellers, roles: ADMIN, menu: true },
  { path: "/users", label: t.users, roles: ADMIN, menu: true },
  { path: "/catalog", label: t.catalog, roles: ADMIN, menu: true },
]

/** May this role open this screen? The admin may open everything. */
export function allowed(screen: Screen, role: Role): boolean {
  return role === "admin" || screen.roles.includes(role)
}

/** The rows in this role's menu, in the order above. */
export function menuFor(role: Role): Screen[] {
  return SCREENS.filter((screen) => screen.menu && allowed(screen, role))
}

/**
 * Where a role lands.
 *
 * The first screen in their menu, which is deliberately the first thing they
 * do: the warehouse opens the batches waiting to be counted, the operator
 * opens the order queue, the admin opens the four numbers.
 */
export function homeFor(role: Role): string {
  return menuFor(role)[0]?.path ?? "/"
}
