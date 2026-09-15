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
  FolderTree,
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
  /** Where the **count** goes, when that is not where the item goes.
   *
   *  `Mahsulotlar 15` opened the catalogue: twenty-six rows, oldest first,
   *  with the fifteen the badge was about scattered through it. A number that
   *  opens a different set from the one it counted is a number nobody trusts
   *  twice — so the word opens the catalogue and the figure opens the queue,
   *  and they are two targets because they are two questions. */
  badgeTo?: string
  /** What that figure is, for the tooltip on it — "15" beside "Mahsulotlar"
   *  says how many and not of what. */
  badgeWord?: string
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
  // `Katalog` was a drawer over two screens and the owner asked for the first
  // one out of it. Taking `Mahsulotlar` out left `Kategoriyalar` alone behind
  // a click, and a drawer holding one thing is strictly worse than the thing —
  // so the drawer is gone and both stand on their own.
  //
  // The held-back count rides on `Mahsulotlar` now that publishing lives on
  // the card: goods on a shelf no customer can buy break nothing and error
  // nowhere, so a figure in the rail is the only thing that gets the queue
  // worked — and it was one level down, which is where a count goes unread.
  {
    to: "/mahsulotlar",
    label: "Mahsulotlar",
    icon: Boxes,
    badge: "held_back",
    // The same address the dashboard tile carries, so the rail, the tile and
    // the list are three views of one figure rather than three figures.
    badgeTo: "/mahsulotlar?status=draft",
    badgeWord: "Do'konga chiqarilmagan kartalar",
  },
  { to: "/kategoriyalar", label: "Kategoriyalar", icon: FolderTree },
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

/**
 * Who this address belongs to, when it does not belong to the person asking.
 *
 * A warehouse worker opening `/mahsulotlar` — from a link, from a bookmark,
 * from yesterday's session — was told "Bunday sahifa yo'q", which is not
 * true: the page is there, it is the owner's, and the sentence sent somebody
 * to report a broken link instead of asking for it. The router builds a route
 * table per role, so "this role has no route" and "there is no such screen"
 * arrive at the same place and have to be told apart here.
 *
 * Matched **exactly**, because the route table is exact: `/ombor/A-02-01` is
 * not a screen anybody has, and answering "it is the warehouse's" because
 * `/ombor` is would be the same lie the other way round. The one prefix is
 * the courier's app, whose own screens hang under `/kuryer`.
 */
const ROLES: Role[] = ["admin", "warehouse", "courier"]

/** Screens a role has that are in no menu — the courier's own app. */
const UNLISTED: Partial<Record<Role, string[]>> = { courier: ["/kuryer"] }

export function rolesFor(pathname: string): Role[] {
  return ROLES.filter((role) => {
    const own = [
      ...leaves(navFor(role)).map((item) => item.to),
      ...(REACHABLE[role] ?? []),
    ]
    return (
      own.some((to) => !to.startsWith("#") && to === pathname) ||
      (UNLISTED[role] ?? []).some(
        (to) => to === pathname || pathname.startsWith(`${to}/`),
      )
    )
  })
}

/** The role in the words the building uses for the people in it. */
const ROLE_WORDS: Record<Role, string> = {
  admin: "Egasi (admin)",
  warehouse: "Ombor xodimi",
  courier: "Kuryer",
  customer: "Xaridor",
}

