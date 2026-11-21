"""Recompute the private grade breakdown of ONE already-graded Motor 1.8 task (aggregates only).

Scope. Read-only. Live ops runs this ON the live validator host only, under Validator-2's ruling (RECEIPTS
2026-11-19). It recomputes the breakdown of one task of ``electric-motor-magnetics`` version ``1.8`` that the door
has already graded, from what the door already holds: the sealed pack directory (its private root, which on the door
is also its public root: ``evaluation-pack.json``, ``sealed-batch.json`` and the role files), the door's installed
menu draw key file (the K_crown file the receiver configuration names under ``menu_draw.key_file``), and the task's
KEPT graded predictions and side files. It runs no model, starts nothing, writes nothing beside its one output file,
and never edits a producer file: every Motor 1.8 producer module (``motor18_dual_pack``, ``motor_sealed_dual_pack``,
``subset_repeat_produce``, ``pool_exam`` and the rest of their ``FILES``) is imported and called unchanged.

It computes epoch E1 only (the registered menu epoch must be ``E1``; anything else refuses).

The path it re-runs is the door's grade path, called unchanged:
``version_overlay.install()`` arms 1.8; the pack snapshot is prepared in memory exactly as the receiver prepares it
(``evaluation_pack.prepare_pack``, nothing written); the sealed bank and adapter come from
``sealed_batch_source.resolve`` (with ``--copy-hotkey`` the validator's own receiver hotkey, as the door passes
``copy_hotkey``); the definition is the public ``accuracy_definition`` role plus ``{"pool": bank["pool"]}``; the menu
key is installed as ``crown_average_host.install`` does (``read_crown_key`` then ``pool_menu.install_key``); the
grade is ``subset_repeat_produce.measure_subset`` inside ``pool_menu.staged_rowcheck(<row-check side file bytes>)``;
the total is ``dual_score.score`` under the pack's private ``score_pack`` role.

Inputs (``--predictions``): the task's kept graded predictions in the door's own retained form, either

- ``predictions.json``: the graded inference snapshot's JSON tensor, a list of one row per bank row in bank order,
  each row the 240 float64 raw outputs (the retention reads row ``p`` as ``graded[p]``); or
- ``worker-evidence.json``: the graph worker evidence object, whose ``predictions_raw_base64`` is the base64 of
  exactly those ``predictions.json`` bytes (canonical base64 required).

``--rowcheck`` is the kept ``carbon.menu-rowcheck.v1`` side file; ``--single-call`` the kept single-call speed side
file (``single_call_timing.read_side_file``); ``--pair`` (optional) the kept subset-repeat side file. Without
``--pair`` every row's twin is its own graded answer (``repeats=[outputs, outputs]``), which only affects gates.
With ``--pair`` the side file is read through ``subset_repeat_evidence.read``; this tool does not hold the graded
receipt, so the recipe/state/image binding values are taken from the side file's own run block and the graded
operation is not compared (a diagnostic weakening: the subset repeat reaches gates only, never A or D).
``--copy-hotkey`` is the door's own receiver hotkey (``receiver_hotkey``); it is an input only, never written.

Exit codes: 0 written (the file's sha256 printed), 2 self-check failed (nothing written), 3 refused (a typed code
printed, nothing written).

Output. Aggregates only (Validator-2's rule): ONE JSON file, schema ``carbon.exam.king-breakdown.v1``, written once
with mode 0600 into ``--out`` (an existing owner-only directory), holding the challenge, version, epoch, A, D, total,
value weight, per-set ordinal A/C/D, per-drawn-task ordinal D/Z/oracle/zero source, the gate verdicts and the number
of menu tasks scored. It never holds a task id, record sha, menu id, draw, row position, case id, per-cell value,
prediction, hotkey, key or path (`_checked_aggregates` refuses anything outside the closed set before writing).
Before writing, the recomputed A, D and total must match ``--expect-a/-d/-total`` within 5e-5; otherwise nothing is
written, only the three recomputed aggregates and ``self_check_failed`` are printed, and the exit code is 2.

    python scripts/dev/king_grade_breakdown.py --private-root P --menu-key-file K \\
        --predictions PRED --rowcheck R --single-call S [--pair X] [--copy-hotkey HK] \\
        --expect-a 0.9423 --expect-d 0.8154 --expect-total 0.8788 --out DIR
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import math
import os
import re
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SCHEMA = "carbon.exam.king-breakdown.v1"
CHALLENGE = "electric-motor-magnetics"
VERSION = "1.8"
EPOCH = "E1"
TOLERANCE = 5e-5
MANIFEST = "evaluation-pack.json"
MAX_INPUT_BYTES = 64 * 1024**2

TOP_KEYS = frozenset(
    {
        "schema",
        "challenge",
        "version",
        "epoch",
        "A",
        "D",
        "total",
        "value_weight",
        "sets",
        "tasks",
        "gates",
        "menu_tasks_scored",
    }
)
SET_KEYS = frozenset({"set", "A", "C", "D"})
TASK_KEYS = frozenset({"task", "D", "Z", "oracle", "zero_source"})
ALL_KEYS = TOP_KEYS | SET_KEYS | TASK_KEYS
ZERO_SOURCES = frozenset({"random", "classical_arm", "model_row_dependent"})
VERDICTS = frozenset({"PASS", "FAIL"})
STRINGS = frozenset({SCHEMA, CHALLENGE, VERSION, EPOCH}) | ZERO_SOURCES | VERDICTS
_GATE_NAME = re.compile(r"[a-z][a-z0-9_]{1,63}")
_HEXISH = re.compile(r"[0-9a-f]{8,}")
_CODE = re.compile(r"[A-Za-z0-9_.:-]{1,160}")


class BreakdownRefused(ValueError):
    """A typed refusal; the code names the check, never hidden content."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class SelfCheckFailed(BreakdownRefused):
    def __init__(self):
        super().__init__("self_check_failed")


