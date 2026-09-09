/**
 * The navigation, which is the only place a role decides what an app is.
 *
 * Three jobs, one bundle. The office reads hundreds of rows at a desk; the
 * bench works standing up with a phone in one hand; the courier is outdoors,
 * one-handed, sometimes in a glove. That is a real difference and it is kept —
 * as a **density on one system** rather than as three applications that drift
 * apart, which is exactly what happened the last time there were three.
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
  Sparkles,
  Tags,
  Truck,
  Users,
  Wallet,
} from "lucide-react"

import type { Role } from "@/lib/session"

export type NavItem = {
  to: string
  label: string
  icon: LucideIcon
  /** A dashboard tile key whose value rides on this item as a count. A queue
   *  nobody can see the length of is a queue that grows. */
  badge?: string
}

/** Interface language is Uzbek. There is no language picker: everybody who
 * signs in here works in this building and reads it. */
const ADMIN: NavItem[] = [
  { to: "/", label: "Boshqaruv", icon: Home },
  { to: "/mahsulotlar", label: "Mahsulotlar", icon: Boxes },
  { to: "/kategoriyalar", label: "Kategoriyalar", icon: Tags },
  { to: "/buyurtmalar", label: "Buyurtmalar", icon: ListOrdered },
  { to: "/ombor", label: "Ombor", icon: Map },
  { to: "/kuryerlar", label: "Kuryerlar", icon: Truck },
  { to: "/xodimlar", label: "Xodimlar", icon: Users },
  { to: "/hisobotlar", label: "Hisobotlar", icon: ClipboardList },
]

const WAREHOUSE: NavItem[] = [
  { to: "/ombor", label: "Ombor xaritasi", icon: Map },
  { to: "/qabul", label: "Qabul", icon: PackageSearch },
  { to: "/terish", label: "Terish", icon: PackageCheck },
  { to: "/sanash", label: "Sanash", icon: Layers },
  { to: "/yorliqlar", label: "Yorliqlar", icon: ScanBarcode },
]

/**
 * The shop window, and it is the whole of this role's menu.
 *
 * Not in the office's menu and not in the bench's. Goods reaching a shelf and
 * goods reaching the shop are two jobs done at different times by people
 * looking at different things — a sack, and a photograph — and while they were
 * one screen neither got done properly. The queue carries its own count,
 * because what is in it is money standing still: goods on a shelf that no
 * customer can buy, and nothing about that breaks or errors.
 */
const SELLER: NavItem[] = [
  {
    to: "/sotuvga-chiqarish",
    label: "Sotuvga chiqarish",
    icon: Sparkles,
    badge: "held_back",
  },
  { to: "/mahsulotlar", label: "Mahsulotlar", icon: Boxes },
  { to: "/kategoriyalar", label: "Kategoriyalar", icon: Tags },
]

const COURIER: NavItem[] = [
  { to: "/ishlarim", label: "Mening ishlarim", icon: Route },
  { to: "/tarix", label: "Tarix", icon: ClipboardList },
  { to: "/daromad", label: "Daromad", icon: Wallet },
]

export function navFor(role: Role): NavItem[] {
  if (role === "admin") return ADMIN
  if (role === "warehouse") return WAREHOUSE
  if (role === "seller") return SELLER
  if (role === "courier") return COURIER
  return []
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
  if (role === "seller") return "/sotuvga-chiqarish"
  return "/ishlarim"
}
