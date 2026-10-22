#!/usr/bin/env bash
# The common sealed-exam payload runner (Validator, VALIDATOR_EXAM_ARCHITECTURE_COMMON_20261022 §3):
# one shell flow for every Challenge's sealed batches, each Challenge supplying only its config
# (scripts/dev/sealed_exam/configs/<challenge>.env), its pack and QA scripts and its probe plan from the
# payload directory ($STATE). Stages:
#
#   guard (C10) -> code pin -> env -> custody -> image -> probe -> [per batch: draw (placement fallback
#   roles, C4) -> solve twice -> seal -> pack -> price check -> decision check (C5) -> QA (C6, C7)]
#
#   STATE=<payload dir> bash run_sealed.sh <challenge> batches       N=<last index> [START=1] [ROLE=...]
#   STATE=<payload dir> bash run_sealed.sh <challenge> u_coverage    (C8: 8 public exam-law cases vs U)
#   DRY=1 verifies files, code, env, image, custody and config and stops before any solve.
#
# The payload's own entry (run.sh) only fetches the pinned bundles, checks out HEAD_SHA, verifies its tree
# and SHA256SUMS, and calls this file from that checkout, so the guard below cannot be skipped.
# Public output only, under ~/carbon-solver-out/<out prefix>-$RUN_TAG/; custody under ~/.carbon-sealed/<dir>/.
# C11: nothing here deletes or rewrites a custody record; a void batch stays, a fresh ROLE continues.
set -euo pipefail

CHALLENGE=${1:?challenge (a file in scripts/dev/sealed_exam/configs, without .env)}
MODE=${2:-batches}
STATE=${STATE:?STATE=the payload directory (probe plan, pack and QA scripts, SHA256SUMS)}
HERE=$(dirname "$(realpath "$0")")
repo=$(cd "$HERE/../../.." && pwd)
# shellcheck source=/dev/null
source "$HERE/configs/$CHALLENGE.env"
: "${EXPECT_HEAD:?the entry passes EXPECT_HEAD}" "${EXPECT_TREE:?the entry passes EXPECT_TREE}"
test "$(git -C "$repo" rev-parse HEAD)" = "$EXPECT_HEAD"
test "$(git -C "$repo" rev-parse 'HEAD^{tree}')" = "$EXPECT_TREE"
( cd "$STATE" && sha256sum -c --quiet SHA256SUMS )

RUN_TAG=${RUN_TAG:-1}
START=${START:-1}
ROLE=${ROLE:-$DEFAULT_ROLE}
base=$HOME/carbon-sealed
venv=$base/$VENV
priv=$HOME/.carbon-sealed/$CUSTODY_DIR
out=$HOME/carbon-solver-out/$OUT_PREFIX-$RUN_TAG
case "$MODE" in u_coverage) out=$HOME/carbon-solver-out/$OUT_PREFIX-ucov-$RUN_TAG ;; esac
if [ "${DRY:-0}" = 1 ]; then out=$out.dry; fi
if [ -e "$out" ] && [ -n "$(ls -A "$out" 2>/dev/null)" ]; then
  echo "refused: $out is not empty (never overwrite an earlier run)" >&2; exit 2
fi
command -v docker git python3 sha256sum nproc awk flock >/dev/null
mkdir -p "$out" "$base" "$HOME/.carbon-sealed"

# --- guard (C10): an unslotted host keeps one sealed run at a time and the load guard; a slotted host
# (C10 amended: ~/.carbon-sealed/slots.conf) takes one flock per slot, requires the slot's cores idle and
# its memory cap available, and gives every container of the job the slot's cpuset and memory ----------
SLOTS_FILE=${SLOTS_FILE:-$HOME/.carbon-sealed/slots.conf}
SLOT=${SLOT:-}
SLOT_CPUSET=""; SLOT_MEM_MIB=""; SLOT_CORES=""
if [ -f "$SLOTS_FILE" ]; then
  [ -n "$SLOT" ] || { echo "STOP: this host is slotted; set SLOT=<name> (see $SLOTS_FILE)" >&2; exit 2; }
  slot_line=$(python3 "$HERE/slot_support.py" resolve "$SLOTS_FILE" "$SLOT") || exit 2
  read -r SLOT_CPUSET SLOT_MEM_MIB SLOT_CORES <<< "$slot_line"
