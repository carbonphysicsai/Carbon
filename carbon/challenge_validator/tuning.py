"""Battery's sealed tuning set, operator-side (VALIDATOR-17;
OWNER-GRAPHITE-TEST-WAVE-08 §1; VALIDATOR-19 slice Q).

The tuning set (`graphite-tuning-v2`, registered in `confirmation_sets/`;
`graphite-tuning-v1` is superseded unsealed) scores every panel member and
compares candidate score weightings. It is used repeatedly for score
development. It is sealed like a confirmation set, and nothing here ever
gives an agent or miner its cases, references, predictions or scores.

Operator steps, all on the hidden host (HIDDEN_HOST_SETUP §6):

    python -m carbon.challenge_validator.tuning export-pool --config HIDDEN.json --out FILE
    python -m carbon.challenge_validator.confirmation seal --role graphite-tuning-v2 \\
        --config HIDDEN.json --prior graphite-hidden-battery-v1-pool=FILE \\
        --prior ev5-confirmation=FILE --prior graphite-confirmation-v1=FILE
    python -m carbon.challenge_validator.tuning jobs --config HIDDEN.json \\
        --commitment COMMITMENT.json --work DIR
    python -m carbon.challenge_validator.tuning solve --work DIR --overlay DIR
    python -m carbon.challenge_validator.tuning quiz-jobs --config HIDDEN.json --work Q
    python -m carbon.challenge_validator.tuning solve --work Q --overlay DIR
    python -m carbon.challenge_validator.tuning quiz-refine --work Q
    python -m carbon.challenge_validator.tuning solve --work Q/refine --overlay DIR
    python -m carbon.challenge_validator.tuning quiz-select --work Q --panel PANEL.json
    python -m carbon.challenge_validator.tuning quiz-seal --config HIDDEN.json --work Q
    python -m carbon.challenge_validator.tuning predict --work DIR --panel PANEL.json \\
        --quiz Q
    python -m carbon.challenge_validator.tuning score --work DIR --quiz Q
    python -m carbon.challenge_validator.tuning recheck --config HIDDEN.json \\
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

The near-limit quiz stratum (`carbon.battery.quiz_stratum`, its own work
directory Q):
- **`quiz-jobs`** draws, from the hidden deployment's root, Q2's oversample
  (`Q2_POOL * 4` candidates) and `Q3_K + 4` Q3 conditions (protected ones
  redrawn), and writes their solve jobs. `--round N` adds 4 Q3 conditions per
  round; Q2 is never redrawn. `solve --work Q` solves them. Each Q3 grid is
  the 117-point lattice (`quiz.q3_candidates`).
- **`quiz-refine`** (quiz-registry-v8), after the lattice solve: every drawn
  Q3 condition's band-edge points (`quiz.q3_refine_points`) are written as
  `Q/refine/jobs.json` (owner-only, `refined: true`), and `solve --work
  Q/refine` runs their refined solves in the same pinned truth image. It
  prints the refine count per scenario, in draw order, and the total. Rerun
  it after a new `--round`; the solve keeps every earlier record.
- **`quiz-select`** settles each Q3 lattice (`quiz.q3_settle`: refined truth
  where the refined solve is OK, the standard reference otherwise) and
  refuses with `tuning_quiz_needs_refine` while a refine point has no
  refined record. It keeps Q2's near-limit pool, rebuilds the registered
  disagreement panel once (its predictions cached under Q), picks Q2's cases
  from the panel's predictions only, and keeps the first `Q3_K` scenarios
  whose settled lattice is feasible. With fewer, it refuses and names the
  next `--round`. Each kept scenario records `refine: {refine_points,
  refined_ok, residual}` (counts only; `residual` is the lattice points
  still UNRESOLVED after settling).
- **`quiz-seal`** commits the quiz's digest and counts to the deployment's
  seed journal (kind `quiz`).
- **`predict --quiz Q`** also predicts the quiz's inputs, and **`score --quiz
  Q`** writes each member's quiz measures (`quiz-scores.json`, Q3's with
  `unresolved`) and `q3-regret.json` (member to mean Q3 decision regret,
  for `tuning_rescore --q3-regret`), judged against the settled references.
  Quiz cases never enter the accuracy rows.

Every file is owner-only and lives outside the repository. DEVELOPMENT only:
no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import argparse
import contextlib
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
QUIZ_DRAWS_SCHEMA = "carbon.challenge-validator.tuning-quiz-draws.v1"
QUIZ_SCORES_SCHEMA = "carbon.challenge-validator.tuning-quiz-scores.v1"


class TuningRefused(ValueError):
    """A typed refusal; its code carries no private case, input or output."""


@contextlib.contextmanager
def _quiz_refusals():
    """The quiz stratum's typed refusals, as the tuning tool's own."""
    from carbon.battery.quiz_stratum import QuizRefused

    try:
        yield
    except QuizRefused as refused:
        raise TuningRefused("tuning_" + refused.code) from None


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


def _replace_private(path, value):
    path = Path(path)
    if path.exists():
        path.unlink()
    _write_private(path, value)


def _read_private(path):
    path = Path(path)
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise TuningRefused("tuning_file_not_owner_only")
    return json.loads(path.read_bytes())


def _records(work):
    """A work directory's solve records by case id (FAILED_INFRA is retried,
    so it is not a reference)."""
    from carbon.battery.quiz_stratum import solved

    return solved(_record_lines(Path(work) / "records.jsonl"))


def _record_lines(path):
    if not path.exists():
        return []
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise TuningRefused("tuning_file_not_owner_only")
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


#: The quiz's refined solves (quiz-registry-v8) live in their own work
#: directory under the quiz's, solved by `solve --work Q/refine`.
REFINE_DIR = "refine"


def _refined_records(work):
    """A quiz work directory's refined records by case id (`refined: true`;
    FAILED_INFRA is retried, so it is not one)."""
    from carbon.battery.quiz_stratum import refined

    return refined(_record_lines(Path(work) / REFINE_DIR / "records.jsonl"))


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


def _backend(backend):
    if backend is None:
        from carbon.battery.worker import DirectBackend

        backend = DirectBackend(str(REPOSITORY))
    return backend


def _rebuild(backend, member, inputs, failure_path):
    """One member rebuilt on host CPU, predicting `inputs`: its bundle, or
    None with its own failure recorded (typed) at `failure_path`."""
    from carbon.battery.value.experiment import member_bundle

    try:
        bundle, _state = member_bundle(
            backend, member["member"], member["strategy"], member["seed"], inputs
        )
    except Exception as failure:  # noqa: BLE001 - typed, recorded
        _replace_private(
            failure_path,
            {"member": member["member"], "failure": type(failure).__name__},
        )
        return None
    if failure_path.exists():
        failure_path.unlink()
    return bundle


def _only(predictions, ids):
    return {c: predictions[c] for c in ids if c in predictions}


def load_quiz(quiz):
    """A quiz work directory's selected quiz (`quiz-select`), checked."""
    from carbon.battery import quiz_stratum as qs

    path = Path(quiz) / "quiz.json"
    if not path.exists():
        raise TuningRefused("tuning_quiz_not_selected")
    with _quiz_refusals():
        return qs.check(_read_private(path))


