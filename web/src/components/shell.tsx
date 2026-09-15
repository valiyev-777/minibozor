/**
 * The frame every screen sits in.
 *
 * A near-black rail down the left and a white bar across the top — the shape
 * every back office in this building has, so somebody who works in two of
 * them is not learning a second building.
 *
 * ----------------------------------------------------------------- the phone
 *
 * Under 48rem this is not that shape at all, and it should not be. The rail
 * became a sheet behind a ☰ in the far top-left corner, which is the corner a
 * right thumb cannot reach; a courier has three destinations and switches
 * between them all day while standing up, and every switch was two taps into
 * a menu. So the phone gets what a phone has: **a row of targets across the
 * bottom**, under the thumb, with the rest of a long menu behind the last one.
 *
 * Three more things change with it, and they are all the same decision —
 * this is read standing up rather than at a desk:
 *
 *   - the **density is comfortable for every role**, not only the courier's.
 *     18px body and a 56px control, because a phone held at arm's length in
 *     daylight is a phone held at arm's length in daylight whether the person
 *     holding it delivers or receives.
 *   - the **title is printed once**. The top bar prints it, the page header
 *     stops — see `lib/page-title`.
 *   - the top bar loses its ☰ and its breadcrumb, because the bar at the
 *     bottom is the navigation and a breadcrumb one level deep is a label.
 *
 * ------------------------------------------------------------------ the rail
 *
 * As tall as the **window**, not as tall as the page.
 *
 * It was a plain flex child once, so it stretched to whatever the screen
 * beside it happened to be: the shelf map made it two thousand pixels of dark
 * blue. It is `fixed` now, and the item list scrolls inside itself on a short
 * window rather than pushing anything off the end.
 *
 * It collapses to icons, and it re-expands while the pointer is over it. The
 * collapse is for the shelf map, which is a wide drawing and wants the
 * column back; the hover is so that collapsing does not mean *losing* the
 * menu — a rail you have to un-collapse to read is a rail nobody collapses.
 *
 * ------------------------------------------------------------------ the item
 *
 * **Full-bleed bars, not pills.** A menu item touches both edges of the rail
 * and has no radius, which is the single most visible thing about the house
 * chrome and the thing ours was getting wrong: an 8px pill inside 12px of
 * padding turns the column into a stack of floating tablets and the rail
 * into a background they happen to be on. A bar that reaches the edge reads
 * as part of the rail, which is what it is. There is no left accent stripe
 * either — the fill is the answer, and a stripe as well is two devices
 * saying one thing.
 *
 * ------------------------------------------------------------------ who
 *
 * The signed-in person is **not** down here. They are in the top bar, in the
 * menu that also holds sign-out and the theme — one place where a person's
 * own things live, rather than a name at the foot of the rail and the
 * controls for it eight hundred pixels away at the top right.
 */

import {
  ChevronDown,
  ChevronLeft,
  LogOut,
  Menu,
  Monitor,
  Moon,
  Palette,
  Sun,
  X,
} from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { NavLink, Outlet, useLocation } from "react-router-dom"

