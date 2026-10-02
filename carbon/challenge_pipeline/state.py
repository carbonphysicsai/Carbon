"""The pipeline's versioned state: the protocol, the rubric and one record per
family that has entered the pipeline or carries a note.

The roadmap page keeps the same record in its shared store, with the same
field names, so a record can move between the two unchanged. The repository
copy is the versioned one. Each file is validated against the roadmap's rules
(`Design_Specs/Challenge_Roadmap.md`):

- **Stages need their gates.** A family is past `queued` only after the
  protocol is locked, except battery, which defines it. Each later stage needs
  the sign-off of the owner the roadmap names for the gate before it.
- **Results come from the frozen run.** Track A and B results need the frozen
  evidence record they came from.
- **Solve time is measured on the reference hardware.** A measured p50 needs
  the protocol's reference hardware, which the technical owner approves, and
  the timing evidence.
- **The rubric is unset until it is approved.** Thresholds need the process
  owner's approval; the open critical and high limits start at the roadmap's
  zero.
- **Construction climbs the ladder** (`ladder.py`, rev 2.2). A family in
  Test/iterate or later has a construction contract at Level 0 or above, each
  level reached with its expansion record and Carbon's reconstruction, and
  frozen results come from a FROZEN level.

A sign-off is written only from the named owner's recorded act: a decision
record or a review on the pull request. These checks keep a record coherent;
they do not grant or prove a sign-off.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from carbon.challenge_pipeline import ladder
from carbon.challenge_pipeline.roadmap import load_families

HERE = Path(__file__).parent
REPOSITORY = HERE.parents[1]
PROTOCOL = HERE / "protocol.json"
RUBRIC = HERE / "rubric.json"
RECORDS = HERE / "records"

STAGES = ("queued", "protocol", "design", "test", "ready", "deployed", "parked")
STAGE_LABELS = {
    "queued": "Queued",
    "protocol": "Protocol definition",
    "design": "Design",
    "test": "Test / iterate",
    "ready": "Ready for deployment",
    "deployed": "Deployed",
    "parked": "Parked",
}
#: The family that defines the protocol (Phase 1).
PROTOCOL_FAMILY = "f05"

#: Each gate, the owner role that signs it, and the stages that need it.
GATES = {
    "scope": ("science", {"design", "test", "ready", "deployed"}),
    "design": ("science", {"test", "ready", "deployed"}),
    "track_a": ("technical", {"ready", "deployed"}),
    "track_b": ("science", {"ready", "deployed"}),
    "deploy": ("process", {"deployed"}),
}
RESULT_FIELDS = ("attC", "attH", "attM", "attL", "rho", "regret", "n", "k")
TIMING_FIELDS = ("p50s", "p95s", "cases")
RECORD_KEYS = {
    "schema",
    "family",
    "stage",
    *TIMING_FIELDS,
    "hw",
    "suite",
    *RESULT_FIELDS,
    "notes",
    "at",
    "gates",
    "evidence",
    "prior_work",
    "construction",
}
RUBRIC_THRESHOLDS = ("minRho", "maxFF", "minN", "maxReg")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class PipelineError(ValueError):
    """A pipeline file breaks one of the roadmap's rules."""


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _exists(ref, root):
    return isinstance(ref, str) and ref and (Path(root) / ref).exists()


def _sign_off(value, role, owners, where):
    if not isinstance(value, dict) or set(value) != {"by", "on", "ref"}:
        raise PipelineError(f"{where}: a sign-off is {{by, on, ref}}")
    if value["by"] != owners[role]:
        raise PipelineError(f"{where}: signed by {value['by']!r}, not the {role} owner")
    if not (isinstance(value["on"], str) and DATE.match(value["on"])):
        raise PipelineError(f"{where}: date must be YYYY-MM-DD")
    if not (isinstance(value["ref"], str) and value["ref"].strip()):
        raise PipelineError(f"{where}: a sign-off names its decision or review")


