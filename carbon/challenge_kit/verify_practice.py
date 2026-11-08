"""Practice on the data kit's VERIFY SET, for the versions that use it (owner 7 Nov: "Yes, verify set").

New versions retire the shared public practice bank for data kits (OWNER-MINER-DATA-KITS-LAUNCH-STAPLE-01). Their
practice in the app scores the kit's verify set instead: a small published file of designs with Carbon's own
solved truths, pinned by its receipted sha256. One path, labelled practice, never a grade:

- the query is the verify designs' inputs, in the interface's input order;
- each design is scored by the Challenge's own PRACTICE measurement (the same `score_case` / `aggregate` the public
  practice bank uses), on the verify truths;
- beside it, the kit's own accuracy-within-U check (`local_scorer`), where the verify set carries a U;
- design value, picks and the sealed minimums need Carbon's hidden pools: never computed here, always reported
  "not evaluated locally".

A version uses this only when it is listed in `REGISTRY` with its kit's verify set path and receipted sha256. The
registry is empty until each verify set lands (the version owner builds it; the Validator receipts its digest).
Until then every practice keeps its current path unchanged.

It opens no evaluation pack, seed, sealed or private material. DEVELOPMENT practice feedback only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LABEL = "practice (kit verify set)"
SOURCE = "kit_verify_set"
NOT_EVALUATED = "not evaluated locally"
MOTOR = "electric-motor-magnetics"
COOLING = "chip-cold-plate"

#: (challenge id, version) -> (the verify set's path from the checkout root, its receipted sha256). Switching a
#: version on = one row here, with the kit's file and the Validator-receipted digest. Empty until a set lands.
REGISTRY: dict[tuple[str, str], tuple[str, str]] = {
    # Motor 1.8: the kit's verify set, digest receipted by the Validator (7 Nov, board 07:55).
    (MOTOR, "1.8"): (
        "kits/motor/verify_set.json",
        "e6179607b3790ac0b05658b1ee4019478a6aac9c2f3bb787a74f96cedc1c7327",
    ),
    # Cooling 1.8: the kit's verify set, digest receipted by the Carbon Validator (7 Nov, board 12:43).
    (COOLING, "1.8"): (
        "kits/cooling/verify_set.json",
        "59dabd83e1484cac28e3ad811aac2cba325d3d8ffc994e37b2e0c78063a15bb0",
    ),
}


class VerifyPracticeRefused(ValueError):
    """The registered verify set is missing, altered or malformed: the practice refuses, never falls back."""


@dataclass(frozen=True)
class VerifySource:
    challenge_id: str
    version: str
    document: dict
    sha256: str

    @property
    def designs(self):
        return self.document["designs"]

    def query(self, input_names):
        """The verify designs' inputs as rows, in the interface's input order."""
        import numpy as np

        return np.asarray(
            [[float(d["inputs"][name]) for name in input_names] for d in self.designs],
            dtype=np.float64,
        )

    @property
    def case_ids(self):
        return [d["case_id"] for d in self.designs]


def registered(challenge_id: str, version: str) -> bool:
    return (challenge_id, version) in REGISTRY


def source(challenge_id: str, version: str, *, root=None, registry=None):
    """This version's verify-set practice source, or None when it keeps its current practice."""
    from carbon.challenge_kit import local_scorer

    table = REGISTRY if registry is None else registry
    entry = table.get((challenge_id, version))
    if entry is None:
        return None
    relative, sha256 = entry
    path = Path(root or ROOT) / relative
    try:
        raw = path.read_bytes()
    except OSError:
        raise VerifyPracticeRefused("verify_set_missing") from None
    names = _input_names(challenge_id)
    if challenge_id == COOLING:
        document = _load_cooling(raw, sha256, names)
        return VerifySource(challenge_id, version, document, sha256)
    try:
        document = local_scorer.load_verify_set(raw, sha256, names)
    except local_scorer.ScorerRefused as refused:
        raise VerifyPracticeRefused("verify_set_invalid: " + str(refused)) from None
    return VerifySource(challenge_id, version, document, sha256)


def _input_names(challenge_id):
    if challenge_id == MOTOR:
        from carbon.motor import domain

        return tuple(domain.INPUTS)
    if challenge_id == COOLING:
        from carbon.cold_plate import domain

        return tuple(domain.INPUTS)
    raise VerifyPracticeRefused("verify_practice_challenge_unsupported")


