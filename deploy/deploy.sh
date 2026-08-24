#!/usr/bin/env bash
#
# Server-side deploy. Invoked over SSH from .github/workflows/deploy.yml.
#
# This is wired up as a forced command in ~/.ssh/authorized_keys, so the deploy
# key cannot run anything else - the workflow opens an SSH session and this runs
# regardless of what it asks for. That keeps a compromised CI secret from being
# a shell on the box.

# FIRST-TIME SETUP IS MANUAL, and not optional. CI runs this script *on the
# server*, so the server must already have it — but the only thing that
# updates the server's checkout is this script. A box that has never been
# deployed to therefore cannot be deployed to; bootstrap it once by hand:
#
#     cd /home/brett/bikegrid && git pull --ff-only origin main
#
# The same applies after any change to this file's path or name.
#
# This file is committed 100755 on purpose. sshd execs the forced command
# directly, so a non-executable checkout fails with 'Permission denied' —
# and running `chmod +x` on the box instead makes the working tree dirty,
# which makes the `git checkout` below abort on every subsequent deploy.

set -euo pipefail

cd /home/brett/bikegrid

echo "==> updating checkout"
# --ff-only rather than a reset: if someone has committed on the box, fail
# loudly instead of silently discarding their work.
git fetch --quiet origin main
git checkout --quiet main
git merge --ff-only --quiet origin/main
echo "    now at $(git rev-parse --short HEAD) $(git log -1 --pretty=%s)"

echo "==> building api image"
docker compose build api

# Migrations run from the NEW image, after the build and before the restart.
# That order is right for additive changes (add a column, then serve code that
# uses it). A destructive change - dropping or renaming a column - needs the
# opposite: ship code that stops referencing it in one deploy, drop it in the
# next. Alembic is idempotent, so this is a no-op when nothing is pending.
echo "==> applying migrations"
docker compose run --rm api alembic upgrade head

echo "==> restarting api"
docker compose up -d api

# Do not report success until the container says it is healthy. The API's
# healthcheck hits /api/v1/health, which touches the database - so this catches
# a container that boots but cannot reach Postgres.
echo "==> waiting for health"
cid="$(docker compose ps -q api)"
for _ in $(seq 1 45); do
  status="$(docker inspect --format '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo starting)"
  if [ "$status" = "healthy" ]; then
    echo "==> healthy"
    exit 0
  fi
  if [ "$status" = "unhealthy" ]; then
    echo "FATAL: container reported unhealthy" >&2
    docker compose logs api --tail 50 >&2
    exit 1
  fi
  sleep 2
done

echo "FATAL: timed out waiting for the api container to become healthy" >&2
docker compose logs api --tail 50 >&2
exit 1