elif [ -n "$SLOT" ]; then
  echo "STOP: SLOT=$SLOT given but this host has no slots file ($SLOTS_FILE)" >&2; exit 2
fi
if [ -n "$SLOT" ]; then
  exec 9> "$HOME/.carbon-sealed/.slot-$SLOT.lock"
else
  exec 9> "$HOME/.carbon-sealed/.sealed-run.lock"
fi
if [ "${DRY:-0}" != 1 ]; then
  flock -n 9 || { echo "STOP: another sealed run holds the ${SLOT:+slot $SLOT }host lock; run alone" >&2; exit 1; }
  if [ -n "$SLOT" ]; then
    python3 "$HERE/slot_support.py" guard "$SLOT_CPUSET" "$SLOT_MEM_MIB" > /dev/null \
      || { echo "STOP: slot $SLOT is not free (see above)" >&2; exit 1; }
    echo "{\"slot\": \"$SLOT\", \"cpuset\": \"$SLOT_CPUSET\", \"cap_mib\": $SLOT_MEM_MIB, \"cores\": $SLOT_CORES}" > "$out/load.json"
    # every container of this job gets the slot's cpuset and memory (no per-script cpusets)
    REAL_DOCKER=$(command -v docker)
    mkdir -p "$out/.shim"
    printf '#!/bin/sh\nexec python3 "%s/slot_support.py" shim "%s" "$@"\n' "$HERE" "$REAL_DOCKER" > "$out/.shim/docker"
    chmod 755 "$out/.shim/docker"
    export SLOT_CPUSET SLOT_MEM_MIB
    export SLOT_MARKER_DIR="$out"
    # a Challenge states the most memory one container asks for; a smaller slot is refused before any solve
    if [ -n "${MEM_REQUIRED_MIB:-}" ] && [ "$SLOT_MEM_MIB" -lt "$MEM_REQUIRED_MIB" ]; then
      echo "STOP: slot_memory_insufficient: slot $SLOT caps $SLOT_MEM_MIB MiB, $CHALLENGE needs $MEM_REQUIRED_MIB MiB; declare the slot at >= $MEM_REQUIRED_MIB" >&2; exit 1
    fi
    PATH="$out/.shim:$PATH"
  else
    load1=$(awk '{printf "%d", $1}' /proc/loadavg)
    if [ "$load1" -gt $(( $(nproc) / 4 )) ] && [ "${ALLOW_BUSY:-0}" != 1 ]; then
      echo "STOP: host load $load1 is above nproc/4 ($(( $(nproc) / 4 ))); run alone (ALLOW_BUSY=1 overrides)" >&2; exit 1
    fi
    echo "{\"load1\": $load1, \"cpus\": $(nproc)}" > "$out/load.json"
  fi
fi

# --- env ------------------------------------------------------------------------------------------------
if [ ! -x "$venv/bin/python" ]; then "$VENV_PYTHON" -m venv "$venv"; fi
"$venv/bin/pip" install -q "numpy==2.4.6"
PY() { PYTHONPATH="$repo" "$venv/bin/python" "$@"; }
PY -c "import sys, numpy; assert sys.version_info >= (3, 10); print('python', sys.version.split()[0], 'numpy', numpy.__version__)"

# --- custody and config (owner-only) --------------------------------------------------------------------
umask 077
mkdir -p "$priv/store" "$priv/producer" "$priv/packs" "$priv/qa" "$priv/logs"
chmod 700 "$HOME/.carbon-sealed" "$priv" "$priv/store" "$priv/producer" "$priv/packs" "$priv/qa" "$priv/logs"
PY - "$priv" "$DEPLOYMENT_SCHEMA" <<'PYEOF'
import json, sys
priv, schema = sys.argv[1:3]
json.dump({"schema": schema, "store": priv + "/store", "custody": priv + "/custody"},
          open(priv + "/deployment.json", "w"))