def predict(work, panel_path, *, quiz=None, backend=None):
    """Rebuild each panel member on host CPU and predict the batch's inputs,
    and with `quiz` (a quiz work directory) the quiz's inputs too, which are
    kept apart in `quiz-predictions/`. Owner-only bundles; resumable (one
    rebuild serves whatever a member still lacks); a member's own failure is
    recorded."""
    from carbon.battery import quiz_stratum as qs

    work = _owner_only_dir(work)
    batch = _read_private(work / "batch.json")
    inputs = {c["case_id"]: dict(c["inputs"]) for c in batch["cases"]}
    document = None if quiz is None else load_quiz(quiz)
    quiz_inputs = {} if document is None else qs.inputs(document)
    backend = _backend(backend)
    out = _owner_only_dir(work / "predictions")
    quiz_out = None if document is None else _owner_only_dir(work / "quiz-predictions")
    done = failed = 0
    for member in load_panel(panel_path):
        path = out / f"{member['member']}.json"
        quiz_path = None if quiz_out is None else quiz_out / f"{member['member']}.json"
        needed = {} if path.exists() else dict(inputs)
        if quiz_path is not None and not quiz_path.exists():
            needed.update(quiz_inputs)
        if not needed:
            continue
        failure = out / f"{member['member']}.failure.json"
        bundle = _rebuild(backend, member, needed, failure)
        if bundle is None:
            failed += 1
            continue
        if not path.exists():
            predictions = _only(bundle["predictions"], inputs)
            _write_private(
                path, {**bundle, "predictions": predictions, "kind": member["kind"]}
            )
        if quiz_path is not None and not quiz_path.exists():
            _write_private(
                quiz_path,
                {
                    "member": member["member"],
                    "kind": member["kind"],
                    "quiz_digest": qs.digest(document),
                    "predictions": _only(bundle["predictions"], quiz_inputs),
                },
            )
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


