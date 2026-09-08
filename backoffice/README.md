# Backoffice

The staff side, on `:5173`. React 19 + TypeScript + Vite, Tailwind 4,
`@tanstack/react-query`, and the shared design system in `../shared`.

```bash
npm install
npm run dev          # or ../dev.sh, which starts the backend and all three panels
npm run gen          # regenerate src/api/schema.d.ts from the running backend
npm run lint         # tsc -b --noEmit
npm run build
```

Sign in with a phone number and the SMS code `123456`.
`cd ../backend && .venv/bin/python -m tools.dev_accounts --apply` prints one
number per role: admin `+998900000001`, operator `+998900000002`, warehouse
`+998900000003`.

## Three roles, one application

`src/lib/nav.ts` is the whole of the difference between them, and both the
menu and the route guard read that one table — a menu built from one list and
a guard written from another is how a panel ends up with a row nobody can open
or a screen anybody can reach by typing its path. The admin is not listed on
every line; `allowed()` lets them through everything.

| Screen | warehouse | operator | admin |
|---|:-:|:-:|:-:|
| `/` — four numbers, each a link to the list behind it | | | ● |
| `/supplies`, `/supplies/:id` — count a batch in, or refuse it | ● | | ● |
| `/orders`, `/orders/:id` — pick, route, cancel | ● | ● | ● |
| `/pickups` — the van, out and back | ● | | ● |
| `/removals` — goods going back to a seller | ● | | ● |
| `/stock` — the movement ledger | ● | | ● |
| `/returns`, `/returns/:id` — the money and the parcel | ● | ● | ● |
| `/sellers`, `/users` | | | ● |
| `/catalog`, `/products/:id/edit` | | | ● |

The warehouse lands on `/supplies`, the operator on `/orders`, the admin on
`/`: whatever they do first.

## What is worth knowing before changing it

**Receiving a batch is the most consequential screen here.** It is the moment
goods reach the shelf *and* the moment a seller's product goes on sale, and it
is built around one rule: the declared figure is never edited. Count boxes
start empty rather than pre-filled, because a pre-filled form is a form
somebody accepts without counting — "Hammasini to'liq" is there for the common
case and is a button somebody has to press.

**Buttons come from the server.** An order's moves are `next_statuses`, a
return's are `next_statuses` plus whether it has been inspected. That is
`app.transitions` answering, so this client keeps no copy of the rules and
cannot offer a button the server refuses.

**Nothing here publishes a product.** `/catalog` lists the cards waiting on a
batch and `/products/:id/edit` fixes what a seller wrote — the title spelled
wrong, the photograph nobody can see anything in. A card reaches the shop when
the warehouse counts its batch in, which is the receive screen. The price is
absent from the editor on purpose: it belongs to the seller's offer.

**A role sees the screens it works, and not the others greyed out.** A
disabled row is an invitation to ask why.

## `src/ui` is a symlink

It points at `../shared/ui`: one button, one badge, one set of loading, empty
and failed states, shared with the seller's cabinet and the courier's app. The
density class on `<html>` — `density-compact` here, because this is hundreds of
rows a day at a desk — is what makes the same component the right size in all
three. Nothing panel-specific belongs in `src/index.css`.
