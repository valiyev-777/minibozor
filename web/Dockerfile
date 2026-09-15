# The web app, as `docker compose` runs it — Vite's dev server, not a build.
#
# Same shape as backend/Dockerfile and for the same reason: no source in the
# image. The repository is bind-mounted over /app, so an edit on the host is
# an HMR update in the browser. What is baked in is node_modules, because that
# is the slow part.
#
# node_modules lives *inside* the image at /app/web/node_modules and compose
# keeps it there with a named volume mounted at that path — otherwise the bind
# mount of the repository would hide it behind the host's copy, which was
# installed by a different npm on a different libc and is not this image's to
# use.
#
# Rebuild when package.json changes:  ./dev.sh build
FROM node:24-alpine

WORKDIR /app/web

# The lockfile, and `npm ci` rather than `npm install`: ci installs exactly
# what the lockfile says and fails if package.json has moved on without it,
# which is the behaviour worth having in an image — an install that quietly
# resolves something newer is an image that differs from every other machine.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

EXPOSE 5173

# --host, because without it Vite listens on 127.0.0.1 *inside the container*,
# where nothing on your machine can reach it. The port and strictPort are
# already in vite.config.ts.
CMD ["npx", "vite", "--host", "0.0.0.0"]
