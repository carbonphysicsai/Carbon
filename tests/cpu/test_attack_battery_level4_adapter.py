"""Battery's Level 4 attack adapter (LEVEL4-DEV-VARIANT-01): the Â§8 suite.

Claims tested:

1. The adapter is registered at (battery, 4), passes the core's validation
   (all eight Track A checks supplied, trained and held-out controls), and
   attacks the registered variant (`contract_digest` is its digest).
2. Every family's attacks are HELD at Carbon's real boundary (G3, G4,
   rebuild), every vulnerable specimen FIRES, and every control PASSES.
3. The families follow the allowlist: every refused op is an attack.
4. Seams are NOT_RUN with an owner; rebuild compiles a strategy under the
   variant and labels it blocked until D3; a bad graph slot is refused.
5. Finding fixed at G4: a document whose declared shapes lie is refused at
   validation (`declared_aval_mismatch`), not only on execution.
"""

from __future__ import annotations

import copy
import os

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.agent_campaign.attack import adapters, engine
from carbon.agent_campaign.attack.adapter import TRACK_A_CHECKS, validate
from carbon.agent_campaign.attack.adapters import battery as b
from carbon.agent_campaign.attack.adapters import battery_level4 as L4


@pytest.fixture(scope="module")
def adapter():
    return adapters.load(b.CHALLENGE_ID, 4)


def test_registered_valid_and_bound_to_its_variant(adapter):
    assert (b.CHALLENGE_ID, 4) in adapters.registered()
    validate(adapter)
    assert adapter.level == 4 and adapter.contract_digest == L4.variant().digest
    checks = {f.check for f in adapter.families()} | {
        s.check for s in adapter.level_families()
    }
    assert checks == set(TRACK_A_CHECKS)
    assert not any(s.level == 4 for s in b.ADAPTER.level_families())


def test_every_attack_held_every_specimen_fired(adapter):
    for definition in adapter.families():
        run = engine.run_family(definition.family)
        verdicts = {(r["role"], r["verdict"]) for r in run.records}
        attacks = [r for r in run.records if r["role"] == "attack"]
        assert attacks and {r["verdict"] for r in attacks} == {"HELD"}, definition.name
        assert ("specimen", "SILENT") not in verdicts, definition.name
        assert ("control", "PASSED") in verdicts, definition.name


def test_every_refused_op_is_attacked(adapter):
    refused = {n for n, e in L4._allowlist().ops.items() if e["default"] == "refuse"}
    attacked = {name[3:] for name, _ in L4._escape_attacks()}
    assert refused == attacked


def test_seams_rebuild_and_refusals(adapter):
    from carbon.battery import level4, level4_worker

    assert {s.state for s in adapter.level_families()} == {b.NOT_RUN}
    strategy = L4._strategy(**{level4.FIELD: "sha256:" + "cd" * 32})
    made = adapter.rebuild(strategy)
    assert isinstance(made, b.Rebuilt)
    assert made.detail["rebuild"] == level4_worker.REBUILD_LABEL
    bad = adapter.rebuild(L4._strategy(**{level4.FIELD: "not-a-digest"}))
    assert isinstance(bad, b.Unrebuildable)
    assert adapter.admission_refusals(L4._strategy(**{level4.FIELD: "x"}))
    assert adapter.permission_inventory()["profile"] == "level-4"


def test_declared_shape_lie_is_refused_at_g4():
    from carbon.level4 import allowlist as allowlist_module
    from carbon.level4 import graph, specimens
    from carbon.level4 import validate as g4

    allowlist = allowlist_module.load()
    doc = copy.deepcopy(specimens._small_document(allowlist))
    node = next(n for n in doc["graphs"]["main"]["nodes"] if n["op"] == "tanh")
    node["out"][0]["shape"] = [4, 3]
    with pytest.raises(graph.GraphRefused) as refused:
        g4.validate(graph.parse(graph.dumps(doc), max_bytes=1 << 26), allowlist)
    assert refused.value.code == "declared_aval_mismatch"


def test_declared_shape_lie_stays_a_permanent_specimen(adapter):
    # Test Lead ruling: PROTECTED. The lie is an attack in the §8 suite, held
    # by Carbon's gates with its typed code, and the unchecked control fires.
    attacks = dict(L4._integrity_attacks())
    value = attacks["declared_shape_lie"]
    held = L4.carbon_gates(value)
    assert (held["status"], held["code"]) == ("REFUSED", "declared_aval_mismatch")
    assert L4._accepted(L4.unchecked_gate(value))


FAMILY_CASES = [(4, "l4_constant_smuggling")]


def _session_attempt(identity, strategy_json, design):
    import json as _json

    from carbon.agent_campaign.attack import analysis
    from carbon.agent_campaign.attack.identity import digest

    return analysis.Attempt(
        identity=identity,
        epoch=1,
        stage=None,
        turn=1,
        position=0,
        tool=analysis.PREFIX + "start_research_task",
        arguments={
            "action": "check_design",
            "arguments_json": _json.dumps({"design": design}),
            "kind": "workspace",
            "strategy_json": strategy_json,
        },
        result={"status": "MINER_PATH_REFUSED"},
        withheld=None,
        intent_digest=digest(identity.encode()),
        result_digest=digest(b"refused"),
    )


@pytest.mark.parametrize("level,family", FAMILY_CASES)
def test_a_session_attempt_is_judged_never_an_oracle_crash(level, family):
    """Stage-A L2-L4 (2026-10-12): verify hands these adapters a view without
    a `value` (they inherit Level 0's `attempt_input`), and the generic oracle
    crashed (`oracle_crashed:TypeError`, INFRA). The value is now the
    attempt's strategy, unwrapped as the rebuild unwraps it."""
    import json as _json

    from carbon.agent_campaign.attack import adapter as core
    from carbon.agent_campaign.attack import verify

    adapter = core.ADAPTERS[("battery-fastcharge-ageing-development-v1", level)]
    design = {"strategy": {"schema_version": "1.0",
              "challenge_id": "battery-fastcharge-ageing-development-v1",
              "backbone": "mlp", "parameters": {}}}  # fmt: skip
    for attempt in (
        _session_attempt("epoch-1-tool-003", _json.dumps(design), design),
        _session_attempt("epoch-1-tool-004", None, design),
    ):
        verdict = verify.verify(attempt, adapter, family=family)
        assert not str(verdict.reason).startswith("oracle_crashed"), verdict
        assert verdict.outcome != verify.INFRA, verdict


def test_a_session_attempt_carrying_a_graph_document_is_judged_on_it():
    """The L4 graph families judge the document an attempt carries."""
    import json as _json

    from carbon.agent_campaign.attack import adapter as core
    from carbon.agent_campaign.attack import verify
    from carbon.agent_campaign.attack.adapters import battery_level4 as l4

    adapter = core.ADAPTERS[("battery-fastcharge-ageing-development-v1", 4)]
    family = "l4_constant_smuggling"
    document = l4._family_table()[family][5]["document"]
    attempt = _session_attempt("epoch-1-tool-006", None, {"document": document})
    view = l4.graph_view(
        verify.oracle_attempt(attempt, None, adapter=adapter, rebuilt=True)
    )
    assert view.value == {"document": document}
    result = adapter.oracle(family, view)
    assert result.verdict not in ("CRASHED", "FAILED_INFRA"), result
    assert _json.loads(document)  # a real graph document, not a strategy
