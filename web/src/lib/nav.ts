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
  Grid3x3,
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
  // High in the list because what is in it is money standing still: goods on
  // a shelf that no customer can buy. Admin only, and deliberately: filing a
  // card needs a category, and writing a category is the office's. Putting it
  // in the warehouse menu would be a screen whose first control refuses.
  { to: "/sotuvga-chiqarish", label: "Sotuvga chiqarish", icon: Sparkles, badge: "held_back" },
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
  { to: "/joylashtirish", label: "Joylashtirish", icon: Grid3x3 },
  { to: "/terish", label: "Terish", icon: PackageCheck },
  { to: "/sanash", label: "Sanash", icon: Layers },
  { to: "/yorliqlar", label: "Yorliqlar", icon: ScanBarcode },
]

const COURIER: NavItem[] = [
  { to: "/ishlarim", label: "Mening ishlarim", icon: Route },
  { to: "/tarix", label: "Tarix", icon: ClipboardList },
  { to: "/daromad", label: "Daromad", icon: Wallet },
]

export function navFor(role: Role): NavItem[] {
  if (role === "admin") return ADMIN
  if (role === "warehouse") return WAREHOUSE
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
  return "/ishlarim"
}
