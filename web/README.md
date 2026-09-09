# web/

One application for three jobs: the office, the warehouse bench and the van.

There used to be three — `backoffice/`, `seller/`, `courier/` — each started in
its own session, each with its own vocabulary for the same colour and its own
idea of how big a button is. None of that was a decision; it was three
starting points. So this is one bundle, and what differs between the jobs is
**the navigation, the density and which routes exist**, all decided by the
role on the signed-in account.

```
npm install
npm run dev          # :5173, VITE_API_URL from the environment
npm run build        # tsc -b && vite build
```

`../dev.sh` starts this alongside the API and Postgres and hands it
`VITE_API_URL`, which is the ordinary way to run it.

## What is where

```
src/lib/format.ts    money, dates and ages — by hand, never Intl (see below)
src/lib/api.ts       the only place this app talks to the API
src/lib/session.tsx  who is signed in, and therefore which app this is
src/lib/nav.ts       role → navigation, density and landing route
src/components/ui/   shadcn/ui components, added with its CLI
src/index.css        Tailwind, then shared/theme.css, then the alias layer
```

## Three decisions worth knowing before editing

**`Intl` is not used for formatting.** `Intl.NumberFormat("uz-UZ")` does not
fail when the locale data is missing — it falls back silently, so the same
build prints `1,250,000` on one machine and `1 250 000` on another. A figure
with commas in it reads as a different number to the person holding the goods.
`src/lib/format.ts` is the only file allowed to turn a number or a date into
text, and it is four lines of arithmetic that does the same thing everywhere.

**The colours come from `shared/theme.css`.** No screen invents one. shadcn's
components speak a different vocabulary (`background`, `primary`,
`destructive`) because they are written to drop into any project, so the two
are bound together once, at the top of `src/index.css`, as aliases onto real
tokens rather than as a second palette.

**Density is a role, not a taste.** `density-compact` at a desk, `density-cozy`
at the bench, `density-comfortable` in the van — 18px body text and a 64px
primary action, because that is a target a thumb hits without aiming while
holding a parcel.
