"""A pool-graded version's adapter: the Challenge's sealed v2 adapter with the pool measure (M2).

`PoolVariant` is a `physical_dual_pack.Variant` of the Challenge's sealed adapter whose `measure` is
`pool_exam.measure_pool` around the Challenge's own sealed `measure`, so `physical_dual_pack.produce` and the dual
`score` are unchanged. Its registered mandatory gates are the sealed grader's native ones plus `physics_pool` and
`speed`.

Exam material (M3, built in custody from the signed Phase-1 set): the sealed pack's bank carries the pool rows as
cohort `pool_design` (inputs only), and its `definition` carries the pools' truths under the key `pool`:
`{"sets": [[<carbon.pool.v1 document>, ...], ...]}`. The definition is private to the grading host.

The owner's constants (B, s_h, the honesty reduction, the A and A_gen scales, how A_gen enters A) are read from
`scripts/validator_host_classes/pool_constants.json`, where each is HUMAN_INPUT until the owner picks it from the per-Challenge owner sheet. A
version with any HUMAN_INPUT refuses to grade: no default, never a guess.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from carbon.scoring import physical_dual_pack as physical
from carbon.scoring import pool_adapters, pool_exam, pool_grader
from carbon.scoring import pool_proof_suite as suite
from carbon.scoring.probe_design import POOL_COHORT

#: Outside `carbon/` (beside the host-class records): the worker image's source digest is the git listing of the build
#: inputs, `carbon/` among them, so an owner-constant write inside it would move the image id and every pack bound to it.
#: Only the host reads it (registered_policies / registered_a_multiplier at grade time); no worker module does.
CONSTANTS = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "validator_host_classes"
    / "pool_constants.json"
)
SCHEMA = "carbon.pool.constants.v1"
HUMAN_INPUT = "HUMAN_INPUT"
POOL_KEY = "pool"
#: Optional material field: per-probe-group reference slopes a version anchors one response input on (F02 2.5).
RESPONSE_REFERENCE = "response_reference"
#: Optional material fields, NEW versions only, both or neither: the coverage-plan class map (`pool_grader.coverage_plan`
#: document) whose sha256 the version's constants register as ``coverage_plan_sha256``, and the coverage plan package's
#: SHA256SUMS text (registered as ``coverage_plan_sums_sha256``) that must list it. Custody: the map names targets.
COVERAGE_PLAN = "coverage_plan"
COVERAGE_PLAN_SUMS = "coverage_plan_sums"
#: Optional material field, NEW versions with a ``variant_rule`` only: ``{target_id: [{"start": [...], "seed": int}, ...]}``,
#: one private start and seed per `pool_grader.variant_slots` slot of each target, derived in custody like the targets'
#: own. Custody: it names targets.
VARIANT_STARTS = "variant_starts"
#: Optional material field, NEW versions with a registered ``physics`` rule only: the scoring-cell document
#: (`pool_physics_score.cell_map`) whose sha256 the rule registers. Custody: it names classes.
SCORING_CELLS = "scoring_cells"
#: Optional material field, NEW versions whose physics rule registers ``in_range_cases_sha256`` only: the sealed in-range
#: case set (`pool_physics_score.in_range_cases`). Custody: hidden truths.
IN_RANGE_CASES = "in_range_cases"
#: Optional material field, NEW versions with a registered ``menu`` block only: the sealed menu tasks
#: (`pool_menu.load_tasks`: per task its problem, duties and carbon.d-menu.v1 record). Custody: hidden truths.
MENU = "menu"
_OPTIONAL_MATERIAL_KEYS = {
    MENU,
    RESPONSE_REFERENCE,
    COVERAGE_PLAN,
    COVERAGE_PLAN_SUMS,
    VARIANT_STARTS,
    SCORING_CELLS,
    IN_RANGE_CASES,
}
MATERIAL_SCHEMA = "carbon.pool.sealed-material.v1"
_MATERIAL_KEYS = {
    "schema",
    "kind",
    "version",
    "input_names",
    "design_names",
    "input_dtype",
    "set_digest",
    "sets",
}
#: The native record of every pool row: nothing names its target (grouping stays in the pool documents).
POOL_RECORD = {"kind": "pool_design"}
#: Challenge id -> the practice-grid kind `pool_adapters` dispatches on.
KINDS = {
    "f08-ribbed-bracket": "f08",
    "f02": "f02",
    "electric-motor-magnetics": "motor",
    "chip-cold-plate": "cooling",
}


class PoolConstantsNotRegistered(pool_exam.ExamRefused):
    """A constant the owner has not picked: the version refuses to grade (Carbon's gap, never a candidate's)."""


def _picked(value):
    if value == HUMAN_INPUT:
        raise PoolConstantsNotRegistered("pool_constants_not_registered")
    return value


def registered_a_multiplier(challenge_id, version, *, path=CONSTANTS):
    """The owner's A-leg tightening m of the version (1 = the sealed grader's registered scale; the sheet's
    ``A multiplier``), or `PoolConstantsNotRegistered`. A positive finite number, never defaulted.
    """
    try:
        document = json.loads(Path(path).read_bytes())
        if document["schema"] != SCHEMA:
            raise ValueError
        value = _picked(
            document["versions"][f"{challenge_id} {version}"]["a_multiplier"]
        )
    except pool_exam.ExamRefused:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        raise PoolConstantsNotRegistered(
            "pool_constants_unregistered_version"
        ) from None
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise PoolConstantsNotRegistered("pool_constants_malformed")
    return float(value)


def _pick_rule(value):
    """The registered design rule ``{"kind": "top_k", "k": k}`` (k picked by the owner, never defaulted) or None."""
    if value is None:
        return None
    if type(value) is not dict or set(value) != {"kind", "k"}:
        raise PoolConstantsNotRegistered("pool_constants_malformed")
    return {"kind": _picked(value["kind"]), "k": _picked(value["k"])}


def _d_aggregate(value):
    """The registered D aggregation of a new version (``balanced_region_mean``) or None; never defaulted when present."""
    return None if value is None else _picked(value)


#: Absent from a registration (every registered version): its field is None.
_ABSENT = object()


def _a_gen_aggregate(value):
    """The registered A_gen aggregation of a new version, or None when the key is absent (every registered version). When
    present it has no default: HUMAN_INPUT refuses, and so does a null (only an absent key is the plain mean).
    """
    if value is _ABSENT:
        return None
    if value is None:
        raise PoolConstantsNotRegistered("pool_constants_malformed")
    return _picked(value)


def _min_class_cases(value):
    """The registered N of a new version's out-of-range A_gen (``a_gen_min_class_cases``, OWNER-ACCURACY-OOD-MIN-01 item
    1, set in the version plan), or None when the key is absent (every registered version). Present, it has no default:
    a null or HUMAN_INPUT refuses, and anything but an int >= 1 refuses."""
    if value is _ABSENT:
        return None
    value = _picked(value)
    if type(value) is not int or value < 1:
        raise PoolConstantsNotRegistered("pool_constants_malformed")
    return value


def _coverage_plan_sha256(value):
    """A registered sha256 (64 hex) of a new version's coverage plan (its class map, or its package's SHA256SUMS), or None
    when the key is absent."""
    if value is _ABSENT:
        return None
    if value is None:
        raise PoolConstantsNotRegistered("pool_constants_malformed")
    return _picked(value)


def _variant_rule(value):
    """The registered neighbour-task rule of a new version (`pool_grader.OptimizerPolicy.variant_rule`), or None when the
    key is absent (every registered version). Present, it has no default: a null refuses, and so does HUMAN_INPUT
    anywhere in it (the limits per Challenge, the minimum of valid variants, the shifts beyond the record's starting
    value are the owner's)."""
    if value is _ABSENT:
        return None
    if value is None:
        raise PoolConstantsNotRegistered("pool_constants_malformed")
    value = _picked(value)
    if type(value) is dict:
        for item in value.values():
            _picked(item)
            if type(item) in (list, tuple):
                for element in item:
                    _picked(element)
    return value


def _physics(value):
    """A new version's registered physics rule (`pool_physics_score.PhysicsRule`), or None when the key is absent (every
    registered version). Present, it has no default: ``{"cells_sha256", "gate_statistic", "gate_threshold", "gate_cases",
    "enters", "ad_split", "total_rule"}`` plus, for the 5 Nov cell scoring, ``"cell_scale"``, or, with ``"scoring":
    "headroom"`` (owner 6 Nov), ``"skill_form", "h_min", "h_lo", "n_min"`` and no cell scale (``cells_sha256`` then names
    the sealed headroom admission document). A null or HUMAN_INPUT anywhere in it refuses (the values are the owner's).
    """
    from carbon.scoring import pool_physics_score

    if value is _ABSENT:
        return None
    value = _picked(value)
    required = {
        "cells_sha256",
        "gate_statistic",
        "gate_threshold",
        "gate_cases",
        "enters",
        "ad_split",
        "total_rule",
    }
    if type(value) is not dict:
        raise PoolConstantsNotRegistered("pool_constants_malformed")
    headroom = value.get("scoring") == "headroom"
    if headroom:
        required = required | {"scoring", "skill_form", "h_min", "h_lo", "n_min"}
    else:
        required = required | {"cell_scale"}
    # optional: a registered in-range case set (absent = none); headroom registers no cell scale
    allowed = (
        required | {"in_range_cases_sha256"} | (set() if headroom else {"scoring"})
    )
    if not required <= set(value) <= allowed:
        raise PoolConstantsNotRegistered("pool_constants_malformed")
    for item in value.values():
        if item is None:
            raise PoolConstantsNotRegistered("pool_constants_not_registered")
        _picked(item)
        if type(item) is dict:
            for inner in item.values():
                _picked(inner)
    rule = pool_physics_score.PhysicsRule(
        **value, **({"cell_scale": None} if headroom else {})
    )
    try:
        pool_physics_score.check_rule(rule)
    except pool_physics_score.PhysicsRefused:
        raise PoolConstantsNotRegistered("pool_constants_malformed") from None
    return rule


def _near_limit(value):
    """A new version's registered near-limit rule (`pool_grader.OptimizerPolicy.near_limit`), or None when the key is
    absent (every registered version: within-U points dropped). Present, it has no default: a null or HUMAN_INPUT
    anywhere in it refuses (the ramp shape is the owner's)."""
    if value is _ABSENT:
        return None
    if value is None:
        raise PoolConstantsNotRegistered("pool_constants_malformed")
    value = _picked(value)
    if type(value) is dict:
        for item in value.values():
            _picked(item)
    return value


def _d_zero(value):
    """A new version's registered engineer's-shortcut zero ``{"kind": "engineer_shortcut", "budget": B}`` (B the owner's, per
    version: HUMAN_INPUT refuses), or None when the key is absent (every registered version: the median zero).
    """
    if value is _ABSENT:
        return None
    value = _picked(
        value
    )  # a whole-value HUMAN_INPUT is "not registered", as for the neighbouring keys
    if type(value) is not dict or set(value) != {"kind", "budget"}:
        raise PoolConstantsNotRegistered("pool_constants_malformed")
    return {"kind": _picked(value["kind"]), "budget": _picked(value["budget"])}


def _menu(value):
    """A new version's registered menu D (`pool_menu.MenuRule`), or None when the key is absent (every registered
    version: D is the per-target pick, unchanged). Present, it has no default:
    ``{"records_sha256": {task_id: sha256}, "epoch": id, "aggregate": "mean", "rotation_days": n,
    "rowcheck": {"rel_tol", "abs_tol", "subset"}}`` plus an optional ``"min_tasks_exception"`` (an owner decision id,
    for fewer than `pool_menu.MIN_TASKS` tasks); a null or HUMAN_INPUT refuses.
    """
    from carbon.scoring import pool_menu

    if value is _ABSENT:
        return None
    value = _picked(value)
    required = {"records_sha256", "epoch", "aggregate", "rotation_days", "rowcheck"}
    if type(value) is not dict or not (
        required <= set(value) <= required | {"min_tasks_exception"}
    ):
        raise PoolConstantsNotRegistered("pool_constants_malformed")
    rowcheck = _picked(value["rowcheck"])
    if type(rowcheck) is not dict or set(rowcheck) != {"rel_tol", "abs_tol", "subset"}:
        raise PoolConstantsNotRegistered("pool_constants_malformed")
    shas = _picked(value["records_sha256"])
    if type(shas) is not dict or not shas:
        raise PoolConstantsNotRegistered("pool_constants_malformed")
    for item in shas.values():
        _picked(item)
    rule = pool_menu.MenuRule(
        records_sha256=tuple(sorted(shas.items())),
        epoch=_picked(value["epoch"]),
        aggregate=_picked(value["aggregate"]),
        rotation_days=_picked(value["rotation_days"]),
        rowcheck=tuple(
            _picked(rowcheck[name]) for name in ("rel_tol", "abs_tol", "subset")
        ),
        min_tasks_exception=(
            _picked(value["min_tasks_exception"])
            if "min_tasks_exception" in value
            else None
        ),
    )
    try:
        pool_menu.check_rule(rule)
    except pool_exam.ExamRefused:
        raise PoolConstantsNotRegistered("pool_constants_malformed") from None
    return rule


def registered_menu(challenge_id, version, *, path=CONSTANTS):
    """The version's registered menu rule, or None (no ``menu`` block)."""
    return registered_policies(challenge_id, version, path=path).menu


def registered_policies(challenge_id, version, *, path=CONSTANTS):
    """The version's `pool_proof_suite.Policies` from the registered file, or `PoolConstantsNotRegistered`."""
    try:
        document = json.loads(Path(path).read_bytes())
        if document["schema"] != SCHEMA:
            raise ValueError
        entry = document["versions"][f"{challenge_id} {version}"]
        optimizer, honesty = entry["optimizer"], entry["honesty"]
    except (OSError, ValueError, KeyError, TypeError):
        raise PoolConstantsNotRegistered(
            "pool_constants_unregistered_version"
        ) from None
    try:
        policies = suite.Policies(
            optimizer=pool_grader.OptimizerPolicy(
                budget=_picked(optimizer["budget"]),
                sigma0=_picked(optimizer["sigma0"]),
                population=_picked(optimizer["population"]),
                # optional: a registered version without a design rule keeps the single pick, unchanged
                pick_rule=_pick_rule(optimizer.get("pick_rule")),
                d_aggregate=_d_aggregate(optimizer.get("d_aggregate")),
                # optional, NEW versions only: absent is today's plain A_gen and no class map, unchanged
                a_gen_aggregate=_a_gen_aggregate(
                    optimizer.get("a_gen_aggregate", _ABSENT)
                ),
                # optional, NEW versions only (with "ood_class_mean"): the version plan's N, no default
                a_gen_min_class_cases=_min_class_cases(
                    optimizer.get("a_gen_min_class_cases", _ABSENT)
                ),
                coverage_plan_sha256=_coverage_plan_sha256(
                    optimizer.get("coverage_plan_sha256", _ABSENT)
                ),
                coverage_plan_sums_sha256=_coverage_plan_sha256(
                    optimizer.get("coverage_plan_sums_sha256", _ABSENT)
                ),
                # optional, NEW versions only: absent is today's D, bit for bit
                variant_rule=_variant_rule(optimizer.get("variant_rule", _ABSENT)),
                # optional, NEW versions only: absent is today's median zero, unchanged
                d_zero=_d_zero(optimizer.get("d_zero", _ABSENT)),
                # optional, NEW versions only: absent is today's within-U drop, unchanged
                near_limit=_near_limit(optimizer.get("near_limit", _ABSENT)),
            ),
            honesty=pool_grader.HonestyPolicy(
                scale=_picked(honesty["scale"]), reduction=_picked(honesty["reduction"])
            ),
            agen_scales=dict(_picked(entry["agen_scales"])),
            a_rule=dict(_picked(entry["a_rule"])),
            c_rule=dict(_picked(entry["c_rule"])),
            # optional, NEW versions only: absent is no physics scoring (no accuracy gate, no record), unchanged
            physics=_physics(entry.get("physics", _ABSENT)),
            # optional, NEW versions only: absent is today's per-target pick D, unchanged
            menu=_menu(entry.get("menu", _ABSENT)),
        )
        if (
            policies.menu is not None
            and policies.physics is not None
            and policies.physics.total_rule == "a_only"
        ):
            # an A-only total has no D for a menu to score
            raise PoolConstantsNotRegistered("pool_constants_malformed")
        pool_grader._check_policies(policies.optimizer, policies.honesty)
    except pool_exam.ExamRefused:
        raise
    except (KeyError, TypeError, ValueError):
        raise PoolConstantsNotRegistered("pool_constants_malformed") from None
    return policies


class PoolVariant(physical.Variant):
    """The sealed adapter of one pool-graded version (see the module docstring)."""

    POOL_GRADED = True

    def __init__(
        self, module, version, evaluation_version, case_id, *, kind, challenge_id
    ):
        super().__init__(module, version, evaluation_version, case_id)
        self._kind = kind
        self._challenge_id = challenge_id

    @staticmethod
    def _without_pool(definition):
        return {k: v for k, v in definition.items() if k != POOL_KEY}

    def validate_definition(self, definition):
        return self._module.validate_definition(self._without_pool(definition))

    def definition(self, *, bank, train_raw):
        return self._module.definition(bank=strip_pool(bank), train_raw=train_raw)

    def applied_pack(self, *, bank_rows, **kwargs):
        sealed_rows = [r for r in bank_rows if r.get("cohort") != POOL_COHORT]
        applied = self._module.applied_pack(bank_rows=sealed_rows, **kwargs)
        return {
            **applied,
            "hard_gates": [
                *applied["hard_gates"],
                pool_exam.PHYSICS_GATE,
                pool_exam.SPEED_GATE,
            ],
        }

    def measure(
        self,
        *,
        bank_rows,
        outputs,
        repeats,
        definition,
        limits,
        objective,
        train_raw,
        names,
        speed_call_seconds=None,
        speed_outputs_match=True,
        capture=None,
        menu_rowcheck=None,
    ):
        from carbon.challenge_registry import speed_gate

        material = definition.get(POOL_KEY)
        if type(material) is not dict or type(material.get("sets")) is not list:
            raise pool_exam.ExamRefused("pool_material_missing_from_the_sealed_pack")
        # The owner's constants first: a version without them grades nothing.
        policies = registered_policies(self._challenge_id, self.VERSION)
        sets = tuple(
            tuple(pool_grader.load_pool(document) for document in group)
            for group in material["sets"]
        )
        # A NEW version's sealed class map and SUMS, checked and attached by `pool_exam.attach_coverage_plan` against the
        # registered digests; a registered version's material carries neither, so its call is unchanged. Likewise a NEW
        # version's per-target variant starts (`pool_exam.attach_variant_starts`, against its registered variant rule).
        plan_material = {
            key: material[key]
            for key in (
                COVERAGE_PLAN,
                COVERAGE_PLAN_SUMS,
                VARIANT_STARTS,
                SCORING_CELLS,
                IN_RANGE_CASES,
            )
            if key in material
        }
        # A NEW version's menu D: its sealed tasks and the validator host's draw key; nothing for any other version.
        menu_arguments = {}
        tasks = menu_tasks(material, getattr(policies, "menu", None))
        if tasks is not None:
            from carbon.scoring import pool_menu

            menu_arguments = {
                "menu_tasks": tasks,
                "menu_key": pool_menu.active_key(),
                # the receiver's fresh keyed re-check (None until the receiver supplies it: refuses, Carbon's gap)
                "menu_rowcheck": menu_rowcheck,
                "menu_rowcheck_key": pool_menu.rowcheck_key(),
            }
        return pool_exam.measure_pool(
            binding=pool_adapters.official_binding(self._kind, self.VERSION),
            sets=sets,
            policies=policies,
            bank_rows=bank_rows,
            outputs=outputs,
            repeats=repeats,
            base_measure=self._module.measure,
            base_arguments={
                "definition": {
                    **self._without_pool(definition),
                    **(
                        {"group_response_reference": material[RESPONSE_REFERENCE]}
                        if material.get(RESPONSE_REFERENCE) is not None
                        else {}
                    ),
                },
                "limits": limits,
                "objective": objective,
                "train_raw": train_raw,
                "names": names,
            },
            speed_call_seconds=speed_call_seconds,
            ceiling_seconds=speed_gate.ceiling_seconds(self._challenge_id),
            input_dtype=check_material(material)["input_dtype"],
            a_multiplier=registered_a_multiplier(self._challenge_id, self.VERSION),
            speed_outputs_match=speed_outputs_match,
            capture=capture,
            **plan_material,
            **menu_arguments,
        )


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def case_id_of(values) -> str:
    """The pool row's id: a hash of its input content only (never its target, its position or a seed)."""
    return (
        "pool-"
        + hashlib.sha256(
            b"carbon.exam-pool-row/1\n"
            + _canonical([float(v) for v in values]).encode()
        ).hexdigest()[:16]
    )


def _reference_ok(value):
    return value is None or (
        type(value) is dict
        and set(value) == {"input", "by_base"}
        and type(value["input"]) is str
        and type(value["by_base"]) is dict
        and bool(value["by_base"])
        and all(
            type(k) is str and type(v) in (int, float) and math.isfinite(v)
            for k, v in value["by_base"].items()
        )
    )


def _coverage_plan_ok(material):
    """Both plan fields or neither; the class map well formed and the SUMS a text (their digests are checked against the
    registration at grade time, `pool_exam.attach_coverage_plan`)."""
    present = [key in material for key in (COVERAGE_PLAN, COVERAGE_PLAN_SUMS)]
    if not any(present):
        return True
    if not all(present) or type(material[COVERAGE_PLAN_SUMS]) is not str:
        return False
    try:
        pool_grader.coverage_plan(material[COVERAGE_PLAN])
    except pool_grader.PoolRefused:
        return False
    return True


def check_material(material):
    if (
        type(material) is not dict
        or set(material) - _OPTIONAL_MATERIAL_KEYS != _MATERIAL_KEYS
        or not _reference_ok(material.get(RESPONSE_REFERENCE))
        or not _coverage_plan_ok(material)
        or material["schema"] != MATERIAL_SCHEMA
        or type(material["input_names"]) is not list
        or type(material["design_names"]) is not list
        or not set(material["design_names"]) <= set(material["input_names"])
        or type(material["input_dtype"]) is not str
        or type(material["set_digest"]) is not str
        or type(material["sets"]) is not list
        or not material["sets"]
        or any(type(group) is not list or not group for group in material["sets"])
    ):
        raise pool_exam.ExamRefused("pool_material_malformed")
    return material


def menu_tasks(material, rule):
    """The sealed menu tasks (`pool_menu.load_tasks`) of a version whose registered menu rule is ``rule``, or None when
    it has none. A menu in the material without a registration, or a registration without one, refuses (Carbon's
    material)."""
    from carbon.scoring import pool_menu

    if rule is None:
        if MENU in material:
            raise pool_exam.ExamRefused("menu_material_without_a_registration")
        return None
    if MENU not in material:
        raise pool_exam.ExamRefused("menu_material_missing_from_the_sealed_pack")
    return pool_menu.load_tasks(
        material[MENU],
        rule,
        input_names=material["input_names"],
        design_names=material["design_names"],
    )


def _menu_rows(material, challenge):
    """The menu's model input rows of a version's material (none without a ``menu`` field)."""
    from carbon.scoring import pool_menu

    if MENU not in material:
        return []
    tasks = menu_tasks(material, registered_menu(challenge, material["version"]))
    return pool_menu.bank_rows(tasks, material["design_names"])


def rows_from_material(material, *, dtype, challenge):
    """``[(case_id, record, input row)]`` of a pool-graded exam's design-search rows, in the canonical order
    (the order `copy_derivation.canonicalize` gives derived rows: by content, or by id for a Challenge whose ids
    carry meaning). Every pool design of every target as the model's input row (the target's fixed conditions
    plus the design, in the interface order), quantised to the bank's ``dtype`` exactly as the delivered query
    holds it; identical queries are one row; no row names its target."""
    import numpy as np

    from carbon.scoring import copy_derivation as cd

    check_material(material)
    names, design_names = material["input_names"], material["design_names"]
    kind = np.dtype(dtype)
    seen = {}
    for group in material["sets"]:
        for document in group:
            spec = pool_grader.load_pool(
                document
            )  # refuses a pool whose digest differs
            fixed = spec.conditions["fixed"]
            for design in spec.designs:
                row = {**fixed, **dict(zip(design_names, design, strict=True))}
                if set(row) != set(names):
                    raise pool_exam.ExamRefused(
                        "pool_inputs_do_not_complete_the_model_row"
                    )
                values = tuple(float(kind.type(row[name])) for name in names)
                seen.setdefault(values, None)
    for row in _menu_rows(material, challenge):
        # menu rows are plain pool rows: same quantisation, dedup and canonical content order (Validator-2B a1)
        values = tuple(float(kind.type(row[name])) for name in names)
        seen.setdefault(values, None)
    by_kind = {kind: challenge_id for challenge_id, kind in KINDS.items()}
    if material["kind"] not in by_kind:
        raise pool_exam.ExamRefused("pool_material_kind_unregistered")
    opaque = cd.opaque_for(by_kind[material["kind"]])
    rows = [(case_id_of(values), dict(POOL_RECORD), list(values)) for values in seen]

    def key(row):
        case_id, record, values = row
        if "case_id" in opaque:
            return _canonical(
                {
                    "cohort": POOL_COHORT,
                    "inputs": values,
                    "record": {k: v for k, v in record.items() if k not in opaque},
                    "reference": [None],
                }
            )
        return case_id

    return sorted(rows, key=key)


def row_accounting(material, *, dtype, challenge=None):
    """Counts only: how the pool's designs become the exam's pool rows (no input, truth or id leaves).

    ``designs_total`` is every design of every target; ``unique_rows`` the distinct model queries after quantising to the
    bank's ``dtype`` (what `rows_from_material` returns); the difference is the duplicates, split into those inside
    one target and those across targets (a Challenge whose model input is the design alone, such as F02, has no
    condition to tell two targets' equal designs apart), and into those that were distinct designs before the
    quantisation made them equal. ``designs_total - unique_rows == dup_within_target + dup_across_targets``.

    A material with a ``menu`` (``challenge`` then required, for its registration) counts every (menu design x duty)
    row the same way, each task one target, and adds ``menu_tasks`` / ``menu_rows`` (Validator-2B a1.2); a material
    without one returns exactly the counts above.
    """
    import numpy as np

    check_material(material)
    names, design_names = material["input_names"], material["design_names"]
    kind = np.dtype(material["input_dtype"] if dtype is None else dtype)
    first = {}  # quantised row -> (target index, raw row)
    counts = {
        "designs_total": 0,
        "unique_rows": 0,
        "dup_within_target": 0,
        "dup_across_targets": 0,
        "dup_created_by_quantisation": 0,
        "targets": 0,
    }

    def targets():
        for group in material["sets"]:
            for document in group:
                spec = pool_grader.load_pool(document)
                fixed = spec.conditions["fixed"]
                yield [
                    {**fixed, **dict(zip(design_names, design, strict=True))}
                    for design in spec.designs
                ]
        if MENU in material:
            from carbon.scoring import pool_menu

            if challenge is None:
                raise pool_exam.ExamRefused("menu_accounting_needs_the_challenge")
            tasks = menu_tasks(
                material, registered_menu(challenge, material["version"])
            )
            counts["menu_tasks"] = len(tasks)
            counts["menu_rows"] = 0
            for task in tasks:
                rows = pool_menu.task_rows(task, design_names)[0]
                counts["menu_rows"] += len(rows)
                yield rows

    for rows in targets():
        target = counts["targets"]
        counts["targets"] += 1
        for row in rows:
            raw = tuple(float(row[name]) for name in names)
            values = tuple(float(kind.type(row[name])) for name in names)
            counts["designs_total"] += 1
            if values not in first:
                first[values] = (target, raw)
                counts["unique_rows"] += 1
                continue
            seen_target, seen_raw = first[values]
            counts[
                ("dup_within_target" if seen_target == target else "dup_across_targets")
            ] += 1
            counts["dup_created_by_quantisation"] += raw != seen_raw
    return counts


def strip_pool(bank):
    """The bank without its pool rows and material: the Challenge's own sealed bank."""
    import numpy as np

    from carbon.scoring import copy_derivation as cd

    size = len(bank["case_ids"])
    keep = [i for i, c in enumerate(bank["cohorts"]) if c != POOL_COHORT]
    out = {}
    for name, value in bank.items():
        if name == POOL_KEY:
            continue
        if name in cd.PER_ROW and len(value) == size:
            value = (
                np.asarray(value)[keep]
                if isinstance(value, np.ndarray)
                else type(value)(value[i] for i in keep)
            )
        out[name] = value
    return out


def material_from_set_dir(
    set_dir, *, kind, version, input_dtype, set_digest=None, sets_file="sets.json"
):
    """The pool material of a custody Phase-1 set directory (`pool-source-<tid>.json` per target and the sets
    file), for the pool version's exam. Custody-side: the documents carry the pool's truths and never leave
    custody; they ride only inside the signed sealed batch."""
    from carbon.scoring import pool_plugin

    root = Path(set_dir)
    binding = pool_adapters.official_binding(kind, version)
    sets = json.loads((root / sets_file).read_text(encoding="utf-8"))
    groups = []
    for targets in sets.values():
        group = []
        for target_id in targets:
            source = json.loads(
                (root / f"pool-source-{target_id}.json").read_text(encoding="utf-8")
            )
            group.append(
                pool_grader.dump_pool(pool_plugin.spec_from_source(source, binding))
            )
        groups.append(group)
    digest = set_digest or (
        "sha256:"
        + hashlib.sha256(
            _canonical([[d["digest"] for d in g] for g in groups]).encode()
        ).hexdigest()
    )
    return check_material(
        {
            "schema": MATERIAL_SCHEMA,
            "kind": kind,
            "version": version,
            "input_names": list(binding.input_names),
            "design_names": list(binding.design_names),
            "input_dtype": input_dtype,
            "set_digest": digest,
            "sets": groups,
        }
    )


def is_pool_bank(bank, is_sealed_bank) -> bool:
    """Whether a bank is a pool version's: the Challenge's own sealed bank (``is_sealed_bank`` says so once the pool
    rows are set aside) plus at least one pool row (cohort `pool_design`, inputs only), nothing else.
    """
    if type(bank) is not dict or type(bank.get("cohorts")) not in (tuple, list):
        return False
    size = len(bank["cohorts"])
    keep = [i for i, c in enumerate(bank["cohorts"]) if c != pool_exam.POOL_COHORT]
    if len(keep) == size:
        return False
    rest = {
        key: (
            [value[i] for i in keep]
            if type(value) in (tuple, list) and len(value) == size
            else value
        )
        for key, value in bank.items()
    }
    return is_sealed_bank(rest)


def variant(module, version, evaluation_version, case_id, *, challenge_id):
    """A pool-graded adapter for ``version`` of ``module``'s Challenge."""
    return PoolVariant(
        module,
        version,
        evaluation_version,
        case_id,
        kind=KINDS[challenge_id],
        challenge_id=challenge_id,
    )


__all__ = [
    "COVERAGE_PLAN",
    "COVERAGE_PLAN_SUMS",
    "HUMAN_INPUT",
    "KINDS",
    "MATERIAL_SCHEMA",
    "POOL_COHORT",
    "POOL_KEY",
    "PoolConstantsNotRegistered",
    "PoolVariant",
    "case_id_of",
    "check_material",
    "is_pool_bank",
    "material_from_set_dir",
    "registered_policies",
    "row_accounting",
    "rows_from_material",
    "strip_pool",
    "variant",
]