import { RailSearch } from "@/components/rail-search"
import { ScreenBoundary } from "@/pages/oops"
import {
  DropdownMenu,
  DropdownMenuCheckItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/cn"
import {
  barSlots,
  densityFor,
  homeFor,
  isGroup,
  matchNav,
  navFor,
  type BarSlot,
  type NavItem,
  type NavLeaf,
} from "@/lib/nav"
import { PageTitleProvider, usePageTitle } from "@/lib/page-title"
import { useDashboard } from "@/lib/queries"
import { useSession } from "@/lib/session"
import { useTheme, type ThemeMode } from "@/lib/theme"
import { useIsPhone } from "@/lib/viewport"

const RAIL_OPEN = "16.5rem" /* 264px */
const RAIL_SHUT = "4.75rem" /* 76px — an icon and its padding */

export function Shell() {
  const { staff } = useSession()
  const [pinned, setPinned] = useState(() => localStorage.getItem("mb:rail") !== "shut")
  const [hovered, setHovered] = useState(false)
  const [sheet, setSheet] = useState(false)
  const location = useLocation()
  const phone = useIsPhone()

  // A menu that stays open behind the screen it opened is a menu that hides
  // the screen it opened.
  useEffect(() => setSheet(false), [location.pathname])

  const items = useMemo(() => (staff ? navFor(staff.role) : []), [staff])
  const here = useMemo(
    () => matchNav(items, location.pathname),
    [items, location.pathname],
  )

  // Exactly one drawer open, and which one is a fact about the URL rather
  // than about what somebody clicked ten screens ago. Recomputed on every
  // navigation; opened by hand in between.
  const parentKey = here?.parent?.to ?? null
  const [openKey, setOpenKey] = useState<string | null>(parentKey)
  useEffect(() => setOpenKey(parentKey), [location.pathname, parentKey])

  if (!staff) return null

  const open = pinned || hovered

  const toggle = () => {
    setHovered(false)
    setPinned((was) => {
      localStorage.setItem("mb:rail", was ? "shut" : "open")
      return !was
    })
  }

  const expand = () => {
    if (pinned) return
    localStorage.setItem("mb:rail", "open")
    setPinned(true)
  }

  const bar = barSlots(items, here)

  return (
    <PageTitleProvider>
    <div
      className={cn(
        "min-h-full",
        // Role decides the density at a desk. A phone is one posture whoever
        // is holding it, so it overrides the role rather than adding a fourth
        // density that would mean the same thing.
        phone ? "density-comfortable" : densityFor(staff.role),
      )}
    >
      {/* ----------------------------------------------------------- the rail */}
      <aside
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{ width: open ? RAIL_OPEN : RAIL_SHUT }}
        className="no-print fixed inset-y-0 left-0 z-40 hidden flex-col border-e border-rail-edge bg-rail text-rail-ink transition-[width] duration-200 md:flex"
      >
        <Brand open={open} onToggle={toggle} pinned={pinned} />
        <RailSearch items={items} collapsed={!open} onExpand={expand} />
        <nav
          aria-label="Asosiy menyu"
          className="scroll-slim flex-1 overflow-y-auto overflow-x-hidden pb-3"
        >
          {items.map((item) => (
            <RailRow
              key={item.to}
              item={item}
              open={open}
              activeTo={here?.item.to}
              openKey={openKey}
              onOpenKey={setOpenKey}
              onExpand={expand}
            />
          ))}
        </nav>
      </aside>

      {/* The rail is `fixed`, so the page needs to be told how wide it is. A
       * margin rather than a flex sibling: the shelf map is a wide drawing
       * that sets its own scroll container, and a flex row would have it
       * fighting the rail for the width every time it redrew. */}
      <div
        style={{ marginInlineStart: pinned ? RAIL_OPEN : RAIL_SHUT }}
        className="min-w-0 transition-[margin] duration-200 max-md:!ms-0">
        <TopBar trail={here} name={staff.full_name || staff.phone} role={staff.role} />

        {/* `--bottom-nav` is the height of the phone's navigation and zero on a
            desk, so a screen never ends underneath the bar it is navigated
            with. The screens with their own sticky foot read the same token. */}
        <main className="p-(--gap-page) pb-[calc(var(--gap-page)+var(--bottom-nav))]">
          {/* Inside the shell: the rail and the top bar did not throw, and
              somebody whose screen fell over still wants the menu. Keyed by
              path so leaving the broken screen clears it. */}
          <ScreenBoundary home={homeFor(staff.role)} at={location.pathname}>
            <Outlet />
          </ScreenBoundary>
        </main>
      </div>

      {/* ------------------------------------------------------ the phone's foot */}
      <BottomBar
        slots={bar.slots}
        more={bar.more}
        here={here}
        onOpenSheet={() => setSheet(true)}
        sheetOpen={sheet}
      />
      {sheet ? (
        <MenuSheet items={items} here={here} onClose={() => setSheet(false)} />
      ) : null}
    </div>
    </PageTitleProvider>
  )
}

/* ----------------------------------------------------------- the phone's menu */