def validate_protocol(protocol):
    owners = protocol["owners"]
    if set(owners) != {"process", "technical", "science"}:
        raise PipelineError("protocol: owners are process, technical and science")
    if protocol["state"] not in ("DEFINING", "LOCKED"):
        raise PipelineError("protocol: state is DEFINING or LOCKED")
    locked = protocol["state"] == "LOCKED"
    # The technical owner alone approves the reference timing hardware
    # (OWNER-CHALLENGE-ROADMAP-02); it is not a lock item.
    if protocol.get("reference_hardware"):
        _sign_off(
            protocol.get("reference_hardware_approval"),
            "technical",
            owners,
            "reference hardware",
        )
    elif protocol.get("reference_hardware_approval") is not None:
        raise PipelineError("protocol: an approval needs the hardware it approves")
    for key in ("construction_ladder", "lessons"):
        if not (isinstance(protocol.get(key), str) and protocol[key].strip()):
            raise PipelineError(f"protocol: names its {key} (rev 2.2)")
    if locked:
        _sign_off(protocol["lock"], "process", owners, "protocol lock")
        for key in ("version", "suite_version", "reference_hardware"):
            if not protocol.get(key):
                raise PipelineError(f"protocol: a locked protocol names its {key}")
    elif protocol["lock"] is not None:
        raise PipelineError("protocol: only a locked protocol carries a lock")
    steps = protocol["phase_1"]
    if [s["step"] for s in steps] != list(range(1, 9)):
        raise PipelineError("protocol: Phase 1 has steps 1 to 8")
    for s in steps:
        if s["status"] not in ("todo", "in_progress", "blocked", "done"):
            raise PipelineError(f"protocol step {s['step']}: unknown status")
        if s["status"] == "done" and not s.get("evidence"):
            raise PipelineError(f"protocol step {s['step']}: done needs its evidence")
    if locked != (steps[-1]["status"] == "done"):
        raise PipelineError("protocol: step 8 is the lock")
    return protocol


def validate_rubric(rubric, protocol):
    set_any = any(rubric.get(key) is not None for key in RUBRIC_THRESHOLDS)
    if set_any or rubric.get("version"):
        _sign_off(rubric.get("approved"), "process", protocol["owners"], "rubric")
        if not all(rubric.get(key) is not None for key in ("minRho", "maxFF", "minN")):
            raise PipelineError(
                "rubric: an approved rubric sets minRho, maxFF and minN"
            )
    elif rubric.get("approved") is not None:
        raise PipelineError("rubric: an approval needs a version and thresholds")
    for key in ("maxC", "maxH"):
        if not (isinstance(rubric.get(key), int) and rubric[key] >= 0):
            raise PipelineError(f"rubric: {key} is a count")
    return rubric


