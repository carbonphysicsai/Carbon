"""A served version's published resource policy is the one every route enforces
(Validator ruling on PROOF_RUN_UNRESOLVED_CULPRIT_20261024.md, A+).

One mapping, `worker_resources_version` of the version's served allowlist, feeds
the kit builders (what is published), `verify_direct_resource_policy` (admission,
graph build and inference, paired inference, calibration, retention) and the
runner argument of the graph build, so a v7 version cannot publish one profile
and run under another. Older versions keep today's profile and their bytes."""

from __future__ import annotations

import os
import re
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from carbon.battery import construction_bundle_material as battery_material
from carbon.challenge_kit import physical_material
from carbon.challenge_kit import version_registry as registry
from carbon.development_session import bundle_construction_worker as bundle
from carbon.development_session import direct_graph_construction_worker as graph
from carbon.development_session.profile import canonical
from carbon.level4.allowlist import Allowlist
from carbon.reconstruction.worker.model import worker_resources_version

ROOT = Path(__file__).resolve().parents[2]
BINDING_KEYS = ("train_digest", "interface_digest", "construction_limits_digest")
posix = pytest.mark.skipif(os.name == "nt", reason="G3 parser needs POSIX rlimits")


def _material(challenge_id, version):
    if challenge_id == battery_material.challenge.CHALLENGE.challenge_id:
        return battery_material.versioned_material(version)
    return physical_material.bundle_material(challenge_id, version)


def _served():
    """Every version the registry serves a kit for (all of them carry one)."""
    return sorted(registry.VERSIONS)


SERVED = _served()


def _binding(kit):
    return {
        "challenge_id": kit["id"],
        "challenge_version": kit["version"],
        **{key: kit[key] for key in BINDING_KEYS},
    }


def test_the_served_set_covers_the_launch_versions_and_battery_2_1():
    assert {
        ("chip-cold-plate", "1.4"),
        ("electric-motor-magnetics", "1.4"),
        ("f08-ribbed-bracket", "1.5"),
        ("f02", "2.4"),
        ("battery-fastcharge-ageing-development-v1", "2.1"),
    } <= set(SERVED)


@pytest.mark.parametrize(("challenge_id", "version"), SERVED)
def test_the_published_policy_is_the_enforced_one_on_every_verifying_route(
    challenge_id, version
):
    material = _material(challenge_id, version)
    binding = _binding(material["construction_kit"])
    limits = material["construction_limits_document"]
    allowed = Allowlist(material["allowlist_bytes"])
    # The bundle route names it from the allowlist it builds under.
    explicit = worker_resources_version(allowed.version)
    # Admission, graph build and inference, paired inference, calibration and
    # retention call the check without naming it: the version's own.
    assert bundle.binding_resources_version(binding) == explicit
    assert bundle.verify_direct_resource_policy(binding, limits, explicit) == (
        binding["construction_limits_digest"]
    )
    assert bundle.verify_direct_resource_policy(binding, limits) == (
        binding["construction_limits_digest"]
    )
    # A v7 version publishes the larger profile; every other keeps today's.
    cpu = limits["reconstruction_resource_policy"]["cpu_count_max"]
    assert cpu == (4 if explicit is not None else 2)


@pytest.mark.parametrize(("challenge_id", "version"), SERVED)
def test_the_runner_argument_is_the_published_profile(challenge_id, version):
    material = _material(challenge_id, version)
    binding = _binding(material["construction_kit"])
    explicit = worker_resources_version(Allowlist(material["allowlist_bytes"]).version)
    assert bundle.resources_kwargs(binding) == (
        {} if explicit is None else {"worker_resources_version": explicit}
    )


def test_an_unregistered_version_keeps_todays_profile():
    binding = {"challenge_id": "nope", "challenge_version": "9.9"}
    assert bundle.binding_resources_version(binding) is None
    assert bundle.resources_kwargs(binding) == {}
    assert bundle.binding_resources_version("not a binding") is None


def test_the_old_profile_is_refused_for_a_v7_version(monkeypatch):
    """A kit that published today's profile for a v7 version (the defect) is
    refused: the check demands the larger one."""
    from carbon.challenge_kit import served_versions

    monkeypatch.setattr(served_versions, "worker_resources", lambda *_: None)
    material = _material("f02", "2.4")
    binding = _binding(material["construction_kit"])
    limits = material["construction_limits_document"]
    assert limits["reconstruction_resource_policy"]["cpu_count_max"] == 2
    with pytest.raises(bundle.RecipeRefused) as refused:
        bundle.verify_direct_resource_policy(
            binding, limits, worker_resources_version("level4-allowlist-v7")
        )
    assert str(refused.value) == "construction_resource_policy_unserved"


def _call_arguments(text, start):
    """The top-level arguments of the call whose `(` is at `start`."""
    depth, args, current = 0, [], []
    for char in text[start:]:
        if char in "([{":
            depth += 1
            if depth == 1:
                continue
        elif char in ")]}":
            depth -= 1
            if depth == 0:
                break
        if char == "," and depth == 1:
            args.append("".join(current))
            current = []
        else:
            current.append(char)
    args.append("".join(current))
    return [arg for arg in args if arg.strip()]


def test_no_caller_names_a_profile_except_the_bundle_worker():
    """A caller that names its own profile can drift from the published one; the
    routes call the check bare and take the version's."""
    named = set()
    for path in sorted((ROOT / "carbon").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"(?<!def )verify_direct_resource_policy\(", text):
            if len(_call_arguments(text, match.end() - 1)) > 2:
                named.add(path.relative_to(ROOT).as_posix())
    assert named <= {"carbon/development_session/bundle_construction_worker.py"}


@posix
@pytest.mark.parametrize(
    "key",
    [("f08-ribbed-bracket", "1.4"), ("f02", "2.3")],
)
def test_the_graph_build_child_is_launched_under_the_published_profile(key, tmp_path):
    from test_f08_f02_graph_adapters import PUBLIC, _case, _image, adapter
    from test_f08_f02_graph_adapters import _binding as graph_binding

    recipe, raw_manifest, files, staging = _case(key, {"steps": 16})
    material = physical_material.bundle_material(*key)
    captured = {}

    class _Captured(Exception):
        pass

    def runner(_ledger, **kwargs):
        captured.update(kwargs)
        raise _Captured

    with pytest.raises(_Captured):
        graph.reconstruct_and_infer_graph_public(
            SimpleNamespace(root=tmp_path),
            owner="test",
            identity="test",
            image=_image(),
            recipe=recipe,
            challenge_binding=graph_binding(key),
            limits_document=PUBLIC[key[0]].construction_limits_document(*key),
            source_envelope=canonical(staging.envelope(raw_manifest, files)),
            train=material["train"],
            inputs=np.ascontiguousarray(material["practice_inputs"]),
            expected_output_shape=tuple(material["expected_output_shape"]),
            allowlist_bytes=adapter.served_allowlist_bytes(*key),
            seed=0,
            runner=runner,
        )
    expected = worker_resources_version(Allowlist(material["allowlist_bytes"]).version)
    assert captured.get("worker_resources_version") == expected
    assert expected is not None  # these three are v7 versions