/**
 * The row of targets across the bottom of a phone.
 *
 * Full-height columns rather than a row of small icons: the whole slot is the
 * target, so the thing a thumb has to hit is a 78 × 64 rectangle and not a
 * 24px glyph. The label is under the icon and always printed — an icon-only
 * bar is a quiz, and `Sanash` and `Terish` are not guessable from a box and a
 * clipboard.
 *
 * Selection is the accent on the glyph and the word, plus a rule along the top
 * edge of the slot. A fill would be a third device and would read as a pressed
 * button rather than as where you are.
 */
function BottomBar({
  slots,
  more,
  here,
  onOpenSheet,
  sheetOpen,
}: {
  slots: BarSlot[]
  more: boolean
  here: NavLeaf | undefined
  onOpenSheet: () => void
  sheetOpen: boolean
}) {
  const at = here?.item.to
  return (
    <nav
      aria-label="Asosiy menyu"
      className="no-print fixed inset-x-0 bottom-0 z-40 flex h-(--nav-bar) border-t border-line bg-surface pb-inset shadow-raised md:hidden"
    >
      {slots.map((slot) => {
        const on = at ? slot.covers.includes(at) : false
        return (
          <NavLink
            key={slot.to}
            to={slot.to}
            end={slot.to === "/"}
            aria-current={on ? "page" : undefined}
            className={cn(
              "relative flex h-full min-w-0 flex-1 flex-col items-center justify-center gap-1 px-0.5 transition-colors",
              on ? "text-brand" : "text-ink-soft",
            )}
          >
            {on ? (
              <span
                aria-hidden
                className="absolute inset-x-2 top-0 h-[2px] rounded-full bg-brand"
              />
            ) : null}
            <span className="relative">
              {slot.icon ? <slot.icon className="size-6" /> : null}
              <Count of={slot.badge} dot on="surface" />
            </span>
            {/* Two lines, centred, never an ellipsis — see `BAR_SLOTS`. */}
            <span className="w-full text-center text-micro font-medium leading-tight">
              {slot.label}
            </span>
          </NavLink>
        )
      })}

      {more ? (
        <button
          type="button"
          onClick={onOpenSheet}
          aria-expanded={sheetOpen}
          className={cn(
            "flex h-full min-w-0 flex-1 flex-col items-center justify-center gap-1 px-0.5 transition-colors",
            sheetOpen ? "text-brand" : "text-ink-soft",
          )}
        >
          <Menu className="size-6" />
          <span className="w-full text-center text-micro font-medium leading-tight">
            Yana
          </span>
        </button>
      ) : null}
    </nav>
  )
}

/**
 * Everything the bar could not fit, and everything it could — the whole menu,
 * flat.
 *
 * It opens **upward from the bar that opened it** rather than dropping out of
 * the top of the window, because that is where the thumb already is. The rail
 * is reused for its colour and its full-bleed rows and for nothing else: the
 * drawers are gone, because a folder that has to be opened before its three
 * screens can be read is a second tap on a menu that is already one tap deep,
 * and on a phone there is room to simply print the group's name over its
 * children.
 *
 * Rows are a full `--control-lg` — 64px here, since a phone is always
 * comfortable — with the icon at 24px and the label at body size. That is the
 * size the owner asked for and the size a menu read at a shelf needs.
 */
function MenuSheet({
  items,
  here,
  onClose,
}: {
  items: NavItem[]
  here: NavLeaf | undefined
  onClose: () => void
}) {
  // A sheet over the page must not leave the page scrolling behind it.
  useEffect(() => {
    const was = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.body.style.overflow = was
    }
  }, [])

  const at = here?.item.to

  return (
    <div className="no-print fixed inset-0 z-50 flex flex-col justify-end md:hidden">
      <button
        type="button"
        aria-label="Yopish"
        onClick={onClose}
        className="absolute inset-0 bg-scrim/60"
      />
      <div className="relative max-h-[85vh] overflow-y-auto rounded-t-panel bg-rail pb-inset text-rail-ink shadow-raised">
        <div className="sticky top-0 flex h-control-lg items-center justify-between gap-3 border-b border-rail-edge bg-rail px-4">
          <span className="text-body font-semibold text-rail-ink-strong">Menyu</span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Yopish"
            className="grid size-control place-items-center rounded-control text-rail-ink transition-colors hover:bg-rail-hover hover:text-rail-ink-strong"
          >
            <X className="size-5" />
          </button>
        </div>

        <nav aria-label="Hamma menyu" className="py-2">
          {items.map((item) =>
            isGroup(item) ? (
              <div key={item.to} className="pt-3">
                <p className="caption px-4 pb-1 text-rail-ink/70">{item.label}</p>
                {(item.children ?? []).map((child) => (
                  <SheetRow key={child.to} item={child} at={at} onGo={onClose} child />
                ))}
              </div>
            ) : (
              <SheetRow key={item.to} item={item} at={at} onGo={onClose} />
            ),
          )}
        </nav>
      </div>
    </div>
  )
}

