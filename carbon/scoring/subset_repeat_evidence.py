"""The subset repeat: one fresh run of the sealed cells and a secret sample of the other graded rows (Motor 1.8 only).

The owner, Sun 15 Nov 2026 08:19 CST (the Lead session): replace Motor 1.8's two full-bank inference-pair passes with
a keyed subset repeat, as the SAME version (pack and exam key unchanged); and 08:38 CST: "66 rows. But we need a % that
generalizes for challenges". CV-Motor-B's rulings (board, Sun 15 Nov) and Validator-2B's R-1..R-5 bind it
(docs/records/2026-11-15-motor18-subset-repeat.json):

- After the graded predictions are committed, the host re-runs, in ONE fresh worker process (same image, state and
  inputs), ALL the graded bank's sealed cells (Q1 = B) plus, INDEPENDENTLY inside EACH registered stratum, ``k`` rows
  drawn uniformly over that stratum (owner, Sun 15 Nov ~09:5x CST: "Yes for 66 per stratum"), each by a per-GRADE,
  per-stratum secret key (HMAC of the grading host's K_speed under this module's own domain tag, the submission id and
  the stratum, so independent of the speed sample and of each other). It is kept write-once beside the dual measurement as a
  host-private side file. The rows and the key never reach any public or miner surface.
- ``k`` is derived from the version's registered PROMISE (`registered_promise`): with ``f`` the fraction of rows a model
  may answer differently on a repeat and ``P`` the probability the repeat must catch it, ``k = min(ceil(ln(1 - P) /
  ln(1 - f)), the stratum's rows)``. The strata are the promise's ``strata`` (graded-bank cohort labels named by
  CV-Motor). An absent, null or malformed promise, or a null, malformed or unknown stratum, fails closed (the receiver
  will not serve; a grade is Carbon's typed unavailable), never "no repeat".
- The scorer reads the side file (`read`) into one value per graded bank row: the fresh answer on a repeated row, None
  on every row that is not repeat-checked. Each fresh answer must equal the graded answer BIT FOR BIT over the whole row
  (`rows_agree`, Q2). Missing or inconsistent evidence is typed unavailable (`SubsetRepeatRefused`), never a candidate
  verdict; a malformed or non-finite fresh answer is read as such and fails the exact check (the candidate's).

`SUBSET_REPEAT_VERSIONS` is the ONE registry of the versions graded this way: the door and the scorer both read it.
This module is a producer file of Motor 1.8 only (`motor18_dual_pack.FILES`); no other version's producer identity
covers it.
"""

from __future__ import annotations

import hashlib
import hmac
import itertools
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

#: The versions whose repeat is the keyed subset repeat (every other version keeps the full pair, unchanged).
SUBSET_REPEAT_VERSIONS = frozenset({("electric-motor-magnetics", "1.8")})
#: Each subset version's producer module (its `physical_dual_pack.producer_digest` identity, checked at receiver start).
PRODUCERS = {("electric-motor-magnetics", "1.8"): "carbon.scoring.motor18_dual_pack"}
#: The side file's schema.
SCHEMA = "carbon.scoring.subset-repeat-evidence.v1"
#: The run inside it (`paired_inference.infer_frozen_once`).
RUN_SCHEMA = "carbon.source-free-inference-repeat.v1"
#: The host values file of the owner's promise per version (public rule values; never a drawn row or a key).
VALUES_SCHEMA = "carbon.exam.subset-repeat.v1"
VALUES_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "validator_host_classes"
    / "subset_repeat.json"
)
_PROMISE_KEYS = {"repeat_fail_fraction", "repeat_detect_prob", "strata"}
#: The sealed grid's cohort label (`sealed_grid_common.GRID_COHORT`; a test holds them equal): its rows are all
#: re-run every grade, so it is never a keyed stratum.
SEALED_COHORT = "decision_sealed_grid"
#: The per-grade key's domain tag (the speed sample's is ``carbon.speed-sample/1``: the two draws are independent).
DOMAIN = b"carbon.subset-repeat/1"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_OPERATION = re.compile(r"operation-[0-9a-f]{64}\Z")
_DOCUMENT = {
    "schema",
    "challenge",
    "challenge_version",
    "evaluation_pack_digest",
    "submission_id",
    "n_rows",
    "sealed_positions",
    "keyed_positions",
    "k",
    "lanes",
    "run",
    "scientific_qualification",
    "official_eligible",
}
_RUN = {
    "schema",
    "execution_boundary",
    "recipe_digest",
    "state_digest",
    "inputs_digest",
    "inference_image_id",
    "logical_prediction_rows",
    "elapsed_seconds",
    "repeat",
    "scientific_qualification",
    "official_eligible",
}
_RECEIPT = {
    "schema",
    "recipe_digest",
    "state_digest",
    "inputs_digest",
    "predictions_digest",
}


