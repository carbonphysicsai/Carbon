"""DASHBOARD-01 D2: the design showcase replays public EV4 material honestly.

The optimizer commits before any reference is read, the replay agrees with
`tasks.judge`, the projection matches battery Q3's, and only committed public
inputs (checked against their pins) are read.
"""

from __future__ import annotations

import gzip
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from carbon.battery.value import contract as ev
from carbon.dashboard import showcase
from carbon.design_search import tasks

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tests" / "cpu" / "showcase_check.cjs"


@pytest.fixture(scope="module")
def public():
    return showcase.load_public()


def _scenario(public, scenario_id):
    return next(s for s in ev.scenarios(public["contract"]) if s["id"] == scenario_id)


def _control_replay(public, scenario_id, name):
    scenario = _scenario(public, scenario_id)
    task = showcase.register_task(public, scenario)
    reference = showcase.truth(public, task, scenario)
    spec = next(s for s in showcase.control_specs(task) if s["name"] == name)
    model = {"id": f"CONTROL-{name}", "kind": "CONTROL", "control": name, "label": name}
    predictor = showcase.control_predictor(task, spec, reference)
    return showcase.replay(public, scenario, model=model, predictor=predictor)


def test_public_inputs_are_pinned_and_public(public):
    assert public["contract"]["data_scope"]["classification"] == "PUBLIC_SYNTHETIC"
    assert len(public["rows"]) == 840


def test_unregistered_inputs_are_refused():
    with pytest.raises(showcase.ShowcaseError):
        showcase._read("carbon/challenge_validator/tuning.py")


def test_tampered_references_are_refused(monkeypatch):
    original = showcase._read

    def altered(relative):
        body = original(relative)
        if relative == showcase.REFERENCES:
            return gzip.compress(gzip.decompress(body) + b"\n")
        return body

    monkeypatch.setattr(showcase, "_read", altered)
    with pytest.raises(showcase.ShowcaseError, match="pin"):
        showcase.load_public()


def test_projection_matches_battery_q3(public):
    from carbon.design_search import battery_q3_v8

    contract = public["contract"]
    rows = list(public["rows"].values())[::37]
    assert rows
    for row in rows:
        assert showcase.projection(contract, row) == battery_q3_v8._projection(
            contract, row
        )


def test_task_registration_follows_the_contract(public):
    scenario = _scenario(public, "D-T24-S0.33")
    task = showcase.register_task(public, scenario)
    assert task["schema"] == tasks.RUNNABLE_SCHEMA
    assert len(task["candidates"]) == 35
    bands = public["contract"]["reference"]["uncertainty"]["bands"]
    limits = {limit["quantity"]: limit for limit in task["limits"]}
    assert limits["plating_margin_v"]["band"] == bands["plating_margin_v"]
    assert limits["peak_temperature_c"]["value"] == 45.0
    assert task["objective"]["quantity"] == "time_to_cv_onset_s"


def test_the_optimizer_commits_before_any_reference_is_read(public, monkeypatch):
    scenario = _scenario(public, "D-T5-S0.12")
    task = showcase.register_task(public, scenario)
    reference = showcase.truth(public, task, scenario)
    events = []
    inner = showcase.control_predictor(task, showcase.control_specs(task)[0], reference)

    def predictor(action, condition):
        events.append("query")
        return inner(action, condition)

    original_truth = showcase.truth

    def watched(*args):
        events.append("truth")
        return original_truth(*args)

    monkeypatch.setattr(showcase, "truth", watched)
    showcase.replay(
        public,
        scenario,
        model={"id": "CONTROL-edge", "kind": "CONTROL", "label": "edge"},
        predictor=predictor,
    )
    assert events.count("truth") == 1
    assert "query" not in events[events.index("truth") :]


@pytest.mark.parametrize(
    ("scenario_id", "control"),
    [("D-T24-S0.33", "edge"), ("V-T19-S0.22", "caution"), ("D-T34-S0.48", "sign")],
)
def test_replay_agrees_with_judge_and_marks_misses(public, scenario_id, control):
    document = _control_replay(public, scenario_id, control)
    scenario = _scenario(public, scenario_id)
    task = showcase.register_task(public, scenario)
    reference = showcase.truth(public, task, scenario)
    commitment = _recommit(public, scenario, control)
    assert (
        document["provenance"]["commitment_digest"] == commitment["commitment_digest"]
    )
    judged = tasks.judge(
        task,
        commitment,
        {(c, showcase.CONDITION): r for c, r in reference.items() if r is not None},
    )
    result = document["result"]
    for key in ("kind", "selected", "best", "reference_state"):
        assert result[key] == judged[key]
    assert result["regret_s"] == judged["regret"]
    if judged["regret"] is not None:
        assert result["regret_buyer_units"] == judged["regret"] / 120.0
    assert result["false_feasible"] == (judged["kind"] == "SELECTED_INFEASIBLE")
    for step in document["steps"]:
        expected = bool(
            step["predicted"]
            and step["truth"]
            and step["predicted"]["feasible"] is True
            and step["truth"]["feasible"] is False
        )
        assert step["safety_miss"] == expected
        if step["truth"] and not step["truth"]["reached"]:
            assert step["truth"]["time_to_cv_onset_s"] is None
    assert result["safety_misses"] == sum(s["safety_miss"] for s in document["steps"])
    assert document["labels"][:2] == ["DEVELOPMENT", "PUBLIC_SYNTHETIC"]
    assert document["provenance"]["references_sha256"] == public["references_sha256"]


def _recommit(public, scenario, control):
    task = showcase.register_task(public, scenario)
    reference = showcase.truth(public, task, scenario)
    spec = next(s for s in showcase.control_specs(task) if s["name"] == control)
    run = tasks.run_optimizer(
        task,
        showcase.control_predictor(task, spec, reference),
        model_id=f"CONTROL-{control}",
    )
    return run["commitment"]


def test_edge_optimist_shows_a_false_feasible_pick(public):
    document = _control_replay(public, "D-T24-S0.33", "edge")
    assert document["result"]["false_feasible"] is True
    assert document["result"]["safety_misses"] >= 1


def test_build_all_writes_an_index(public, tmp_path, monkeypatch):
    real = ev.scenarios
    monkeypatch.setattr(
        showcase.ev, "scenarios", lambda contract, split=None: real(contract)[:1]
    )
    index = showcase.build_all(tmp_path / "showcase")
    assert len(index["replays"]) == 3
    for entry in index["replays"]:
        body = json.loads((tmp_path / "showcase" / entry["file"]).read_text())
        assert body["schema"] == showcase.REPLAY_SCHEMA


def test_replays_in_node(public, tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed here")
    files = []
    for scenario_id, control in (
        ("D-T24-S0.33", "edge"),
        ("V-T19-S0.22", "caution"),
        ("D-T5-S0.12", "sign"),
    ):
        path = tmp_path / f"{scenario_id}-{control}.json"
        path.write_text(json.dumps(_control_replay(public, scenario_id, control)))
        files.append(str(path))
    result = subprocess.run(
        [node, str(CHECK), *files], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["replays"] == len(files)