/** One line in the sheet: full-bleed, 64px, and big enough to hit without
 *  looking. A child of a group carries the rail's dash instead of an icon —
 *  the same mark that says "filed inside that one" up in the column. */
function SheetRow({
  item,
  at,
  onGo,
  child = false,
}: {
  item: NavItem
  at?: string
  onGo: () => void
  child?: boolean
}) {
  const on = item.to === at
  return (
    <NavLink
      to={item.to}
      end={item.to === "/"}
      onClick={onGo}
      className={cn(
        "flex h-control-lg w-full items-center gap-3 px-4 text-body transition-colors",
        on ? "bg-rail-active font-semibold text-rail-ink-strong" : "text-rail-ink",
      )}
    >
      {child ? (
        <span
          aria-hidden
          className={cn(
            "ms-1 h-[2px] w-4 shrink-0",
            on ? "bg-brand" : "bg-rail-ink/40",
          )}
        />
      ) : item.icon ? (
        <item.icon className={cn("size-6 shrink-0", on ? "text-brand" : "text-rail-ink")} />
      ) : null}
      <span className="min-w-0 flex-1 truncate">{item.label}</span>
      <Count of={item.badge} />
    </NavLink>
  )
}

/* ------------------------------------------------------------------ the rail */

/** The shape every row in the rail has: 44px, full-bleed, square. */
const ROW =
  "group relative flex w-full items-center gap-3 px-4 text-left transition-colors"

function RailRow({
  item,
  open,
  activeTo,
  openKey,
  onOpenKey,
  onExpand,
}: {
  item: NavItem
  open: boolean
  activeTo?: string
  openKey: string | null
  onOpenKey: (key: string | null) => void
  onExpand: () => void
}) {
  if (isGroup(item)) {
    return (
      <RailGroup
        item={item}
        open={open}
        activeTo={activeTo}
        openKey={openKey}
        onOpenKey={onOpenKey}
        onExpand={onExpand}
      />
    )
  }
  return <RailLink item={item} open={open} />
}

function RailLink({ item, open }: { item: NavItem; open: boolean }) {
  return (
    <NavLink
      to={item.to}
      end={item.to === "/"}
      title={open ? undefined : item.label}
      className={({ isActive }) =>
        cn(
          ROW,
          "h-control-lg text-small font-medium",
          open ? "" : "justify-center px-0",
          isActive
            ? "bg-rail-active font-semibold text-rail-ink-strong"
            : "text-rail-ink hover:bg-rail-hover hover:text-brand",
        )
      }
    >
      {({ isActive }) => (
        <>
          {item.icon ? (
            <item.icon
              className={cn(
                "size-5 shrink-0 transition-colors",
                isActive ? "text-brand" : "text-rail-ink group-hover:text-brand",
              )}
            />
          ) : null}
          {open ? (
            <>
              <span className="flex-1 truncate">{item.label}</span>
              <Count of={item.badge} />
            </>
          ) : (
            <Count of={item.badge} dot />
          )}
        </>
      )}
    </NavLink>
  )
}

/**
 * A drawer: a row that opens rather than goes anywhere, and the screens
 * inside it.
 *
 * A child has no icon of its own. It gets a dash — the width of a
 * hyphen, two pixels tall — which is not decoration: a column of six icons
 * where two of them belong *under* another one reads as eight equal things,
 * and the dash is what says "this one is filed inside that one" without
 * spending an icon on it.
 */
