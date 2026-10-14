"""Prospective composition adapter semantics; public CPU fixtures only."""

import copy
from dataclasses import replace

import pytest

from carbon.agent_campaign.attack import engine
from carbon.agent_campaign.attack.adapter import NOT_RUN, AttackInput
from carbon.agent_campaign.attack.adapters import battery as b
from carbon.agent_campaign.attack.adapters import battery_declarative as d
from carbon.agent_campaign.attack.adapters import battery_level2 as l2
from carbon.agent_campaign.attack.adapters import battery_level3 as l3


@pytest.mark.parametrize("module", [l2, l3])
def test_foreign_fields_are_positive_controls_and_malformed_shapes_still_fire(
    module, monkeypatch
):
    family = f"l{module.LEVEL}_cross_level_fields"
    original = module._families()
    for name, value in module._combination_controls():
        assert d.composition_gate(value)["status"] == "OK", name
        made = module.ADAPTER.rebuild(value)
        assert isinstance(made, b.Rebuilt)
        assert (
            made.detail["development"]["composition_digest"]
            == module.ADAPTER.contract_digest
        )
        assert made.detail["observation"] == "COMPILED_ONLY"
        assert (
            module.ADAPTER.oracle(family, AttackInput(name, value)).verdict == NOT_RUN
        )
    attacks = module._cross_level_attacks()
    for name, value in attacks:
        assert original[family].attack_shape(value)
        assert (
            module.ADAPTER.oracle(family, AttackInput(name, value)).verdict
            == engine.HELD
        )
    weakened = {
        **original,
        family: replace(original[family], boundary=d.unchecked_gate),
    }
    monkeypatch.setattr(module.ADAPTER, "_table", lambda: weakened)
    for name, value in attacks:
        verdict = module.ADAPTER.oracle(family, AttackInput(name, value))
        assert (
            verdict.verdict == engine.BREACHED
            and verdict.condition == engine.FINDING_CONDITION
        )


@pytest.mark.parametrize("module", [l2, l3])
def test_graph_digest_without_admitted_documents_is_unknown_not_a_finding(module):
    value = module._strategy(composition_graphs="sha256:" + "a" * 64)
    assert d.composition_gate(value)["code"] == "graph_workspace_unavailable"
    assert isinstance(module.ADAPTER.rebuild(value), b.Unrebuildable)
    result = module.ADAPTER.oracle(
        f"l{module.LEVEL}_cross_level_fields", AttackInput("raw_graph", value)
    )
    assert result.verdict == NOT_RUN and result.condition is None


def test_adapter_exact_composed_records_execute_and_each_changed_field_takes_effect():
    from carbon.agent_campaign.attack.adapters import battery_level1

    full = l2._strategy(
        muon_spectral=True,
        polish_steps=6,
        quasi_newton_family="bfgs",
        line_search="backtracking",
        loss_expressions=battery_level1.VALID["valid_robust_l2"],
    )
    first = d._state_digest(full, "composition", d.SEED)
    assert d._state_digest(full, "composition", d.SEED) == first
    for field in (
        "loss_expressions",
        "muon_spectral",
        "quasi_newton_family",
        "line_search",
    ):
        fewer = copy.deepcopy(full)
        fewer["parameters"].pop(field)
        assert d._state_digest(fewer, "composition", d.SEED) != first, field


def test_adapter_record_stages_the_same_parameters_as_its_executed_composition(
    tmp_path,
):
    import json
    import subprocess
    import sys
    from pathlib import Path

    from test_construction_contract import strategy

    from carbon.battery import development_rebuild
    from carbon.battery.worker import RECONSTRUCT_PROGRAM, reconstruct_files

    requested = strategy("l1", "spectral", "pool", "l3")
    made = l2.ADAPTER.rebuild(requested)
    assert isinstance(made, b.Rebuilt)
    found = d._compile_composition(requested)
    record = development_rebuild.record(made.detail["record"])
    assert record == found.record
    first = d._backend().reconstruct(None, found.construction, d.SEED, record)
    repository = Path(__file__).resolve().parents[2]
    program, files, trainer = development_rebuild.stage(
        record,
        RECONSTRUCT_PROGRAM,
        reconstruct_files(repository, found.construction, d.SEED),
        level1_program=lambda: pytest.fail("classic L1 route"),
    )
    assert trainer == development_rebuild.COMPOSED
    work, out = tmp_path / "work", tmp_path / "output"
    work.mkdir()
    out.mkdir()
    for name, body in files.items():
        (work / name).write_bytes(body)
    (work / "program.py").write_text(program, encoding="utf-8")
    subprocess.run(
        [sys.executable, "program.py"],
        cwd=work,
        env={
            "PYTHONPATH": str(repository),
            "JAX_PLATFORMS": "cpu",
            "PATH": "/usr/bin:/bin",
        },
        check=True,
        timeout=900,
    )
    staged = json.loads((out / "fit.json").read_text(encoding="utf-8"))
    assert staged["params_sha256"] == first[1]["params_sha256"]
