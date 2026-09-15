---
name: backoffice-design
description: The Mini Bozor design system for web/ — the back office's palette, type, density, chrome and component recipes ported from the react-backoffice-boilerplate, plus the courier surface, which is a deliberate second visual language. Load before writing or restyling anything in web/ (screens, panels, tables, forms, either shell) so a new screen is drawn in the same language as the rest of the surface it belongs to.
---

# Back-office design

**Two surfaces, one system.** Everything in this document is the back office —
admin and warehouse, read at a desk or at a shelf. The courier's app is a
second visual language on the same tokens and the same file; it is described at
the end, under **The courier surface**, and a screen belongs to exactly one of
the two. Read that section before touching anything under
`web/src/pages/kuryer/` or `web/src/components/kuryer/`.

One visual language for `web/`, ported from `react-backoffice-boilerplate`
(Ant Design + Tailwind v4). We do **not** use Ant Design — the look is
reproduced on the existing Tailwind + Radix stack. What follows is the look,
stated as tokens and recipes.

**The rule that matters:** every value below already exists as a token in
`shared/theme.css`. A screen never writes a hex, never writes a Tailwind
palette colour (`bg-slate-100`, `text-blue-600`), and never writes a pixel
height for a control. If a screen needs a colour the system does not have,
the system is wrong and gets a token — not the screen.

## Palette

| Meaning | Token | Light | Dark |
| --- | --- | --- | --- |
| Body text | `ink` | `#121C25` | `#E6EBF2` |
| Secondary text | `ink-soft` | `#4B5C76` | `#A6B3C9` |
| Hint / placeholder | `ink-faint` | `#8E9BA8` | `#6B7785` |
| Border, divider | `line` | `#E2E5E8` | `#283549` |
| Fill, stripe, hover | `line-soft` | `#F3F5F4` | `#1B2636` |
| Card | `surface` | `#FFFFFF` | `#141D2A` |
| Page behind cards | `canvas` | `#F1F3F6` | `#0C1017` |
| Sidebar | `rail` | `#FFFFFF` | `#090E14` |
| Sidebar text | `rail-ink` | `#4B5C76` | `#F3F4F6` |
| Sidebar text, selected | `rail-ink-strong` | `#121C25` | `#FFFFFF` |
| Sidebar hairline | `rail-edge` | `#E2E5E8` | `rgb(255 255 255 / .10)` |
| Sidebar hover / field fill | `rail-hover` | `#F3F5F4` | `rgb(255 255 255 / .06)` |
| Sidebar selected fill | `rail-active` | `#E8F0FE` | `rgb(37 133 255 / .18)` |
| Floating over the sidebar | `rail-raised` | `#FFFFFF` | `#131C28` |
| Ground under a modal | `scrim` | `#090E14` | `#090E14` |
| Accent | `brand` | `#2585FF` | `#2585FF` |
| Accent, pressed / link text | `brand-deep` | `#0653C9` | `#7DB6FF` |
| Accent tint | `brand-soft` | `#E8F0FE` | `rgb(37 133 255 / .16)` |
| Happened | `good` | `#35C04C` | `#4CD03A` |
| Not yet | `warn` | `#F39C12` | `#F39C12` |
| Refused | `danger` | `#D0413A` | `#E7395B` |

The accent is **one hue everywhere**. Green means *it happened* and nothing
else — never use it for warmth or for a brand accent.

`-soft` is the tint a meaning sits on, `-ink` is the text that sits **in** the
meaning. `bg-danger text-danger-ink`, `bg-danger-soft text-danger`.

**The rail follows the theme.** It used to be near-black in both, on the
argument that a rail the same value as the page stops being a rail. The owner
looked at a black column on a white app and called it a fault — *"mavzuga
ergashsin"* — and that decision stands over the argument. In light the rail is
white and separates itself from the grey page by being *lighter* than it plus a
`rail-edge` hairline; in dark it is the near-black it always was, darker than
the page. Nothing inside the rail may be painted `text-white` or `white/10`
again: the seven `rail-*` tokens above are the whole family, and the sign-in
wall, the menu search and the phone's menu sheet all read them. `scrim` is its
own token for the same reason — an overlay borrowed from `rail` dims nothing
once `rail` is white.

## Type

Roboto, self-hosted from `web/public/fonts/roboto-v30/` (300/400/500/700), with
a system fallback. Weights used: 400 body, 500 labels/nav/table headers, 600–700
figures and titles. Nothing else.