def score_motor(src: VerifySource, rows, train):
    """Motor practice on the verify set: (predictions by case id, summary, verify block).

    `rows` are the model's 60-angle torque curves for `src.designs`, in order; `train` is the public TRAIN records
    the practice scales come from (`exam.scales_from_train`), as the public practice bank uses them.
    """
    from carbon.challenge_kit import local_scorer
    from carbon.motor import exam

    if src.challenge_id != MOTOR:
        raise VerifyPracticeRefused("verify_practice_challenge_unsupported")
    designs = src.designs
    if len(rows) != len(designs):
        raise VerifyPracticeRefused("verify_practice_row_count")
    scales = exam.scales_from_train(train)
    predictions = {}
    scored = []
    for design, row in zip(designs, rows):
        curve = [float(v) for v in row]
        predictions[design["case_id"]] = {"torque_nm": curve}
        reference = {
            "case_id": design["case_id"],
            "inputs": dict(design["inputs"]),
            "outputs": {"torque_nm": [float(v) for v in design["truth"]["torque_nm"]]},
            "status": "OK",
        }
        scored.append(
            exam.score_case(predictions[design["case_id"]], reference, scales)
        )
    summary = exam.aggregate(scored)
    u = local_scorer._u(src.document)
    checks = [local_scorer._motor_design(d, r, u) for d, r in zip(designs, rows)]
    verify = {
        "label": LABEL,
        "source": SOURCE,
        "verify_set_sha256": src.sha256,
        "aggregate": local_scorer._motor_aggregate(checks, u),
        "design_value": NOT_EVALUATED,
        "minimums": NOT_EVALUATED,
    }
    return predictions, summary, verify


# --- Cooling -------------------------------------------------------------------------------------------------------

#: Cooling's graded quantities with a U in its verify set (the keys of `kits/cooling/kit.py` `U_COOLING_16`).
COOLING_U_KEYS = ("die_peak_c", "hydraulic_w")


def _load_cooling(raw, sha256, input_names):
    """Cooling's verify set, only at its receipted digest: designs with the interface's inputs and finite truths of
    the exam's declared shapes (`exam.SHAPES`)."""
    import hashlib
    import json
    import math

    from carbon.cold_plate import exam

    if hashlib.sha256(raw).hexdigest() != sha256:
        raise VerifyPracticeRefused(
            "verify_set_invalid: the bytes differ from the receipted sha256"
        )
    try:
        document = json.loads(raw)
    except ValueError:
        raise VerifyPracticeRefused("verify_set_invalid: not JSON") from None
    designs = document.get("designs") if type(document) is dict else None
    if (
        type(document) is not dict
        or document.get("challenge") != COOLING
        or type(designs) is not list
        or not designs
    ):
        raise VerifyPracticeRefused("verify_set_invalid: not a Cooling verify set")
    seen = set()
    for design in designs:
        case_id = design.get("case_id") if type(design) is dict else None
        if type(case_id) is not str or not case_id or case_id in seen:
            raise VerifyPracticeRefused(
                "verify_set_invalid: each design needs its own case_id"
            )
        seen.add(case_id)
        inputs, truth = design.get("inputs"), design.get("truth")
        if (
            type(inputs) is not dict
            or set(inputs) != set(input_names)
            or not all(
                type(inputs[n]) in (int, float) and math.isfinite(inputs[n])
                for n in input_names
            )
            or type(truth) is not dict
            or set(truth) != set(exam.SHAPES)
            or not exam._finite_shape(truth)
        ):
            raise VerifyPracticeRefused(f"verify_set_invalid: {case_id} is malformed")
    return document


def _cooling_u(document):
    """{quantity: ("abs" | "rel", value)} from the verify set's U, or None while unregistered."""
    u = document.get("u")
    if type(u) is not dict or set(u) != set(COOLING_U_KEYS):
        return None
    out = {}
    for name in COOLING_U_KEYS:
        entry = u[name]
        if type(entry) is not dict or len(entry) != 1 or set(entry) - {"abs", "rel"}:
            return None
        ((kind, value),) = entry.items()
        if type(value) not in (int, float) or not value >= 0:
            return None
        out[name] = (kind, float(value))
    return out


