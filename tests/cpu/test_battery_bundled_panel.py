"""OPT-09: public Graphite bundle registration; no model or solver runs."""

import copy
import json
from pathlib import Path

import pytest

from carbon.battery.value import contract as ev
from carbon.battery.value import level_compile
from carbon.battery.value import panel as pn
from carbon.battery.value.experiment import (
    LEVEL_COMPILER_REQUIRED,
    LEVEL_REFUSED,
    ExperimentError,
    member_bundle,
)
from scripts.dev.exam_design import runner, value_phases, value_plans

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "carbon/battery/value/contracts/ev4-dev-proof-bundled-v1.json"
SOURCE = ROOT / "carbon/battery/value/panels/proof-panel-levels-v1.json"
PANEL = "ev4-dev-proof-bundled"


class ProbeBackend:
    def __init__(self):
        self.identity = {"kind": "toy"}

    def reconstruct(self, _name, recipe, _seed):
        self.digest = recipe.recipe_digest
        return object(), {}

    def infer(self, _name, _state, _inputs):
        return {}


def test_exact_bundled_members_and_non_counting_lane_g():
    source = json.loads(SOURCE.read_bytes())
    selected = [row for row in source["members"] if row["source"]["bundled"]]
    rows = pn.members(PANEL)
    levels = pn.levels(PANEL)
    assert len(selected) == len(rows) == 10
    assert {
        level: sum(value[0] == level for value in levels.values())
        for level in range(1, 5)
    } == {
        1: 1,
        2: 3,
        3: 3,
        4: 3,
    }
    assert {row[0] for row in rows} == {
        f"{row['label']}-s{seed}" for row in selected for seed in row["seeds"]
    }
    assert all(not row["counts_for_level"] for row in selected if row["level"] == 4)
    assert all(
        not pn.BUNDLED_IDENTITIES[member]["counts_for_level"]
        for member, (level, _arm) in levels.items()
        if level == 4
    )
    assert PANEL not in pn.ATTACK_PANELS
    assert len(pn.members("ev4-dev-proof-l1")) == 20  # historical study unchanged


def test_contract_pins_public_source_and_every_member():
    contract, _digest = ev.load(CONTRACT)
    assert contract["panel"] == PANEL
    assert contract["panel_registration"] == ev.proof_bundled_registration()
    assert (
        contract["public_reference_sha256"]
        == ev.load(ROOT / "carbon/battery/value/contracts/ev4-dev-proof-l1-v1.json")[0][
            "public_reference_sha256"
        ]
    )
    bad = copy.deepcopy(contract)
    member = next(iter(bad["panel_registration"]["member_sha256"]))
    bad["panel_registration"]["member_sha256"][member] = "sha256:" + "0" * 64
    with pytest.raises(ev.ContractError, match="panel_member_mismatch"):
        ev.validate(bad)
    bad = copy.deepcopy(contract)
    bad["panel_registration"]["source_sha256"][SOURCE.name] = "sha256:" + "0" * 64
    with pytest.raises(ev.ContractError, match="panel_source_mismatch"):
        ev.validate(bad)
    bad = copy.deepcopy(contract)
    del bad["panel_registration"]
    with pytest.raises(ev.ContractError, match="panel_registration_required"):
        ev.validate(bad)


@pytest.mark.parametrize("level", (1, 2, 3, 4))
def test_rebuild_uses_registered_level_variant_and_recipe_digest(level, monkeypatch):
    source = json.loads(SOURCE.read_bytes())["members"]
    row = next(r for r in source if r["level"] == level and r["source"]["bundled"])
    member = f"{row['label']}-s{row['seeds'][0]}"
    backend = ProbeBackend()
    kwargs = {
        "level": level,
        "arm": row.get("arm"),
        "level_compiler": level_compile,
        "panel_name": PANEL,
    }
    with pytest.raises(ExperimentError, match=LEVEL_COMPILER_REQUIRED):
        member_bundle(backend, member, row["strategy"], row["seeds"][0], {})
    bundle, _state = member_bundle(
        backend, member, row["strategy"], row["seeds"][0], {}, **kwargs
    )
    assert bundle["recipe_digest"] == backend.digest == row["source"]["recipe_digest"]
    assert (
        level_compile.variant_digest(level, row.get("arm")) == row["variant"]["digest"]
    )
    with pytest.raises(ExperimentError, match=LEVEL_REFUSED):
        member_bundle(
            backend,
            member,
            {**row["strategy"], "parameters": {}},
            row["seeds"][0],
            {},
            **kwargs,
        )
    monkeypatch.setattr(level_compile, "variant_digest", lambda *_args: "sha256:wrong")
    with pytest.raises(ExperimentError, match=LEVEL_REFUSED):
        member_bundle(backend, member, row["strategy"], row["seeds"][0], {}, **kwargs)


def test_public_panel_plan_has_no_reference_solve_or_private_input():
    study = value_plans._study("ev4-bundled")
    plans = value_plans.panel_plans(
        1, study["contract"], study["prefix"], study["panel_data"]
    )
    assert len(plans) == 1
    plan = next(iter(plans.values()))
    assert plan["phase"] == "value_panel"
    assert plan["contract"] == CONTRACT.relative_to(ROOT).as_posix()
    assert any(path.endswith("decision-references.jsonl.gz") for path in plan["ship"])
    assert not any("refs-b/out" in path or "private" in path for path in plan["ship"])


def test_phase_uses_exact_public_contract_and_public_scoring_inputs(
    tmp_path, monkeypatch
):
    from carbon.battery.value import experiment as exp
    from carbon.battery.value import optimizer as op
    from scripts.dev.battery import l1_decision_q1 as l1

    seen = []

    def inputs(contract, repository, *, scoring_set):
        assert contract["panel"] == PANEL
        assert scoring_set is l1.public_ev4_scoring_set
        seen.append(repository)
        return {}

    monkeypatch.setattr(exp, "panel_inputs", inputs)
    monkeypatch.setattr(runner, "host_info", lambda: {"kind": "toy"})
    monkeypatch.setattr(op, "grid_predictions", lambda *_args: {})
    monkeypatch.setattr(
        op,
        "grid_document",
        lambda contract, *_args, **_kwargs: {"contract_digest": ev.digest(contract)},
    )
    value_phases.run_value_panel(
        {"contract": str(CONTRACT), "shard": 0, "shards": 10},
        str(tmp_path),
        backend=ProbeBackend(),
    )
    assert seen == ["."]
    assert len(list((tmp_path / "predictions").glob("*.json.gz"))) == 1
