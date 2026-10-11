"""MODEL-PREDICTIONS-FOR-EVIDENCE-01: the f02 transient-heat kit, on
fixtures. Its support is the registered TRAIN plan's domain, the plan must
cover every panel row, and the predictions pass the pipeline's Carbon hop."""

from __future__ import annotations

import itertools
import json
import re

import numpy as np
import pytest
from test_evidence_pipeline import export_questions

from carbon.design_search import tasks
from carbon.development_comparison import carbon_arm as arm
from carbon.development_comparison import evidence_pipeline as ep
from carbon.development_comparison import f02_kit

QUICK = {"steps": 300, "width": 32, "depth": 2}
MENU = list(itertools.product((80.0, 100.0, 120.0, 140.0), (5.0, 10.0, 15.0, 20.0)))
CONTEXTS = [
    f"c{c:g}-i{i:g}-s{s:g}-{w}"
    for (c, _h), i, s, w in itertools.product(
        f02_kit.COOLING, f02_kit.INITIAL_C, f02_kit.SPLITS, f02_kit.WAVEFORMS
    )
]


def toy(context, peak, on):
    """Synthetic observables (never solver output)."""
    coolant, initial = (float(x) for x in re.findall(r"[ci]([0-9.]+)-", context)[:2])
    return {
        "peak_top_c": initial + 0.2 * peak + on * coolant / 100,
        "extra_energy_j": (peak - 20.0) * on,
    }


def export(condition="c40-i55-s0.8-rectangular", menu=MENU):
    actions = {f"p{p:g}-d{d:g}": {"peak_w": p, "on_time_s": d} for p, d in menu}
    variables = []
    for name in ("peak_w", "on_time_s"):
        values = sorted({a[name] for a in actions.values()})
        step = min(b - a for a, b in itertools.pairwise(values))
        variables.append(
            {
                "name": name,
                "type": "number",
                "min": values[0],
                "max": values[-1],
                "step": step,
            }
        )
    task = tasks.task(
        "f02-burst",
        identity={
            "challenge": "synthetic-challenge",
            "contract_version": "fixture-v1",
            "action_grammar": {
                "schema": tasks.GRAMMAR_SCHEMA,
                "version": "fixture-v1",
                "variables": variables,
                "rules": [],
            },
            "optimizer": {"class": "exhaustive", "version": "v1"},
            "query_budget": len(actions),
            "seed": 0,
            "observer_version": "synthetic-observer-v1",
            "reference_bank": "synthetic-bank",
        },
        conditions=[{"id": condition, "stratum": "only"}],
        strata={"only": {"p": 1, "q": 1, "w": 1}},
        candidates=list(actions),
        actions=actions,
        objective={"quantity": "extra_energy_j", "unit": "J", "sense": "max", "aggregate": "worst"},
        limits=[{"quantity": "peak_top_c", "unit": "degC", "op": "<=", "value": 95}],
    )  # fmt: skip
    reference = [
        {"candidate": c, "condition": condition, "values": toy(condition, a["peak_w"], a["on_time_s"])}
        for c, a in actions.items()
    ]  # fmt: skip
    return export_questions("f02", task, reference)


def train_bytes(per_context=6, extra=()):
    rng = np.random.default_rng(20261010)
    lines = []
    for ctx in CONTEXTS:
        for k in range(per_context):
            peak = float(round(rng.uniform(80, 140)))
            on = float(round(rng.uniform(5, 20), 1))
            lines.append(
                json.dumps(
                    {
                        "schema": f02_kit.TRAIN_SCHEMA,
                        "case_id": f"{ctx}-{k}",
                        "inputs": {
                            **f02_kit.context(ctx),
                            "peak_w": peak,
                            "on_time_s": on,
                        },
                        "outputs": toy(ctx, peak, on),
                        "fixture": True,
                    }
                )
            )
    lines.extend(json.dumps(r) for r in extra)
    return ("\n".join(lines) + "\n").encode()


def load(data):
    return arm.load_train(f02_kit.KIT, data, arm.sha256(data))


def test_the_plan_covers_every_panel_row_and_the_edges_are_predicted():
    panel = export()
    assert arm.domain_gaps(f02_kit.KIT, panel) == []
    predictions, receipt = arm.run(
        f02_kit.KIT,
        panel,
        load(train_bytes()),
        scope="SYNTHETIC_FIXTURE",
        settings=QUICK,
    )
    # The menu's corners (80 W, 5 s; 140 W, 20 s) lie on the plan's boundary:
    # the registered domain supports them, so nothing abstains.
    assert receipt["abstained"] == 0
    assert receipt["train"]["support"] == "the registered TRAIN domain"
    assert len(ep._predictions(panel, predictions)) == 16


@pytest.mark.parametrize(
    "panel",
    [
        export(menu=[*MENU[:-1], (150.0, 20.0)]),
        export(menu=[*MENU[:-1], (140.0, 25.0)]),
        export(condition="c35-i55-s0.8-rectangular"),
    ],
)
def test_a_panel_row_outside_the_plan_refuses_the_run(panel):
    try:
        gaps = arm.domain_gaps(f02_kit.KIT, panel)
    except arm.ArmRefused as refused:
        assert refused.code == "CONTEXT_UNREGISTERED"
        return
    assert len(gaps) == 1
    with pytest.raises(arm.ArmRefused) as refused:
        arm.run(
            f02_kit.KIT,
            panel,
            load(train_bytes(per_context=2)),
            scope="SYNTHETIC_FIXTURE",
            settings=QUICK,
        )
    assert refused.value.code == "PANEL_OUTSIDE_TRAIN_DOMAIN"


def test_conditions_map_to_registered_contexts():
    assert len(CONTEXTS) == 24
    assert f02_kit.context("c40-i55-s0.8-rectangular") == {
        "coolant_c": 40.0,
        "h_w_m2_k": 1500.0,
        "initial_c": 55.0,
        "left_source_fraction": 0.8,
        "waveform": "rectangular",
    }
    with pytest.raises(arm.ArmRefused) as unreadable:
        f02_kit.context("context")
    assert unreadable.value.code == "CONDITION_UNREADABLE"


def test_train_must_lie_in_the_registered_domain():
    inside = json.loads(train_bytes(per_context=1).splitlines()[0])
    outside = {**inside, "inputs": {**inside["inputs"], "peak_w": 150.0}}
    with pytest.raises(arm.ArmRefused) as refused:
        load(train_bytes(per_context=1, extra=[outside]))
    assert refused.value.code == "TRAIN_OUTSIDE_REGISTERED_DOMAIN"
    bad = {**inside, "inputs": {**inside["inputs"], "waveform": "sawtooth"}}
    with pytest.raises(arm.ArmRefused) as refused:
        load(train_bytes(per_context=1, extra=[bad]))
    assert refused.value.code == "TRAIN_INPUTS_NOT_FINITE"


def test_the_context_is_one_hot_and_the_rebuild_is_reproducible():
    data = load(train_bytes())
    net = arm.Network(f02_kit.KIT, settings=QUICK)
    x = net._x([json.loads(line)["inputs"] for line in train_bytes().splitlines()[:2]])
    assert x.shape == (2, 2 + 2 + 2 + 2 + 2 + 3)
    fits = [arm.Network(f02_kit.KIT, settings=QUICK).fit(data, 5) for _ in range(2)]
    assert fits[0]["params_sha256"] == fits[1]["params_sha256"]
