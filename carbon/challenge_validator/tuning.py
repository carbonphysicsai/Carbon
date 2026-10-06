"""Battery's sealed tuning set, operator-side (VALIDATOR-17;
OWNER-GRAPHITE-TEST-WAVE-08 §1).

The tuning set (`graphite-tuning-v1`, registered in `confirmation_sets/`)
scores every panel member and compares candidate score weightings. It is used
repeatedly for score development. It is sealed like a confirmation set, and
nothing here ever gives an agent or miner its cases, references, predictions
or scores.

Operator steps, all on the operator host:

    python -m carbon.challenge_validator.tuning export-pool --config HIDDEN.json --out FILE
    python -m carbon.challenge_validator.confirmation seal --role graphite-tuning-v1 \\
        --config TESTNET.json --prior graphite-hidden-battery-v1-pool=FILE
    python -m carbon.challenge_validator.tuning jobs --config TESTNET.json \\
        --commitment COMMITMENT.json --work DIR
    python -m carbon.challenge_validator.tuning solve --work DIR --overlay DIR
    python -m carbon.challenge_validator.tuning predict --work DIR --panel PANEL.json
    python -m carbon.challenge_validator.tuning score --work DIR
    python -m carbon.challenge_validator.tuning recheck --config TESTNET.json \\
        --commitment COMMITMENT.json --public FILE --work DIR

- **`export-pool`** writes the rotating hidden pool's case inputs, the
  `graphite-hidden-battery-v1` deployment's every pooled batch, as the
  owner-only private-prior file the seal's overlap check reads.
- **`jobs`** regenerates the sealed tuning batch from the deployment's root and
  recalls it against its public commitment. It never commits, and it never
  opens the pool store.
- **`solve`** runs the truth solves in the pinned truth image, with no network.
- **`predict`** rebuilds each panel member on host CPU and predicts the batch.
- **`score`** scores each member's stored predictions: the exam's components
  per member, plus per-case rows kept for re-scoring candidate weightings
  without retraining.
- **`recheck`** compares the sealed set against a public case set committed
  after the seal, such as PRACTICE-SAFETY-01's B4 decision set. It reports
  only a verdict and a count, never which cases overlap: that would reveal
  tuning cases. On any overlap the public set is reselected, never the sealed
  tuning set (the Test Lead, 2026-10-05). The re-check is recorded owner-only
  in the work directory, and its public summary in the tuning set's record.

Every file is owner-only and lives outside the repository. DEVELOPMENT only:
no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

from .interface import BATTERY_TUNING_ROLE

REPOSITORY = Path(__file__).resolve().parents[2]
SCORES_SCHEMA = "carbon.challenge-validator.tuning-scores.v1"
RECHECK_SCHEMA = "carbon.challenge-validator.tuning-recheck.v1"
PANEL_SCHEMA = "carbon.challenge-validator.tuning-panel.v1"


class TuningRefused(ValueError):
    """A typed refusal; its code carries no private case, input or output."""


def _outside_repository(path):
    resolved = Path(path).resolve()
    root = REPOSITORY.resolve()
    if resolved == root or root in resolved.parents:
        raise TuningRefused("tuning_work_inside_repository")
    return Path(path)


def _owner_only_dir(path):
    path = _outside_repository(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        raise TuningRefused("tuning_work_not_owner_only")
    return path


def _write_private(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle, sort_keys=True)
        handle.write("\n")


def _read_private(path):
    path = Path(path)
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise TuningRefused("tuning_file_not_owner_only")
    return json.loads(path.read_bytes())


def _tuning_set():
    from .confirmation import confirmation_set

    return confirmation_set(BATTERY_TUNING_ROLE)


# --- export-pool ----------------------------------------------------------------------


def export_pool(config_path, out):
    """The hidden deployment's pooled case inputs, as the owner-only private
    prior `graphite-hidden-battery-v1-pool`. Read only."""
    from carbon.battery import deployment

    target = deployment.validator(
        Path(config_path), repository=REPOSITORY, readonly=True
    )
    cases = [
        {"inputs": dict(case["inputs"])}
        for batch in target.store.batches()
        for case in batch["document"]["cases"]
    ]
    out = _outside_repository(out)
    _write_private(out, {"cases": cases})
    return {"batches": len(target.store.batches()), "cases": len(cases)}


# --- jobs, solve ----------------------------------------------------------------------


def recall(root, pin, journal, commitment, item):
    """The sealed tuning batch, regenerated and recalled. Refused unless it is
    exactly the public commitment (fingerprint and journal sequence).
    `SeedJournal.recall` never commits."""
    from carbon.battery import seeds

    batch = seeds.make_batch(
        root, pin, item.role, item.batch_size, item.hidden_duplicates
    )
    if batch.fingerprint != commitment["fingerprint"]:
        raise TuningRefused("tuning_fingerprint_mismatch")
    committed = journal.recall(batch)
    if committed.sequence != commitment["journal_sequence"]:
        raise TuningRefused("tuning_sequence_mismatch")
    return committed


def jobs(config_path, commitment_path, work):
    """Write the batch (owner-only) and its distinct solve jobs."""
    from carbon.battery import deployment, seeds

    from .confirmation import sealed

    commitment = sealed(json.loads(Path(commitment_path).read_bytes()))
    if commitment is None:
        raise TuningRefused("tuning_commitment_malformed")
    config = deployment.load_config(config_path)
    root = seeds.PrivateRoot.load(deployment._private(config["private_root"]))
    journal = seeds.SeedJournal(config["journal"])
    committed = recall(root, journal.root_pin(root), journal, commitment, _tuning_set())
    work = _owner_only_dir(work)
    document = committed.batch.document()
    duplicates = set(document["duplicates"])
    distinct = [
        {"case_id": c["case_id"], **c["inputs"]}
        for c in document["cases"]
        if c["case_id"] not in duplicates
    ]
    _write_private(work / "batch.json", document)
    _write_private(
        work / "jobs.json", {"fingerprint": committed.fingerprint, "jobs": distinct}
    )
    return {
        "fingerprint": committed.fingerprint,
        "journal_sequence": committed.sequence,
        "cases": len(document["cases"]),
        "distinct_solves": len(distinct),
    }


def solve(work, overlay, *, workers=7, timeout_s=1200.0, runner=None):
    """The truth solves in the pinned truth image (no network). Resumable."""
    import subprocess

    from carbon.battery import truth_env

    work = _owner_only_dir(work)
    if not (work / "records.jsonl").exists():
        (work / "records.jsonl").touch(mode=0o600)
    command = truth_env.solve_command(
        overlay, work, repository=REPOSITORY, workers=workers, timeout_s=timeout_s
    )
    completed = (runner or subprocess.run)(command, check=False)
    return {"returncode": completed.returncode}


def references(work):
    """The batch and each case's reference record; a hidden duplicate reuses
    its original's solve, as the validator does."""
    batch = _read_private(Path(work) / "batch.json")
    records = {}
    for line in (Path(work) / "records.jsonl").read_text().splitlines():
        if line.strip():
            record = json.loads(line)
            if record.get("status") != "FAILED_INFRA":
                records[record["case_id"]] = record
    refs = {}
    for case in batch["cases"]:
        source = batch["duplicates"].get(case["case_id"], case["case_id"])
        if source in records:
            refs[case["case_id"]] = {**records[source], "case_id": case["case_id"]}
    return batch, refs