def _require(condition, code):
    if not condition:
        raise BreakdownRefused(code)


# --- the closed output ----------------------------------------------------------------


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _checked_aggregates(doc):
    """``doc`` unchanged when it is exactly the closed aggregates document, else `BreakdownRefused`.

    Every key at every level is in a closed set (gate names: lower-case identifiers with no hex run, under ``gates``
    only); every string value is in a closed set; lists appear only as ``sets`` and ``tasks``, of closed objects.
    """
    _require(type(doc) is dict and set(doc) == TOP_KEYS, "aggregates_keys")
    _require(doc["schema"] == SCHEMA, "aggregates_schema")
    _require(doc["challenge"] == CHALLENGE, "aggregates_challenge")
    _require(doc["version"] == VERSION, "aggregates_version")
    _require(doc["epoch"] == EPOCH, "aggregates_epoch")
    for name in ("A", "D", "total", "value_weight"):
        _require(_finite(doc[name]), "aggregates_number")
    sets = doc["sets"]
    _require(type(sets) is list, "aggregates_sets")
    for ordinal, item in enumerate(sets, start=1):
        _require(type(item) is dict and set(item) == SET_KEYS, "aggregates_set_keys")
        _require(type(item["set"]) is int and item["set"] == ordinal, "aggregates_set")
        for name in ("A", "C", "D"):
            _require(_finite(item[name]), "aggregates_number")
    tasks = doc["tasks"]
    _require(type(tasks) is list, "aggregates_tasks")
    for ordinal, item in enumerate(tasks, start=1):
        _require(type(item) is dict and set(item) == TASK_KEYS, "aggregates_task_keys")
        _require(
            type(item["task"]) is int and item["task"] == ordinal, "aggregates_task"
        )
        _require(_finite(item["D"]), "aggregates_number")
        for name in ("Z", "oracle"):
            _require(item[name] is None or _finite(item[name]), "aggregates_number")
        _require(
            type(item["zero_source"]) is str and item["zero_source"] in ZERO_SOURCES,
            "aggregates_string",
        )
    gates = doc["gates"]
    _require(type(gates) is dict, "aggregates_gates")
    for name, verdict in gates.items():
        _require(
            type(name) is str
            and _GATE_NAME.fullmatch(name) is not None
            and _HEXISH.search(name) is None,
            "aggregates_gate_name",
        )
        _require(type(verdict) is str and verdict in VERDICTS, "aggregates_string")
    _require(
        type(doc["menu_tasks_scored"]) is int
        and doc["menu_tasks_scored"] == len(tasks),
        "aggregates_menu_tasks_scored",
    )
    _walk_strings(doc)
    return doc