def cooling_quantities(case, outputs):
    """Die peak and hydraulic power exactly as `exam.feasibility` reads them, without its input-bounds check: the
    verify designs sit inside the public cap, beyond the TRAIN box, and widening the module's bounds in a running
    app is not safe. A test pins equality with `exam.feasibility` inside the box."""
    from carbon.cold_plate import domain, exam

    case = {name: float(case[name]) for name in domain.INPUTS}
    seg = 30.0 / exam.PROFILE_SEGMENTS
    profile = [float(v) for v in outputs["profile_c"]]
    through_tim = max(
        t + domain.heat_flux(case, (i + 0.5) * seg) * exam.TIM_RESISTANCE_M2K_W
        for i, t in enumerate(profile)
    )
    return {
        "die_peak_c": through_tim + max(0.0, float(outputs["peak_c"]) - max(profile)),
        "hydraulic_w": float(outputs["pressure_drop_pa"])
        * domain.derived(case)["flow_m3_s"],
    }


def _cooling_check(design, prediction, row, u):
    from carbon.cold_plate import exam

    check = {"case_id": design["case_id"], "state": row["state"], "gates": row["gates"]}
    if u is None:
        check["accuracy_vs_u"] = {
            "status": NOT_EVALUATED,
            "reason": "the verify set carries no registered U",
        }
        return check
    if row["state"] != exam.SCORABLE:
        check["accuracy_vs_u"] = {"within_u": False, "reason": "a gate failed"}
        return check
    got = cooling_quantities(design["inputs"], prediction)
    want = cooling_quantities(design["inputs"], design["truth"])
    within, block = True, {}
    for name in COOLING_U_KEYS:
        kind, value = u[name]
        limit = value if kind == "abs" else value * abs(want[name])
        delta = abs(got[name] - want[name])
        ok = delta <= limit
        block[name] = {
            "model": got[name],
            "truth": want[name],
            "delta": delta,
            "u": limit,
            "within_u": ok,
        }
        within = within and ok
    block["within_u"] = within
    check["accuracy_vs_u"] = block
    return check


def score_cooling(src: VerifySource, predictions, train):
    """Cooling practice on the verify set: (predictions by case id, summary, verify block).

    `predictions` are the model's named outputs for `src.designs`, in order (the practice's own decode of each
    row); `train` is the public TRAIN records the practice scales come from (`exam.scales_from_train`), as the
    public practice bank uses them.
    """
    from carbon.cold_plate import exam

    if src.challenge_id != COOLING:
        raise VerifyPracticeRefused("verify_practice_challenge_unsupported")
    designs = src.designs
    if len(predictions) != len(designs):
        raise VerifyPracticeRefused("verify_practice_row_count")
    scales = exam.scales_from_train(train)
    u = _cooling_u(src.document)
    by_case, scored, checks = {}, [], []
    for design, prediction in zip(designs, predictions):
        by_case[design["case_id"]] = prediction
        reference = {
            "case_id": design["case_id"],
            "inputs": dict(design["inputs"]),
            "outputs": dict(design["truth"]),
            "status": "OK",
        }
        row = exam.score_case(prediction, reference, scales)
        scored.append(row)
        checks.append(_cooling_check(design, prediction, row, u))
    fails = {}
    for check in checks:
        for gate, verdict in check["gates"].items():
            if verdict == exam.FAIL:
                fails[gate] = fails.get(gate, 0) + 1
    aggregate = {
        "n_designs": len(checks),
        "n_scorable": sum(c["state"] == exam.SCORABLE for c in checks),
        "n_gate_failed": sum(c["state"] == exam.GATE_FAILED for c in checks),
        "gate_failures": fails,
    }
    if u is None:
        aggregate["accuracy_vs_u"] = {"status": NOT_EVALUATED}
    else:
        aggregate["accuracy_vs_u"] = {
            **{
                name: sum(
                    c["accuracy_vs_u"].get(name, {}).get("within_u", False)
                    for c in checks
                )
                for name in COOLING_U_KEYS
            },
            "n_within_u": sum(c["accuracy_vs_u"]["within_u"] for c in checks),
        }
    verify = {
        "label": LABEL,
        "source": SOURCE,
        "verify_set_sha256": src.sha256,
        "designs": checks,
        "aggregate": aggregate,
        "design_value": NOT_EVALUATED,
        "minimums": NOT_EVALUATED,
    }
    return by_case, exam.aggregate(scored), verify
