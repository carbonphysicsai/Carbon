"""MODEL-PREDICTIONS-FOR-EVIDENCE-01: the Carbon arm and the battery v3 kit, on
synthetic fixtures. The predictions are checked by the evidence pipeline's own
Carbon hop (`evidence_pipeline._predictions`); no solve, no panel truth read."""

from __future__ import annotations

import dataclasses
import json
import math

import pytest
from test_evidence_pipeline import bundle

from carbon.development_comparison import battery_v3_kit
from carbon.development_comparison import carbon_arm as arm
from carbon.development_comparison import cheap_baselines as cb
from carbon.development_comparison import evidence_pipeline as ep

#: Small and quick: the tests check the mechanism, never a model's quality.
QUICK = {"steps": 300, "width": 32, "depth": 2}

#: The fixture export's observables (`test_evidence_pipeline.bundle`).
FIXTURE_KIT = dataclasses.replace(
    battery_v3_kit.KIT,
    kit_id="fixture-kit",
    row_inputs=lambda row: {**battery_v3_kit.action_inputs(row), "soc0": 0.1},
    observables=("minutes", "temperature"),
    model_id="fixture-carbon",
)


def fixture_export():
    _, documents = bundle("battery-v3")
    return documents["export"]


def train_bytes(kit=FIXTURE_KIT, *, c1=(1, 1.25, 1.5, 1.75, 2), fixture=True, extra=()):
    """A synthetic TRAIN set over the fixture's action space and bands, from a
    toy formula (never a panel value)."""
    lines = []
    for a in c1:
        for b in (0.25, 0.3, 0.375, 0.45, 0.5):
            for band in (5, 15, 25, 35, 40):
                outputs = {"minutes": 30 - a - b, "temperature": band + a + b}
                if kit.observables != FIXTURE_KIT.observables:
                    outputs = {q: a + b + band / 10 for q in kit.observables}
                record = {
                    "schema": kit.train_schema,
                    "case_id": f"t-{a}-{b}-{band}",
                    "inputs": {
                        "c1": a,
                        "c2": b,
                        "switch_v": 4,
                        "cooling": 1,
                        "ambient_c": band,
                        "soc0": 0.1,
                    },
                    "outputs": outputs,
                }
                if fixture:
                    record["fixture"] = True
                lines.append(json.dumps(record))
    lines.extend(json.dumps(record) for record in extra)
    return ("\n".join(lines) + "\n").encode()


def load(data, kit=FIXTURE_KIT):
    return arm.load_train(kit, data, arm.sha256(data))


def test_predictions_pass_the_pipelines_carbon_hop():
    export = fixture_export()
    predictions, receipt = arm.run(
        FIXTURE_KIT,
        export,
        load(train_bytes()),
        scope="SYNTHETIC_FIXTURE",
        settings=QUICK,
    )
    accepted = ep._predictions(export, predictions)
    assert len(accepted) == len(cb._physical_rows(export)) == len(predictions["rows"])
    assert predictions["source_receipt_digest"] == arm.sha256(arm.canonical(receipt))
    assert receipt["abstained"] == 0
    cost = receipt["cost"]
    assert cost["fit"]["fit_wall_s"] > 0 and cost["inference"]["wall_s"] >= 0
    assert cost["inference"]["rows"] == len(predictions["rows"])
    assert all(
        math.isfinite(v) for row in predictions["rows"] for v in row["values"].values()
    )


def test_rows_outside_trains_support_abstain_explicitly():
    export = fixture_export()
    predictions, receipt = arm.run(
        FIXTURE_KIT,
        export,
        load(train_bytes(c1=(1, 1.25, 1.5))),
        scope="SYNTHETIC_FIXTURE",
        settings=QUICK,
    )
    rows = predictions["rows"]
    actions = {r["candidate"]: r["action"] for r in cb._physical_rows(export)}
    for row in rows:
        assert (row["values"] is None) == (actions[row["candidate"]]["c1"] > 1.5)
    assert receipt["abstained"] == sum(row["values"] is None for row in rows) > 0
    ep._predictions(export, predictions)  # abstention is accepted, never repaired


def test_the_rebuild_is_reproducible_at_its_seed():
    data = load(train_bytes())
    stats = [
        arm.Network(FIXTURE_KIT, settings=QUICK).fit(data, seed)["params_sha256"]
        for seed in (3, 3, 4)
    ]
    assert stats[0] == stats[1] != stats[2]


def test_the_pytorch_backend_trains_the_same_network():
    pytest.importorskip("torch")
    data = load(train_bytes())
    jax_fit = arm.Network(FIXTURE_KIT, settings=QUICK).fit(data, 3)
    torch_net = arm.Network(FIXTURE_KIT, backend="pytorch", settings=QUICK)
    torch_fit = torch_net.fit(data, 3)
    assert torch_fit["n_params"] == jax_fit["n_params"]
    [values] = torch_net.predict([json.loads(train_bytes().splitlines()[0])["inputs"]])
    assert set(values) == set(FIXTURE_KIT.observables)