def _walk_strings(value, under_gates=False):
    """Belt and braces: every string anywhere is a closed value (or a checked gate key)."""
    if type(value) is str:
        _require(value in STRINGS, "aggregates_string")
    elif type(value) is dict:
        for key, item in value.items():
            if not under_gates:
                _require(key in ALL_KEYS, "aggregates_keys")
            _walk_strings(item, under_gates=(key == "gates" and not under_gates))
    elif type(value) is list:
        for item in value:
            _require(type(item) is dict, "aggregates_list_item")
            _walk_strings(item)
    else:
        _require(value is None or _finite(value), "aggregates_value")


def _self_check(recomputed, expected, tolerance=TOLERANCE):
    """Refuse (`SelfCheckFailed`) unless A, D and total each match the recorded value within ``tolerance``."""
    for name in ("A", "D", "total"):
        got, want = recomputed.get(name), expected.get(name)
        if not (_finite(got) and _finite(want) and abs(got - want) <= tolerance):
            raise SelfCheckFailed()


def _private_out_dir(path):
    """The output directory: an existing exact directory owned by this user with no group/other bits (POSIX only)."""
    _require(os.name == "posix", "out_dir_requires_posix")
    selected = Path(path)
    _require(
        selected.is_absolute()
        and not selected.is_symlink()
        and selected.is_dir()
        and selected.resolve() == selected,
        "out_dir_invalid",
    )
    info = selected.stat()
    _require(stat.S_IMODE(info.st_mode) & 0o077 == 0, "out_dir_not_owner_only")
    _require(info.st_uid == os.getuid(), "out_dir_not_owned")
    return selected


def _write_once(directory, doc):
    """Write the checked document once (O_EXCL, mode 0600); returns its sha256 hex."""
    body = _checked_aggregates(doc)
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
    raw = (text + "\n").encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    target = directory / ("king-breakdown-" + digest[:16] + ".json")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(target, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return digest


# --- reading the kept files -----------------------------------------------------------


def _read_file(path, limit=MAX_INPUT_BYTES):
    selected = Path(path)
    if not selected.exists() and not selected.is_symlink():
        # a kept predictions.json held COMPRESSED on the door (`data.compress_raw`): its RAW bytes, checked
        from carbon.development_session.data import raw_exists, read_raw

        _require(raw_exists(selected), "input_file_unavailable")
        try:
            return read_raw(selected, max_bytes=limit)
        except ValueError:
            raise BreakdownRefused("input_file_size") from None
    _require(selected.is_file() and not selected.is_symlink(), "input_file_unavailable")
    _require(0 < selected.stat().st_size <= limit, "input_file_size")
    raw = selected.read_bytes()
    if selected.name.endswith(".json.gz"):
        # a kept side file stored gzipped (`lean_recipe_retention.SIDE_GZ`): its own bytes
        import gzip
        import io

        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            raw = stream.read(limit + 1)
        _require(0 < len(raw) <= limit, "input_file_size")
    return raw


def _strict_json(raw, code):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            _require(key not in value, code)
            value[key] = item
        return value

    def finite(text):
        number = float(text)
        _require(math.isfinite(number), code)
        return number

    def constant(_text):
        raise BreakdownRefused(code)

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_float=finite,
            parse_constant=constant,
        )
    except (UnicodeError, ValueError) as exc:
        if isinstance(exc, BreakdownRefused):
            raise
        raise BreakdownRefused(code) from exc


