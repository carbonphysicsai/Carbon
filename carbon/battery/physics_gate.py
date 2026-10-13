"""Prospective DEVELOPMENT B15 admission and operator card measurements.

Only registered data is executed. No solver, score analysis, hidden material,
seed generation or miner disclosure lives here. OWNER-PHYSICS-GATES-01 owns
the allowance; an operator supplies and pins the probe plan, not the miner.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from carbon.challenge_validator import physics_contract as pc
from carbon.challenge_validator.strict_json import MalformedStrategy, parse_strategy

CONTRACT = "carbon/battery/physics_contract.v2.json"
PROBE_SCHEMA = "carbon.battery.physics-probes.v1"
CODE = "physics_gate_b15"
REFERENCE_IMAGE = (
    "sha256:2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940"
)
DECISION = ".agent/decisions/2026-10-13-OWNER-PHYSICS-GATES-01.md"
FIELDS = frozenset(
    {"contract_sha256", "probes_path", "probes_sha256", "reference_image"}
)
_SHA = re.compile(r"[0-9a-f]{64}\Z")
MAX_BYTES = 4 * 1024 * 1024  # Engineering bound, not a probe population.


class PhysicsRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def check_term(term):
    if (
        type(term) is not dict
        or set(term) != FIELDS
        or any(type(v) is not str or not v for v in term.values())
        or not _SHA.fullmatch(term["contract_sha256"])
        or not _SHA.fullmatch(term["probes_sha256"])
        or term["reference_image"] != REFERENCE_IMAGE
    ):
        raise PhysicsRefused("physics_contract_term")
    return dict(term)


def _read(path, expected):
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != expected:
            raise PhysicsRefused("physics_contract_digest")
        return raw, parse_strategy(raw, max_bytes=MAX_BYTES)
    except (OSError, MalformedStrategy):
        raise PhysicsRefused("physics_contract_unavailable") from None


def _law(contract, name):
    return next(law for law in contract["laws"] if law["id"] == name)


def _finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def _curve(output, name, size=121):
    value = output.get(name) if type(output) is dict else None
    return (
        type(value) in (list, tuple)
        and len(value) == size
        and all(_finite(x) for x in value)
    )


def verdict(residuals, *, expected, unresolved=0):
    """An incomplete or invalid candidate never passes the adopted gate."""
    checked = [x for x in residuals if _finite(x) and x >= 0]
    valid = (
        expected > 0
        and len(residuals) == expected
        and unresolved == 0
        and len(checked) == expected
    )
    failures = sum(x > 1e-4 for x in checked)
    return {
        "eligible": bool(valid and failures == 0),
        "code": None if valid and failures == 0 else CODE,
        "n_pairs": expected,
        "n_checked": len(checked),
        "n_unresolved": max(unresolved, expected - len(checked)),
        "n_violations": failures,
        "max_absolute_c": max(checked) if checked else None,
    }


class BatteryPhysics:
    """Validated, immutable bytes for one optional deployment component.

    The v2 source is the registered local contract, checked against the
    owner's exact adoption; alternate tolerances cannot enter this loader.
    The plan covers both axes and contains complete matched pairs. Its
    population/count has no default here and is never candidate-supplied.
    """

    __slots__ = ("_contract", "_identity", "_plan")

    def __setattr__(self, name, value):
        if hasattr(self, name):
            raise AttributeError("registered physics component is immutable")
        object.__setattr__(self, name, value)

    def __init__(self, term, repository, *, reference_image):
        term = check_term(term)
        if reference_image != REFERENCE_IMAGE:
            raise PhysicsRefused("physics_contract_image_mismatch")
        raw, contract = _read(Path(repository) / CONTRACT, term["contract_sha256"])
        try:
            pc.validate(contract)
            b15 = _law(contract, "B15")
            if (
                contract.get("version") != "battery-physics-v2"
                or contract.get("status") != "DEVELOPMENT_ADOPTED_B15"
                or b15.get("adoption") != "ADOPTED"
                or b15.get("role") != "MANDATORY_ADMISSIBILITY"
                or b15.get("allowance_absolute_c") != 1e-4
                or type(b15.get("allowance_absolute_c")) is not float
                or b15.get("gate_max_violation_rate") != 0
                or type(b15.get("gate_max_violation_rate")) is not int
                or b15.get("reference_image") != REFERENCE_IMAGE
                or b15.get("adoption_reference") != DECISION
                or b15.get("type") != "prefix_invariance"
                or b15.get("output") != "temperature_c"
                or b15.get("inputs") != ["c1", "c2"]
                or b15.get("step") != 0.05
                or b15.get("grid_step_s") != 30
                or b15.get("switch_time_s") != 120
            ):
                raise PhysicsRefused("physics_contract_adoption")
            # All other laws and the measurement geometry keep their v1
            # meaning. v1 is historical and never edited by this ticket.
            try:
                legacy = pc.load(
                    Path(repository) / "carbon/battery/physics_contract.v1.json"
                )
            except (OSError, ValueError):
                raise PhysicsRefused("physics_contract_legacy_unavailable") from None
            if any(
                contract.get(k) != legacy.get(k)
                for k in (
                    "schema",
                    "challenge",
                    "validity",
                    "validity_status",
                    "validity_models",
                    "required_outputs",
                    "output_shapes",
                    "probe_region",
                    "tolerance",
                    "aux",
                )
            ) or [law for law in contract["laws"] if law["id"] != "B15"] != [
                law for law in legacy["laws"] if law["id"] != "B15"
            ]:
                raise PhysicsRefused("physics_contract_other_law_changed")
        except (pc.ContractRefused, KeyError, StopIteration):
            raise PhysicsRefused("physics_contract_adoption") from None
        plan_path = Path(term["probes_path"])
        if not plan_path.is_absolute():
            plan_path = Path(repository) / plan_path
        plan_raw, plan = _read(plan_path, term["probes_sha256"])
        if (
            set(plan) != {"schema", "contract_sha256", "pairs"}
            or plan["schema"] != PROBE_SCHEMA
            or plan["contract_sha256"] != term["contract_sha256"]
            or type(plan["pairs"]) is not list
            or not plan["pairs"]
        ):
            raise PhysicsRefused("physics_probe_plan")
        axes, seen = set(), set()
        for pair in plan["pairs"]:
            if type(pair) is not dict or set(pair) != {"axis", "base", "partner"}:
                raise PhysicsRefused("physics_probe_pair")
            axis, base, partner = pair["axis"], pair["base"], pair["partner"]
            region = contract["probe_region"]
            if (
                axis not in b15["inputs"]
                or type(base) is not dict
                or type(partner) is not dict
                or set(base) != set(region)
                or set(partner) != set(region)
                or not pc.applicable(contract, base)
                or not pc.applicable(contract, partner)
                or any(base[k] != partner[k] for k in region if k != axis)
                or not math.isclose(
                    partner[axis] - base[axis],
                    b15["step"] * (region[axis][1] - region[axis][0]),
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                )
            ):
                raise PhysicsRefused("physics_probe_pair")
            key = (
                axis,
                *(base[k] for k in sorted(region)),
                *(partner[k] for k in sorted(region)),
            )
            if key in seen:
                raise PhysicsRefused("physics_probe_duplicate")
            seen.add(key)
            axes.add(axis)
        if axes != set(b15["inputs"]):
            raise PhysicsRefused("physics_probe_axes")
        self._contract, self._plan = raw, plan_raw
        self._identity = json.dumps(
            {
                "schema": "carbon.battery.physics-component.v1",
                "contract_sha256": term["contract_sha256"],
                "probes_sha256": term["probes_sha256"],
                "reference_image": REFERENCE_IMAGE,
                "adoption_reference": DECISION,
                "checker_sha256": {
                    "physics_gate.py": hashlib.sha256(
                        Path(__file__).read_bytes()
                    ).hexdigest(),
                    "physics_contract.py": hashlib.sha256(
                        Path(pc.__file__).read_bytes()
                    ).hexdigest(),
                },
            },
            sort_keys=True,
        )

    @property
    def identity(self):
        return json.loads(self._identity)

    @property
    def namespace(self):
        return "physics/" + hashlib.sha256(self._identity.encode()).hexdigest() + "/"

    def inputs(self):
        return {
            f"p{i}-{side}": pair[side]
            for i, pair in enumerate(json.loads(self._plan)["pairs"])
            for side in ("base", "partner")
        }

    def measure(self, predictions, cases):
        contract, plan = json.loads(self._contract), json.loads(self._plan)
        readings, leaks, unresolved = [], [], 0
        for i, pair in enumerate(plan["pairs"]):
            a, b = [predictions.get(f"p{i}-{side}") for side in ("base", "partner")]
            if all(_curve(o, "temperature_c") for o in (a, b)):
                readings.append(
                    pc.pair_residual(_law(contract, "B15"), a, b, pair["axis"], 1)
                )
            else:
                unresolved += 1
            if all(_curve(o, "voltage_v") for o in (a, b)):
                leak = 1000 * pc.pair_residual(
                    _law(contract, "B16"), a, b, pair["axis"], 1
                )
                if _finite(leak):
                    leaks.append(leak)
        deficits, missing = [], 0
        for inputs, outputs in cases:
            if pc.applicable(contract, inputs) and _curve(outputs, "temperature_c"):
                deficits.append(
                    max(0.0, inputs["t_amb_c"] - min(outputs["temperature_c"]))
                )
            else:
                missing += 1
        return {
            "identity": self.identity,
            "B15": verdict(
                readings, expected=len(plan["pairs"]), unresolved=unresolved
            ),
            "model_card": {
                "B16": {
                    "rest_voltage_leak_mv": max(leaks) if leaks else None,
                    "n_pairs": len(plan["pairs"]),
                    "n_checked": len(leaks),
                    "n_unresolved": len(plan["pairs"]) - len(leaks),
                },
                "B9": {
                    "max_below_ambient_deficit_c": max(deficits) if deficits else None,
                    "share_cases_gt_0_1_c": (
                        sum(d > 0.1 for d in deficits) / len(deficits)
                        if deficits
                        else None
                    ),
                    "share_cases_gt_1_c": (
                        sum(d > 1 for d in deficits) / len(deficits)
                        if deficits
                        else None
                    ),
                    "n_checked": len(deficits),
                    "n_unresolved": missing,
                },
            },
        }