# --- predict --------------------------------------------------------------------------


def load_panel(path):
    """The operator's panel file: `{"schema", "members": [{"member", "kind",
    "strategy", "seed"}, ...]}`."""
    panel = json.loads(Path(path).read_bytes())
    members = panel.get("members") if type(panel) is dict else None
    if (
        panel.get("schema") != PANEL_SCHEMA
        or type(members) is not list
        or not members
        or len({m.get("member") for m in members}) != len(members)
        or not all(
            type(m) is dict
            and set(m) == {"member", "kind", "strategy", "seed"}
            and type(m["member"]) is str
            and "/" not in m["member"]
            and type(m["seed"]) is int
            for m in members
        )
    ):
        raise TuningRefused("tuning_panel_malformed")
    return members


def predict(work, panel_path, *, backend=None):
    """Rebuild each panel member on host CPU and predict the batch's inputs.
    Owner-only bundles; resumable; a member's own failure is recorded."""
    from carbon.battery.value.experiment import member_bundle

    work = _owner_only_dir(work)
    batch = _read_private(work / "batch.json")
    inputs = {c["case_id"]: dict(c["inputs"]) for c in batch["cases"]}
    if backend is None:
        from carbon.battery.worker import DirectBackend

        backend = DirectBackend(str(REPOSITORY))
    out = _owner_only_dir(work / "predictions")
    done = failed = 0
    for member in load_panel(panel_path):
        path = out / f"{member['member']}.json"
        if path.exists():
            continue
        try:
            bundle, _state = member_bundle(
                backend, member["member"], member["strategy"], member["seed"], inputs
            )
        except Exception as failure:  # noqa: BLE001 - typed, recorded
            _write_private(
                out / f"{member['member']}.failure.json",
                {"member": member["member"], "failure": type(failure).__name__},
            )
            failed += 1
            continue
        _write_private(path, {**bundle, "kind": member["kind"]})
        done += 1
    return {"rebuilt": done, "failed": failed}