function RailGroup({
  item,
  open,
  activeTo,
  openKey,
  onOpenKey,
  onExpand,
}: {
  item: NavItem
  open: boolean
  activeTo?: string
  openKey: string | null
  onOpenKey: (key: string | null) => void
  onExpand: () => void
}) {
  const children = item.children ?? []
  const holdsActive = children.some((child) => child.to === activeTo)
  const isOpen = openKey === item.to

  return (
    <div>
      <button
        type="button"
        aria-expanded={isOpen}
        title={open ? undefined : item.label}
        onClick={() => {
          // On a narrow rail there is nowhere to put the children, so the
          // click widens the rail first rather than opening a drawer the
          // person cannot see.
          if (!open) onExpand()
          onOpenKey(isOpen ? null : item.to)
        }}
        className={cn(
          ROW,
          "h-control-lg text-small font-medium",
          open ? "" : "justify-center px-0",
          // While the drawer is open the fill belongs to the child that is
          // selected, not to the drawer as well — two fills stacked read as
          // two selections. A shut rail has no children to show, so the
          // drawer carries the fill itself.
          holdsActive && (!open || !isOpen)
            ? "bg-rail-active font-semibold text-rail-ink-strong"
            : "text-rail-ink hover:bg-rail-hover hover:text-brand",
        )}
      >
        {item.icon ? (
          <item.icon
            className={cn(
              "size-5 shrink-0 transition-colors",
              holdsActive ? "text-brand" : "text-rail-ink group-hover:text-brand",
            )}
          />
        ) : null}
        {open ? (
          <>
            <span className={cn("flex-1 truncate", holdsActive && "text-rail-ink-strong")}>
              {item.label}
            </span>
            <ChevronDown
              className={cn(
                "size-4 shrink-0 text-rail-ink/70 transition-transform duration-200",
                isOpen && "rotate-180",
              )}
            />
          </>
        ) : null}
      </button>

      {/* Height animated with a grid track rather than a max-height guess:
       * a guessed maximum is either a jump or a lag, depending on how many
       * children the drawer turns out to have. */}
      <div
        className={cn(
          "grid transition-[grid-template-rows] duration-200 ease-out",
          open && isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
        )}
      >
        <div className="overflow-hidden">
          {children.map((child) => (
            <NavLink
              key={child.to}
              to={child.to}
              tabIndex={open && isOpen ? undefined : -1}
              aria-hidden={open && isOpen ? undefined : true}
              className={({ isActive }) =>
                cn(
                  ROW,
                  "h-control-lg gap-2 ps-8 text-small font-normal",
                  isActive
                    ? "bg-rail-active font-medium text-rail-ink-strong"
                    : "text-rail-ink/80 hover:bg-rail-hover hover:text-rail-ink-strong",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    aria-hidden
                    className={cn(
                      "h-[2px] w-3 shrink-0 transition-colors",
                      isActive
                        ? "bg-brand"
                        : "bg-rail-ink/40 group-hover:bg-rail-ink-strong",
                    )}
                  />
                  <span className="flex-1 truncate">{child.label}</span>
                  <Count of={child.badge} />
                </>
              )}
            </NavLink>
          ))}
        </div>
      </div>
    </div>
  )
}

/**
 * The number beside a menu item, from the dashboard tile of the same key.
 *
 * A queue nobody can see the length of is a queue that grows. The held-back
 * cards in "Mahsulotlar" are goods on a shelf that no customer can buy, which
 * breaks nothing and errors nowhere — so the only thing that makes the queue
 * get worked is a figure somebody walks past.
 *
 * On a collapsed rail there is no room for the figure, and a queue that
 * disappears when the rail narrows is the same queue nobody can see. It
 * becomes a dot in the corner of the icon instead: less information, but the
 * one bit that matters — there is something in there.
 */
