"""Discovery agrees with the real compiler without widening existing grants."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from c02_fixtures import compile_c02_plan

from carbon.reconstruction.catalogue import (
    capability_projection,
    reconstruction_capabilities,
)
from carbon.reconstruction.profile import compile_development_profile


@pytest.mark.parametrize("capability", reconstruction_capabilities())
def test_catalogue_matches_compiler_identity(tmp_path: Path, capability) -> None:
    plan = compile_c02_plan(
        tmp_path,
        backbone=capability.architecture_family,
        foundax=capability.implementation_id == "foundax",
    )
    bound = plan.backbone_binding
    actual = compile_development_profile(plan)
    assert (bound.backbone_id, bound.backbone_version) == (
        capability.backbone_id,
        capability.backbone_version,
    )
    assert (
        bound.implementation_pin.implementation_id,
        bound.implementation_pin.implementation_version,
        bound.implementation_pin.content_digest,
    ) == (
        capability.implementation_id,
        capability.implementation_version,
        capability.implementation_digest,
    )
    assert (
        bound.environment_pin.environment_id,
        bound.environment_pin.environment_version,
        bound.environment_pin.content_digest,
    ) == (
        capability.environment_id,
        capability.environment_version,
        capability.environment_digest,
    )
    for name in (
        "backbone_kind",
        "environment_digest",
        "input_interface_digest",
        "output_interface_digest",
    ):
        assert getattr(actual, name) == getattr(capability, name)
    assert actual.profile_id == capability.reconstruction_profile_id
    assert actual.profile_version == capability.reconstruction_profile_version


def test_only_registered_implementations_and_current_research_selection() -> None:
    entries = reconstruction_capabilities()
    assert {item.backbone_id for item in entries} == {
        "carbon_jax_fno1d",
        "carbon_jax_deeponet1d",
        "foundax_fno1d",
    }
    assert {
        item.backbone_id for item in entries if item.current_research_selection
    } == {"carbon_jax_fno1d", "carbon_jax_deeponet1d"}
    assert all(item.backend == "cpu" for item in entries)
    assert all(item.host_availability == "NOT_OBSERVED" for item in entries)
    assert all(
        item.evidence_use == "UNQUALIFIED_PUBLIC_DEVELOPMENT" for item in entries
    )
    assert len(entries[-1].training_objectives) == 1
    with pytest.raises(FrozenInstanceError):
        entries[0].backend = "tpu"


@pytest.mark.parametrize("audience", ("miner", "validator", "workbench"))
def test_projection_is_public_serializable_and_defensively_copied(
    audience: str,
) -> None:
    projection = capability_projection(audience=audience)
    assert projection["audience"] == audience
    assert (
        json.loads(json.dumps(projection))["implementations"][0]["framework"] == "jax"
    )
    projection["implementations"][0]["backend"] = "tpu"
    projection["limitations"].clear()
    clean = capability_projection(audience=audience)
    assert clean["implementations"][0]["backend"] == "cpu"
    assert clean["limitations"]
    assert (
        clean["implementations"]
        == capability_projection(audience="miner")["implementations"]
    )


@pytest.mark.parametrize(
    "audience", ("operator", "public", "MINER", "", None, [], True)
)
def test_unknown_audience_rejected(audience) -> None:
    with pytest.raises(ValueError, match="unsupported capability audience"):
        capability_projection(audience=audience)


def test_discovery_does_not_import_numerical_or_compatibility_runtimes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import importlib.abc
import sys
blocked = {'jax', 'jaxlib', 'numpy', 'torch', 'neuralop', 'physicsnemo'}
attempted = []
class RejectRuntime(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in blocked or fullname.startswith('carbon.backbones'):
            attempted.append(fullname)
            raise AssertionError('discovery imported runtime: ' + fullname)
sys.meta_path.insert(0, RejectRuntime())
from carbon.reconstruction.catalogue import capability_projection
assert len(capability_projection(audience='miner')['implementations']) == 3
assert not attempted, attempted
assert not any(name.split('.')[0] in blocked for name in sys.modules)
""",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