def test_a_fixture_train_set_can_never_produce_public_predictions():
    with pytest.raises(arm.ArmRefused) as refused:
        arm.run(
            FIXTURE_KIT,
            fixture_export(),
            load(train_bytes()),
            scope="PUBLIC_DEVELOPMENT",
            settings=QUICK,
        )
    assert refused.value.code == "FIXTURE_TRAIN_CANNOT_BE_PUBLIC"


def test_the_battery_v3_kit_names_the_panels_observables_and_refuses_others(
    monkeypatch,
):
    kit = battery_v3_kit.KIT
    assert kit.observables == (
        "charging_t_max_c",
        "minutes",
        "plating_min_v",
        "q30_over_q1",
        "v_max_v",
    )
    assert kit.names == ("c1", "c2", "switch_v", "cooling", "ambient_c", "soc0")
    row = {
        "band": 25.0,
        "action": {"c1": 0.25, "c2": 0.3, "switch_v": 4.1, "cooling": 4},
        "values": {"never": "read"},
    }
    # The panel's SOC0 is not in the export: it is the registered value, and
    # unregistered the kit predicts nothing.
    assert kit.row_inputs(row)["soc0"] == battery_v3_kit.PANEL_SOC0 == 0.1
    assert "initial_soc" in battery_v3_kit.PANEL_SOC0_SOURCE
    monkeypatch.setattr(battery_v3_kit, "PANEL_SOC0", None)
    with pytest.raises(arm.ArmRefused) as unregistered:
        kit.row_inputs(row)
    assert unregistered.value.code == "PANEL_SOC0_UNREGISTERED"
    monkeypatch.undo()
    assert battery_v3_kit.action_inputs(row) == {
        "c1": 0.25,
        "c2": 0.3,
        "switch_v": 4.1,
        "cooling": 4,
        "ambient_c": 25.0,
    }
    kit = dataclasses.replace(kit, row_inputs=FIXTURE_KIT.row_inputs)
    with pytest.raises(arm.ArmRefused) as refused:
        arm.run(
            kit,
            fixture_export(),
            load(train_bytes(kit), kit),
            scope="SYNTHETIC_FIXTURE",
            settings=QUICK,
        )
    assert refused.value.code == "OBSERVABLE_INVENTORY_MISMATCH"


@pytest.mark.parametrize(
    "change,code",
    [
        (lambda data: (data, "sha256:" + "0" * 64), "TRAIN_SHA256_MISMATCH"),
        (
            lambda data: (data.replace(b'"minutes"', b'"hours"', 1), None),
            "TRAIN_RECORD_SHAPE",
        ),
    ],
)
def test_train_is_pinned_and_shaped(change, code):
    data, pin = change(train_bytes())
    with pytest.raises(arm.ArmRefused) as refused:
        arm.load_train(FIXTURE_KIT, data, pin or arm.sha256(data))
    assert refused.value.code == code


def test_a_non_finite_output_excludes_its_record_and_is_counted():
    record = json.loads(train_bytes().splitlines()[0])
    record["outputs"]["minutes"] = None
    data = train_bytes(extra=[record])
    train = load(data)
    assert train.excluded == 1 and len(train.records) == 125


def test_fixture_and_public_records_never_mix():
    record = json.loads(train_bytes().splitlines()[0])
    del record["fixture"]
    with pytest.raises(arm.ArmRefused) as refused:
        load(train_bytes(extra=[record]))
    assert refused.value.code == "TRAIN_MIXES_FIXTURE_AND_PUBLIC"


def test_the_command_writes_pinned_predictions_and_never_overwrites(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(arm, "kits", lambda: {"battery-v3": FIXTURE_KIT})
    monkeypatch.setattr(arm, "TRAINER_DEFAULTS", {**arm.TRAINER_DEFAULTS, **QUICK})
    export = json.dumps(fixture_export()).encode()
    (tmp_path / "export.json").write_bytes(export)
    data = train_bytes()
    (tmp_path / "train.jsonl").write_bytes(data)
    argv = [
        "battery-v3",
        "--export",
        str(tmp_path / "export.json"),
        "--export-sha256",
        arm.sha256(export),
        "--train",
        str(tmp_path / "train.jsonl"),
        "--train-sha256",
        arm.sha256(data),
        "--scope",
        "SYNTHETIC_FIXTURE",
        "--output-dir",
        str(tmp_path / "arm"),
    ]
    assert arm.main(argv) == 0
    done = json.loads(capsys.readouterr().out)
    for name, pin in done["pins"].items():
        assert arm.sha256((tmp_path / "arm" / name).read_bytes()) == pin
    receipt = json.loads((tmp_path / "arm" / "receipt.json").read_bytes())
    assert receipt["code"]["files"]["carbon_arm.py"].startswith("sha256:")
    assert arm.main(argv) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "OUTPUT_EXISTS"
