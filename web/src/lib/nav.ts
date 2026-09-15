/**
 * The navigation, which is the only place a role decides what an app is.
 *
 * Three jobs, one bundle. The office reads hundreds of rows at a desk; the
 * bench works standing up with a phone in one hand; the courier is outdoors,
 * one-handed, sometimes in a glove. That is a real difference and it is kept —
 * as a **density on one system** rather than as three applications that drift
 * apart, which is exactly what happened the last time there were three.
 *
 * ------------------------------------------------------------------ grouping
 *
 * The menu nests **one level and no more**. One level is a drawer somebody
 * opens; two is a filing cabinet somebody gives up on, and a back office with
 * fourteen flat items is a list nobody reads past the sixth. The office menu
 * is the only one long enough to want it — the bench and the road have four
 * or five screens each and stay flat, because grouping five things hides them
 * behind a click for no reason.
 *
 * A group has no route. Its `to` is a `#key` that no router will ever match,
 * which is what makes "clicking it opens rather than navigates" a property of
 * the data rather than a rule every renderer has to remember.
 */

import type { LucideIcon } from "lucide-react"
import {
  Boxes,
  ClipboardList,
  Home,
  Layers,
  ListOrdered,
  Map,
  PackageCheck,
  PackageSearch,
  Route,
  ScanBarcode,
  Truck,
  Undo2,
  Users,
  Wallet,
  Warehouse,
} from "lucide-react"

import type { Role } from "@/lib/session"

export type NavItem = {
  /** The route — or, for a group, a `#key` that matches no route. */
  to: string
  label: string
  /** A group and a top-level item have one. A child has a dash instead. */
  icon?: LucideIcon
  /** A dashboard tile key whose value rides on this item as a count. A queue
   *  nobody can see the length of is a queue that grows. */
  badge?: string
  /** One level deep. A parent with children navigates nowhere: it opens. */
  children?: NavItem[]
}

/** Does this item open a drawer rather than go somewhere? */
export function isGroup(item: NavItem): boolean {
  return Boolean(item.children?.length)
}

/** Interface language is Uzbek. There is no language picker: everybody who
 * signs in here works in this building and reads it. */
const ADMIN: NavItem[] = [
  { to: "/", label: "Boshqaruv", icon: Home },
  {
    to: "#katalog",
    label: "Katalog",
    icon: Boxes,
    children: [
      // The held-back count rides here now that publishing lives on the card:
      // goods on a shelf no customer can buy break nothing and error nowhere,
      // so a figure in the rail is the only thing that gets the queue worked.
      { to: "/mahsulotlar", label: "Mahsulotlar", badge: "held_back" },
      { to: "/kategoriyalar", label: "Kategoriyalar" },
    ],
  },
  // Everything about an order's journey, including the half that runs
  // backwards. A return is not a kind of order and not a kind of receiving —
  // it is a customer waiting for an answer, and it was the one flow in the
  // building with a person at the far end of it and no screen at all.
  {
    to: "#buyurtmalar",
    label: "Buyurtmalar",
    icon: ListOrdered,
    children: [
      { to: "/buyurtmalar", label: "Buyurtmalar" },
      { to: "/qaytarishlar", label: "Qaytarishlar" },
      { to: "/olib-kelish", label: "Olib kelish" },
      { to: "/yetkazish-oynalari", label: "Yetkazish oynalari" },
    ],
  },
  {
    to: "#ombor",
    label: "Ombor",
    icon: Warehouse,
    children: [
      { to: "/ombor", label: "Ombor xaritasi" },
      // Goods labelled at the bench and not yet in a cell — the second moment
      // of a receipt, waiting.
      { to: "/qabul", label: "Qabul", badge: "labelled_unshelved" },
    ],
  },
  {
    to: "#odamlar",
    label: "Odamlar",
    icon: Users,
    children: [
      { to: "/xodimlar", label: "Xodimlar" },
      { to: "/mijozlar", label: "Mijozlar" },
      { to: "/kuryerlar", label: "Kuryerlar" },
    ],
  },
  // `Harakatlar` — the paged table of raw stock movements — used to be the
  // first child here, and it is gone. Not moved and not renamed: the owner
  // said the panel does not watch movements ("harakatlarni olib tashlash
  // kerak, buni kuzatish kerak emas"), and `/hisobotlar` is now the six
  // reports that answer the question they were opening this menu to ask.
  // `GET /warehouse/stock/movements` still exists and has no caller in the
  // panel; the shelf map and a stocktake are where a disagreement about a
  // count gets settled now.
  //
  // `Jurnal` stays, because it is a different question — who changed what,
  // and when — and nobody asked for it to go.
  {
    to: "#hisobotlar",
    label: "Hisobotlar",
    icon: ClipboardList,
    children: [
      { to: "/hisobotlar", label: "Ko'rsatkichlar" },
      { to: "/jurnal", label: "Jurnal" },
    ],
  },
]