# --- score ----------------------------------------------------------------------------


def case_store(batch, refs, repository=REPOSITORY):
    """The exam's case store over the tuning references, built as the validator
    builds its own (`daemon._case_store`)."""
    import numpy as np

    from carbon.battery import exam
    from carbon.battery.calibration import SHAPES, frozen_calibration
    from carbon.battery.challenge import PublicMaterial

    material = PublicMaterial.load(repository)
    ocv = {
        c: float(np.interp(r["inputs"]["soc0"], material.ocv_soc, material.ocv_v))
        for c, r in refs.items()
        if r.get("inputs")
    }
    tol, scales = frozen_calibration(repository)
    return exam.CaseStore(refs, ocv, tol, scales, SHAPES, dict(batch["duplicates"]))


def score_members(batch, refs, predictions, kinds, repository=REPOSITORY):
    """Each member's exam components on the tuning set, and its per-case rows
    for re-scoring weightings. The panel's synthetic controls are added."""
    from carbon.battery import exam
    from carbon.battery.value import panel as pn
    from carbon.battery.value import scoring as sc

    store = case_store(batch, refs, repository)
    ids = sorted(refs)
    members, kinds = dict(predictions), dict(kinds)
    for kind in pn.CONTROLS:
        members["control-" + kind] = pn.control_predictions(kind, store.refs)
        kinds["control-" + kind] = "SYNTHETIC_CONTROL"
    summary, rows = {}, {}
    for member, member_predictions in sorted(members.items()):
        summary[member] = {
            "kind": kinds.get(member, "RECONSTRUCTED"),
            **sc.components(member_predictions, ids, store),
        }
        rows[member], _ = exam.evaluate(member_predictions, ids, store)
    return summary, rows


def score(work, repository=REPOSITORY):
    """Score every stored member on the tuning set. Owner-only outputs:
    `scores.json` (per member) and `rows/<member>.json` (per case)."""
    from carbon.battery import seeds

    work = _owner_only_dir(work)
    batch, refs = references(work)
    from carbon.battery import rebuild_identity as ri

    predictions, kinds, bundles = {}, {}, []
    for path in sorted((work / "predictions").glob("*.json")):
        if path.name.endswith(".failure.json"):
            continue
        bundle = _read_private(path)
        predictions[bundle["member"]] = bundle["predictions"]
        kinds[bundle["member"]] = bundle.get("kind", "RECONSTRUCTED")
        bundles.append(bundle)
    # The members are ranked against each other downstream (score tuning):
    # one device class, or nothing is scored (TORCH-GPU-01).
    try:
        device_class = ri.bundles_class(bundles)
    except ri.DeviceClassMixed:
        raise TuningRefused("tuning_device_classes_mixed") from None
    summary, rows = score_members(batch, refs, predictions, kinds, repository)
    out = _owner_only_dir(work / "rows")
    for member, member_rows in rows.items():
        path = out / f"{member}.json"
        if path.exists():
            path.unlink()
        _write_private(path, member_rows)
    document = {
        "schema": SCORES_SCHEMA,
        "role": BATTERY_TUNING_ROLE,
        "batch_fingerprint": seeds.PrivateBatch.from_document(batch).fingerprint,
        "cases": len(batch["cases"]),
        "cases_with_reference": len(refs),
        "members": summary,
        "device_class": device_class,
        "state": "DEVELOPMENT_TUNING",
        "audience": "operator only; never an agent or miner",
    }
    target = work / "scores.json"
    if target.exists():
        target.unlink()
    _write_private(target, document)
    return {"members": len(summary), "cases_with_reference": len(refs)}