def _flat(value):
    if type(value) is list:
        return [number for item in value for number in _flat(item)]
    _require(_finite(value), "predictions_value")
    return [value]


def read_predictions(raw, n_rows, width):
    """The graded raw answers, one list per bank row in bank order, from ``predictions.json`` bytes or from a worker
    evidence object carrying them as ``predictions_raw_base64``."""
    body = _strict_json(raw, "predictions_malformed")
    if type(body) is dict:
        encoded = body.get("predictions_raw_base64")
        _require(type(encoded) is str, "predictions_malformed")
        try:
            inner = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (binascii.Error, UnicodeError) as exc:
            raise BreakdownRefused("predictions_encoding") from exc
        _require(
            base64.b64encode(inner).decode("ascii") == encoded, "predictions_encoding"
        )
        body = _strict_json(inner, "predictions_malformed")
    _require(type(body) is list and len(body) == n_rows, "predictions_shape")
    rows = [_flat(row) for row in body]
    _require(all(len(row) == width for row in rows), "predictions_shape")
    return rows


# --- the grade ------------------------------------------------------------------------


def _arm():
    """Motor 1.8 armed exactly as the door arms it: the overlay, then the sealed grader module."""
    import importlib

    from carbon.challenge_kit import version_overlay

    installed = version_overlay.install()
    _require((CHALLENGE, VERSION) in installed, "overlay_has_no_motor_1_8")
    importlib.import_module("carbon.scoring.motor_sealed_dual_pack")
    from carbon.scoring import motor18_dual_pack

    adapter = motor18_dual_pack.sealed_adapter(VERSION)
    _require(adapter is not None, "motor_1_8_adapter_unavailable")
    return adapter


def _install_menu_key(key_file):
    """`crown_average_host.install`'s ``menu_draw`` half, from the same key file: the key stays in this process."""
    from carbon.challenge_validator import crown_average_host
    from carbon.scoring import pool_menu

    name = str(Path(key_file))
    pool_menu.install_key(crown_average_host.read_crown_key(name))


def _snapshot(private_root):
    """The pack snapshot as the receiver prepares it (in memory; nothing is written)."""
    from carbon.challenge_validator import evaluation_pack

    prepared = evaluation_pack.prepare_pack(
        private_root,
        MANIFEST,
        public_root=private_root,
        private_root=private_root,
        challenge_id=CHALLENGE,
        challenge_version=VERSION,
    )
    return prepared.snapshot


def _roles(snapshot, root):
    roles = {}
    for audience, names in (
        (
            "public",
            ("accuracy_definition", "important_limit_definition", "design_objective"),
        ),
        ("private", ("score_pack",)),
    ):
        for name in names:
            roles[name] = snapshot.read_json_role(
                root, audience, name, max_bytes=1024 * 1024
            )
    train_raw = snapshot.read_role(root, "public", "train", max_bytes=16 * 1024**2)
    return roles, train_raw


def _twins(pair_path, snapshot, root, adapter, bank, n_rows, width):
    """One fresh answer per bank row (None when not repeat-checked), as the subset producer reads its side file. The
    run binding values (recipe, state, image) are read from the side file's own run block: see the module notes.
    """
    if pair_path is None:
        return [None] * n_rows
    import io

    import numpy as np

    from carbon.scoring import subset_repeat_evidence as subset_evidence

    raw = _read_file(pair_path)
    document = _strict_json(raw, "pair_malformed")
    run = document.get("run") if type(document) is dict else None
    _require(type(run) is dict, "pair_malformed")
    case_bank = snapshot.read_role(root, "private", "case_bank", max_bytes=16 * 1024**2)
    with np.load(io.BytesIO(case_bank), allow_pickle=False) as loaded:
        graded_inputs = loaded["inputs"]
    try:
        twins = subset_evidence.read(
            raw,
            registered_sha256="sha256:" + hashlib.sha256(raw).hexdigest(),
            challenge=adapter.CHALLENGE,
            version=adapter.VERSION,
            evaluation_pack_digest=snapshot.manifest_digest,
            strata=subset_evidence.bank_strata(
                adapter.CHALLENGE, adapter.VERSION, bank
            ),
            graded_inputs=graded_inputs,
            output_shape=[n_rows, width],
            recipe_digest=run.get("recipe_digest"),
            state_digest=run.get("state_digest"),
            inference_image_id=run.get("inference_image_id"),
            graded_operation=None,
        )
    except subset_evidence.SubsetRepeatRefused as exc:
        raise BreakdownRefused("pair_unavailable:" + exc.code) from exc
    return list(twins)


