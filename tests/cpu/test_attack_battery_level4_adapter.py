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
