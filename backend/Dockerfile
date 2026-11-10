FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Mirrors are slow/flaky from some networks; retry instead of dying on a
    # single stalled read.
    PIP_DEFAULT_TIMEOUT=60 \
    PIP_RETRIES=5

# Official PyPI first. PIP_FALLBACK_INDEX_URLS is a space-separated list of
# mirrors tried in order when an index is unreachable or misses a package
# (hatchling is missing from some corporate mirrors).
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_FALLBACK_INDEX_URLS=
ENV PIP_INDEX_URL=$PIP_INDEX_URL

# Debian mirror used only when deb.debian.org is unreachable from the build
# network. Empty keeps the official Debian sources untouched.
ARG DEBIAN_MIRROR_URL=
ARG DEBIAN_MIRROR_SECURITY_URL=

COPY pyproject.toml ./

# psql/pg_dump power the superadmin database backup dashboard. Keep this
# layer before the source copy so normal code changes don't reinstall it.
# Official Debian sources stay in place when they are reachable; the sed
# rewrite to the mirror only happens when a real HTTP fetch fails (a TCP
# connect can succeed while the HTTP payload is blocked by DPI).
RUN set -eux; \
    if [ -n "$DEBIAN_MIRROR_URL" ] && ! timeout 15 python -c "import urllib.request; urllib.request.urlopen('http://deb.debian.org/debian/dists/trixie/InRelease', timeout=5)"; then \
      echo "deb.debian.org unreachable; switching to $DEBIAN_MIRROR_URL"; \
      for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; do \
        [ -f "$f" ] || continue; \
        sed -i \
          -e "s|http://deb.debian.org/debian-security|$DEBIAN_MIRROR_SECURITY_URL|g" \
          -e "s|https://deb.debian.org/debian-security|$DEBIAN_MIRROR_SECURITY_URL|g" \
          -e "s|http://deb.debian.org/debian|$DEBIAN_MIRROR_URL|g" \
          -e "s|https://deb.debian.org/debian|$DEBIAN_MIRROR_URL|g" \
          "$f"; \
      done; \
    fi; \
    APT_OPTS="-o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::http::Pipeline-Depth=0"; \
    apt-get $APT_OPTS update; \
    apt-get $APT_OPTS install -y --no-install-recommends postgresql-client; \
    rm -rf /var/lib/apt/lists/*

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN --mount=type=cache,target=/root/.cache/pip \
    sh -c 'reachable=""; \
           for index in $PIP_INDEX_URL $PIP_FALLBACK_INDEX_URLS; do \
             if timeout 10 python -c "import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=5)" "$index"; then \
               reachable="$reachable $index"; \
             else \
               echo "skipping unreachable index: $index"; \
             fi; \
           done; \
           [ -n "$reachable" ] || { echo "no pip index reachable"; exit 1; }; \
           for index in $reachable; do \
             echo "pip install using $index"; \
             PIP_INDEX_URL="$index" pip install . && exit 0; \
           done; \
           echo "pip install failed on every reachable index"; exit 1'

EXPOSE 8001

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8001"]
