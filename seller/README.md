# Sotuvchi kabineti · seller

The shopkeeper's side, on `:5174`. React 19 + TypeScript + Vite, Tailwind 4,
`@tanstack/react-query`, and the shared design system in `../shared`.

```bash
npm install
npm run dev          # or ../dev.sh, which starts the backend and all three panels
npm run gen          # regenerate src/api/schema.d.ts from the running backend
npm run lint         # tsc -b --noEmit
npm run build
```

Sign in with a phone number and the SMS code `123456` — dev builds answer with
the code and the login screen shows it. The seed's seller is `+998900000005`;
`cd ../backend && .venv/bin/python -m tools.dev_accounts --apply` prints the
rest.

## What is here

Six screens, and they are the six in `docs/rebuild-plan.md` §5. There is no
dashboard, no chart and no settings page: every screen answers a question a
shopkeeper actually asks.

| Route | The question it answers |
|---|---|
| `/products` | Did my things arrive, and are they selling? |
| `/products/new` | One form: the card, its photographs, its price, colours, sizes and how many are coming. |
| `/products/:id` | What happened to this one — including *why* it was refused. Price, send more, take it back. |
| `/supplies` | Has my box been counted yet, and did the count match? |
| `/orders` | What has sold. Read-only. |
| `/returns` | Something came back: the warehouse's verdict, and my decision. |
| `/account` | What am I owed? |

## Three things worth knowing before changing it

**`src/api/schema.d.ts` is generated.** It comes out of the backend's own
OpenAPI document, so a field that moves breaks the build instead of quietly
rendering `undefined`. `src/api/types.ts` names only the shapes a *seller* can
reach — the plan's §3 in TypeScript — so a screen cannot casually call an
operator's endpoint and put a 403 in front of somebody.

**Buttons come from the server.** A return's `seller_decisions` is the list of
moves still open on that row, and the rule that damaged goods do not go back on
sale lives in `POST /staff/returns/{id}/decide`. This client deliberately keeps
no copy of it: a client with its own copy eventually offers a button the server
refuses.

**The access token is in memory only.** The refresh token is an HttpOnly cookie
this code cannot read, so `credentials: "include"` is the whole of our
involvement — see the note at the top of `src/api/client.ts`.

## `src/ui` is a symlink

It points at `../shared/ui`: one button, one badge, one set of loading, empty
and failed states, shared with the backoffice and the courier's app. The
density class on `<html>` (`density-cozy` here) is what makes the same
component the right size in all three. Nothing panel-specific belongs in
`src/index.css`.
