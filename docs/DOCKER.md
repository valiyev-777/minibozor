# Docker, in this project

Everything here is about *this* repository — the three containers `./dev.sh`
starts, why each line of `docker-compose.yml` says what it says, and what to do
when one of them will not come up. The generic tutorial is elsewhere; this is
the one that matches what is on your screen.

---

## 1. The one idea

A container is **one process, with its own filesystem and its own network
stack, sharing your machine's kernel.**

That is the whole thing. It is not a virtual machine: there is no second
operating system booting, no emulated hardware, no fixed slice of RAM. When
`minibozor_api` runs `uvicorn`, `ps` on your laptop shows a normal Linux process
— it has simply been told that its `/` is a Debian image with Python 3.12 in it,
and that its `localhost` is its own.

Three words, and the rest of this file is consequences of them:

| Word | What it is | In this project |
|---|---|---|
| **Image** | A read-only filesystem, built once. | `minibozor-api`, `minibozor-web` |
| **Container** | One running process using an image as its disk. | `minibozor_api`, `minibozor_web`, `minibozor_db` |
| **Volume** | Storage that outlives the container. | `backend_minibozor_pgdata` |

An image is to a container what a program on disk is to a process. One image,
many containers; delete the container and the image is untouched.

---

## 2. The three containers

```
        your machine                            the compose network
 ┌────────────────────────────┐        ┌──────────────────────────────────┐
 │  Chrome  → localhost:5173 ─┼───────►│  minibozor_web    vite      :5173│
 │                            │        │                                  │
 │  Chrome  → localhost:8000 ─┼───────►│  minibozor_api    uvicorn   :8000│
 │  phone   → localhost:8000  │        │          │                       │
 │   (adb reverse, over USB)  │        │          └──► db:5432            │
 │                            │        │  minibozor_db     postgres  :5432│
 └────────────────────────────┘        └──────────────────────────────────┘
```

Two different networks are in that picture and mixing them up is the single
most common Docker mistake:

* **From your machine** a container is reachable only on a port it *published* —
  the `ports:` list. `localhost:8000` works because `api` publishes `8000:8000`.
* **From another container** the address is the **service name**: `db`, `api`,
  `web`. Compose runs a DNS server on the private network so those names
  resolve. The port is the one the process actually listens on *inside* — for
  Postgres always `5432`, never the `5434` you use from outside.

So `db:5432` and `localhost:5434` are the same database by two different routes,
and each route only works from one side. This is why `docker-compose.yml` says:

```yaml
MB_DATABASE_URL: ${MB_DOCKER_DATABASE_URL:-sqlite:///./minibozor.db}
```

and why the comment above it insists on `db`, not `localhost`. Inside a
container **`localhost` means the container itself** — a Postgres URL pointing
at `localhost` from inside `api` finds nothing, because nothing in that
container is listening.

The mirror image of the same rule is in the `web` service:

```yaml
VITE_API_URL: ${MB_API_URL:-http://localhost:8000}
```

That one is `localhost` *on purpose*. `VITE_API_URL` is not fetched by the web
container — it is compiled into JavaScript that runs in **Chrome, on your
machine**. `http://api:8000` would be correct for the container and meaningless
in the browser.

> **The rule:** ask *who is doing the connecting?* A container → service name. A
> browser, a phone, `curl` in your terminal → `localhost` and a published port.

---

## 3. Why editing code still works

The usual objection to Docker for local development is that every edit means
rebuilding an image. That is true only if the source is *in* the image, and here
it is not. Both Dockerfiles install dependencies and stop. The source arrives at
run time:

```yaml
volumes:
  - ./:/app
```

That is a **bind mount**: the directory on the left, on your disk, *is* the
directory on the right, inside the container. Not a copy — the same bytes. Save
`web/src/App.tsx` in your editor and the Vite process inside the container sees
the write immediately and pushes an HMR update; save a router and uvicorn's
`--reload` restarts the worker.

So:

| You changed | What to run |
|---|---|
| Any `.py`, `.ts`, `.tsx`, `.css` | Nothing. It already reloaded. |
| `backend/pyproject.toml` | `./dev.sh build` |
| `web/package.json` | `./dev.sh build` |
| `docker-compose.yml` | `./dev.sh` (compose recreates what changed) |

The repository **root** is mounted, not `backend/` and `web/` separately,
because `web/src/index.css` imports `../../shared/theme.css`. Mount the two apps
on their own and that import points outside the container at nothing.

### The node_modules exception

One line looks strange and is load-bearing:

```yaml
- web_node_modules:/app/web/node_modules
```

`npm ci` ran during the image build, so `node_modules` exists inside the image
at `/app/web/node_modules`. But the bind mount above lays your whole repository
over `/app`, which *covers* it with the host's `web/node_modules` — installed by
a different npm, on a different libc, possibly with different native binaries.
Mounting a named volume back on top of that one path un-covers the image's copy.

Bind mount for source, named volume for anything the image installed under it.

