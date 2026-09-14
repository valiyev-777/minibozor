---
name: backoffice-design
description: The Mini Bozor back-office design system — palette, type, density, chrome and component recipes ported from the react-backoffice-boilerplate. Load before writing or restyling anything in web/ (screens, panels, tables, forms, the shell) so a new screen is drawn in the same language as the rest.
---

# Back-office design

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
| Card | `surface` | `#FFFFFF` | `#0C1017` |
| Page behind cards | `canvas` | `#F1F3F6` | `#090E14` |
| Sidebar | `rail` | `#090E14` | `#090E14` |
| Sidebar text | `rail-ink` | `#F3F4F6` | `#F3F4F6` |
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
- `.density-cozy` — seller / warehouse. 15px body, 40px control.
- `.density-comfortable` — courier. 18px body, 56px control, 64px primary.

A component reads `h-control` / `h-control-sm` / `h-control-lg` (and
`size-control*` for square icon buttons). It never writes `h-9`.

## Shape and depth

- `rounded-control` (8px) — buttons, inputs, chips, nav items, small things.
- `rounded-panel` (12px) — cards, panels, modals, anything that holds content.
- `rounded-full` — pills and avatars only.
- `shadow-panel` — a resting surface. `shadow-raised` — the thing that is
  acting: an open menu, a modal, a sticky header once the page has scrolled.
- Nothing else. Two steps of elevation is the whole ramp.

## Chrome

**The rail.** 264px, `bg-rail` (`#090E14`), fixed, full window height, white
text. Collapses to 76px (icons only) and re-expands on hover. A 72px brand
header at the top with a blurred brand-blue glow behind it and a hairline
`border-white/10` under it. Menu items are 44px tall, `rounded-control`,
`text-small font-medium`; hover is `bg-brand/10`, active is `bg-brand/15` with
white text and a **brand-coloured icon**. A count rides on the right of an item
when the queue behind it has a length.

**The top bar.** 72px, `bg-surface`, sticky, breadcrumb on the left and the
profile menu on the right, and it grows `shadow-raised` only once the page has
scrolled. The breadcrumb is the page's location, not its title.

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
carried by the icon box and the figure, never by washing the whole card.

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
(`light` / `dark` / `system`, remembered in `localStorage`). Neutrals flip to a
cool navy ramp; the brand hue and the three meanings keep their identity. Never
put a colour only inside the `.dark` block — define it light first.

## Printing

Label sheets and cell labels are a real output. Page furniture carries
`no-print`; `@media print` drops it and whitens the page.