export function roleWord(role: Role): string {
  return ROLE_WORDS[role]
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

/* ------------------------------------------------------------ the phone's bar
 *
 * On a phone the menu is a row across the bottom, under the thumb, and not a
 * drawer behind a button in the far top-left corner. A courier has three
 * destinations and switches between them all day while standing up; three taps
 * behind a hamburger is the wrong shape for that, and it is the wrong shape
 * for the bench too.
 *
 * Four targets is what fits, and the number is a measurement rather than a
 * taste: on a 390px screen four slots are 97px each, which holds the longest
 * word in this menu (`Kategoriyalar`, 83px at the phone's label size) without
 * an ellipsis, and five would not. The office has seven top-level items and
 * the bench has seven screens, so the last slot becomes a door to the rest.
 */
export const BAR_SLOTS = 4

/**
 * One target on the bottom bar. `covers` is every route it stands for, which
 * is how a slot knows it is the current one — a group's slot is lit by any of
 * its children.
 */
export type BarSlot = {
  to: string
  label: string
  icon?: LucideIcon
  badge?: string
  covers: string[]
}

/**
 * Which three screens a role gets on the bar, said out loud.
 *
 * The bar used to take the first three items of the rail, and the rail is
 * ordered for a **desk** — a list somebody reads down with a pointer, where
 * `Kategoriyalar` sitting under `Mahsulotlar` costs nothing. Down here it cost
 * the two screens the day is actually spent in: the office's bar read
 * `Boshqaruv · Mahsulotlar · Kategoriyalar`, and `Buyurtmalar` and `Qabul`
 * were both behind `Yana`. A catalogue of categories is edited about once a
 * season; an order arrives every few minutes.
 *
 * So the phone's order is declared, per role, as the work it does — and
 * anything not named here keeps the rail's order behind it, which is what the
 * bench gets: `Ombor xaritasi`, `Qabul`, `Terish` is already the day.
 */
const BAR_ORDER: Partial<Record<Role, string[]>> = {
  admin: ["/", "/buyurtmalar", "/mahsulotlar"],
}

export function barOrderFor(role: Role): string[] {
  return BAR_ORDER[role] ?? []
}

/**
 * The menu as a row of at most five targets, and whether anything was left
 * over.
 *
 * A group is a door in the rail; down here it is **its first screen**, because
 * a bar slot that opens a submenu is a menu inside a menu and the drawer
 * behind `Yana` already holds the whole thing flat.
 *
 * When the screen somebody is actually on did not fit, it takes the last
 * visible slot. A bar that never shows where you are is a bar people stop
 * reading — and without it `/jurnal` would light nothing at all.
 */
export function barSlots(
  items: NavItem[],
  at?: NavLeaf,
  order: string[] = [],
): { slots: BarSlot[]; more: boolean } {
  const all: BarSlot[] = items.map((item) => {
    const kids = item.children ?? []
    return {
      to: kids.length ? kids[0].to : item.to,
      label: item.label,
      icon: item.icon,
      // A count filed one level down is a count nobody sees on a phone, since
      // the drawer it lives in is shut: it rides up to the slot.
      badge: item.badge ?? kids.find((kid) => kid.badge)?.badge,
      covers: kids.length ? kids.map((kid) => kid.to) : [item.to],
    }
  })

  if (all.length <= BAR_SLOTS) return { slots: all, more: false }

  // The declared screens first, in the order they were declared, then the
  // rail's own order for everything the role did not name. A screen named
  // twice is still one slot.
  const named = order
    .map((to) => all.find((slot) => slot.to === to || slot.covers.includes(to)))
    .filter((slot): slot is BarSlot => Boolean(slot))
  const ranked = [...new Set([...named, ...all])]

  const slots = ranked.slice(0, BAR_SLOTS - 1)
  const here = at?.item.to
  if (here && !slots.some((slot) => slot.covers.includes(here))) {
    const mine = ranked.find((slot) => slot.covers.includes(here))
    if (mine) slots[slots.length - 1] = mine
  }
  return { slots, more: true }
}

/**
 * The density class for a role, from `shared/theme.css`.
 *
 * Not a preference. A row read at arm's length at a desk wants to be small
 * so that more of them fit; a button pressed with a glove on wants to be
 * 64px whatever anybody's taste is.
 *
 * **Role decides this only on a desk.** On a phone every role is comfortable —
 * see the shell — because a warehouse worker holding a phone at the shelves
 * has the same thumb and the same eyes as a courier, and `density-compact` on
 * a 390px screen is a 36px target and 14px type held at arm's length outdoors.
 * That is the existing third density rather than a fourth one for phones:
 * there is only one thing "read standing up, one-handed" means.
 */
export function densityFor(role: Role): string {
  if (role === "admin") return "density-compact"
  if (role === "courier") return "density-comfortable"
  return "density-cozy"
}

/**
 * Where a role lands after signing in.
 *
 * A courier lands in **their own app** — `/kuryer`, the map — and not in the
 * rail's `/ishlarim`. The two exist side by side on purpose (see `App.tsx`):
 * `/ishlarim`, `/tarix` and `/daromad` are the desk view of the same round and
 * stay reachable from the menu, but the round is driven on a phone, and what a
 * phone opens on should be the screen built for it.
 */
export function homeFor(role: Role): string {
  if (role === "admin") return "/"
  if (role === "warehouse") return "/ombor"
  if (role === "courier") return "/kuryer"
  return "/ishlarim"
}