def score(work, repository=REPOSITORY, *, quiz=None):
    """Score every stored member on the tuning set. Owner-only outputs:
    `scores.json` (per member) and `rows/<member>.json` (per case); with
    `quiz`, also `quiz-scores.json` and `q3-regret.json` (`score_quiz`)."""
    from carbon.battery import seeds

    work = _owner_only_dir(work)
    if quiz is not None:
        load_quiz(quiz)  # refused before anything is written
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
    result = {"members": len(summary), "cases_with_reference": len(refs)}
    if quiz is not None:
        result["quiz"] = score_quiz(work, quiz, repository)
    return result


def score_quiz(work, quiz, repository=REPOSITORY):
    """Every member's quiz measures, from its stored quiz predictions and the
    quiz's settled references (`quiz_references`), with the panel's
    synthetic controls added. Owner-only:
    `quiz-scores.json` (Q2 and Q3 measures and Q3 outcomes per member) and
    `q3-regret.json` (member to mean Q3 decision regret over the quiz's
    feasible scenarios, None when unmeasured). Accuracy is never computed on
    a quiz case."""
    from carbon.battery import quiz_stratum as qs
    from carbon.battery.value import panel as pn

    work = _owner_only_dir(work)
    document = load_quiz(quiz)
    quiz_digest = qs.digest(document)
    contract = qs.contract(repository)
    refs = quiz_references(quiz, document, contract)
    predictions, kinds = {}, {}
    folder = work / "quiz-predictions"
    for path in sorted(folder.glob("*.json")) if folder.exists() else ():
        bundle = _read_private(path)
        if bundle.get("quiz_digest") != quiz_digest:
            raise TuningRefused("tuning_quiz_predictions_stale")
        predictions[bundle["member"]] = bundle["predictions"]
        kinds[bundle["member"]] = bundle.get("kind", "RECONSTRUCTED")
    for kind in pn.CONTROLS:
        predictions["control-" + kind] = pn.control_predictions(kind, refs)
        kinds["control-" + kind] = "SYNTHETIC_CONTROL"
    members = {}
    with _quiz_refusals():
        for member, member_predictions in sorted(predictions.items()):
            members[member] = {
                "kind": kinds[member],
                **qs.member_measures(contract, document, member_predictions, refs),
            }
    _replace_private(
        work / "quiz-scores.json",
        {
            "schema": QUIZ_SCORES_SCHEMA,
            "role": document["role"],
            "quiz_digest": quiz_digest,
            "panel_version": document["panel_version"],
            "q2_cases": len(document["q2"]),
            "q3_scenarios": len(document["q3"]),
            "members": members,
            "state": "DEVELOPMENT_TUNING",
            "audience": "operator only; never an agent or miner",
        },
    )
    _replace_private(
        work / "q3-regret.json",
        {member: row["q3"]["regret"] for member, row in members.items()},
    )
    return {"members": len(members), "quiz_digest": quiz_digest}


# --- the quiz stratum -----------------------------------------------------------------


