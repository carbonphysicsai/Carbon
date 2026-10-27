"""A pool-graded version's adapter: the Challenge's sealed v2 adapter with the pool measure (M2).

`PoolVariant` is a `physical_dual_pack.Variant` of the Challenge's sealed adapter whose `measure` is
`pool_exam.measure_pool` around the Challenge's own sealed `measure`, so `physical_dual_pack.produce` and the dual
`score` are unchanged. Its registered mandatory gates are the sealed grader's native ones plus `physics_pool` and
`speed`.

Exam material (M3, built in custody from the signed Phase-1 set): the sealed pack's bank carries the pool rows as
cohort `pool_design` (inputs only), and its `definition` carries the pools' truths under the key `pool`:
`{"sets": [[<carbon.pool.v1 document>, ...], ...]}`. The definition is private to the grading host.

The owner's constants (B, s_h, the honesty reduction, the A and A_gen scales, how A_gen enters A) are read from
`pool_constants.json`, where each is HUMAN_INPUT until the owner picks it from the per-Challenge owner sheet. A
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

CONSTANTS = Path(__file__).with_name("pool_constants.json")
SCHEMA = "carbon.pool.constants.v1"
HUMAN_INPUT = "HUMAN_INPUT"
POOL_KEY = "pool"
#: Optional material field: per-probe-group reference slopes a version anchors one response input on (F02 2.5).
RESPONSE_REFERENCE = "response_reference"
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
            ),
            honesty=pool_grader.HonestyPolicy(
                scale=_picked(honesty["scale"]), reduction=_picked(honesty["reduction"])
            ),
            agen_scales=dict(_picked(entry["agen_scales"])),
            a_rule=dict(_picked(entry["a_rule"])),
            c_rule=dict(_picked(entry["c_rule"])),
        )
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


def check_material(material):
    if (
        type(material) is not dict
        or set(material) - {RESPONSE_REFERENCE} != _MATERIAL_KEYS
        or not _reference_ok(material.get(RESPONSE_REFERENCE))
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
    "rows_from_material",
    "strip_pool",
    "variant",
]