# --- recheck --------------------------------------------------------------------------


def public_keys(path, source):
    """A committed public set's case keys: an engineering-value contract (its
    decision cases) or `{"cases": [{"inputs": {...}}, ...]}`."""
    from carbon.battery.value import contract as ev

    document = json.loads(Path(path).read_bytes())
    if type(document) is dict and "scenarios" in document:
        cases = ev.decision_cases(ev.validate(document))
        return {source.key(case) for case in cases}
    try:
        return {source.key(case["inputs"]) for case in document["cases"]}
    except (KeyError, TypeError, ValueError):
        raise TuningRefused("tuning_public_set_malformed") from None


def recheck(config_path, commitment_path, public_path, work):
    """Re-check the sealed tuning set against a public set committed after the
    seal. Returns, and records owner-only, only a verdict and a count."""
    import hashlib

    from carbon.battery import deployment, seeds

    from .confirmation import sealed
    from .confirmation_sources import source_for

    commitment = sealed(json.loads(Path(commitment_path).read_bytes()))
    if commitment is None:
        raise TuningRefused("tuning_commitment_malformed")
    item = _tuning_set()
    source = source_for(item.challenge_id)
    config = deployment.load_config(config_path)
    root = seeds.PrivateRoot.load(deployment._private(config["private_root"]))
    journal = seeds.SeedJournal(config["journal"])
    committed = recall(root, journal.root_pin(root), journal, commitment, item)
    tuning_keys = {source.key(dict(x)) for _c, x in committed.batch.cases}
    public = public_keys(public_path, source)
    overlaps = len(tuning_keys & public)
    record = {
        "schema": RECHECK_SCHEMA,
        "role": BATTERY_TUNING_ROLE,
        "tuning_fingerprint": committed.fingerprint,
        "public_file_sha256": hashlib.sha256(
            Path(public_path).read_bytes()
        ).hexdigest(),
        "public_cases": len(public),
        "overlapping_cases": overlaps,
        "verdict": "CLEAR" if overlaps == 0 else "OVERLAP_RESELECT_PUBLIC_SET",
    }
    work = _owner_only_dir(work)
    path = work / f"recheck-{record['public_file_sha256'][:12]}.json"
    if path.exists():
        path.unlink()
    _write_private(path, record)
    return record


# --- CLI -------------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.challenge_validator.tuning")
    sub = parser.add_subparsers(dest="command", required=True)
    exported = sub.add_parser("export-pool")
    exported.add_argument("--config", required=True)
    exported.add_argument("--out", required=True)
    made = sub.add_parser("jobs")
    for name in ("config", "commitment", "work"):
        made.add_argument("--" + name, required=True)
    solved = sub.add_parser("solve")
    solved.add_argument("--work", required=True)
    solved.add_argument("--overlay", required=True)
    predicted = sub.add_parser("predict")
    predicted.add_argument("--work", required=True)
    predicted.add_argument("--panel", required=True)
    scored = sub.add_parser("score")
    scored.add_argument("--work", required=True)
    rechecked = sub.add_parser("recheck")
    for name in ("config", "commitment", "public", "work"):
        rechecked.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "export-pool":
            result = export_pool(args.config, args.out)
        elif args.command == "jobs":
            result = jobs(args.config, args.commitment, args.work)
        elif args.command == "solve":
            result = solve(args.work, args.overlay)
        elif args.command == "predict":
            result = predict(args.work, args.panel)
        elif args.command == "recheck":
            result = recheck(args.config, args.commitment, args.public, args.work)
        else:
            result = score(args.work)
    except TuningRefused as refused:
        print(json.dumps({"status": "REFUSED", "reason": str(refused)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