### Whose files are these?

A bind mount is a two-way street, and this is the part that bites. A container
writing through it writes onto *your* disk — with the container's user id, not
yours. A container running as root therefore leaves root-owned files behind in
your repository.

That happened here: `backend/minibozor.db` and four uploaded photos came back
owned by `root:root` at mode 644 — readable by your venv and no longer writable
by it. The database still worked *inside the container*, which is what makes it
a nasty one: nothing looks broken until you next run the backend on the host.

The fix is one line on the service, so the process runs as you:

```yaml
user: "${MB_UID:-1000}:${MB_GID:-1000}"
```

Only the API needs it. The web container writes nothing into the repository,
and its `node_modules` was installed by root inside the image — so running
*that* one as your uid would break npm instead. To check at any time:

```bash
find . -path ./.git -prune -o \( -user root \) -print   # should list nothing
```

Repairing files that already went root-owned needs no `sudo` on the host — the
container is already root, so let it hand them back:

```bash
docker compose exec api chown 1000:1000 /app/backend/minibozor.db
```

---

## 4. State, and what `down` destroys

Containers are disposable; that is the point. Everything written inside one goes
away when it is removed — *except* what was written to a volume or a bind mount.

This project has state in two places:

* **`backend/minibozor.db`** — the SQLite file, the database actually in use. It
  lives in your repository and is bind-mounted in. Containers cannot lose it.
  It is at `head` with the real catalogue in it.
* **`backend_minibozor_pgdata`** — a named volume holding a Postgres cluster.
  Currently an empty database still at `0001_baseline`; it is there for when you
  want Postgres.

Hence:

```bash
./dev.sh down        # removes the containers. Both databases survive.
./dev.sh down -v     # also deletes the volume. The Postgres data is gone.
```

`-v` is the only destructive one.

Volumes are named for the compose project, so this one is `minibozor_pgdata` —
`name: minibozor` at the top of the file is where that prefix comes from. Rename
the project and compose looks for a volume that does not exist, mounts a fresh
empty one, and leaves the old one **orphaned**: still on disk, still taking
space, invisible unless you go looking.

That has already happened once here. The compose file used to live in
`backend/`, so its volume is `backend_minibozor_pgdata`, and nothing references
it now. It only ever held an empty cluster at `0001_baseline`, so:

```bash
docker volume ls                              # see what is on disk
docker volume rm backend_minibozor_pgdata     # reclaim it
```

That is the one bit of Docker housekeeping nothing does for you — `docker system
prune` deliberately leaves named volumes alone, because data is exactly the
thing you do not want a cleanup command guessing about.

---

## 5. Reading a compose file

`docker-compose.yml` is the answer to "what runs". Every key in it:

```yaml
services:
  api:
    build: ./backend          # build the image from backend/Dockerfile
    env_file: [./backend/.env] # pour this file into the container's environment
    environment:               # ...and override these keys specifically
      MB_DATABASE_URL: ...
    volumes: ["./:/app"]      # the repository, mounted live
    working_dir: /app/backend # where the command runs
    ports: ["8000:8000"]      # HOST:CONTAINER — the left one is yours
    depends_on:
      db: {condition: service_healthy}
    healthcheck: ...          # how compose knows "running" means "working"
```

Two of those are worth dwelling on.

**`ports: "8000:8000"` is `HOST:CONTAINER`.** They are equal here, which hides
the asymmetry, so look at the database instead: `"5434:5432"`. Postgres listens
on 5432 inside; you reach it on 5434 outside, because 5432 and 5433 are usually
some other project's. Changing the left number changes nothing inside the
container.

**`depends_on` + `healthcheck` is ordering, done properly.** `depends_on` on its
own only waits for the container to *start*, which for a database means the
process exists and is not yet accepting connections. With `condition:
service_healthy` compose waits for the `healthcheck` command to pass. That is
what replaced the hand-written wait loops in the old `dev.sh`.

It is still not quite enough on a first boot — `pg_isready` answers once while
`initdb` is still setting up — which is why `backend/docker-entrypoint.sh` opens
a real connection before it trusts anything.

### Where the configuration comes from

There are two separate things called "env" and they are not the same:

```bash
docker compose --env-file backend/.env ...   # substitutes ${VAR} IN the yml file
```

```yaml
env_file: [./backend/.env]                   # puts vars INSIDE the container
```

`dev.sh` passes both, from the same file. The first is why
`${MB_POSTGRES_PASSWORD:?...}` resolves; the second is why the API can read
`MB_SECRET_KEY`. Compose reads `.env` from its own directory by default, and
this project's lives one level down in `backend/`, next to the app that owns it
— hence the explicit `--env-file`.

The `:?` in `${MB_POSTGRES_PASSWORD:?set MB_POSTGRES_PASSWORD in backend/.env}`
means *fail with this message if unset*. A default would have been worse: a
database that quietly comes up with a known password is not a convenience.

---

