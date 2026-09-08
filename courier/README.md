# Kuryer · courier

The last mile, on `:5175`. A PWA: React 19 + TypeScript + Vite, Tailwind 4,
`@tanstack/react-query`, and the shared design system in `../shared`.

```bash
npm install
npm run dev              # or ../dev.sh, which starts the backend and all three panels
npm run dev -- --host    # and on the LAN, to open it on a real handset
npm run gen              # regenerate src/api/schema.d.ts from the running backend
npm run lint
npm run build
```

Sign in with a phone number and the SMS code `123456`. The seed's courier is
`+998900000004` — `cd ../backend && .venv/bin/python -m tools.dev_accounts
--apply` writes it.

## Three screens

| Route | The question it answers |
|---|---|
| `/` | Where am I going today? Deliveries and collections in one list. |
| `/orders/:id` | One door: the address, the telephone, and what happened. |
| `/pickups/:id` | One collection run: each door marked, then sent. |

No navigation, because there is nowhere to go — two of the three screens are
opened by tapping a row on the first.

## It is designed for a thumb, outdoors

`density-comfortable` on `<html>`: 18px body text and a 64px primary action,
because a phone at arm's length in daylight loses the bottom of its contrast
range and that is a target a thumb hits without aiming while holding a parcel.
The numbers and the reasoning are in `../shared/theme.css`, shared with the
other two panels — this app is a *variant of one system*, not a second one.

It is also the only one of the three that opts into dark (`allow-dark`), and
not as a preference: under a dark sky the phone switches and it is usually
right, because its light sensor is looking at the same sky the courier is.

## Two things a reader should know before changing it

**Every write carries an `Idempotency-Key`, and the key belongs to the
*action*.** A courier presses "Yetkazdim", the phone loses signal in a
stairwell, they press again — that is one delivery pressed twice, and both
attempts must carry the same key so the second replays the first answer
instead of selling the same shirt again. `src/api/keys.ts` derives it from what
is being done to what, and bumps an attempt counter when the server *refuses*,
so a corrected cash figure is a new request rather than a replay of the
refusal.

**There is no offline outbox in this version.** The plan says so, and the
consequence is on the screen rather than hidden: the header shows an offline
banner, and a write that cannot reach the server fails visibly so the courier
presses the button again. Queueing writes needs a store and a replay order, and
half of one is worse than none — it loses things silently. The idempotency keys
above are what a real outbox will be built on when it arrives.

## The install prompt and the icons

`beforeinstallprompt` is captured and held so the header can offer a button;
a browser that never fires it (every iOS one) gets no button rather than one
that does nothing — there, installing is Share → Add to Home Screen and no
button we render can reach it.

`public/icon-192.png` and `icon-512.png` are drawn by
`../tools/courier_icons.py` rather than committed as opaque binaries: an icon
nobody can regenerate is an icon nobody can change. `public/icon.svg` is the
same parcel written by hand for the browser tab.