def _total(pack, measured):
    """``dual_score.score`` of the one measured model under the pack (the door's ScoreEngine v4 call)."""
    from carbon.scoring import dual_score
    from carbon.scoring import physical_dual_pack as physical

    gates = list(pack.get("hard_gates", []))
    _require(gates == list(measured["gates"]), "gate_contract")

    def leg(value):
        if value is None:
            return {"status": "CANDIDATE_INVALID", "value": None, "unit": "1"}
        return {"status": "RESOLVED", "value": value, "unit": "1"}

    placeholder = "sha256:" + "0" * 64
    benchmark = {
        "schema": "carbon.scoring.dual-benchmark-input.v1",
        "scope": pack["scope"],
        "challenge": CHALLENGE,
        "physics_contract_digest": pack["physics_contract_digest"],
        "measurement_contract_digest": pack["measurement_contract_digest"],
        "population_role": "P",
        "common_mask_digest": placeholder,
        "models": [
            {
                "artifact_digest": placeholder,
                "gates": {
                    k: ("PASS" if measured["gates"][k] else "FAIL") for k in gates
                },
                "measurements": {
                    physical.METRICS["A"]: leg(measured["A"]),
                    physical.METRICS["D"]: leg(measured["D"]),
                },
                "decision_outcome": measured["decision_outcome"],
            }
        ],
    }
    row = dual_score.score(benchmark, pack)["models"][0]
    legs, total, w = row["legs"], row["score"], pack["value_weight"]
    if total is not None and pack.get("combination") == "weighted_arithmetic_mean":
        _require(abs(total - ((1 - w) * legs["A"] + w * legs["D"])) <= 1e-12, "total")
    return legs.get("A"), legs.get("D"), total, w


def _menu_tasks(policies, material, record, se_d):
    """Per drawn task: the measured d, and Z / oracle re-run through `menu_score.score_task` exactly as
    `pool_menu.score` calls it (key = the installed menu key, epoch = the rule's epoch).
    """
    from carbon.scoring import menu_score, pool_menu, pool_version

    rule = policies.menu
    _require(rule is not None and rule.epoch == EPOCH, "menu_epoch_not_e1")
    key = pool_menu.active_key()
    tasks = pool_version.menu_tasks(material, rule)
    drawn = set(pool_menu.draw_tasks(rule, key, epoch=EPOCH))
    scored = [t for t in tasks if t.problem.target_id in drawn]
    measured = record["tasks"]
    _require(
        [m["task_id"] for m in measured] == [t.problem.target_id for t in scored],
        "menu_drawn_tasks_differ",
    )
    rows = []
    if record.get("state") == pool_menu.MODEL_ROW_DEPENDENT:
        for m in measured:
            _require(m["d"] == 0.0, "menu_task_d_mismatch")
            rows.append((0.0, None, None, "model_row_dependent"))
    else:
        predictions = record["predictions"]
        for task, m in zip(scored, measured, strict=True):
            result = menu_score.score_task(
                task.problem,
                task.record,
                predictions[task.problem.target_id],
                key=key,
                epoch=rule.epoch,
            )
            _require(result["d"] == m["d"], "menu_task_d_mismatch")
            rows.append(
                (m["d"], result["zero"], result["oracle"], result["zero_source"])
            )
    if se_d is not None and rows:
        _require(math.fsum(r[0] for r in rows) / len(rows) == se_d, "menu_d_mismatch")
    return [
        {"task": i, "D": float(d), "Z": z, "oracle": o, "zero_source": s}
        for i, (d, z, o, s) in enumerate(rows, start=1)
    ]