Sizes are **tokens that move with density**, never literals:

- `text-body` — the default
- `text-small` — labels, table cells, nav
- `text-micro` — hints, captions, pills, table headers
- `.figure` — the one number a panel exists to show
- `.display` — the one number a *page* exists to show (at most one)
- `.caption` — uppercase, tracked, quiet label over a figure
- `.tabular` — any column of numbers, always

## Density

One class on the shell, from `densityFor(role)` in `web/src/lib/nav.ts`:

- `.density-compact` — admin. 14px body, 36px control. Hundreds of rows at a desk.
- `.density-cozy` — warehouse. 15px body, 40px control. Also the fallback, so
  a role added later is cozy until somebody decides otherwise.
- `.density-comfortable` — courier. 18px body, 56px control, 64px primary.

A component reads `h-control` / `h-control-sm` / `h-control-lg` (and
`size-control*` for square icon buttons). It never writes `h-9`.

**Role decides this only at a desk.** Under 48rem the shell puts
`density-comfortable` on every role, whoever is signed in: a phone held at
arm's length is a phone held at arm's length whether the person delivers or
receives, and `density-compact` on a 390px screen is a 36px target and 14px
type read standing up. That is the existing third density rather than a fourth
one for phones. Desktop is untouched.

## The phone

Under 48rem the chrome is not a narrow version of the desk's, it is the other
shape — and everything below is a breakpoint addition, never a change to the
desk.

- **The menu is a bar across the bottom**, not a ☰ in the corner a thumb cannot
  reach. `barSlots()` in `lib/nav.ts` turns the menu into at most `BAR_SLOTS`
  (4) targets — a group becomes its first screen — and the last slot is `Yana`,
  which opens the whole menu as a sheet when there was more. The current screen
  always occupies a slot even when it did not fit. Four is a measurement: four
  slots on 390px are 97px, which holds `Kategoriyalar` without an ellipsis.
- **The sheet is flat.** No accordions: a group prints its name as a `.caption`
  over its children. Rows are `h-control-lg`, icons `size-6`, painted in the
  `rail-*` family.
- **One title.** The top bar prints it and `PageHeader` does not — the header
  card draws nothing at all on a phone unless it was given actions. The title
  travels through `lib/page-title`, so the bar says `MB-000412` where the
  screen did, not the menu's word for it. Left-aligned with the subtitle under
  it; the right end is the person; **the middle stays empty**.
- **The top bar is not a band.** `index.html` paints the native status strip in
  `canvas`, so at rest the bar is `canvas` too and strip, bar and page are one
  field; it becomes `surface` with `shadow-raised` once the page has scrolled.
  Its padding carries `env(safe-area-inset-top)`.
- **`--bottom-nav`** is the height of that bar and `0px` at a desk. Anything
  that sits at the foot of a screen reads it: the shell's own padding, the
  sticky `Qabul` bar, the shelf map's selection, the toaster's offset. A screen
  ending under the navigation is the bug this token exists to make impossible.
- **Nothing ellipsises.** A figure wraps (`[overflow-wrap:anywhere]`), a row
  that cannot fit its prompt wraps the prompt onto a second line, a table lives
  in its `overflow-x-auto` and its card carries `min-w-0` so it cannot push the
  page sideways instead.

## Shape and depth

- `rounded-control` (8px) — buttons, inputs, chips, nav items, small things.
- `rounded-panel` (12px) — cards, panels, modals, anything that holds content.
- `rounded-full` — pills and avatars only.
- `shadow-panel` — a resting surface. `shadow-raised` — the thing that is
  acting: an open menu, a modal, a sticky header once the page has scrolled.
- Nothing else. Two steps of elevation is the whole ramp.

## Chrome

**The rail.** 264px, `bg-rail`, fixed, full window height, `text-rail-ink`, a
`border-rail-edge` hairline down its inner edge. Collapses to 76px (icons only)
and re-expands on hover. A 72px brand header at the top with a blurred
brand-blue glow behind it — quiet in light, strong in dark — and a
`border-rail-edge` hairline under it. Menu items are 44px tall, full-bleed,
`text-small font-medium`; hover is `bg-rail-hover`, active is `bg-rail-active`
with `text-rail-ink-strong` and a **brand-coloured icon**. A count rides on the
right of an item when the queue behind it has a length. Hidden below 48rem,
where the bottom bar is the menu.

