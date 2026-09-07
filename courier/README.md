# Mini Bozor · Kuryer

Vite + React + TypeScript + Tailwind, installed to a courier's home screen and
built to keep working when the phone cannot reach anything.

## Why this is its own project

A courier is not staff at a desk. They are outdoors, one-handed, on an issued
phone, and half their day happens in stairwells and basements where there is no
network at all. None of that is true of the backoffice or the seller cabinet,
and the code that follows from it — a write queue on disk, a session that
survives having no server to ask, a palette built for direct sun — has nothing
to say to either of them.

So: its own build, its own deployment, its own OpenAPI client, its own
primitives. `api/client.ts` and the pieces in `components/ui.tsx` began as
copies of the seller cabinet's and have already diverged; that is the design
working, not drift to be tidied up. Sharing them would need a workspace, a
build step and a version to keep three applications in step, which costs more
than the two hundred lines it saves.

**A web app rather than a native one.** Couriers are issued cheap Android
handsets, and everything below — the queue, the offline start, the camera, the
one-tap call — is reachable from a browser. What it costs is stated under
*Known limits*.

## Running it

```sh
# 1. the API, on 8001. Not 8000: the customer app's dev server owns that and
#    both are usually running. It must name this origin — it answers with
#    credentials, and a browser refuses a wildcard alongside them.
cd backend
MB_ENV=dev \
MB_CORS_ORIGINS=http://localhost:5175,http://127.0.0.1:5175 \
  .venv/bin/python -m uvicorn app.main:app --reload --port 8001

# 2. a courier with a day's work in front of them. `app.seed` builds a
#    catalogue and a customer and stops there — nothing in it assigns anybody
#    a delivery, because until this app existed nothing read one.
cd ../courier
MB_DATABASE_URL=sqlite:///../backend/minibozor.db \
PYTHONPATH=../backend python3 tools/seed-round.py

# 3. the app
npm install
npm run dev            # http://localhost:5175
```

Sign in as `+998 90 000 00 07`. In dev the SMS code is always `123456` and the
login screen shows it, because `/auth/otp/request` echoes it back when
`MB_ENV=dev`.

**Only a courier gets in.** An operator or an admin is turned away as firmly as
a customer, and told which role they signed in as and where their own panel is.
`/staff/me` is what answers — the customer profile shape carries no role, and
two shipped apps read it, so it is not going to grow one.

## The queue, which is most of this application

Everything the courier writes — a delivery, a failed attempt, opening or
closing a shift, handing in a collection — goes through one path, online or
not. There is no "send it now if we can, queue it otherwise" branch in any
screen. A delivery recorded on good signal and one recorded in a lift take the
same route, get the same key, and are sent by the same loop; the only
difference is how long the row lives.

The rules, and what each one is protecting:

- **One key per action, minted once.** Every write in `/courier/*` requires an
  `Idempotency-Key`. It is a uuid generated at the moment the courier taps the
  button and written to IndexedDB before anything is sent, and every later
  attempt carries that same key. Minting a fresh one on retry is the bug this
  app exists to prevent: the server would see two unrelated requests and put
  the same 240 000 so'm on the shift twice, and nobody would notice until the
  courier was accused of being short.
- **The body is frozen with it.** The request is encoded once and sent byte for
  byte thereafter. The server hashes the body alongside the key, so a body that
  differs on the second attempt is not a retry — it is refused with a 409, and
  rightly, because it is a different request. This is why `postKeyed` takes a
  string and not an object, and why a photo cannot be attached to an action
  after the fact.
- **In order, one at a time.** A delivery cannot land before the shift it
  belongs to is open, and a shift must not close before the deliveries that
  make up its cash. A network failure stops the run rather than burning the
  battery discovering the same thing five times.
- **A refusal is not a retry.** A 4xx means the server understood and said no.
  The row is marked blocked, stays on the queue screen with the server's own
  sentence on it, and the loop moves on to the next — the rows behind it are
  unrelated doors. Only a blocked row can be discarded, and only deliberately:
  a pending row holds work the courier actually did.
- **It survives the phone.** IndexedDB, and `navigator.storage.persist()` is
  requested on first load so Chrome does not evict the queue when the handset
  runs short of space. Installing the app to the home screen is what makes that
  request succeed without a prompt — worth telling dispatch.
- **The courier can see it.** The count is in the header of every screen, and
  the queue screen spells out what, when, how many tries, and why the server
  refused it. A courier who finishes a round with eleven actions queued and no
  idea they are queued hands the phone back and goes home.

`offline/sync.ts` is the loop, `offline/outbox.ts` the rows, `offline/derive.ts`
the overlay that puts unsent work on the screens as unsent rather than as fact.

The service worker matters for the same reason: a courier who reloads
underground must get the application back rather than the dinosaur, with the
queue behind it unreachable until they find signal — which is the one moment
they cannot.

## Testing it

```sh
npm test                      # the queue, against a real IndexedDB
MB_LIVE=1 npm test            # …and against a running backend on 8001
```

`outbox.test.ts` proves the queue behaves: a delivery recorded with no network
is retried under the key it was born with, survives the database being closed
and reopened, and is sent exactly once when the network returns. The live suite
proves the two halves agree — that the header this app sends is the one
`app/idempotency.py` reads, that four attempts are one sale and one lot of cash
at the far end, and that the same key carrying a different body is refused. It
consumes the fixture; re-run `tools/seed-round.py` afterwards.

## Known limits

- **A photograph needs signal.** It is optional, and it is only offered when
  the app can reach the server, because the upload has to happen *before* the
  action is queued — the body cannot change after the key is issued. The
  recipient's name is the evidence that always works, which is why the server
  requires that and not the photo.
- **The API does not carry the line items.** `CourierOrderOut` has a count and
  a total and no list, so the order screen shows those. The contents would be a
  field on that shape rather than a second request from here — a courier is
  refused the operator's endpoint that has them, and correctly.
- **Sending happens while the app is open.** There is no Background Sync
  registration: the service worker would need to hold the access token to send
  anything, and putting a credential there is a trade this app declined for a
  tool the courier has open all shift. The queue is emptied on load, when the
  phone reports a network, when the app comes back to the foreground, and every
  thirty seconds while anything is waiting.
- **One language.** All the copy is Uzbek, written inline the way the seller
  cabinet writes its own. The server answers in Uzbek too — the client sends
  `Accept-Language: uz` — so error text arrives already worded.

## Regenerating the API client

`src/api/schema.d.ts` comes out of the backend's own OpenAPI document. Nothing
in it is hand-written, so when a field moves the build says so rather than a
screen quietly showing `undefined`:

```sh
MB_API_URL=http://localhost:8001 npm run gen
```