def _hidden(config_path):
    """The deployment's root, its committed seed pin and its journal."""
    from carbon.battery import deployment, seeds

    config = deployment.load_config(config_path)
    root = seeds.PrivateRoot.load(deployment._private(config["private_root"]))
    journal = seeds.SeedJournal(config["journal"])
    try:
        pin = journal.root_pin(root)
    except ValueError:
        raise TuningRefused("tuning_root_not_committed") from None
    return root, pin, journal


def _quiz_dir(work):
    work = _owner_only_dir(work)
    if (work / "batch.json").exists():
        raise TuningRefused("tuning_quiz_work_is_the_tuning_work")
    return work


def _draws(root, pin, role, round_, repository):
    from carbon.battery import quiz_stratum as qs

    with _quiz_refusals():
        points = qs.protected_conditions(repository)
        return {
            "schema": QUIZ_DRAWS_SCHEMA,
            "role": role,
            "round": round_,
            "q2": qs.q2_candidates(root, pin, role, qs.q2_draws()),
            "q3": qs.q3_conditions(root, pin, role, qs.q3_draws(round_), points),
        }


def _quiz_draws(work):
    """The quiz work directory's draws (`quiz-jobs`), checked."""
    if not (Path(work) / "draws.json").exists():
        raise TuningRefused("tuning_quiz_jobs_missing")
    draws = _read_private(Path(work) / "draws.json")
    if draws.get("schema") != QUIZ_DRAWS_SCHEMA or draws["role"] != _tuning_set().role:
        raise TuningRefused("tuning_quiz_draws_malformed")
    return draws


def _settled(work, contract, conditions):
    """`(standard refs, refine points, refined records, settled refs)` for
    the Q3 `conditions` of a quiz work directory. Refused while a lattice
    point is unsolved (`tuning_quiz_unsolved`) or a refine point has no
    terminal refined record (`tuning_quiz_needs_refine`)."""
    from carbon.battery import quiz_stratum as qs

    refs, refined = _records(work), _refined_records(work)
    with _quiz_refusals():
        points = qs.refine_points(contract, conditions, refs)
        missing = qs.unrefined(points, refined)
    if missing:
        raise TuningRefused("tuning_quiz_needs_refine")
    return refs, points, refined, qs.settle(refs, points, refined)


def quiz_references(quiz, document, contract):
    """The selected quiz's settled references, by case id: what `score`
    judges against."""
    from carbon.battery import quiz_stratum as qs

    ids = set(qs.inputs(document))
    _refs, _points, _refined, settled = _settled(quiz, contract, document["q3"])
    return {c: r for c, r in settled.items() if c in ids}


def quiz_refine(work, repository=REPOSITORY):
    """Write the refined-solve jobs (quiz-registry-v8) for every drawn Q3
    condition's band-edge lattice points, as `refine/jobs.json` (owner-only;
    the shape `solve` reads). Rerunnable: refined records already solved are
    kept by the solve. Prints counts only."""
    from carbon.battery import quiz_stratum as qs

    work = _quiz_dir(work)
    if (work / "quiz.json").exists():
        raise TuningRefused("tuning_quiz_already_selected")
    draws = _quiz_draws(work)
    contract = qs.contract(repository)
    with _quiz_refusals():
        points = qs.refine_points(contract, draws["q3"], _records(work))
    jobs = qs.refine_jobs(points)
    refine = _owner_only_dir(work / REFINE_DIR)
    _replace_private(
        refine / "jobs.json", {"fingerprint": qs.digest(draws), "jobs": jobs}
    )
    if not (refine / "records.jsonl").exists():
        (refine / "records.jsonl").touch(mode=0o600)
    return {
        "round": draws["round"],
        "refine_points_per_scenario": [
            len(points[entry["scenario_id"]]) for entry in draws["q3"]
        ],
        "refine_jobs": len(jobs),
    }


