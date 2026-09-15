# The API, as `docker compose` runs it.
#
# This is a *development* image and it deliberately holds no source code. The
# repository is bind-mounted over /app at run time, so what is baked in here is
# only the part that is slow to install and slow to change: the interpreter and
# the dependencies. Editing a router on the host is then a uvicorn reload, not
# an image rebuild — which is the objection to Docker for local work, and the
# answer to it.
#
# Rebuild when pyproject.toml changes:  ./dev.sh build
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# curl, for the healthcheck compose runs against /health. Nothing else: pillow
# and psycopg[binary] both ship wheels, so this image needs no compiler and no
# system libpq.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# The dependency list is *read out of* pyproject.toml rather than copied into a
# requirements.txt beside it. A second list is a list that drifts: it goes
# wrong silently and in one direction, and the day anybody notices is the day
# the image turns out to have been missing something the host venv has had for
# a month. One source, parsed.
COPY pyproject.toml ./
RUN python - <<'PY' > /tmp/requirements.txt
import tomllib

project = tomllib.load(open("pyproject.toml", "rb"))["project"]
extras = project.get("optional-dependencies", {})
# `dev` and `postgres` as well as the base set. The tests are meant to run in
# here — an environment you cannot run the suite in is not the environment the
# application runs in — and Postgres is one variable away at all times.
for requirement in project["dependencies"] + extras["postgres"] + extras["dev"]:
    print(requirement)
PY
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