def breakdown(args, keep=None):
    """The aggregates document (unchecked against the expectations; see `main`). ``keep`` (a dict, optional) receives
    what the private grade breakdown needs: the values this same measure offered (`grade_breakdown.staged`), the exam
    key, the gates and the A / D the self-check reads."""
    from carbon.development_session import single_call_timing
    from carbon.scoring import physical_dual_pack as physical
    from carbon.scoring import (
        pool_exam,
        pool_menu,
        pool_version,
        producer_successor,
        sealed_batch_source,
    )
    from carbon.scoring import subset_repeat_produce as subset_produce

    private_root = Path(args.private_root)
    _require(
        private_root.is_absolute() and private_root.is_dir(), "private_root_invalid"
    )
    development = _arm()
    _install_menu_key(args.menu_key_file)
    snapshot = _snapshot(private_root)
    sealed = sealed_batch_source.resolve(
        challenge=CHALLENGE,
        version=VERSION,
        selected_pack=snapshot,
        private_root=private_root,
        development_adapter=development,
        copy_hotkey=args.copy_hotkey,
    )
    _require(sealed is not None, "pack_is_not_sealed")
    bank, adapter = sealed
    _require(type(adapter) is type(development), "adapter_differs")
    names = physical.input_names(adapter)
    roles, train_raw = _roles(snapshot, private_root)
    _require(type(bank.get("pool")) is dict, "pool_material_missing")
    definition = {**roles["accuracy_definition"], "pool": bank["pool"]}
    adapter.validate_definition(definition)
    _require(
        definition.get("bank_digest") == physical.bank_digest(bank), "bank_binding"
    )
    _require(
        producer_successor.binds(
            adapter.CHALLENGE,
            adapter.VERSION,
            definition.get("producer_digest"),
            physical.producer_digest(adapter),
        ),
        "producer_binding",
    )
    n_rows, width = len(bank["case_ids"]), len(bank["references"][0])
    outputs = read_predictions(_read_file(args.predictions), n_rows, width)
    twins = _twins(args.pair, snapshot, private_root, adapter, bank, n_rows, width)
    call_s, outputs_match = single_call_timing.read_side_file(
        _read_file(args.single_call)
    )
    rowcheck_raw = _read_file(args.rowcheck)
    capture = {}
    from carbon.scoring import grade_breakdown

    with pool_menu.staged_rowcheck(rowcheck_raw), grade_breakdown.staged() as stage:
        measured = subset_produce.measure_subset(
            adapter,
            outputs=outputs,
            twins=twins,
            capture=capture,
            bank_rows=physical.bank_rows(bank, names),
            definition=definition,
            limits=roles["important_limit_definition"],
            objective=roles["design_objective"],
            train_raw=train_raw,
            names=names,
            speed_call_seconds=call_s,
            speed_outputs_match=outputs_match,
        )
    pool = measured.get("pool") or {}
    gates = dict(measured["gates"])
    # the pool records agree with the gate verdicts (consistency only; never written)
    failed = pool.get("physics_failed")
    if type(failed) is list and pool_exam.PHYSICS_GATE in gates:
        _require((not failed) == bool(gates[pool_exam.PHYSICS_GATE]), "physics_gate")
    speed = pool.get("speed")
    if type(speed) is dict and pool_exam.SPEED_GATE in gates:
        passed = bool(speed.get("passed"))
        _require(passed == bool(gates[pool_exam.SPEED_GATE]), "speed_gate")
    accuracy = (pool.get("accuracy") or {}).get("gate")
    if type(accuracy) is dict and pool_exam.ACCURACY_GATE in gates:
        passed = bool(accuracy.get("passed"))
        _require(passed == bool(gates[pool_exam.ACCURACY_GATE]), "accuracy_gate")
    basis = capture.get("se_basis") or {}
    sets = []
    if not basis.get("gated", True):
        c, menu_d = basis["c"], basis.get("menu_d")
        _require(_finite(menu_d), "menu_d_missing")
        for i, a in enumerate(basis["a_sets"], start=1):
            d = min(menu_d, c)
            sets.append({"set": i, "A": float(a), "C": float(c), "D": float(d)})
    tasks = []
    if "menu" in pool:
        policies = pool_version.registered_policies(CHALLENGE, VERSION)
        tasks = _menu_tasks(
            policies, definition["pool"], pool["menu"], basis.get("menu_d")
        )
    a, d, total, w = _total(roles["score_pack"], measured)
    if keep is not None:
        keep.update(
            values=grade_breakdown.kept(stage),
            exam_key=snapshot.manifest_digest,
            gates=dict(gates),
            contract_ids={
                "physics_contract": roles["score_pack"]["physics_contract_digest"],
                "measurement_contract": roles["score_pack"][
                    "measurement_contract_digest"
                ],
            },
            halves={"A": a, "D": d},
        )
    return {
        "schema": SCHEMA,
        "challenge": CHALLENGE,
        "version": VERSION,
        "epoch": EPOCH,
        "A": a,
        "D": d,
        "total": total,
        "value_weight": w,
        "sets": sets,
        "tasks": tasks,
        "gates": {k: ("PASS" if v else "FAIL") for k, v in gates.items()},
        "menu_tasks_scored": len(tasks),
    }


