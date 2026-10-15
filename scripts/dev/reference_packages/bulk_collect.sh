#!/usr/bin/env bash
# Pack a bulk run for download before the VM is deleted.
#
#   bash bulk_collect.sh [--bulk /srv/bulk] [--no-work] [--dest DIR]
#
# Writes DEST/bulk-<plan_id>-<UTC stamp>.tar.zst (.tar.gz without zstd) with plan.json, dry-run.json,
# run.log, out/ledger.jsonl, out/summary/, every case's meta/ (cgroup stats,
# docker logs, outputs.json) and, unless --no-work, every case's work/
# (solver outputs). Prints the archive's sha256 for the transfer record.
# Rewrites the summaries from the ledger when they are older than it (a
# crashed or still running runner). Read-only for the run itself.
set -euo pipefail

BULK=/srv/bulk DEST="" WORK=1
while [ "$#" -gt 0 ]; do
    case "$1" in
    --bulk) BULK="$2"; shift 2 ;;
    --dest) DEST="$2"; shift 2 ;;
    --no-work) WORK=0; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done
DEST="${DEST:-$BULK}"
RUNNER="${RUNNER:-/opt/carbon/scripts/dev/reference_packages/bulk_run.py}"
[ -f "$BULK/out/ledger.jsonl" ] || { echo "no ledger at $BULK/out" >&2; exit 2; }

if [ -f "$RUNNER" ] && [ "$BULK/out/ledger.jsonl" -nt "$BULK/out/summary/all.json" ]; then
    python3 "$RUNNER" --plan "$BULK/plan.json" --out "$BULK/out" --summarize > /dev/null
fi
PLAN_ID=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["plan_id"])' "$BULK/plan.json")
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
if command -v zstd > /dev/null; then
    ARCHIVE="$DEST/bulk-$PLAN_ID-$STAMP.tar.zst" PACK="zstd -q -T0 -10"
else
    ARCHIVE="$DEST/bulk-$PLAN_ID-$STAMP.tar.gz" PACK="gzip -6"
fi

cd "$BULK"
LIST=$(mktemp)
for f in plan.json dry-run.json run.log out/ledger.jsonl out/summary; do
    [ -e "$f" ] && echo "$f" >> "$LIST"
done
if [ -d out/cases ]; then
    find out/cases -mindepth 3 -maxdepth 3 -type d -name meta >> "$LIST"
    [ "$WORK" -eq 1 ] && find out/cases -mindepth 3 -maxdepth 3 -type d -name work >> "$LIST"
fi
tar -cf - -T "$LIST" | $PACK > "$ARCHIVE"
rm -f "$LIST"
echo "$ARCHIVE"
sha256sum "$ARCHIVE"
du -h "$ARCHIVE" | cut -f1
