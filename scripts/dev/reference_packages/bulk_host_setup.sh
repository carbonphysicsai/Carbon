#!/usr/bin/env bash
# Bootstrap a fresh Ubuntu/Debian x86-64 cloud VM for bulk_run.py.
#
#   sudo bash bulk_host_setup.sh --bundle /root/bundle \
#       (--repo URL --commit SHA | --repo-tarball carbon.tar.gz) \
#       [--mirror https://mirror.gcr.io] [--pull REPO@sha256:...]... [--start]
#
# The bundle directory (copied to the VM with scp/rsync) holds:
#   plan.json                 carbon.reference-bulk.run-plan.v1, manifest_dir
#                             paths relative to itself (e.g. decks/f02)
#   decks/<family>/...        each family's frozen manifest dir
#   images/*.tar.zst          optional: `docker save REF | zstd` exports
#
# Steps: install docker.io, zstd, git, python3; optional registry mirror;
# load image tarballs and/or pull digest references; place the repo at the
# exact commit in /opt/carbon; copy the bundle to /srv/bulk; run the dry run
# (images, hashes, schedule estimate); with --start, run the plan under
# nohup as the unprivileged user `bulk`. Nothing here creates, sizes or
# deletes the VM: that, and the spend, stay with the operator's grant.
#
# Stop conventions (see docs/development/challenge_pipeline/bulk-run/README.md):
#   touch /srv/bulk/out/STOP       drain: no new cases, running ones finish
#   touch /srv/bulk/out/STOP_NOW   stop running cases now (censored)
set -euo pipefail

BUNDLE="" REPO="" COMMIT="" TARBALL="" MIRROR="" START=0
PULLS=()
while [ "$#" -gt 0 ]; do
    case "$1" in
    --bundle) BUNDLE="$2"; shift 2 ;;
    --repo) REPO="$2"; shift 2 ;;
    --commit) COMMIT="$2"; shift 2 ;;
    --repo-tarball) TARBALL="$2"; shift 2 ;;
    --mirror) MIRROR="$2"; shift 2 ;;
    --pull) PULLS+=("$2"); shift 2 ;;
    --start) START=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done
[ "$(id -u)" -eq 0 ] || { echo "run as root (sudo)" >&2; exit 2; }
[ -f "$BUNDLE/plan.json" ] || { echo "--bundle must contain plan.json" >&2; exit 2; }
if [ -z "$TARBALL" ] && { [ -z "$REPO" ] || [ -z "$COMMIT" ]; }; then
    echo "give --repo and --commit, or --repo-tarball" >&2; exit 2
fi
[ "$(uname -m)" = x86_64 ] || { echo "x86-64 only (pinned images are amd64)" >&2; exit 2; }

BULK=/srv/bulk
CARBON=/opt/carbon
log() { echo "[bulk-setup $(date -u +%H:%M:%S)] $*"; }

log "host: $(nproc) CPUs, $(awk '/MemTotal/ {printf "%.1f GiB", $2/1048576}' /proc/meminfo)," \
    "$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs)"
if [ -f /sys/fs/cgroup/cgroup.controllers ]; then
    log "cgroup v2 (memory.peak needs kernel >= 5.19: $(uname -r))"
else
    log "cgroup v1: memory peak is memory.max_usage_in_bytes (includes page cache)"
fi

log "installing docker.io zstd git python3"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq docker.io zstd git python3 ca-certificates >/dev/null
python3 -c 'import sys; assert sys.version_info >= (3, 11), sys.version' || {
    echo "bulk_run.py needs Python 3.11+ (Ubuntu 24.04 / Debian 13)" >&2; exit 2; }

if [ -n "$MIRROR" ]; then
    log "registry mirror $MIRROR"
    mkdir -p /etc/docker
    printf '{"registry-mirrors": ["%s"]}\n' "$MIRROR" > /etc/docker/daemon.json
fi
systemctl enable --now docker >/dev/null
systemctl restart docker
docker info --format 'docker {{.ServerVersion}}, cgroup {{.CgroupVersion}}, {{.Driver}}'

shopt -s nullglob
for tarball in "$BUNDLE"/images/*.tar.zst; do
    log "loading $tarball ($(sha256sum "$tarball" | cut -c1-16)...)"
    zstd -dc "$tarball" | docker load
done
for ref in "${PULLS[@]}"; do
    case "$ref" in *@sha256:*) ;; *) echo "--pull takes REPO@sha256:... only: $ref" >&2; exit 2 ;; esac
    log "pulling $ref"
    docker pull -q "$ref"
done
log "images here (a family's plan image is an ID or REPO@sha256 from this list):"
docker images --digests --no-trunc --format '  {{.Repository}}:{{.Tag}} {{.Digest}} {{.ID}}'

log "placing the repository in $CARBON"
rm -rf "$CARBON"
if [ -n "$TARBALL" ]; then
    mkdir -p "$CARBON"
    tar -xzf "$TARBALL" -C "$CARBON"
else
    git clone -q --filter=blob:none --no-checkout "$REPO" "$CARBON"
    git -C "$CARBON" checkout -q "$COMMIT"
    log "repo at $(git -C "$CARBON" rev-parse HEAD)"
fi
RUNNER="$CARBON/scripts/dev/reference_packages/bulk_run.py"
[ -f "$RUNNER" ] || { echo "no $RUNNER in that commit" >&2; exit 2; }

log "placing the bundle in $BULK"
id bulk >/dev/null 2>&1 || useradd --create-home --shell /bin/bash bulk
usermod -aG docker bulk
mkdir -p "$BULK"
cp "$BUNDLE/plan.json" "$BULK/plan.json"
[ -d "$BUNDLE/decks" ] && cp -a "$BUNDLE/decks" "$BULK/"
chown -R bulk:bulk "$BULK"

log "dry run (images, case hashes, schedule estimate) -> $BULK/dry-run.json"
runuser -u bulk -- python3 "$RUNNER" --plan "$BULK/plan.json" --out "$BULK/out" --dry-run \
    | runuser -u bulk -- tee "$BULK/dry-run.json"

if [ "$START" -eq 1 ]; then
    log "starting the plan under nohup; log $BULK/run.log"
    runuser -u bulk -- bash -c "cd $BULK && nohup python3 $RUNNER --plan $BULK/plan.json \
        --out $BULK/out > $BULK/run.log 2>&1 & echo \$! > $BULK/run.pid"
    log "pid $(cat $BULK/run.pid). Drain: touch $BULK/out/STOP. Stop now: touch $BULK/out/STOP_NOW"
    log "progress: tail -f $BULK/run.log; collect: bash $CARBON/scripts/dev/reference_packages/bulk_collect.sh"
else
    log "dry run only. Start with:"
    echo "  runuser -u bulk -- bash -c 'cd $BULK && nohup python3 $RUNNER --plan $BULK/plan.json --out $BULK/out > $BULK/run.log 2>&1 & echo \$! > $BULK/run.pid'"
fi