function Count({
  of,
  dot = false,
  on = "rail",
}: {
  of?: string
  dot?: boolean
  /** Which background it is sitting on — the near-black column, or the white
   *  bar at the foot of a phone. The ring has to be the colour behind it or
   *  the dot has a grey halo. */
  on?: "rail" | "surface"
}) {
  // Called unconditionally because a hook must be, and switched off when
  // there is no badge to draw: a courier may not read the dashboard at all.
  const dashboard = useDashboard(Boolean(of))
  if (!of) return null
  const tile = dashboard.data?.tiles.find((one) => one.key === of)
  if (!tile?.value) return null

  if (dot) {
    return (
      <span
        aria-hidden
        className={cn(
          "absolute size-2.5 rounded-full ring-2",
          on === "rail" ? "right-3 top-2 ring-rail" : "-right-1 -top-0.5 ring-surface",
          tile.urgent ? "bg-danger" : "bg-brand",
        )}
      />
    )
  }
  return (
    <span
      className={cn(
        "min-w-5 rounded-full px-1.5 text-center text-micro font-semibold tabular",
        tile.urgent
          ? "bg-danger text-danger-ink"
          : on === "rail"
            ? "bg-rail-active text-rail-ink-strong"
            : "bg-brand-soft text-brand-deep",
      )}
    >
      {tile.value}
    </span>
  )
}

/**
 * The rail's head: the mark, the name, and the button that narrows it.
 *
 * The blue behind it is a heavily blurred wash of the accent rather than a
 * flat panel — the top of the rail is where the eye lands first, and a
 * near-black column with nothing at the top of it reads as an unfinished
 * page. It is `pointer-events-none` because it is a light, not a surface.
 */
function Brand({
  open,
  pinned,
  onToggle,
}: {
  open: boolean
  pinned: boolean
  onToggle: () => void
}) {
  return (
    <div className="relative flex h-[72px] shrink-0 items-center gap-3 overflow-hidden border-b border-rail-edge px-4">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-brand opacity-20 blur-[70px] dark:opacity-60"
      />
      <span className="relative z-10 grid size-9 shrink-0 place-items-center rounded-control bg-brand text-body font-bold text-brand-ink">
        MB
      </span>
      {open ? (
        <span className="relative z-10 flex-1 truncate font-semibold tracking-tight text-rail-ink-strong">
          Mini Bozor
        </span>
      ) : null}
      {open ? (
        <button
          type="button"
          onClick={onToggle}
          aria-label={pinned ? "Menyuni yig'ish" : "Menyuni ochish"}
          className="relative z-10 grid size-7 place-items-center rounded-control text-rail-ink transition-colors hover:bg-rail-hover hover:text-rail-ink-strong"
        >
          <ChevronLeft
            className={cn("size-4 transition-transform", !pinned && "rotate-180")}
          />
        </button>
      ) : null}
    </div>
  )
}

/* ---------------------------------------------------------------- the top bar */

/**
 * Breadcrumb on the left, the person on the right, and a hairline shadow
 * that only appears once the page has scrolled — so a screen at rest is flat
 * and a screen with content above the fold says so.
 *
 * The separator is a brand dot rather than a slash. A slash between two
 * words is a third word; a 4px dot in the accent is punctuation, and it
 * ties the one coloured thing in the top bar to the one coloured thing in
 * the rail.
 *
 * ------------------------------------------------------------------ on a phone
 *
 * There is no breadcrumb and no ☰, and **nothing sits in the middle**. A trail
 * one level deep on a 390px screen is not a location, it is the page's name
 * with the shop's name in front of it — and it was being printed here *and* in
 * the page's own header card directly underneath, which between them spent a
 * fifth of the window before any content. So this bar prints the **title**,
 * once, hard against the left: the screen's own words where the screen set
 * them (`MB-000412`, not `Terish`), with the subtitle under it, because
 * `4 qator · 2 qoldi` is the line a picker is reading. The right-hand end is
 * the person. The middle is empty and stays empty.
 *
 * **It is not a band.** `index.html` paints the native status strip in
 * `canvas`, so a white bar under it would make three stripes across the top of
 * the phone — strip, bar, page. At rest the bar is `canvas` too and the three
 * are one field; it turns into a `surface` with a shadow only once the page
 * has scrolled, which is the moment there is actually something underneath it
 * to separate from. The status strip's own height is added as padding rather
 * than guessed, so the title clears a notch.
 */
