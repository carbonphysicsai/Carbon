"""Motor Q1 fixture panel: does the motor score rank models by decision quality?

TRACK-B-HARNESS-01, approved by the Test Lead on 2026-10-05. The panel has
five members:
- the textbook analytical model (`analytic-v1`);
- the registered KRR (`learned-krr-v1`);
- three constructed controls, built from public TRAIN only:
  - `flat`: the KRR curve's mean held constant, so zero ripple. It hides
    ripple; is the score penalised for that?
  - `phase-shifted`: the KRR curve rolled by a quarter period. Its mean and
    peak-to-peak are identical to KRR's, so its decisions are identical, but
    its pointwise error is worse. This probes the opposite direction of
    divergence: does the score punish decision-irrelevant error?
  - `saturation-blind`: KRR fitted only on TRAIN at current density <= 10
    A/mm², and scaled linearly in current above that. It overpredicts torque
    at deep saturation (b01, 15 A/mm²).

How each member is measured:
- **Score.** Every member is scored on the SAME source: the public PRACTICE
  pool, with the registered TRAIN scales (`practice.score_practice`). The
  score is mean normalised error, so lower is better. The textbook and KRR
  private scores exist and are reported on a separate descriptive line, never
  in the ranking.
- **Decision value.** Track B Q1 on the counted motor replay: fixed grid,
  48 queries, one-time costs excluded, ranked by `track_b.decision_value`.
- **Statistics.** With n = 5 and deterministic members, tau and rho are
  descriptive. There is no seed band and no band claim.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from carbon.design_search import score_value, track_b

from . import decision_study as ds
from . import track_b as motor

CONTROLS = ("flat", "phase-shifted", "saturation-blind")
SATURATION_KNEE_A_MM2 = 10.0
SCHEMA = "carbon.motor.q1-fixture-panel.v1"


def _batch(one):
    return lambda inputs: {key: one(case) for key, case in inputs.items()}


def _saturation_blind(config, repository):
    """KRR on TRAIN at or below the knee, scaled linearly in current above it."""

    import numpy as np

    from carbon import learned_baseline

    from . import domain

    spec = config["models"]["learned-krr-v1"]
    train = [
        r
        for r in motor._train(config, repository)
        if r["inputs"]["current_density_a_mm2"] <= SATURATION_KNEE_A_MM2
    ]
    model = learned_baseline.KernelRidge(
        learned_baseline.scale(
            [r["inputs"] for r in train], domain.INPUTS, domain.INPUT_BOUNDS
        ),
        np.array([r["outputs"]["torque_nm"] for r in train]),
        length=spec["length"],
        ridge=spec["ridge"],
    )

    def one(inputs):
        current = inputs["current_density_a_mm2"]
        query = dict(inputs)
        scale = 1.0
        if current > SATURATION_KNEE_A_MM2:
            query["current_density_a_mm2"] = SATURATION_KNEE_A_MM2
            scale = current / SATURATION_KNEE_A_MM2
        curve = model.predict(
            learned_baseline.scale([query], domain.INPUTS, domain.INPUT_BOUNDS)
        )[0]
        return {"torque_nm": [float(v) * scale for v in curve]}

    return one, len(train)


def members(config, repository):
    """Each member's batch model: {key: inputs} -> {key: {"torque_nm": [...]}}."""

    models, _ = ds.reconstruct_models(config, repository=repository)
    krr = models["learned-krr-v1"]

    def flat(inputs):
        out = {}
        for key, curve in krr(inputs).items():
            values = curve["torque_nm"]
            mean = sum(values) / len(values)
            out[key] = {"torque_nm": [mean] * len(values)}
        return out

    def shifted(inputs):
        out = {}
        for key, curve in krr(inputs).items():
            values = curve["torque_nm"]
            quarter = len(values) // 4
            out[key] = {"torque_nm": values[quarter:] + values[:quarter]}
        return out

    blind, n_train = _saturation_blind(config, repository)
    return {
        "analytic-v1": models["analytic-v1"],
        "learned-krr-v1": krr,
        "flat": flat,
        "phase-shifted": shifted,
        "saturation-blind": _batch(blind),
    }, {"saturation_blind_train_cases": n_train}