def quiz_jobs(config_path, work, round_=1, repository=REPOSITORY):
    """Draw the quiz stratum's candidates from the deployment's root and
    write their solve jobs (owner-only). Round 1 draws Q2's oversample and
    `Q3_K + 4` Q3 conditions; each later round adds 4 Q3 conditions, and Q2
    is never redrawn. Rerunnable: the draws are deterministic and solved
    records are kept."""
    from carbon.battery import quiz_stratum as qs

    if type(round_) is not int or round_ < 1:
        raise TuningRefused("tuning_quiz_round_malformed")
    work = _quiz_dir(work)
    if (work / "quiz.json").exists():
        raise TuningRefused("tuning_quiz_already_selected")
    role = _tuning_set().role
    root, pin, _journal = _hidden(config_path)
    draws = _draws(root, pin, role, round_, repository)
    jobs = qs.solve_jobs(qs.contract(repository), draws["q2"], draws["q3"])
    _replace_private(work / "draws.json", draws)
    _replace_private(
        work / "jobs.json", {"fingerprint": qs.digest(draws), "jobs": jobs}
    )
    if not (work / "records.jsonl").exists():
        (work / "records.jsonl").touch(mode=0o600)
    last = draws["q3"][-1]
    return {
        "round": round_,
        "q2_candidates": len(draws["q2"]),
        "q3_conditions": len(draws["q3"]),
        "q3_protected_redraws": last["attempt"] + 1 - len(draws["q3"]),
        "solve_jobs": len(jobs),
    }


def _panel_predictions(members, inputs, cache, backend):
    """Each registered panel member's predictions on the Q2 candidates:
    rebuilt once per panel version and cached owner-only under the quiz
    work directory. A member whose rebuild failed is missing (and retried on
    the next run)."""
    from carbon.battery import quiz_stratum as qs

    key = qs.digest(inputs)
    found = {}
    for member in members:
        path = cache / f"{member['member']}.json"
        if not path.exists():
            bundle = _rebuild(
                _backend(backend),
                member,
                inputs,
                cache / f"{member['member']}.failure.json",
            )
            if bundle is None:
                continue
            _write_private(
                path,
                {
                    "member": member["member"],
                    "inputs_digest": key,
                    "predictions": _only(bundle["predictions"], inputs),
                },
            )
        cached = _read_private(path)
        if cached["inputs_digest"] != key:
            raise TuningRefused("tuning_quiz_panel_cache_stale")
        found[member["member"]] = cached["predictions"]
    return found


def quiz_select(work, panel_path, *, backend=None, repository=REPOSITORY):
    """Select the quiz from the solved draws: each Q3 lattice settled with
    its refined solves (refused with `tuning_quiz_needs_refine` until they
    are in), Q3's first `Q3_K` feasible scenarios (refused, naming the next
    `--round`, when fewer are), then Q2's near-limit pool and the panel's
    pick. Writes owner-only `quiz.json`."""
    from carbon.battery import quiz_stratum as qs
    from carbon.battery.value import quiz as qz

    work = _quiz_dir(work)
    if (work / "quiz.json").exists():
        raise TuningRefused("tuning_quiz_already_selected")
    draws = _quiz_draws(work)
    contract = qs.contract(repository)
    refs, points, refined, settled = _settled(work, contract, draws["q3"])
    with _quiz_refusals():
        q3, redraws = qs.q3_select(contract, draws["q3"], settled)
        if len(q3) < qz.Q3_K:
            raise TuningRefused(
                f"tuning_quiz_needs_more_q3:--round {draws['round'] + 1}"
            )
        pool = qs.q2_pool(contract, draws["q2"], refs)
        if len(pool) < qz.Q2_N:
            raise TuningRefused("tuning_quiz_q2_pool_short")
        registered = qs.registered_panel(repository)
    members = load_panel(panel_path)
    if sorted(m["member"] for m in members) != sorted(registered):
        raise TuningRefused("tuning_quiz_panel_not_registered")
    inputs = {c["case_id"]: dict(c["inputs"]) for c in draws["q2"]}
    cache = _owner_only_dir(work / f"panel-v{qz.PANEL_VERSION}")
    panel = _panel_predictions(members, inputs, cache, backend)
    if len(panel) != len(members):
        raise TuningRefused("tuning_quiz_panel_incomplete")
    chosen = qs.q2_choose(contract, pool, panel)
    q3 = qs.with_refine(contract, q3, points, refined, settled)
    document = qs.document(
        draws["role"],
        qz.PANEL_VERSION,
        [{"case_id": c, "inputs": inputs[c]} for c in chosen],
        q3,
        redraws,
    )
    _write_private(work / "quiz.json", document)
    return {
        "digest": qs.digest(document),
        "panel_version": qz.PANEL_VERSION,
        "panel_members": len(panel),
        "q2_pool": len(pool),
        "q2_cases": len(chosen),
        "q3_scenarios": len(q3),
        "q3_refine": {
            k: sum(s["refine"][k] for s in q3)
            for k in ("refine_points", "refined_ok", "residual")
        },
        "redraws": redraws,
    }