class SubsetRepeatRefused(ValueError):
    """Unavailable or inconsistent subset-repeat material: Carbon's gap, never a candidate verdict."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(ok, code):
    if not ok:
        raise SubsetRepeatRefused(code)


def is_subset_version(challenge, version) -> bool:
    return (challenge, version) in SUBSET_REPEAT_VERSIONS


# -- the promise and k --------------------------------------------------------------------------------------------------


def _probability(value):
    """A JSON number strictly between 0 and 1 (a float: 0 and 1 are the only integers in range, and both are out)."""
    return type(value) is float and math.isfinite(value) and 0.0 < value < 1.0


def _promise_row(challenge, version, path):
    try:
        document = json.loads(Path(VALUES_PATH if path is None else path).read_bytes())
    except (OSError, ValueError) as exc:
        raise SubsetRepeatRefused("subset_repeat_promise_unregistered") from exc
    rows = document.get("rows") if type(document) is dict else None
    row = rows.get(f"{challenge} {version}") if type(rows) is dict else None
    _require(
        type(document) is dict
        and document.get("schema") == VALUES_SCHEMA
        and set(document) == {"schema", "rows"}
        and type(row) is dict
        and set(row) == _PROMISE_KEYS
        and _probability(row["repeat_fail_fraction"])
        and _probability(row["repeat_detect_prob"]),
        "subset_repeat_promise_unregistered",
    )
    return row


def registered_rate(challenge, version, *, path=None):
    """``(repeat_fail_fraction, repeat_detect_prob)`` alone (a count tool needs no strata): each a JSON number strictly
    between 0 and 1 (finite, never a bool), else ``subset_repeat_promise_unregistered``.
    """
    row = _promise_row(challenge, version, path)
    return row["repeat_fail_fraction"], row["repeat_detect_prob"]


def registered_promise(challenge, version, *, path=None):
    """``(repeat_fail_fraction, repeat_detect_prob, strata)`` registered for ``"<challenge> <version>"``.

    ``f`` and ``P`` as `registered_rate`; ``strata`` (owner, Sun 15 Nov ~09:5x CST: "Yes for 66 per stratum"; the names
    are CV-Motor-B's, defined in code by `STRATA`) is a non-empty list of distinct names, never the sealed grid's (its
    rows are all re-run). An absent file or row, a null or malformed value, or any other key refuses (fail closed):
    ``subset_repeat_promise_unregistered``, or ``subset_repeat_strata_unregistered`` for the strata alone.
    """
    row = _promise_row(challenge, version, path)
    strata = row["strata"]
    _require(
        type(strata) is list
        and bool(strata)
        and all(type(name) is str and bool(name) for name in strata)
        and len(set(strata)) == len(strata)
        and SEALED_COHORT not in strata,
        "subset_repeat_strata_unregistered",
    )
    return row["repeat_fail_fraction"], row["repeat_detect_prob"], list(strata)


def derived_k(fail_fraction, detect_prob, n_rows):
    """The fewest uniformly drawn rows that catch, with probability at least ``detect_prob``, a model that answers a
    ``fail_fraction`` of the rows differently on a repeat (sampling with replacement bounds it from above), capped at
    the stratum's rows: ``min(ceil(ln(1 - P) / ln(1 - f)), n_rows)``."""
    _require(
        _probability(fail_fraction)
        and _probability(detect_prob)
        and type(n_rows) is int
        and not isinstance(n_rows, bool)
        and n_rows >= 1,
        "subset_repeat_promise_unregistered",
    )
    need = math.ceil(math.log1p(-detect_prob) / math.log1p(-fail_fraction))
    return max(1, min(need, n_rows))


# -- the strata ----------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Stratum:
    """One stratum of a subset version's graded bank: where its rows come from (``source``, ``selector``), whether every
    row is re-run (``every``) or ``min(k, n)`` keyed rows, and, for a registered gate set, its registered size ``n``.
    """

    source: str  # "cohort" | "coverage_class" | "in_range_outputs" | "menu_task"
    selector: object
    every: bool = False
    n: int | None = None


#: The torque outputs and the open-circuit output of Motor 1.8's in-range gate case sets (pool_constants physics
#: gate_threshold): a case of the registered in-range case set (``in_range_cases_sha256``) belongs to the torque gate
#: set when its truths are exactly the torque outputs, and to the OC gate set when they are exactly the OC output.
_TORQUE_GATE = ("mean_torque_nm", "ripple_pk_pk_nm")
_OC_GATE = ("back_emf_open_circuit",)

#: Each subset version's strata (CV-Motor-B, Sun 15 Nov, after the owner's "Yes for 66 per stratum"). The sealed grid's
#: cells are always ALL re-run and are no stratum here. Every other graded row must land in exactly ONE stratum:
#: - ``probe_response``: the bank's probe rows (their cohort);
#: - ``H-1`` / ``H-3a`` / ``H-3b``: pool rows of the targets the REGISTERED coverage plan (``coverage_plan_sha256``,
#:   vocabulary ``coverage_class_vocabulary``) puts in that class;
#: - ``gate_torque_7d1761c3`` / ``gate_oc_697a0d7b``: ALL rows of the registered in-range case set's torque gate cases
#:   (gate set 7d1761c3, n 23) and open-circuit gate cases (gate set 697a0d7b, n 24) (pool_constants record);
#: - ``menu_D3`` .. ``menu_D6``: the menu rows (design x duty) of each registered menu task.
#: Sources and sizes are the registered ones (pool_constants), read and checked at every build; nothing here is a value.
STRATA = {
    ("electric-motor-magnetics", "1.8"): {
        "probe_response": Stratum("cohort", "probe_response"),
        "H-1": Stratum("coverage_class", "H-1"),
        "H-3a": Stratum("coverage_class", "H-3a"),
        "H-3b": Stratum("coverage_class", "H-3b"),
        "gate_torque_7d1761c3": Stratum("in_range_outputs", _TORQUE_GATE, True, 23),
        "gate_oc_697a0d7b": Stratum("in_range_outputs", _OC_GATE, True, 24),
        **{
            f"menu_{task}": Stratum("menu_task", task)
            for task in ("D3", "D4", "D5", "D6")
        },
    }
}


@dataclass(frozen=True)
class BankStrata:
    """One graded bank split into its strata: ``sealed`` positions (all re-run), ``members`` {stratum: positions} and the
    strata re-run in full (``every``)."""

    sealed: tuple
    members: dict
    every: frozenset


def definitions(challenge, version):
    """The code-defined strata of a subset version, or a typed refusal."""
    found = STRATA.get((challenge, version))
    _require(found is not None, "subset_repeat_strata_undefined")
    return found


def _pool_key(kind, names):
    def key(row):
        return tuple(float(kind.type(row[name])) for name in names)

    return key


def _pool_sources(challenge, version, bank, defined):
    """``{(source, selector): {quantised pool row}}`` for every pool-row stratum source, from the bank's carried pool
    material, each checked against its registration (coverage plan and sums, in-range case set, menu records).
    """
    import numpy as np

    from carbon.scoring import (
        pool_exam,
        pool_grader,
        pool_menu,
        pool_physics_score,
        pool_version,
    )

    wanted = {(d.source, d.selector) for d in defined.values() if d.source != "cohort"}
    if not wanted:
        return {}, None
    material = bank.get("pool") if type(bank) is dict else None
    try:
        pool_version.check_material(material)
        names, design_names = material["input_names"], material["design_names"]
        kind = np.dtype(material["input_dtype"])
        key = _pool_key(kind, names)
        policies = pool_version.registered_policies(challenge, version)
        sets = tuple(
            tuple(pool_grader.load_pool(document) for document in group)
            for group in material["sets"]
        )
        sources = {source: set() for source in wanted}
        if any(source == "coverage_class" for source, _ in wanted):
            plan = pool_exam.attach_coverage_plan(
                policies,
                material.get(pool_version.COVERAGE_PLAN),
                material.get(pool_version.COVERAGE_PLAN_SUMS),
                sets,
            ).optimizer.coverage_plan
            _require(plan is not None, "subset_repeat_coverage_plan_unregistered")
            for group in sets:
                for spec in group:
                    bucket = sources.get(
                        ("coverage_class", plan.class_of(spec.target_id))
                    )
                    if bucket is None:
                        continue
                    fixed = spec.conditions["fixed"]
                    for design in spec.designs:
                        bucket.add(
                            key(
                                {
                                    **fixed,
                                    **dict(zip(design_names, design, strict=True)),
                                }
                            )
                        )
        if any(source == "in_range_outputs" for source, _ in wanted):
            registered = getattr(policies.physics, "in_range_cases_sha256", None)
            cases = pool_physics_score.in_range_cases(
                material.get(pool_version.IN_RANGE_CASES)
            )
            _require(
                registered is not None and cases.sha256 == registered,
                "subset_repeat_in_range_cases_unregistered",
            )
            for _class, inputs, truths, _u in cases.cases:
                bucket = sources.get(("in_range_outputs", tuple(sorted(truths))))
                if bucket is not None:
                    bucket.add(key(inputs))
        if any(source == "menu_task" for source, _ in wanted):
            tasks = pool_version.menu_tasks(
                material, pool_version.registered_menu(challenge, version)
            )
            _require(tasks is not None, "subset_repeat_menu_unregistered")
            for task in tasks:
                bucket = sources.get(("menu_task", task.problem.target_id))
                if bucket is not None:
                    bucket.update(
                        key(row) for row in pool_menu.task_rows(task, design_names)[0]
                    )
    except SubsetRepeatRefused:
        raise
    except Exception as exc:
        # any fault of the sealed material is Carbon's, typed
        raise SubsetRepeatRefused("subset_repeat_strata_material") from exc
    return sources, key


def census(challenge, version, bank):
    """Counts only: ``{"sealed": n, "strata": {name: n}, "overlaps": {"a+b": n}, "none": n}`` of one graded bank under the
    version's code-defined strata. A row in two strata is counted under ``overlaps`` (never resolved), a row in none
    under ``none``; neither is in any stratum's ``n``."""
    import numpy as np

    defined = definitions(challenge, version)
    try:
        cohorts = list(bank["cohorts"])
        inputs = np.asarray(bank["inputs"])
        _require(len(inputs) == len(cohorts), "subset_repeat_bank_shape")
    except (KeyError, TypeError) as exc:
        raise SubsetRepeatRefused("subset_repeat_bank_shape") from exc
    sources, key = _pool_sources(challenge, version, bank, defined)
    names = list(bank["pool"]["input_names"]) if key is not None else None
    members = {name: [] for name in defined}
    overlaps, none, sealed = {}, [], []
    for i, cohort in enumerate(cohorts):
        if cohort == SEALED_COHORT:
            sealed.append(i)
            continue
        hits = [
            name
            for name, d in defined.items()
            if d.source == "cohort" and d.selector == cohort
        ]
        if key is not None and cohort != "probe_response":
            row = key(dict(zip(names, inputs[i], strict=True)))
            hits += [
                name
                for name, d in defined.items()
                if d.source != "cohort" and row in sources[(d.source, d.selector)]
            ]
        if len(hits) == 1:
            members[hits[0]].append(i)
        elif hits:
            label = "+".join(sorted(hits))
            overlaps[label] = overlaps.get(label, 0) + 1
        else:
            none.append(i)
    return {
        "sealed": sealed,
        "members": members,
        "overlaps": overlaps,
        "none": none,
    }


def bank_strata(challenge, version, bank):
    """The graded bank split into the version's strata, or a typed refusal: a row in TWO strata
    (``subset_repeat_row_in_two_strata``) or in NONE (``subset_repeat_row_in_no_stratum``), no sealed cells, an empty
    stratum, or a registered gate set of another size (``subset_repeat_gate_set_size``).
    """
    defined = definitions(challenge, version)
    counted = census(challenge, version, bank)
    _require(not counted["overlaps"], "subset_repeat_row_in_two_strata")
    _require(not counted["none"], "subset_repeat_row_in_no_stratum")
    _require(bool(counted["sealed"]), "subset_repeat_bank_strata")
    for name, d in defined.items():
        _require(bool(counted["members"][name]), "subset_repeat_stratum_empty")
        _require(
            d.n is None or len(counted["members"][name]) == d.n,
            "subset_repeat_gate_set_size",
        )
    return BankStrata(
        sealed=tuple(counted["sealed"]),
        members={name: tuple(rows) for name, rows in counted["members"].items()},
        every=frozenset(name for name, d in defined.items() if d.every),
    )


def registered_counts(challenge, version, strata, *, path=None):
    """``{stratum: k}`` of one graded bank: ``n`` for a stratum re-run in full, else ``min(k, n)`` with ``k`` from the
    registered promise. The promise must name exactly the version's strata (``subset_repeat_stratum_unknown`` for a
    name the code does not define, ``subset_repeat_strata_unregistered`` for a missing one).
    """
    fail_fraction, detect_prob, names = registered_promise(
        challenge, version, path=path
    )
    _require(set(names) <= set(strata.members), "subset_repeat_stratum_unknown")
    _require(set(names) == set(strata.members), "subset_repeat_strata_unregistered")
    return {
        name: (
            len(strata.members[name])
            if name in strata.every
            else derived_k(fail_fraction, detect_prob, len(strata.members[name]))
        )
        for name in names
    }


# -- the identities -----------------------------------------------------------------------------------------------------


def run_identity(evaluation_pack_digest, submission_id, *, retry=False):
    """The identity the door gives one subset repeat (its wall retry adds ``-wall-retry``)."""
    return (
        "subset-repeat-"
        + evaluation_pack_digest
        + "-"
        + submission_id
        + ("-wall-retry" if retry else "")
    )


def ledger_identity(identity):
    """The ledger child of a run identity (`paired_inference.repeat_identity`, the same formula; a test holds them
    equal)."""
    return "subset-repeat-" + hashlib.sha256(identity.encode()).hexdigest()


# -- the draw -----------------------------------------------------------------------------------------------------------


def grade_key(k_speed, submission_id, stratum):
    """The per-grade, per-stratum draw key: HMAC-SHA256(K_speed, DOMAIN || 0x00 || submission id || 0x00 || stratum),
    so every stratum's draw is independent of every other's. Custody's, never the miner's.
    """
    _require(
        type(k_speed) is bytes
        and len(k_speed) >= 32
        and type(submission_id) is str
        and bool(submission_id)
        and type(stratum) is str
        and bool(stratum),
        "subset_repeat_key_unavailable",
    )
    message = b"\x00".join(
        [DOMAIN, submission_id.encode("utf-8"), stratum.encode("utf-8")]
    )
    return hmac.new(k_speed, message, hashlib.sha256).digest()


def _uniform(key):
    """Uniform integers below a bound, from HMAC-SHA256(key, counter) blocks, by rejection (no modulo bias)."""
    counter = 0

    def below(bound):
        nonlocal counter
        limit = (2**64 // bound) * bound
        while True:
            block = hmac.new(
                key, b"draw\x00" + counter.to_bytes(8, "big"), hashlib.sha256
            ).digest()
            counter += 1
            for start in range(0, 32, 8):
                value = int.from_bytes(block[start : start + 8], "big")
                if value < limit:
                    return value % bound

    return below


def keyed_sample(key, candidates, k):
    """``k`` distinct members of ``candidates``, uniformly (a keyed partial Fisher-Yates shuffle), ascending."""
    rows = list(candidates)
    _require(
        type(key) is bytes
        and len(key) == 32
        and type(k) is int
        and 1 <= k <= len(rows),
        "subset_repeat_draw_invalid",
    )
    below = _uniform(key)
    for i in range(k):
        j = i + below(len(rows) - i)
        rows[i], rows[j] = rows[j], rows[i]
    return sorted(rows[:k])


def plan(k_speed, submission_id, *, challenge, version, strata):
    """``(sealed, {stratum: positions})`` of one grade's repeat: ALL the sealed cells (CV-Motor-B, Q1 = B), every row of a
    stratum re-run in full, and, INDEPENDENTLY inside each other stratum, ``min(k, n)`` keyed rows (owner, "Yes for 66
    per stratum"), each drawn under its own per-stratum key."""
    counts = registered_counts(challenge, version, strata)
    keyed = {
        name: (
            list(strata.members[name])
            if name in strata.every
            else keyed_sample(
                grade_key(k_speed, submission_id, name), strata.members[name], k
            )
        )
        for name, k in counts.items()
    }
    return list(strata.sealed), keyed


def positions_of(sealed, keyed):
    """Every repeated row, ascending: the order the fresh run answered them in."""
    return sorted({*sealed, *(p for rows in keyed.values() for p in rows)})


# -- the side file ------------------------------------------------------------------------------------------------------


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")


def side_file(
    *,
    challenge,
    version,
    evaluation_pack_digest,
    submission_id,
    n_rows,
    sealed,
    keyed,
    run,
    lanes=None,
):
    """The host-private side file of one subset repeat (canonical JSON bytes). ``keyed`` is ``{stratum: positions}``.
    The run answered the graded rows `rerun_rows` names: for a vmap-64 version (``lanes`` = the model's L) the ORIGINAL
    chunks holding every drawn row, else the drawn rows (`positions_of`) themselves, in that order.
    """
    return canonical(
        {
            "schema": SCHEMA,
            "challenge": challenge,
            "challenge_version": version,
            "evaluation_pack_digest": evaluation_pack_digest,
            "submission_id": submission_id,
            "n_rows": n_rows,
            "sealed_positions": list(sealed),
            "keyed_positions": {name: list(rows) for name, rows in keyed.items()},
            "k": {name: len(rows) for name, rows in keyed.items()},
            "lanes": lanes,
            "run": run,
            "scientific_qualification": False,
            "official_eligible": False,
        }
    )


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def rerun_rows(challenge, version, positions, n_rows, lanes):
    """``(queried rows, where)``: the graded rows a subset repeat's fresh run answers, in order, and the index of each
    drawn position's answer in it. A vmap-64 version (`direct_graph_construction_worker.VMAP64_INFERENCE_VERSIONS`)
    graded each row in an isolated lane of a chunk of the model's L lanes, bit for bit only beside the same companions
    and padding, so its run is the ORIGINAL chunks (`vmap64_rerun_rows` at ``lanes``, which must be its L); every
    other version runs the drawn rows themselves (``lanes`` None)."""
    from carbon.development_session.direct_graph_construction_worker import (
        VMAP64_INFERENCE_VERSIONS,
        VMAP64_LANES,
        vmap64_rerun_rows,
    )

    if (challenge, version) in VMAP64_INFERENCE_VERSIONS:
        _require(
            type(lanes) is int
            and not isinstance(lanes, bool)
            and 1 <= lanes <= VMAP64_LANES,
            "subset_repeat_lanes",
        )
        try:
            queried, where = vmap64_rerun_rows(list(positions), n_rows, lanes)
        except ValueError as exc:
            raise SubsetRepeatRefused("subset_repeat_lanes") from exc
        return list(queried), list(where)
    _require(lanes is None, "subset_repeat_lanes")
    return list(positions), list(range(len(positions)))


def _ascending(values, n_rows):
    return (
        type(values) is list
        and all(type(p) is int and 0 <= p < n_rows for p in values)
        and all(a < b for a, b in itertools.pairwise(values))
    )


def _answers(raw, rows, rest):
    """The fresh answers, one per repeated row, as flat tuples of floats (non-finite values kept, so the exact check
    fails them), or ``()`` for a row that is not one answer of the registered shape. Never refuses: a malformed fresh
    answer is the candidate's (CV-Motor-B, Q2)."""

    def flat(value, shape):
        if not shape:
            if type(value) in (int, float) and not isinstance(value, bool):
                return [float(value)]
            return None
        if type(value) is not list or len(value) != shape[0]:
            return None
        out = []
        for item in value:
            part = flat(item, shape[1:])
            if part is None:
                return None
            out.extend(part)
        return out

    try:
        parsed = json.loads(raw.decode("utf-8"), parse_constant=float)
    except (UnicodeError, ValueError, RecursionError, OverflowError):
        return [()] * rows
    if type(parsed) is not list or len(parsed) != rows:
        return [()] * rows
    answers = []
    for value in parsed:
        try:
            row = flat(value, rest)
        except (RecursionError, OverflowError):
            # (a JSON integer too large for a float is a malformed answer, the candidate's)
            row = None
        answers.append(() if row is None else tuple(row))
    return answers


def rows_agree(graded, fresh):
    """The subset repeat's decisive rule (CV-Motor-B, Q2): the fresh answer equals the graded answer BIT FOR BIT over the
    whole row. A different value (``0.0`` and ``-0.0`` differ), a non-finite or missing value, or a row of another
    width disagrees."""
    if fresh is None or len(fresh) != len(graded):
        return False
    return all(
        type(b) is float and math.isfinite(b) and float(a).hex() == b.hex()
        for a, b in zip(graded, fresh, strict=True)
    )


#: The carrier's own ceiling on a worker's predictions file (`bundle_construction_worker._infer_state`): every answer
#: the carrier accepted is read, so a large or malformed answer is judged, never turned into Carbon's gap.
_ANSWER_BYTES = 16 * 1024**2


def read(
    raw,
    *,
    registered_sha256,
    challenge,
    version,
    evaluation_pack_digest,
    strata,
    graded_inputs,
    output_shape,
    recipe_digest,
    state_digest,
    inference_image_id,
    graded_operation,
):
    """The fresh answer per graded bank row: a tuple on a repeated row (``()`` when it is no answer of the registered
    shape; non-finite values kept), None on every row that is not repeat-checked.

    The side file must be exactly the registered bytes and bind this grade: the served version and evaluation pack;
    ALL the bank's sealed cells plus, in each registered stratum of ``strata`` (`bank_strata`), exactly its registered
    count (`registered_counts`) of distinct rows of that stratum (every row of a stratum re-run in full); the graded run's recipe, state and image; inputs that are exactly the graded query's rows at those
    positions; and ONE settled operation that is not the graded one, under the ledger identity the door gives this
    submission's repeat (or its wall retry). ``output_shape`` is the graded query's full output shape. Anything else
    refuses, typed (Carbon's gap, never a verdict)."""
    import numpy as np

    from carbon.development_session.bundle_construction_worker import _tensors
    from carbon.scoring import inference_pair_evidence as pair

    try:
        n_rows = int(output_shape[0])
        rest = [int(v) for v in output_shape[1:]]
        width = math.prod(rest)
    except (TypeError, ValueError, IndexError) as exc:
        raise SubsetRepeatRefused("subset_repeat_expected_shape") from exc
    limit = 4 * (_ANSWER_BYTES + pair._MAX_RECEIPT) // 3 + 2 * 1024**2
    _require(
        type(registered_sha256) is str
        and _DIGEST.fullmatch(registered_sha256) is not None,
        "subset_repeat_registered_digest",
    )
    _require(
        type(raw) is bytes and 0 < len(raw) <= limit, "subset_repeat_evidence_bytes"
    )
    _require(_sha(raw) == registered_sha256, "subset_repeat_registered_digest")
    _require(
        type(strata) is BankStrata
        and len(strata.sealed) + sum(len(r) for r in strata.members.values()) == n_rows,
        "subset_repeat_expected_shape",
    )
    try:
        document = pair._parse(raw, limit, "subset_repeat")
        _require(
            type(document) is dict
            and set(document) == _DOCUMENT
            and canonical(document) == raw,
            "subset_repeat_shape",
        )
        submission = document["submission_id"]
        _require(
            document["schema"] == SCHEMA
            and document["challenge"] == challenge
            and document["challenge_version"] == version
            and is_subset_version(challenge, version)
            and document["evaluation_pack_digest"] == evaluation_pack_digest
            and type(submission) is str
            and bool(submission)
            and document["scientific_qualification"] is False
            and document["official_eligible"] is False,
            "subset_repeat_identity",
        )
        sealed, keyed, k = (
            document["sealed_positions"],
            document["keyed_positions"],
            document["k"],
        )
        counts = registered_counts(challenge, version, strata)
        _require(
            document["n_rows"] == n_rows
            and bool(strata.sealed)
            and sealed == list(strata.sealed)
            and type(keyed) is dict
            and set(keyed) == set(counts)
            and k == counts
            and all(
                _ascending(keyed[name], n_rows)
                and len(keyed[name]) == counts[name]
                and set(keyed[name]) <= set(strata.members[name])
                for name in counts
            ),
            "subset_repeat_positions",
        )
        positions = positions_of(sealed, keyed)
        queried, where = rerun_rows(
            challenge, version, positions, n_rows, document["lanes"]
        )
        run = document["run"]
        _require(type(run) is dict and set(run) == _RUN, "subset_repeat_run_shape")
        subset = np.ascontiguousarray(np.asarray(graded_inputs)[queried])
        _require(
            run["schema"] == RUN_SCHEMA
            and run["execution_boundary"] == "C03_DOCKER"
            and run["scientific_qualification"] is False
            and run["official_eligible"] is False
            and run["recipe_digest"] == recipe_digest
            and run["state_digest"] == state_digest
            and run["inference_image_id"] == inference_image_id
            and run["inputs_digest"] == _sha(_tensors(inputs=subset))
            and type(run["logical_prediction_rows"]) is int
            and run["logical_prediction_rows"] == len(queried)
            and type(run["elapsed_seconds"]) in (int, float)
            and math.isfinite(run["elapsed_seconds"])
            and run["elapsed_seconds"] >= 0,
            "subset_repeat_binding",
        )
        phase = run["repeat"]
        _require(
            type(phase) is dict
            and set(phase)
            == {"worker_operation", "controls_digest", "originals", "accounting"},
            "subset_repeat_phase_shape",
        )
        operation = phase["worker_operation"]
        _require(
            type(operation) is str
            and _OPERATION.fullmatch(operation) is not None
            and operation != graded_operation
            and type(phase["controls_digest"]) is str
            and _DIGEST.fullmatch(phase["controls_digest"]) is not None,
            "subset_repeat_not_independent",
        )
        originals = phase["originals"]
        _require(
            type(originals) is dict
            and set(originals) == {"predictions.json", "receipt.json"},
            "subset_repeat_originals_shape",
        )
        predictions_raw = pair._original(originals["predictions.json"], _ANSWER_BYTES)
        receipt_raw = pair._original(originals["receipt.json"], pair._MAX_RECEIPT)
        receipt = pair._parse(receipt_raw, pair._MAX_RECEIPT, "receipt")
        _require(
            type(receipt) is dict
            and set(receipt) == _RECEIPT
            and receipt["schema"] == "carbon.development.bundle-inference.v1"
            and receipt["recipe_digest"] == recipe_digest
            and receipt["state_digest"] == state_digest
            and receipt["inputs_digest"] == run["inputs_digest"]
            and receipt["predictions_digest"] == _sha(predictions_raw),
            "subset_repeat_receipt_binding",
        )
        accounting = phase["accounting"]
        ledger = accounting.get("ledger_identity") if type(accounting) is dict else None
        _require(
            ledger
            in {
                ledger_identity(
                    run_identity(evaluation_pack_digest, submission, retry=retry)
                )
                for retry in (False, True)
            },
            "subset_repeat_accounting_identity",
        )
        pair._accounting(accounting, ledger, operation, originals)
    except pair.PairEvidenceRefused as exc:
        code = (
            exc.code
            if exc.code.startswith("subset_repeat")
            else "subset_repeat_" + exc.code
        )
        raise SubsetRepeatRefused(code) from exc
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        if isinstance(exc, SubsetRepeatRefused):
            raise
        raise SubsetRepeatRefused("subset_repeat_evidence_unreadable") from exc
    answers = _answers(predictions_raw, len(queried), rest)
    twins = [None] * n_rows
    # only the drawn rows are repeat-checked; a re-run chunk's other rows are read but never judged
    for position, index in zip(positions, where, strict=True):
        twins[position] = answers[index]
    del width
    return twins


__all__ = [
    "DOMAIN",
    "PRODUCERS",
    "RUN_SCHEMA",
    "SCHEMA",
    "SEALED_COHORT",
    "STRATA",
    "SUBSET_REPEAT_VERSIONS",
    "VALUES_PATH",
    "VALUES_SCHEMA",
    "BankStrata",
    "Stratum",
    "SubsetRepeatRefused",
    "bank_strata",
    "census",
    "definitions",
    "derived_k",
    "grade_key",
    "is_subset_version",
    "keyed_sample",
    "ledger_identity",
    "plan",
    "positions_of",
    "read",
    "registered_counts",
    "registered_promise",
    "registered_rate",
    "rerun_rows",
    "rows_agree",
    "run_identity",
    "side_file",
]