def _parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--menu-key-file", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--rowcheck", required=True)
    parser.add_argument("--single-call", required=True)
    parser.add_argument("--pair", default=None)
    parser.add_argument("--copy-hotkey", default=None)
    parser.add_argument("--expect-a", type=float, required=True)
    parser.add_argument("--expect-d", type=float, required=True)
    parser.add_argument("--expect-total", type=float, required=True)
    parser.add_argument("--out", required=True)
    # the private grade breakdown of the SAME recompute (king card source "recomputed"): the graded task's id and the
    # lane its single calls were timed on (its grade_lane line: "local" or the lane's docker host)
    parser.add_argument("--task", default=None)
    parser.add_argument("--speed-lane", default=None)
    return parser


def grade_breakdown_document(args, keep):
    """The checked private grade breakdown of this recompute (`grade_breakdown` schema), written only after the
    self-check matched."""
    from carbon.scoring import grade_breakdown

    values = keep["values"] or {}
    speed = values.get("speed")
    return grade_breakdown.breakdown(
        challenge_id=CHALLENGE,
        challenge_version=VERSION,
        submission_id=args.task,
        exam_key=keep["exam_key"],
        contract_ids=keep["contract_ids"],
        sets=values.get("sets", {}),
        tasks=values.get("tasks", []),
        rule_flags={k: bool(v) for k, v in keep["gates"].items()},
        halves=keep["halves"],
        outputs=values.get("outputs"),
        speed=None if speed is None else {**speed, "lane": args.speed_lane},
    )


def _code(exc):
    code = getattr(exc, "code", None)
    if type(code) is str and _CODE.fullmatch(code):
        return code
    return type(exc).__name__


def main(argv=None):
    args = _parser().parse_args(argv)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    keep = {}
    try:
        out = _private_out_dir(args.out)
        doc = breakdown(args, keep)
    except Exception as exc:  # noqa: BLE001 - a typed code only, never a message
        print("refused:" + _code(exc))
        return 3
    try:
        _self_check(
            doc,
            {"A": args.expect_a, "D": args.expect_d, "total": args.expect_total},
        )
    except SelfCheckFailed:
        print(json.dumps({"A": doc["A"], "D": doc["D"], "total": doc["total"]}))
        print("self_check_failed")
        return 2
    try:
        digest = _write_once(out, doc)
        kept = None
        if args.task is not None:
            from carbon.scoring import grade_breakdown

            kept = grade_breakdown.write(out, grade_breakdown_document(args, keep))
    except Exception as exc:  # noqa: BLE001 - a typed code only, never a message
        print("refused:" + _code(exc))
        return 3
    print(digest)
    if kept is not None:
        print(kept.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