PYEOF
record_sha=$(sha256sum "$repo/.agent/decisions/$RECORD_FILE" | cut -d' ' -f1)
test -f "$repo/.agent/decisions/$RECORD_FILE"
PY - "$priv" "$CID" "$RECORD" "$RECORD_FILE" "$record_sha" "$(id -un)" <<'PYEOF'
import json, sys
priv, cid, record, name, sha, account = sys.argv[1:7]
json.dump({"schema": "carbon.challenge-validator.producer-config.v1",
           "service_account": account, "producer_dir": priv + "/producer",
           "sources": {cid: {"deployment": priv + "/deployment.json",
                             "approval": {"record": record, "file": name, "sha256": sha}}}},
          open(priv + "/config.json", "w"), indent=1)
PYEOF
chmod 600 "$priv/deployment.json" "$priv/config.json"
if [ ! -e "$priv/custody.initialised" ]; then
  ( cd "$repo" && PY -m "$SOURCE_MODULE" init --deployment "$priv/deployment.json" $SOURCE_INIT_ARGS ) > "$out/init.json"
  touch "$priv/custody.initialised"
fi
( cd "$repo" && PY -m carbon.challenge_validator.producer status --config "$priv/config.json" ) > "$out/status-before.json"

# --- image ----------------------------------------------------------------------------------------------
inspect() { docker image inspect "$IMAGE" --format '{"id": "{{.Id}}"}'; }
before=$(inspect) || { echo "STOP: the pinned image $IMAGE is not on this host" >&2; exit 1; }

producer() { ( cd "$repo" && PY -m carbon.challenge_validator.producer "$@" --config "$priv/config.json" ); }
field() { PY -c "import json,sys; print(json.loads(sys.argv[1])[sys.argv[2]])" "$1" "$2"; }

if [ "$MODE" = u_coverage ]; then
  # C8: 8 public cases from the exam's own law (recorded public seed) through the Challenge's rung solves.
  if [ "${DRY:-0}" = 1 ]; then echo "DRY=1: verified files, code, env, custody, config and image; stopped before solving"; exit 0; fi
  ( cd "$repo" && PY "$HERE/u_coverage.py" plan "$CHALLENGE_KEY" "$out/plan.json" ) > "$out/plan.log"
  ( cd "$repo" && PY "$HERE/u_coverage.py" disjoint "$CHALLENGE_KEY" "$priv/config.json" "$out/plan.json" ) > "$out/disjoint.json" \
    || { echo "STOP: a coverage geometry equals a sealed one (see disjoint.json)" >&2; exit 1; }
  ( cd "$repo" && export "$RUNNER_IMAGE_ENV=$RUNNER_IMAGE_VALUE" && PY "$repo/$RUNNER" "$out/plan.json" --out "$out/run" \
      --parallel "${PARALLEL:-8}" --timeout-s 7200 --keep none ) > "$out/run.log" 2>&1 \
    || { echo "STOP: the coverage run failed (see run.log)" >&2; exit 1; }
  ( cd "$repo" && PY "$HERE/u_coverage.py" compute "$CHALLENGE_KEY" "$out/run/records.jsonl" "$out/u-coverage.json" )
  exit $?
fi

[ "$MODE" = batches ] || { echo "unknown mode $MODE" >&2; exit 2; }
N=${N:?N=last batch index, e.g. 2}
if [ "${DRY:-0}" = 1 ]; then echo "DRY=1: verified files, code, env, custody, config and image; stopped before solving"; exit 0; fi

