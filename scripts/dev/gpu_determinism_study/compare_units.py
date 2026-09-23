"""Compare pinned sessions across units, refusing a comparison the driver confounds.

The acceptance makes one pre-run check hard: **driver builds must match across
the compared units**, because otherwise a driver difference is indistinguishable
from a device difference and the study loses its question. Stage A enforced it -
`stage_a_matrix.sh` reads every device's build from NVML and refuses when they
differ - but only across devices in one chassis. Nothing compared drivers across
pods, which is where stage B needed it, and stage B's two hosts did differ
(`580.159.03` against `580.159.04`). That was found afterwards by reading two
records side by side. This closes it.

Enforced by construction rather than by a check a caller could skip:

- A `UnitSession` can only be built from a session record by `UnitSession.read`,
  and that refuses a record that does not carry the driver build NVML reported.
  An unreadable build is not a matching one, and an operator-stated identity
  (`STUDY_DEVICE_UUID`) carries no build at all, so neither can be compared.
- `compare` takes only `UnitSession`s. When builds differ it returns
  `REFUSED_DRIVER_MISMATCH` - not `DISAGREE`, because nothing was measured that
  could disagree - unless it is handed a `DriverDeviation` naming **exactly** the
  builds observed. A deviation written for one pair of builds does not excuse a
  different pair, and a deviation handed to a matched comparison is refused
  rather than silently carried, so the record never claims a deviation that did
  not occur.
- An accepted deviation is written into the result. The comparison that
  proceeded across a driver difference says so in the same record as its digest.

Device agreement only. Two units agreeing on a digest is not two validators
agreeing on a score, and nothing here qualifies anything.

    python compare_units.py --preflight <identity.json>...
    python compare_units.py <session.json>... [--deviation <deviation.json>]

`--preflight` refuses a driver difference even when a deviation exists. A
deviation records a decision about a run that has happened; it is not a way to
start one on differing drivers without deciding to.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA = "carbon.study.unit-comparison.v1"
DEVIATION_SCHEMA = "carbon.study.driver-deviation.v1"

# What `run_on_pod.sh` exports for the pinned condition and `repeat_gpu.py`
# refuses to run without. Read back from the record's numerics, not from a label.
PINNED_FLAGS = (
    "--xla_gpu_deterministic_ops=true",
    "--xla_gpu_exclude_nondeterministic_ops=true",
    "--xla_gpu_autotune_level=0",
)


class RecordError(Exception):
    """A session record that cannot enter a comparison, with the reason named."""


# Held only by the readers below. Both types refuse construction without it, so
# the only way to obtain one is through the reader that enforces its contents.
_READ = object()


def _require_read(token: object, kind: str) -> None:
    if token is not _READ:
        raise TypeError(
            f"{kind} is built by {kind}.read, which enforces what it carries"
        )


@dataclass(frozen=True)
class UnitSession:
    """One pinned session on one named unit, with the driver build it ran under.

    Only `read` can build one, so a session whose driver build was never read
    cannot reach `compare` at all - the error lands where the record is loaded,
    not somewhere downstream that forgot to check.
    """

    label: str
    device_uuid: str
    driver_version: str
    weights_sha256: str
    pinned: bool
    _token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        _require_read(self._token, "UnitSession")

    @classmethod
    def read(cls, record: dict, *, source: str = "record") -> UnitSession:
        label = record.get("label") or source
        if record.get("status", "").startswith("REFUSED"):
            raise RecordError(
                f"{label}: the session refused to run ({record['status']})"
            )
        identity = record.get("device_identity")
        if not isinstance(identity, dict):
            raise RecordError(
                f"{label}: no device_identity. The driver build is read from NVML "
                "at run time and a record without it cannot show which driver "
                "produced its digest"
            )
        uuid = identity.get("uuid")
        if not isinstance(uuid, str) or not uuid:
            raise RecordError(
                f"{label}: device UUID is unreadable; absent is not a name"
            )
        driver = identity.get("driver_version")
        if not isinstance(driver, str) or not driver:
            raise RecordError(
                f"{label}: driver build was not recorded. An unknown build cannot "
                "be shown to match, so the comparison is refused rather than assumed"
            )
        if not record.get("bit_identical"):
            raise RecordError(
                f"{label}: runs within the session did not all complete with one "
                "digest, so the session has no single digest to compare"
            )
        digests = {run.get("weights_sha256") for run in record.get("runs", []) if run}
        if len(digests) != 1 or None in digests:
            raise RecordError(f"{label}: the session has no single weights digest")
        flags = (record.get("numerics") or {}).get("xla_flags") or ""
        pinned = all(flag in flags for flag in PINNED_FLAGS)
        return cls(label, uuid, driver, digests.pop(), pinned, _READ)


@dataclass(frozen=True)
class DriverDeviation:
    """A recorded decision to compare across differing driver builds.

    Names the exact builds it covers and why. It is evidence about the run, so it
    travels into the result rather than being consumed by the comparison.
    """

    builds: frozenset[str]
    recorded_in: str
    reason: str
    _token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        _require_read(self._token, "DriverDeviation")

    @classmethod
    def read(cls, document: dict) -> DriverDeviation:
        if document.get("schema") != DEVIATION_SCHEMA:
            raise RecordError(
                f"deviation schema is {document.get('schema')!r}, expected "
                f"{DEVIATION_SCHEMA!r}"
            )
        builds = document.get("builds")
        if not isinstance(builds, list) or len(set(builds)) < 2:
            raise RecordError(
                "a driver deviation must name at least two distinct builds; one "
                "build is not a deviation"
            )
        for name in ("recorded_in", "reason"):
            if not isinstance(document.get(name), str) or not document[name].strip():
                raise RecordError(f"a driver deviation must state {name}")
        return cls(
            frozenset(builds), document["recorded_in"], document["reason"], _READ
        )


def preflight(identities: list[dict]) -> list[str]:
    """Problems that must stop a run before it starts. Empty means proceed.

    Takes `device_identity.py` output from every unit about to be compared - one
    list per pod, concatenated - so the check the acceptance calls hard runs
    *before* any device time is spent rather than being discovered in the
    records afterwards.
    """
    problems = []
    for identity in identities:
        if not identity.get("uuid"):
            problems.append(f"device {identity.get('index')} has no readable UUID")
        if not identity.get("driver_version"):
            problems.append(
                f"device {identity.get('uuid') or identity.get('index')} has no "
                "readable driver build; it is required to be recorded and matched"
            )
    if len({i.get("uuid") for i in identities if i.get("uuid")}) < 2:
        problems.append("fewer than two named units; there is nothing to compare")
    builds = sorted(
        {i["driver_version"] for i in identities if i.get("driver_version")}
    )
    if len(builds) > 1:
        problems.append(
            f"driver builds differ across the compared units: {builds}. "
            "Re-provision to match, or record a driver deviation before running"
        )
    return problems


def compare(
    sessions: list[UnitSession], deviation: DriverDeviation | None = None
) -> dict:
    """The comparison, or the reason it could not be made."""
    units = sorted({s.device_uuid for s in sessions})
    builds = sorted({s.driver_version for s in sessions})
    result: dict = {
        "schema": SCHEMA,
        "units": units,
        "driver_builds": builds,
        "sessions": [
            {
                "label": s.label,
                "device_uuid": s.device_uuid,
                "driver_version": s.driver_version,
                "weights_sha256": s.weights_sha256,
                "pinned": s.pinned,
            }
            for s in sorted(sessions, key=lambda s: (s.device_uuid, s.label))
        ],
        "deviation": None,
    }
    if len(units) < 2:
        result["outcome"] = "REFUSED_ONE_UNIT"
        result["reason"] = "a comparison across units needs at least two named units"
        return result

    conditions = {s.pinned for s in sessions}
    if len(conditions) > 1:
        result["outcome"] = "REFUSED_MIXED_CONDITION"
        result["reason"] = (
            "pinned and unpinned sessions were given together; unpinned sessions "
            "diverge by design, so a mixed comparison attributes that to the units"
        )
        return result
    result["pinned"] = conditions.pop()

    if len(builds) > 1:
        if deviation is None:
            result["outcome"] = "REFUSED_DRIVER_MISMATCH"
            result["reason"] = (
                f"driver builds differ across the compared units: {builds}. A "
                "driver difference is indistinguishable from a device difference, "
                "so nothing was compared. Re-provision to match, or record a "
                "deviation naming exactly these builds"
            )
            return result
        if deviation.builds != frozenset(builds):
            result["outcome"] = "REFUSED_DRIVER_MISMATCH"
            result["reason"] = (
                f"the deviation covers {sorted(deviation.builds)}, but the "
                f"compared units ran {builds}. A deviation excuses the builds it "
                "names and no others"
            )
            return result
    elif deviation is not None:
        result["outcome"] = "REFUSED_UNUSED_DEVIATION"
        result["reason"] = (
            f"every unit ran {builds[0]}, so there is no driver difference for the "
            "deviation to cover; carrying it would record a deviation that did "
            "not occur"
        )
        return result

    if deviation is not None:
        result["deviation"] = {
            "builds": sorted(deviation.builds),
            "recorded_in": deviation.recorded_in,
            "reason": deviation.reason,
        }
    digests = sorted({s.weights_sha256 for s in sessions})
    result["weight_digests"] = digests
    result["outcome"] = "AGREE" if len(digests) == 1 else "DISAGREE"
    return result


def main(argv: list[str]) -> int:
    args = list(argv[1:])
    if args[:1] == ["--preflight"]:
        identities: list[dict] = []
        for name in args[1:]:
            try:
                value = json.loads(Path(name).read_text())
            except (OSError, ValueError) as error:
                print(f"{name}: not readable identity output: {error}", file=sys.stderr)
                return 2
            identities.extend(value if isinstance(value, list) else [value])
        problems = preflight(identities)
        for problem in problems:
            print(f"refusing to run: {problem}", file=sys.stderr)
        if not problems:
            print(f"driver build {identities[0]['driver_version']} on every unit")
        return 2 if problems else 0
    deviation = None
    if "--deviation" in args:
        at = args.index("--deviation")
        try:
            deviation = DriverDeviation.read(json.loads(Path(args[at + 1]).read_text()))
        except (IndexError, OSError, ValueError, RecordError) as error:
            print(f"deviation: {error}", file=sys.stderr)
            return 2
        del args[at : at + 2]
    if len(args) < 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    sessions = []
    for name in args:
        try:
            record = json.loads(Path(name).read_text())
            sessions.append(UnitSession.read(record, source=name))
        except (OSError, ValueError) as error:
            print(f"{name}: not a readable session record: {error}", file=sys.stderr)
            return 2
        except RecordError as error:
            print(f"refusing: {error}", file=sys.stderr)
            return 2
    result = compare(sessions, deviation)
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0 if result["outcome"] in ("AGREE", "DISAGREE") else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