def practice_scores(batches, repository):
    from .challenge import PublicMaterial
    from .practice import PracticeSet, score_practice

    practice = PracticeSet.load(repository)
    material = PublicMaterial.load(repository)
    inputs = {r["case_id"]: r["inputs"] for r in practice.records}
    out = {}
    for name, batch in batches.items():
        _, summary = score_practice(batch(inputs), practice, material)
        out[name] = summary
    return out


def run(repository, directory):
    repository = Path(repository)
    config = motor.load_config(repository)
    table = json.loads((repository / motor.REPLAY).read_text(encoding="utf-8"))
    reference = motor.replay_reference(config, table)
    problem, contract = motor.problem(config)
    batches, notes = members(config, repository)
    practice = practice_scores(batches, repository)
    registered = json.loads(
        (
            repository / config["models"]["learned-krr-v1"]["calibration_report"]
        ).read_text(encoding="utf-8")
    )["scores"]
    for name, key in (("analytic-v1", "closed_form"), ("learned-krr-v1", "learned")):
        expected = registered["practice"][key]["score"]
        if not math.isclose(
            practice[name]["score"], expected, rel_tol=0, abs_tol=1e-12
        ):
            raise ValueError(f"practice_score_not_reproduced: {name}")
    predictors = [
        motor._model(name, contract, batch) for name, batch in batches.items()
    ]
    q1 = track_b.alignment(
        problem,
        predictors,
        method="fixed_grid",
        parameters={},
        query_allowance=len(problem.designs) * len(problem.conditions),
        reference=reference,
        directory=Path(directory),
        unit=motor.UNIT,
    )
    scope = track_b.CONTRACT_SCOPE
    panel = {
        name: {
            "score": -practice[name]["score"],
            "value": track_b.decision_value(q1["arms"][name]["scopes"][scope]),
            "eligible": bool(practice[name]["eligible"]),
            "recipe": name,
            "kind": "CONTROL" if name in CONTROLS else "REGISTERED_BASELINE",
        }
        for name in batches
    }
    alignment = score_value.alignment(panel, top_k=2)
    rows = {
        name: {
            "kind": panel[name]["kind"],
            "practice_score": practice[name]["score"],
            "practice_eligible": practice[name]["eligible"],
            "selection": q1["arms"][name]["design_id"],
            "decision": {
                k: q1["arms"][name]["scopes"][scope][k]
                for k in (
                    "proposal_outcome",
                    "false_feasible",
                    "tie_determined",
                    "correct_decision",
                    "missed_feasible_designs",
                )
            },
            "regret": q1["arms"][name]["scopes"][scope]["regret"],
            "groups": {
                g: q1["arms"][name]["scopes"][g]["proposal_outcome"]
                for g in track_b.GROUPS
            },
            "decision_value": panel[name]["value"],
        }
        for name in batches
    }
    return {
        "schema": SCHEMA,
        "score_source": (
            "public PRACTICE pool, registered TRAIN scales; mean normalised error, "
            "lower is better"
        ),
        "private_scores_descriptive_only": {
            "analytic-v1": registered["private"]["closed_form"]["score"],
            "learned-krr-v1": registered["private"]["learned"]["score"],
            "note": "operator-held private pool; not in the ranking",
        },
        "decision_source": (
            "Track B Q1 on the counted motor replay (study V2), fixed grid, 48 "
            "queries, one-time costs excluded"
        ),
        "notes": notes,
        "members": rows,
        "alignment": alignment,
        "comparator": q1["comparators"][scope],
        "statistics": "n = 5 deterministic members: tau and rho descriptive, no band",
    }