## 6. The commands worth knowing

`./dev.sh` wraps these, but the wrapper is thin and these work on any project:

```bash
docker compose ps                 # what is running, and is it healthy
docker compose logs -f api        # follow one service
docker compose exec api sh        # a shell in a RUNNING container
docker compose run --rm \
  -e MB_DATABASE_URL=sqlite:////tmp/test.db -e MB_NO_SEED=1 \
  api python -m pytest tests -q   # a NEW throwaway container, own database
docker compose restart api
docker compose build --no-cache api
docker compose down -v            # stop, remove, and delete volumes
```

`exec` versus `run` is the distinction people trip on: **`exec` joins something
already running**, `run` starts another container from the same image. Use
`exec` to look around; use `run --rm` for a one-off task that should not disturb
the running server.

Outside compose:

```bash
docker ps                  # running containers (-a for stopped ones too)
docker images              # images on disk
docker volume ls           # volumes — the things that hold data
docker stats               # live CPU and memory, per container
docker system df           # how much disk all of this is using
docker system prune        # reclaim it (does NOT touch named volumes)
```

---

## 7. Reading a Dockerfile

`backend/Dockerfile`, with the reasoning attached:

```dockerfile
FROM python:3.12-slim      # the base filesystem. -slim: no build tools.
ENV PYTHONUNBUFFERED=1     # or logs sit in a buffer and `logs -f` shows nothing
WORKDIR /app/backend       # mkdir -p and cd, for every line after this
COPY pyproject.toml ./     # just the dependency list...
RUN pip install ...        # ...so this layer is cached until THAT file changes
ENTRYPOINT ["docker-entrypoint.sh"]   # always runs
CMD ["uvicorn", "app.main:app", ...]  # the arguments, overridable
```

**Layers and the cache** are the reason for the order. Each instruction produces
a layer; Docker reuses a cached layer if that instruction and its inputs are
unchanged, and once one layer misses, everything after it rebuilds. Copying only
`pyproject.toml` before `pip install` means editing a router does not reinstall
FastAPI. (Here no source is copied at all, so the point is mostly about
`pyproject.toml` itself — but it is the habit that makes every other image
fast.)

**`.dockerignore`** controls what is even sent to the builder. `backend/.venv`
is hundreds of megabytes and is useless in a Linux image built from scratch;
excluding it is the difference between a two-second build context and a
two-minute one.

**`ENTRYPOINT` versus `CMD`:** the entrypoint always runs and receives `CMD` as
its arguments. Here the entrypoint waits for the database, runs
`alembic upgrade head`, seeds if the database has no users, then `exec "$@"` —
which is the `CMD`. So `./dev.sh sh api` still gets a shell: the arguments were
replaced, the entrypoint's preparation was not.

`exec "$@"` rather than plain `"$@"` matters: it *replaces* the shell rather
than forking, so uvicorn becomes PID 1 and receives the signal when Docker stops
the container. Without `exec`, the shell gets the signal, the server does not,
and the container takes the full ten-second timeout to die every time.

---

## 8. When it will not start

| What you see | What it means |
|---|---|
| `port is already allocated` | Something else holds the host port. `./dev.sh status`, or `docker ps`, then move it: `MB_API_PORT=8100 ./dev.sh` |
| `Cannot connect to the Docker daemon` | Docker is not running. `sudo systemctl start docker` |
| `container name ... already in use` | An older container has the name. `docker rm -f minibozor_db` — the volume, and so the data, is not touched. |
| API up, web says connection refused | `VITE_API_URL` or CORS. The browser's address, not the container's. |
| Web container runs, browser gets nothing | Vite bound to 127.0.0.1 inside the container. It needs `--host 0.0.0.0`. |
| Code edits do nothing | The bind mount is missing or the wrong path. `docker compose exec web ls /app/web/src` |
| `exec: not found` on `bash` | Alpine images have `sh`, not `bash`. |
| Everything is slow, disk is full | `docker system df`, then `docker system prune` |

The first move in all cases is the same:

```bash
./dev.sh logs api        # or web, or db
docker compose ps        # is it even running, and is it healthy
```

---

## 9. What this setup deliberately is not

This is a development topology. In production the same applications are built
differently and the differences are not details:

* **No source mounted.** The image contains the code, at a known commit.
* **No `--reload`, no dev server.** Uvicorn with real workers; the web app built
  to static files and served by a real web server, not Vite.
* **A multi-stage build** for the web app — Node builds it, and the shipped
  image is a web server with the `dist/` output and no Node in it at all.
* **No seeding, no automatic migration on start.** Migrating is a deploy step
  somebody watches, not something a restart does.
* **Secrets are not a bind-mounted `.env`.**
* **Not root.** The API already runs as your uid here (see "Whose files are
  these?" in section 3); the web container still runs as root. A production
  image creates its own user and drops to it.

`docker-compose.yml` here brings up a laptop. Host, domain, TLS, nginx and CI
are absent on purpose.