function TopBar({
  trail,
  name,
  role,
}: {
  trail: { item: NavItem; parent?: NavItem } | undefined
  name: string
  role: string
}) {
  const [scrolled, setScrolled] = useState(false)
  const published = usePageTitle()

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 0)
    onScroll()
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])

  // A drawer whose first screen carries the drawer's own name — Buyurtmalar
  // inside Buyurtmalar — says it twice and means it once. The parent is the
  // location and the leaf is the page; where they are the same word there is
  // only one of them to print.
  const crumbs = ["Mini Bozor"]
  if (trail?.parent && trail.parent.label !== trail.item.label) {
    crumbs.push(trail.parent.label)
  }
  if (trail) crumbs.push(trail.item.label)

  // The nav's word for the screen is the fallback, not the answer: a screen
  // can be about one order and say so.
  const title = published?.title ?? trail?.item.label ?? "Mini Bozor"

  return (
    <header
      className={cn(
        "no-print sticky top-0 z-30 flex items-center justify-between gap-3 px-4 transition-[background-color,box-shadow] md:gap-4 md:px-6",
        // A desk bar is a fixed 72px. A phone bar is 72px of content plus
        // however much of the window the status strip is standing on.
        "min-h-[72px] py-2 pt-[calc(0.5rem+env(safe-area-inset-top))] md:h-[72px] md:py-0 md:pt-0",
        "max-md:bg-canvas md:bg-surface",
        scrolled ? "shadow-raised max-md:bg-surface" : "",
      )}
    >
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-body font-semibold tracking-tight md:hidden">
          {title}
        </h1>
        {published?.subtitle ? (
          <p className="line-clamp-2 text-micro text-ink-soft md:hidden">
            {published.subtitle}
          </p>
        ) : null}

        <nav
          aria-label="Joylashuv"
          className="hidden min-w-0 items-center gap-2 truncate text-small md:flex"
        >
          {crumbs.map((crumb, at) => (
            <span key={at} className="flex min-w-0 items-center gap-2">
              {at > 0 ? (
                <span aria-hidden className="size-1 shrink-0 rounded-full bg-brand" />
              ) : null}
              <span
                className={cn(
                  "truncate",
                  at === crumbs.length - 1
                    ? "text-ink-faint"
                    : "font-medium text-ink",
                )}
              >
                {crumb}
              </span>
            </span>
          ))}
        </nav>
      </div>

      <ProfileMenu name={name} role={role} />
    </header>
  )
}

/** Who is signed in, and everything that belongs to them: the theme, and the
 *  way out. */
function ProfileMenu({ name, role }: { name: string; role: string }) {
  const { signOut } = useSession()
  const { mode, setMode } = useTheme()

  const themes: Array<{ key: ThemeMode; label: string; icon: typeof Sun }> = [
    { key: "light", label: "Yorug'", icon: Sun },
    { key: "dark", label: "Qorong'i", icon: Moon },
    { key: "system", label: "Tizim bo'yicha", icon: Monitor },
  ]

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex h-control items-center gap-2.5 rounded-control px-2 text-left outline-none transition-colors hover:bg-line-soft focus-visible:ring-2 focus-visible:ring-brand/40">
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-brand-soft text-micro font-semibold text-brand-deep">
          {initials(name)}
        </span>
        <span className="hidden min-w-0 sm:block">
          <span className="block max-w-40 truncate text-small font-medium">{name}</span>
          <span className="block text-micro text-ink-faint">{roleWord(role)}</span>
        </span>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end">
        <DropdownMenuLabel>{name}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuSub>
          <DropdownMenuSubTrigger>
            <Palette />
            Ko'rinish
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent>
            {themes.map((one) => (
              <DropdownMenuCheckItem
                key={one.key}
                checked={mode === one.key}
                onSelect={() => setMode(one.key)}
              >
                <one.icon />
                {one.label}
              </DropdownMenuCheckItem>
            ))}
          </DropdownMenuSubContent>
        </DropdownMenuSub>
        <DropdownMenuSeparator />
        <DropdownMenuItem tone="danger" onSelect={signOut}>
          <LogOut />
          Chiqish
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/* ------------------------------------------------------------------- wording */

function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return "?"
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase()
  return (words[0][0] + words[1][0]).toUpperCase()
}

function roleWord(role: string): string {
  if (role === "admin") return "Administrator"
  if (role === "warehouse") return "Ombor xodimi"
  if (role === "courier") return "Kuryer"
  return role
}
