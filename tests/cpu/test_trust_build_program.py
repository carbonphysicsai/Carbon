"""The trust BUILD program and staging (SELF_TRUST H3d-2c part 2): a candidate that declares self-trust builds in a container that stages
the trust trainer, state, registration and trust-head rule and checks the pinned trust trainer; every other build keeps its staged
modules and program text byte for byte.
"""

from __future__ import annotations

import dataclasses

import pytest

from carbon.development_session import (
    direct_graph_construction_worker as worker,
    physical_graph_adapter_v2 as adapter,
)
from carbon.development_session.construction_recipe import RecipeRefused

TRUST_MODULES = (
    "carbon.development_session.physical_graph_state_v3",
    "carbon.development_session.physical_graph_trainer_v4",
    "carbon.development_session.physical_graph_trust_registry",
    "carbon.level4.trust_head",
)
KEY = next(iter(adapter.SPECS))


def test_the_v2_staged_set_has_no_trust_module_and_the_trust_set_is_it_plus_exactly_four():
    assert not any(name in worker.PHYSICAL_V2_STAGED_MODULES for name in TRUST_MODULES)
    assert worker.PHYSICAL_V2_TRUST_STAGED_MODULES == (
        *worker.PHYSICAL_V2_STAGED_MODULES,
        *TRUST_MODULES,
    )


def test_the_trust_build_program_differs_from_the_v2_one_only_by_its_four_anchored_changes():
    base, trust = worker.PHYSICAL_V2_BUILD_PROGRAM, worker.PHYSICAL_V2_TRUST_BUILD_PROGRAM
    assert trust != base and "trainer_v4" not in base and "TRAINER_V4_SHA256" not in base
    assert trust.count("physical_graph_state_v3 import load") == 1
    assert "pinned graph trainer v4 differs" in trust
    # the v2 program still checks v2's and v3's pins exactly as before
    for text in ("pinned graph trainer differs", "pinned graph trainer v3 differs"):
        assert text in base and text in trust
    restored = (
        trust.replace(repr(worker.PHYSICAL_V2_TRUST_STAGED_MODULES), repr(worker.PHYSICAL_V2_STAGED_MODULES))
        .replace("physical_graph_state_v3 import load", "physical_graph_state_v2 import load")
        .replace("TRAINER_V3_SHA256, TRAINER_V4_SHA256,", "TRAINER_V3_SHA256,")
        .replace(
            'trainer4 = (work / "carbon.development_session.physical_graph_trainer_v4.py").read_bytes()\n'
            'if digest(trainer4) != "sha256:" + TRAINER_V4_SHA256:\n'
            '    raise ValueError("pinned graph trainer v4 differs")\n',
            "",
        )
    )
    assert restored == base
    compile(trust, "trust_build_program", "exec")


def _stage(monkeypatch, *, trust_spec, trust):
    spec = adapter.SPECS[KEY]
    if trust_spec:
        spec = dataclasses.replace(spec, trust_outputs=2)
        monkeypatch.setitem(adapter.SPECS, KEY, spec)
    binding = {
        "challenge_id": spec.challenge_id,
        "challenge_version": spec.version,
        "train_digest": "sha256:" + spec.train_sha256,
    }
    limits = {"graph_training_adapter": adapter.adapter_block(*KEY)}
    allowlist = adapter.served_allowlist_bytes(*KEY)
    return worker._v2_stage(binding, limits, allowlist, trust=trust)


def test_a_plain_build_stages_no_trust_file(monkeypatch):
    _, _, files = _stage(monkeypatch, trust_spec=False, trust=False)
    assert not any("trainer_v4" in name or "state_v3" in name or "trust_" in name for name in files)


def test_a_trust_build_stages_the_trust_files_and_verifies_the_pinned_trainer(monkeypatch):
    _, _, files = _stage(monkeypatch, trust_spec=True, trust=True)
    for module in TRUST_MODULES:
        assert module + ".py" in files, module
    assert files["carbon.development_session.physical_graph_trainer_v4.py"] == adapter.trust_trainer_source()


def test_a_trust_build_of_a_version_that_offers_none_is_refused_typed(monkeypatch):
    with pytest.raises(RecipeRefused, match="direct_graph_trust_interface_not_offered"):
        _stage(monkeypatch, trust_spec=False, trust=True)