def quiz_seal(config_path, work, repository=REPOSITORY):
    """Commit the selected quiz's digest to the deployment's seed journal
    (kind `quiz`: digest, counts and panel version only). Refused unless the
    quiz's cases are this deployment root's own draws. Idempotent."""
    from carbon.battery import deployment
    from carbon.battery import quiz_stratum as qs

    work = _quiz_dir(work)
    document = load_quiz(work)
    draws = _read_private(work / "draws.json")
    root, pin, _journal = _hidden(config_path)
    regenerated = _draws(root, pin, draws["role"], draws["round"], repository)
    q2 = {c["case_id"]: c["inputs"] for c in regenerated["q2"]}
    q3 = {s["scenario_id"]: s["condition"] for s in regenerated["q3"]}
    if (
        regenerated != draws
        or document["role"] != draws["role"]
        or any(q2.get(c["case_id"]) != c["inputs"] for c in document["q2"])
        or any(q3.get(s["scenario_id"]) != s["condition"] for s in document["q3"])
    ):
        raise TuningRefused("tuning_quiz_not_from_this_root")
    target = deployment.validator(
        Path(config_path), repository=repository, readonly=True
    )
    with deployment.writer(target), _quiz_refusals():
        entry = qs.seal(target.journal, document)
    return {"digest": entry["digest"], "journal_sequence": entry["sequence"]}


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
    predicted.add_argument("--quiz")
    scored = sub.add_parser("score")
    scored.add_argument("--work", required=True)
    scored.add_argument("--quiz")
    rechecked = sub.add_parser("recheck")
    for name in ("config", "commitment", "public", "work"):
        rechecked.add_argument("--" + name, required=True)
    drawn = sub.add_parser("quiz-jobs")
    drawn.add_argument("--config", required=True)
    drawn.add_argument("--work", required=True)
    drawn.add_argument("--round", type=int, default=1)
    sub.add_parser("quiz-refine").add_argument("--work", required=True)
    selected = sub.add_parser("quiz-select")
    selected.add_argument("--work", required=True)
    selected.add_argument("--panel", required=True)
    committed = sub.add_parser("quiz-seal")
    committed.add_argument("--config", required=True)
    committed.add_argument("--work", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "export-pool":
            result = export_pool(args.config, args.out)
        elif args.command == "jobs":
            result = jobs(args.config, args.commitment, args.work)
        elif args.command == "solve":
            result = solve(args.work, args.overlay)
        elif args.command == "predict":
            result = predict(args.work, args.panel, quiz=args.quiz)
        elif args.command == "recheck":
            result = recheck(args.config, args.commitment, args.public, args.work)
        elif args.command == "quiz-jobs":
            result = quiz_jobs(args.config, args.work, args.round)
        elif args.command == "quiz-refine":
            result = quiz_refine(args.work)
        elif args.command == "quiz-select":
            result = quiz_select(args.work, args.panel)
        elif args.command == "quiz-seal":
            result = quiz_seal(args.config, args.work)
        else:
            result = score(args.work, quiz=args.quiz)
    except TuningRefused as refused:
        print(json.dumps({"status": "REFUSED", "reason": str(refused)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