# --- probe (a public case; nothing hidden) -------------------------------------------------------------
sample() {
  while :; do
    mem=$(docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' 2>/dev/null \
      | awk -v pre="^$PROBE_NAME_PREFIX" '$1 ~ pre { v=$2; u=v; gsub(/[0-9.]/,"",u); gsub(/[^0-9.]/,"",v);
             f = (u=="GiB") ? 1024 : (u=="KiB") ? 1/1024 : 1; s += v*f } END { printf "%.1f", s+0 }')
    printf '%s %s\n' "$(date +%s)" "$mem" >> "$1"
    sleep 10
  done
}
cp "$STATE/probe-plan.json" "$out/"
# the sampler must not inherit the host-lock descriptor (9), or a dead run would keep the lock
sampler=""
trap 'if [ -n "$sampler" ]; then kill "$sampler" 2>/dev/null || true; fi' EXIT
sample "$out/probe.resources.log" 9>&- & sampler=$!
probe_rc=0
( cd "$repo" && export "$RUNNER_IMAGE_ENV=$RUNNER_IMAGE_VALUE" && PY "$repo/$RUNNER" "$out/probe-plan.json" --out "$out/probe" \
    --parallel "$PROBE_PARALLEL" --timeout-s 7200 --keep none ) > "$out/probe.log" 2>&1 || probe_rc=$?
kill "$sampler" 2>/dev/null || true
PY - "$out" "$probe_rc" "$(awk 'BEGIN{m=0} {if($2>m)m=$2} END{print m}' "$out/probe.resources.log")" \
    "$(awk '/^MemAvailable:/{printf "%d", $2/1024}' /proc/meminfo)" "${SLOT_CORES:-$(nproc)}" \
    "$PROBE_KEY" "$PROBE_EXPECT" "$PROBE_BOUND" "$PROBE_MEM_DIV" <<'PYEOF'
import json, math, sys
import os
out, rc = sys.argv[1], int(sys.argv[2])
peak, avail, cpus = map(float, sys.argv[3:6])
cap = float(os.environ.get("SLOT_MEM_MIB") or 0)
if cap:
    avail = min(avail, cap)  # a slot job may use its cap, not the whole host
key, expect, bound, div = sys.argv[6], float(sys.argv[7]), float(sys.argv[8]), float(sys.argv[9])
record = json.loads(open(out + "/probe/records.jsonl").readline())
status = record["status"]
value = (record.get("outputs") or {}).get(key)
delta = None if value is None else abs(value - expect)
per_case = peak / div if peak > 0 else 0
limits = {"memory": math.floor(0.7 * avail / per_case) if per_case > 0 else None, "cpus": math.floor(cpus / 2)}
parallel = max(1, min(v for v in limits.values() if v is not None))
stop = status != "OK" or delta is None or delta > bound or bool(cap and peak > cap)  # peak above the slot cap: it does not fit
json.dump({"schema": "carbon.sealed-probe.v1", "status": status, "runner_rc": rc, "reasons": record.get("reasons", []),
           "key": key, "value": value, "expect": expect, "abs_delta": delta, "bound": bound,
           "wall_s": record.get("wall_s"), "peak_memory_mib": peak, "available_memory_mib": avail,
           "cpus": cpus, "slot_cap_mib": cap or None, "limits": limits, "parallel": parallel, "stop": stop},
          open(out + "/probe.json", "w"), indent=1)
print(json.dumps({"probe": status, "abs_delta": delta, "parallel": parallel}))
sys.exit(1 if stop else 0)
PYEOF
parallel=$(PY -c "import json,sys; print(json.load(open(sys.argv[1]))['parallel'])" "$out/probe.json")

# --- batches --------------------------------------------------------------------------------------------
unusable=0
i=$START
while [ "$i" -le "$N" ]; do
  for role in "$ROLE-$i" "$ROLE-$i-r1"; do
    t0=$(date +%s)
    # C4: placement precedes every solve; a seed that places nothing moves to the next role, recorded.
    drawn=""
    for p in "" -p1 -p2 -p3 -p4 -p5; do
      if drawn=$(producer draw --challenge "$CID" --role "$role$p" --kind screening 2> "$out/draw-err.log"); then
        echo "{\"role_index\": $i, \"attempt\": \"$role$p\", \"placed\": true}" >> "$out/seeds.jsonl"
        break
      fi
      echo "{\"role_index\": $i, \"attempt\": \"$role$p\", \"placed\": false}" >> "$out/seeds.jsonl"
      drawn=""
    done
    [ -n "$drawn" ] || { echo "STOP: no seed placed a batch in 6 tries (see seeds.jsonl)" >&2; exit 1; }
    fp=$(field "$drawn" fingerprint)
    producer solve --challenge "$CID" --fingerprint "$fp" --workers "$parallel" --timeout-s 7200 >> "$priv/logs/solve-${fp#sha256:}.log" 2>&1
    producer solve --challenge "$CID" --fingerprint "$fp" --workers "$parallel" --timeout-s 7200 >> "$priv/logs/solve-${fp#sha256:}.log" 2>&1
    if [ -e "$out/.slot_memory_insufficient" ] || [ -e "$out/.slot_oom_137" ]; then
      echo "STOP: slot_memory_insufficient / OOM rc 137 in slot $SLOT (infrastructure, typed); to the Validator" >&2; exit 1
    fi
    if [ -n "$SLOT" ] && grep -q '"status": "REFERENCE_TIMEOUT"' "$priv/producer/work/$CID/${fp#sha256:}/records.jsonl" 2>/dev/null; then
      echo "STOP: a REFERENCE_TIMEOUT while slotted (slot $SLOT): the isolation did not hold; to the Validator" >&2; exit 1
    fi
    sealed=$(producer seal --challenge "$CID" --fingerprint "$fp" || true)
    echo "$sealed" >> "$out/seal.jsonl"
    pack_rc=0
    ( cd "$repo" && PY "$STATE/$PACK_SCRIPT" "$priv/config.json" "$fp" "$priv/packs" ) >> "$out/summary.jsonl" || pack_rc=$?
    qa_rc=-1
    dec_rc=0
    if [ "$pack_rc" -eq 0 ] && [ -n "${DECISION_KEY:-}" ]; then
      # C5: the post-solve decision check on the reference labels with U (sealed_exam_common);
      # a batch that cannot measure design value is unusable like a straddle shortfall (rc 10)
      ( cd "$repo" && PY "$HERE/decision_stage.py" "$DECISION_KEY" "$priv/config.json" "$fp" ) \
        >> "$out/decision.jsonl" || dec_rc=$?
      qa_rc=$dec_rc
    fi
    if [ "$pack_rc" -eq 0 ] && [ "$dec_rc" -eq 0 ]; then
      qa_rc=0
      ( cd "$repo" && PY "$STATE/$QA_SCRIPT" judge "$priv/config.json" "$fp" "$priv/qa/${fp#sha256:}" ) \
        >> "$out/qa-public.jsonl" || qa_rc=$?
    fi
    wall=$(( $(date +%s) - t0 ))
    echo "{\"role_index\": $i, \"attempt\": \"$role\", \"wall_s\": $wall, \"pack_rc\": $pack_rc, \"qa_rc\": $qa_rc, \"slot\": \"$SLOT\", \"cpuset\": \"$SLOT_CPUSET\", \"cap_mib\": \"$SLOT_MEM_MIB\"}" >> "$out/walls.jsonl"
    if [ "$wall" -gt "$BATCH_WALL_LIMIT_S" ]; then echo "STOP: a batch ran past $BATCH_WALL_LIMIT_S s; re-price before continuing" >&2; exit 1; fi
    if [ "$qa_rc" -ne 0 ] && [ "$qa_rc" -ne 10 ] && [ "$qa_rc" -ne -1 ]; then
      echo "STOP: exam QA rc $qa_rc (12 stop, else an error; see qa-public.jsonl); to the Validator" >&2; exit 1
    fi
    if [ "$qa_rc" -eq 0 ]; then unusable=0; break; fi
    unusable=$((unusable + 1))
    if [ "$unusable" -ge 2 ]; then echo "STOP: two unusable batches in a row (see summary.jsonl, qa-public.jsonl)" >&2; exit 1; fi
  done
  i=$((i + 1))
done
after=$(inspect)
PY - "$out" "$before" "$after" <<'PYEOF'
import json, sys
out, before, after = sys.argv[1], json.loads(sys.argv[2]), json.loads(sys.argv[3])
rows = [json.loads(l) for l in open(out + "/summary.jsonl") if l.strip()]
qa = [json.loads(l) for l in open(out + "/qa-public.jsonl") if l.strip()]
kept = sum(r.get("action") == "keep" for r in qa)
json.dump({"schema": "carbon.sealed-run.v1", "image_unchanged": before == after,
           "packed": sum(r.get("packed") is True for r in rows), "qa_kept": kept,
           "batches": rows, "qa": qa}, open(out + "/run-record.json", "w"), indent=1)
print(json.dumps({"image_unchanged": before == after, "qa_kept": kept}))
PYEOF