def validate_record(record, protocol, families, *, root=REPOSITORY):
    fid = record.get("family")
    where = f"record {fid}"
    if set(record) != RECORD_KEYS:
        raise PipelineError(
            f"{where}: keys differ by {sorted(set(record) ^ RECORD_KEYS)}"
        )
    if record["schema"] != "carbon.challenge-pipeline.record.v1":
        raise PipelineError(f"{where}: unknown schema")
    if fid not in families:
        raise PipelineError(f"{where}: no such family")
    stage = record["stage"]
    if stage not in STAGES:
        raise PipelineError(f"{where}: unknown stage {stage!r}")
    locked = protocol["state"] == "LOCKED"
    if stage == "protocol" and (fid != PROTOCOL_FAMILY or locked):
        raise PipelineError(f"{where}: only battery defines the protocol, before lock")
    if fid != PROTOCOL_FAMILY and stage != "queued" and not locked:
        raise PipelineError(
            f"{where}: challenges enter the pipeline after protocol lock"
        )
    gates = record["gates"]
    if set(gates) != set(GATES):
        raise PipelineError(f"{where}: gates are {sorted(GATES)}")
    for gate, (role, needed_by) in GATES.items():
        if gates[gate] is not None:
            _sign_off(gates[gate], role, protocol["owners"], f"{where} gate {gate}")
        elif stage in needed_by:
            raise PipelineError(f"{where}: stage {stage} needs the {gate} gate")
    evidence = record["evidence"]
    if set(evidence) != {"status", "brief", "design_packet", "timing", "frozen"}:
        raise PipelineError(f"{where}: unknown evidence keys")
    for kind, ref in evidence.items():
        if ref is not None and not _exists(ref, root):
            raise PipelineError(
                f"{where}: {kind} evidence {ref!r} is not in the repository"
            )
    if record["p50s"] is not None:
        if not protocol.get("reference_hardware"):
            raise PipelineError(f"{where}: no reference hardware is set to measure on")
        if record["hw"] != protocol["reference_hardware"]:
            raise PipelineError(f"{where}: measured off the reference hardware")
        if evidence["timing"] is None or not (record["p50s"] > 0):
            raise PipelineError(f"{where}: a measured p50 needs its timing evidence")
        if record["p95s"] is not None and record["p95s"] < record["p50s"]:
            raise PipelineError(f"{where}: p95 is below p50")
    elif record["p95s"] is not None:
        raise PipelineError(f"{where}: p95 needs a p50")
    if any(record[key] is not None for key in RESULT_FIELDS) or record["suite"]:
        if evidence["frozen"] is None or not record["suite"]:
            raise PipelineError(
                f"{where}: results come from a frozen run on a named suite"
            )
        if record["n"] is not None and not (
            isinstance(record["n"], int) and record["n"] >= 1
        ):
            raise PipelineError(f"{where}: n is a count of independent scenarios")
        if record["k"] is not None and not (
            isinstance(record["k"], int)
            and record["n"] is not None
            and 0 <= record["k"] <= record["n"]
        ):
            raise PipelineError(f"{where}: k is a count of at most n")
    if not (isinstance(record["at"], str) and DATE.match(record["at"])):
        raise PipelineError(f"{where}: at is the record's date")
    if (
        len(record["notes"]) > 400
        or len(record["hw"]) > 200
        or len(record["suite"]) > 60
    ):
        raise PipelineError(f"{where}: a text field is longer than the page allows")
    try:
        construction = ladder.validate(record["construction"], where, root)
    except ladder.LadderError as error:
        raise PipelineError(str(error)) from error
    if stage in ("test", "ready", "deployed") and construction["level"] is None:
        raise PipelineError(
            f"{where}: stage {stage} needs a construction contract on the ladder; "
            "Design exits with Level 0 that Carbon rebuilds"
        )
    if evidence["frozen"] is not None and (
        construction["level"] is None
        or ladder.state_of(construction, construction["level"]) != "FROZEN"
    ):
        raise PipelineError(
            f"{where}: a frozen run is taken at a FROZEN construction level"
        )
    for item in record["prior_work"]:
        if set(item) != {"what", "ref"} or not _exists(item["ref"], root):
            raise PipelineError(
                f"{where}: prior work is {{what, ref}} with a repository ref"
            )
    return record


def load_state(
    *, root=REPOSITORY, protocol_path=PROTOCOL, rubric_path=RUBRIC, records=RECORDS
):
    """The validated protocol, rubric and records, keyed by family id."""
    families = load_families()
    ids = {f["id"] for f in families["families"]}
    protocol = validate_protocol(_load(protocol_path))
    rubric = validate_rubric(_load(rubric_path), protocol)
    out = {}
    for path in sorted(Path(records).glob("*.json")):
        record = validate_record(_load(path), protocol, ids, root=root)
        if path.stem != record["family"]:
            raise PipelineError(f"{path.name}: named for {record['family']}")
        out[record["family"]] = record
    return families, protocol, rubric, out


def stage_of(records, fid):
    record = records.get(fid)
    if record is not None:
        return record["stage"]
    return "protocol" if fid == PROTOCOL_FAMILY else "queued"


def measured_times(records):
    return {fid: r["p50s"] for fid, r in records.items() if r["p50s"] is not None}