/**
 * The bench, standing up.
 *
 * `Qaytarishlar` and `Olib kelish` are here as well as in the office's menu
 * because opening the parcel is the warehouse's job and deciding about the
 * money is the owner's — the server draws that line too, and the two halves
 * of a return are done by two people at two benches. What the bench cannot do
 * from this screen is approve, reject or pay.
 */
const WAREHOUSE: NavItem[] = [
  { to: "/ombor", label: "Ombor xaritasi", icon: Map },
  { to: "/qabul", label: "Qabul", icon: PackageSearch, badge: "labelled_unshelved" },
  { to: "/terish", label: "Terish", icon: PackageCheck },
  { to: "/sanash", label: "Sanash", icon: Layers },
  { to: "/qaytarishlar", label: "Qaytarishlar", icon: Undo2 },
  { to: "/olib-kelish", label: "Olib kelish", icon: Truck },
  { to: "/yorliqlar", label: "Yorliqlar", icon: ScanBarcode },
]

// The seller role is gone, and with it the "Sotuvga chiqarish" screen it
// owned: there is one shop, and the person who photographs the goods is the
// person who sells them. Publishing is three gates on the product card in
// `/mahsulotlar`, and the held-back count rides on that menu item instead.

const COURIER: NavItem[] = [
  { to: "/ishlarim", label: "Mening ishlarim", icon: Route },
  { to: "/tarix", label: "Tarix", icon: ClipboardList },
  { to: "/daromad", label: "Daromad", icon: Wallet },
]

/**
 * The screens a role may *open* without one being in their menu.
 *
 * It is empty, and that is the fix rather than an omission. The office had
 * two entries here — the receiving desk and the shop window — because the
 * dashboard links a figure at the screen it is worked on, and an owner who
 * taps one has to arrive somewhere. Both are now in the office's menu, under
 * a parent, which is the better answer to the same problem: a screen an owner
 * can be sent to but cannot find is a screen they can only reach by being
 * sent. The hook stays because the next such screen will want it.
 */
const REACHABLE: Partial<Record<Role, string[]>> = {}

/** Every navigable item in a tree — groups are doors, not destinations. */
function leaves(items: NavItem[]): NavItem[] {
  return items.flatMap((item) => (item.children?.length ? item.children : [item]))
}

/**
 * May this role open this screen?
 *
 * Asked by the router, which builds the route table from it, and by any
 * screen that draws a link to another — a link to a screen the router will
 * not build is a link that quietly lands somewhere else. It walks into
 * groups: a screen filed under a parent is no less reachable for it.
 */
export function canReach(role: Role, to: string): boolean {
  return (
    leaves(navFor(role)).some((item) => item.to === to) ||
    (REACHABLE[role] ?? []).includes(to)
  )
}

export function navFor(role: Role): NavItem[] {
  if (role === "admin") return ADMIN
  if (role === "warehouse") return WAREHOUSE
  if (role === "courier") return COURIER
  return []
}

/**
 * Every screen in a role's menu, flat, each knowing the drawer it came out
 * of — what the rail's search searches and what the breadcrumb reads.
 */
export type NavLeaf = { item: NavItem; parent?: NavItem }

export function navLeaves(items: NavItem[]): NavLeaf[] {
  return items.flatMap((item) =>
    item.children?.length
      ? item.children.map((child) => ({ item: child, parent: item }))
      : [{ item }],
  )
}

/**
 * Which item the current URL is on, and which drawer that puts open.
 *
 * Longest prefix wins, so `/ombor/A1` lands on `Ombor xaritasi` rather than
 * on nothing, and a future `/xodimlar/7` keeps `Odamlar` open behind it. The
 * root is matched exactly: everything starts with `/`.
 */
export function matchNav(items: NavItem[], pathname: string): NavLeaf | undefined {
  let best: NavLeaf | undefined
  let longest = 0

  for (const leaf of navLeaves(items)) {
    const to = leaf.item.to
    if (to.startsWith("#")) continue
    const hit = to === pathname || (to !== "/" && pathname.startsWith(`${to}/`))
    if (hit && to.length > longest) {
      longest = to.length
      best = leaf
    }
  }
  return best
}

/**
 * The density class for a role, from `shared/theme.css`.
 *
 * Not a preference. A row read at arm's length at a desk wants to be small
 * so that more of them fit; a button pressed with a glove on wants to be
 * 64px whatever anybody's taste is.
 */
export function densityFor(role: Role): string {
  if (role === "admin") return "density-compact"
  if (role === "courier") return "density-comfortable"
  return "density-cozy"
}

/** Where a role lands after signing in. */
export function homeFor(role: Role): string {
  if (role === "admin") return "/"
  if (role === "warehouse") return "/ombor"
  return "/ishlarim"
}