**The top bar.** 72px, sticky, and it grows `shadow-raised` only once the page
has scrolled. At a desk it is `bg-surface` with the breadcrumb on the left and
the profile menu on the right, and the breadcrumb is the page's location, not
its title. On a phone see **The phone** above: title on the left, person on the
right, nothing in the middle.

**The content.** `p-6` (`--gap-page`), a 12-column grid with `gap-4`. Every
screen opens with a `PageHeader` — a surface card with the title and the
screen's actions on one line — then its panels.

## Components

**Panel.** `rounded-panel border border-line bg-surface shadow-panel`, an
optional 48px header row with a `text-small font-semibold` title and a bottom
`border-line`, body padding `p-4`. `bare` when the body is a list of rows that
supply their own padding.

**Table.** Lives inside a `bare` Panel, corners clipped by the panel.
Header row `bg-line-soft`, `text-micro font-medium text-ink-soft`, cells
`px-4 py-3`. Body rows have **no bottom border** — odd rows are striped
`bg-line-soft/60` instead, and hover is `bg-line-soft`. Numbers right-aligned
and `.tabular`.

**Stat.** A card with a coloured, rounded icon box on the left, the figure
beside it in 600 weight, and the label in `text-micro` underneath. Urgency is
carried by the icon box and the figure, never by washing the whole card. The
figure **wraps and never truncates** — `15 000 so'm` cut to `15 00…` is not a
tidier sum, it is a wrong one; the tile gets taller and the grid row equalises.

**Button.** Four variants and they mean different things. `primary` is filled
brand and there is **one per screen** — the act the screen exists for.
`secondary` is a bordered surface button. `ghost` sits inside a row and must
not compete with it. `danger` is for the act somebody has to mean. Height is
`h-control`, radius `rounded-control`, weight 500.

**Input.** Filled, not outlined: `bg-line-soft` with a transparent border,
`rounded-control`, `h-control`. Focus brings a brand border and a `ring-brand/25`.
Error is `bg-danger-soft` with a `border-danger`.

**Pill.** `rounded-full px-2 py-0.5 text-micro font-medium`, tone tint plus
tone ink. One word about the state of the row it sits in.

**Modal.** `rounded-panel`, `shadow-raised`, and three bands with hairlines
between them: header `p-4` with a bottom `border-line`, body `p-5`, footer
`p-4` with a top `border-line` whose buttons are full-width and split.

## Dark mode

Class-based: `.dark` on `<html>`, set by `web/src/lib/theme.tsx`
(`light` / `dark` / `system`, **defaulting to system**, remembered in
`localStorage`). Neutrals flip to a cool navy ramp; the brand hue and the three
meanings keep their identity. Never put a colour only inside the `.dark` block
— define it light first. The rail is in the ramp now, not outside it: check
both themes on the selected menu item, an unselected one, the badge counts, the
search box and the collapse chevron before calling a chrome change done.

## Printing

Label sheets and cell labels are a real output. Page furniture carries
`no-print`; `@media print` drops it and whitens the page.

## The courier surface — the second visual language

`web/src/pages/kuryer/` and `web/src/components/kuryer/` are **not** the back
office and must not be drawn in it. This is a deliberate departure, made once,
and everything above stops applying at the `/kuryer` route.

**Why.** The back office is a page of cards on a grey field with a rail down
the left: a desk tool, read sitting down, at arm's length, on a monitor. The
courier's app is a map held in one hand outdoors, in daylight, by somebody who
is walking and carrying a parcel. That difference is not a density — it is a
different shape of screen:

- A map has **no canvas** to put a card on. The chrome has to float over
  somebody else's imagery, which is what glass and a hairline are for.
- There is **no rail and no breadcrumb**, because there are four destinations
  and a tab bar under the thumb is how a phone navigates. A breadcrumb for four
  screens is a label.
- There is **no `PageHeader` card**. The screen's name is set large at the top
  of the scroll and nothing boxes it.
- The screens **own the viewport and scroll inside themselves**, because a
  bottom sheet that scrolls its stop list while the map behind it stays put is
  not something a document-scrolling page can do.

So the courier role has **its own shell** — `web/src/components/kuryer/shell.tsx`
— a sibling of `components/shell.tsx` in `App.tsx`, never nested inside it. The
other roles' rail, top bar and phone bottom bar are untouched by any of this and
must not regress.

