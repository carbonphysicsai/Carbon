#!/usr/bin/env bash
# Stage A: one chassis, two devices, both conditions - driven from inside the pod.
#
# This is the whole of what a stage A pod executes. It lives in the repository
# rather than on the mounted volume deliberately: `stage_manifest` digests the
# checkout, so a driver kept here is covered by the revision pin, while one
# written onto the volume by whatever staged it is not. In a study whose subject
# is provenance, the script that runs the study should not be the one file
# nothing pins.
#
#   STUDY_DEVICES     device indices to compare          [default "0 1"]
#   STUDY_SESSIONS    fresh processes per cell           [default 3]
#   STUDY_RUNS        invocations inside each session    [default 3]
#   CARBON_REPO       the staged checkout                [default /runpod-volume/carbon]
#   CARBON_REVISION   the revision it must be            [required]
#   STUDY_IMAGE_REF   the image digest, for the record   [required]
#
# A session is one invocation of `run_on_pod.sh`, and the sessions below are
# separate processes for that reason: unpinned, the autotuner chooses kernels
# once per process and reuses them, so repeating inside one process reproduces
# bit-identically where fresh processes do not. STUDY_RUNS repeats *within* a
# session and measures something else.
set -euo pipefail

CARBON_REPO="${CARBON_REPO:-/runpod-volume/carbon}"
: "${CARBON_REVISION:?set CARBON_REVISION to the revision the checkout must be}"
: "${STUDY_IMAGE_REF:?set STUDY_IMAGE_REF to the image digest this pod was built from}"
DEVICES="${STUDY_DEVICES:-0 1}"
SESSIONS="${STUDY_SESSIONS:-3}"
export STUDY_RUNS="${STUDY_RUNS:-3}"
export STUDY_MATERIALS="${STUDY_MATERIALS:-/tmp/carbon-study/materials}"
export STUDY_RESULTS="${STUDY_RESULTS:-/tmp/carbon-study/results}"
export CARBON_REPO

HERE="${CARBON_REPO}/scripts/dev/gpu_determinism_study"
PYTHON="${STUDY_PYTHON:-/opt/carbon-worker/bin/python}"
[ -x "${PYTHON}" ] || PYTHON="$(command -v python3)"

echo "STAGE_A_BEGIN"
# Recorded in the runner's own words, because a study that measured a different
# path than it claims is not an exact replay of anything.
echo "execution class: direct execution inside the pinned image; not validator_launch; containment from the provider's runtime"
echo "image: ${STUDY_IMAGE_REF}"
echo "carbon revision: ${CARBON_REVISION}"
echo "devices: ${DEVICES}   sessions per cell: ${SESSIONS}   runs per session: ${STUDY_RUNS}"

# Pre-flight, all of it refusing rather than warning. Each check below is a
# thing the acceptance requires established *before* any device time is spent,
# and a pod-minute is cheaper than a result nobody can attribute.
identity="$("${PYTHON}" "${HERE}/device_identity.py")" || {
  echo "REFUSED: no device identity available; a per-device study cannot name its devices" >&2
  exit 2; }
echo "device identity:"
echo "${identity}"
# Read this, not the per-run numerics record, for the driver build. The numerics
# schema carries its own `driver_version` which is null on this image because it
# has no nvidia-smi to read - absent because it was never readable there, not
# because the driver is unknown. The authoritative read is the one above.
echo "driver build recorded from NVML above; the per-run numerics driver_version field is unreadable on this image and is not evidence of an unknown driver"

"${PYTHON}" - "${identity}" "${DEVICES}" <<'PY' || exit 2
import json, sys
devices = json.loads(sys.argv[1])
wanted = [int(i) for i in sys.argv[2].split()]
by_index = {d["index"]: d for d in devices}
problems = []
for index in wanted:
    device = by_index.get(index)
    if device is None:
        problems.append(f"no device at index {index}")
        continue
    if not device.get("uuid"):
        problems.append(f"device {index} has no readable UUID; absent is not a name")
# Same chassis is not evidence of the same driver, so it is read rather than
# assumed. A mismatch means a difference between the devices that is not the
# device, which is precisely what stage A must not blame on the hardware.
builds = {by_index[i].get("driver_version") for i in wanted if i in by_index}
if len(builds) > 1:
    problems.append(f"driver builds differ across the compared devices: {sorted(builds)}")
if builds == {None}:
    problems.append("driver build is unreadable; it is required to be recorded and matched")
for problem in problems:
    print(f"REFUSED: {problem}", file=sys.stderr)
raise SystemExit(1 if problems else 0)
PY

# Materials once, from the pinned revision, before the matrix. Deriving them
# here means the execution class already describes them.
if [ ! -f "${STUDY_MATERIALS}/materials.json" ]; then
  mkdir -p "${STUDY_MATERIALS}"
  STUDY_OUT="${STUDY_MATERIALS}" "${PYTHON}" "${HERE}/prepare.py"
fi

failed=0
for device in ${DEVICES}; do
  for condition in pinned unpinned; do
    for session in $(seq 1 "${SESSIONS}"); do
      label="${condition}-d${device}-s${session}"
      echo "=== ${label} ==="
      # A refusal is a result. It is recorded and the matrix continues, so one
      # refused cell cannot be mistaken for a cell that was never attempted.
      if STUDY_DEVICE_INDEX="${device}" \
         STUDY_PINNED="$([ "${condition}" = pinned ] && echo 1 || echo 0)" \
         bash "${HERE}/run_on_pod.sh" "${label}"; then
        echo "=== ${label} completed ==="
      else
        echo "=== ${label} REFUSED OR FAILED (exit $?) ==="
        failed=$((failed + 1))
      fi
    done
  done
done

echo "STAGE_A_END failed_or_refused_cells=${failed}"
# Deliberately not a verdict. Whether the devices agree is read from the
# digests, by a human, against the acceptance - not decided here.
