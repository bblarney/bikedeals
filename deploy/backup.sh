#!/usr/bin/env bash
#
# Nightly backup of the bikegrid database.
#
# bikes and scrape_log regenerate from the next scrape run. price_events and
# subscribers do not: price history cannot be re-scraped after the fact, and
# subscriber emails cannot be re-collected. Those two tables are why this exists.
#
# Runs from a systemd timer; see deploy/bikegrid-backup.timer.

set -euo pipefail

COMPOSE_DIR="${COMPOSE_DIR:-/home/brett/bikegrid}"
BACKUP_DIR="${BACKUP_DIR:-/home/brett/backups}"
RCLONE_REMOTE="${RCLONE_REMOTE:-r2:bikegrid-backups}"
KEEP_LOCAL_DAYS="${KEEP_LOCAL_DAYS:-7}"
AGE_RECIPIENT_FILE="${AGE_RECIPIENT_FILE:-/home/brett/.config/bikegrid/backup-recipient.txt}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-}"

cd "$COMPOSE_DIR"
set -a; . ./.env; set +a

mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP="$BACKUP_DIR/bikegrid-$STAMP.dump"
ENC="$DUMP.age"

# Clean up the plaintext dump on any exit path. It contains subscriber email
# addresses and must not linger on disk unencrypted.
cleanup() { rm -f "$DUMP"; }
trap cleanup EXIT

echo "==> dumping"
# Custom format: compressed, and pg_restore can then restore selectively -
# useful when you want one table back rather than the whole database.
docker compose exec -T db pg_dump \
  -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --format=custom --compress=9 > "$DUMP"

# A dump that written but is unreadable is worse than no dump, because it looks
# like success. pg_restore --list parses the archive header and table of
# contents, so it fails loudly on a truncated or corrupt file.
echo "==> verifying archive is readable"
docker compose exec -T db pg_restore --list < "$DUMP" > /dev/null

# Guard against the silent-empty-database case: a dump of nothing is a valid
# archive, so check the tables we actually care about are represented.
for tbl in price_events subscribers bikes; do
  if ! docker compose exec -T db pg_restore --list < "$DUMP" | grep -q "TABLE DATA public $tbl"; then
    echo "FATAL: $tbl missing from dump" >&2
    exit 1
  fi
done

SIZE="$(du -h "$DUMP" | cut -f1)"
echo "==> dump ok ($SIZE)"

echo "==> encrypting"
# Asymmetric: the server holds only the public key, so anyone who compromises
# this box can create new backups but cannot read old ones.
age -R "$AGE_RECIPIENT_FILE" -o "$ENC" "$DUMP"

echo "==> uploading"
rclone copy "$ENC" "$RCLONE_REMOTE/daily/" --s3-no-check-bucket

echo "==> pruning local copies older than $KEEP_LOCAL_DAYS days"
find "$BACKUP_DIR" -name 'bikegrid-*.dump.age' -mtime +"$KEEP_LOCAL_DAYS" -delete

if [ -n "$HEALTHCHECK_URL" ]; then
  curl -fsS -m 10 --retry 3 "$HEALTHCHECK_URL" > /dev/null
  echo "==> pinged healthcheck"
fi

echo "==> done: $(basename "$ENC")"
