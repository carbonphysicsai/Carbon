"""Calibration grading of a v2 sealed-grid bank with interleaved private probes: the
proof run grades sealed v2 banks, not the retained development bundle. F02's sealed
batch, with the registered law and response legs, graded through `calibration_grade`
equals the sealed grader's own measurement and sees every probe row."""

from __future__ import annotations

import json

import numpy as np
import pytest
from test_f02_sealed_pack import batch

from carbon.challenge_kit import f02_sealed_pack as sealed
from carbon.challenge_kit import physical_pack
from carbon.challenge_validator import calibration_grade as cg
from carbon.scoring import dual_score
from carbon.scoring import f02_sealed_dual_pack
from carbon.scoring import physical_dual_pack as physical


def _power_law(train_inputs, train_targets):
    x = np.asarray(train_inputs, float)
    rise = np.asarray(train_targets, float)[:, 0] - 40.0
    design = np.column_stack([np.ones(len(x)), np.log(x)])
    coefficients, *_ = np.linalg.lstsq(design, np.log(rise), rcond=None)
    return lambda p: [
        40.0
        + float(
            np.exp(np.concatenate([[1.0], np.log(np.asarray(p, float))]) @ coefficients)
        )
    ]


def test_a_v2_sealed_bank_with_probes_grades_like_the_sealed_grader():
    from carbon.challenge_kit import f02_train

    adapter = f02_sealed_dual_pack.adapter("2.3")
    document, records = batch()
    bank = sealed.sealed_bank(document, records)  # probes interleaved
    cohorts = list(bank["cohorts"])
    assert "probe_response" in cohorts
    public = physical_pack.public_roles(adapter.CHALLENGE, "2.3")
    names = adapter.input_names()
    rows = physical.bank_rows(bank, names)
    train = f02_train.load_public_train("2.0")
    model = _power_law(train["inputs"], train["targets"])
    outputs = [
        (
            list(map(float, model(list(r["inputs"].values()))))
            if r["cohort"] == "probe_response"
            else [float(r["reference"][0])]
        )
        for r in rows
    ]
    definition = adapter.definition(bank=bank, train_raw=public["train"])
    assert "physics" in definition and "critical" in definition
    limits = json.loads(public["important_limit_definition"])
    objective = json.loads(public["design_objective"])
    direct = adapter.measure(
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        definition=definition,
        limits=limits,
        objective=objective,
        train_raw=public["train"],
        names=names,
    )
    from test_dual_score import fixture

    body, _ = fixture()
    body["value_weight"] = 0.5
    for leg in ("A", "D"):
        body["legs"][leg]["components"][0]["metric"] = physical.METRICS[leg]
    body["hard_gates"] = list(direct["gates"])
    calls = []

    def infer(inputs):
        calls.append(len(inputs))
        return outputs

    result = cg.grade(
        adapter=adapter,
        bank=bank,
        pack=dual_score.register_pack(body),
        definition=definition,
        limits=limits,
        objective=objective,
        train_raw=public["train"],
        interface_names=names,
        infer=infer,
        entry_id="sha256:" + "a" * 64,
        challenge=adapter.CHALLENGE,
    )
    # the probes ride in the same inference calls as the cells
    assert calls == [len(bank["inputs"])] * 3
    assert len(bank["inputs"]) > sum(1 for c in bank["cohorts"] if c != "probe_response")
    assert result["A"] == direct["A"] and result["D"] == direct["D"]
    assert result["A_legs"] == direct["A_legs"]
    assert set(result["A_legs"]) == {"A_acc", "A_robust", "A_law", "A_response"}
    assert result["total"] == pytest.approx(0.5 * direct["A"] + 0.5 * direct["D"])
    assert result["gates"] == {k: bool(v) for k, v in direct["gates"].items()}
    text = json.dumps(result)
    for case_id in bank["case_ids"]:
        assert case_id not in text