**What is shared:** the session, the query client, the `.dark` class on
`<html>`, the toaster, `lib/format` (never `Intl`, on either surface), the
density variables, and the token file. Two languages, one system.

### Where its tokens live

In `shared/theme.css`, in a documented `kuryer-*` group inside the same
`@theme` block, with a dark restatement in the same `.dark` block as everything
else. **The rule at the top of this document is unchanged**: a courier screen
never writes a hex either, and there is none anywhere under those two
directories. The group was added because the system did not have these colours,
which is what "the system is wrong and gets a token" means in practice.

| Meaning | Token family |
| --- | --- |
| An act the courier can take | `kuryer-act` (+ `-ink`, `-deep`, `-soft`, `-edge`) |
| A thing that happened | `kuryer-done` (+ the same four) |
| Money in a pocket | `kuryer-cash` (+ `-ink`, `-soft`, `-edge`) |
| Stop — offline, a door that did not open | `kuryer-halt` (+ `-ink`, `-soft`, `-edge`) |
| The wash behind everything | `kuryer-ground`, `kuryer-ground-deep` |
| Text | `kuryer-ink`, `-ink-soft`, `-ink-faint` |
| Surfaces | `kuryer-card` (opaque), `kuryer-glass`, `kuryer-glass-strong`, `kuryer-sheet`, `kuryer-glass-edge` |
| Furniture | `kuryer-grab`, `kuryer-hair`, `kuryer-quiet` |

**These are not the back office's tokens renamed.** `brand` is a `#2585ff`
chosen to sit on white paper at a desk; `act` is the iOS `#0a84ff`, which is
what a floating pill over a map needs to stay blue in sun. `warn` means "not
yet" and `cash` means "an amount somebody is carrying" — one is a state and the
other is a sum, and the day they diverge a shared token would have been wrong.
Green still means *it happened* and nothing else, on both surfaces.

Radii are a second family, named the same way: `sheet` (34px), `glass` (28px),
`tile` (24px), `slab` (20px), `nub` (15px). Shadows likewise —
`shadow-kuryer-card`, `-glass`, `-float`, `-sheet`, and the two coloured ones,
`-act` and `-done`. Those two are the **only** place in this system a shadow is
allowed a hue: it is the glow under a filled button that is lit.

One extra type size, `--text-kuryer-title` (30px), for a screen's own name —
smaller than `.figure` and `.display`, which stay what they are, because the
sum under the heading is the thing being read. It is fixed rather than restated
per density: the courier surface is always `density-comfortable`, at every
width, by construction.

### The recipes

- **`.kuryer-glass`** — the fill *and* the blur, as one class, and they must
  never be separated: an 78%-opaque pane without `blur(22px) saturate(180%)`
  behind it has road names running through its text. `.kuryer-glass-strong` is
  the same thing at 94%, for a pane that scrolling content passes **under**.
  `.kuryer-sheet` is the bottom sheet: more blur, hairline on the top edge only.
- **Heights are still tokens.** `h-control-lg` (64px here) is a screen's
  primary action, `h-control-md` a secondary, `h-control-sm` a small one. The
  artboard drew 58/50/46; the token is the rule. The one exception is the 44px
  round glass button floating over a map, which is not in a row of its own.
- **One filled `act` slab per screen**, exactly as the office has one `primary`
  button per screen, for the same reason.
- **`.kuryer-tabs`** is the courier's `--bottom-nav`: the height of the
  floating tab bar plus its gap plus the home indicator. Its own token, because
  the two shells are siblings and a screen that reads the wrong one ends either
  under a bar or above a stripe of nothing. The tab bar is `z-[900]` and every
  sheet sits below it.
- **The map** is `leaflet` used directly, over OpenStreetMap tiles, and it is
  treated as a **convenience the whole time**. No network, no tiles, or no
  coordinates each say which of the three it is and hand the screen to the stop
  list — a courier in a basement still has to finish the round. Tiles are never
  precached; `.kuryer-tiles` is the class the dark theme's filter hangs off,
  and `.kuryer-route` / `.kuryer-pin-*` are how Leaflet's own nodes read tokens.

### Dark

The artboard is a light iOS mockup and has no dark. It exists anyway, because
this app has a theme switch and a courier works after sunset: the wash and the
glass invert into the same navy ramp as everything else, the three hues keep
their identity and only their inks move, and the tiles themselves are filtered.
Check both themes on the map, the sheet, the glass panes and the tab bar before
calling a courier change done — the same rule as the rail.
