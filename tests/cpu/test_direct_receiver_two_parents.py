"""A receiver that opts in to both CPU construction parents
(OWNER-BACKBONE-CATALOG-01; Validator, 2026-10-20). Without the field the
receiver is byte-identical; with it, the frozen campaign and the immutable
binding name each runtime's parent, every owner task picks its bundle's own,
and a root first opened the other way is refused."""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_direct_parents import torch_image
from test_direct_receiver import (
    OWNER,
    RECEIVER,
    _allow_windows_receiver_fixture,
    _config,
)

from carbon.challenge_validator import direct_receiver as receiver
from carbon.development_session import gpu_practice


def test_the_opt_in_names_exactly_both_cpu_runtimes(tmp_path, monkeypatch):
    cfg = {
        **_config(tmp_path),
        "construction_runtimes": receiver.CONSTRUCTION_RUNTIMES,
    }
    monkeypatch.setattr(receiver, "private_json", lambda _: cfg)
    assert receiver.load_config(tmp_path / "config.json") == cfg
    for runtimes in (
        ["torch-cpu-py311"],
        ["torch-cpu-py311", "python-cpu-py311"],
        ["python-cpu-py311", "torch-cpu-py311", "jax-cuda13-py311"],
        "python-cpu-py311",
    ):
        cfg["construction_runtimes"] = runtimes
        with pytest.raises(ValueError, match="construction runtimes"):
            receiver.load_config(tmp_path / "config.json")


def test_the_cpu_parent_is_derived_checked_and_must_be_installed(monkeypatch):
    from carbon.development_session import research_campaign
    from carbon.reconstruction.worker import docker_runtime

    checked, eligible = [], {"value": True}
    monkeypatch.setattr(
        research_campaign,
        "verify_direct_v13_worker",
        lambda image, implementation, *, role: checked.append((image, role)),
    )
    monkeypatch.setattr(
        docker_runtime,
        "doctor",
        lambda *, image_id, image_identity: SimpleNamespace(eligible=eligible["value"]),
    )
    parents = receiver.construction_parents(torch_image(), {"revision": "a" * 40})
    cpu = gpu_practice.derived_cpu_parent(torch_image())
    assert parents.for_runtime("python-cpu-py311") == cpu
    assert parents.for_runtime("torch-cpu-py311") == torch_image()
    assert checked == [(cpu, "cpu")]
    eligible["value"] = False
    with pytest.raises(receiver.ReceiverUnavailable) as missing:
        receiver.construction_parents(torch_image(), {"revision": "a" * 40})
    assert missing.value.code == "installed_cpu_construction_worker_unavailable"
    with pytest.raises(ValueError, match="PyTorch CPU worker"):
        receiver.construction_parents(cpu, {"revision": "a" * 40})


def test_the_parents_must_include_the_receivers_own_parent(tmp_path):
    parents = gpu_practice.DirectParents.from_torch(torch_image())
    other = replace(
        torch_image(), image_id="sha256:" + "e" * 64, config_digest="sha256:" + "e" * 64
    )
    with pytest.raises(ValueError, match="include the receiver parent"):
        receiver.OwnerProviders(tmp_path, None, other, None, parents=parents)
    with pytest.raises(ValueError, match="include the receiver parent"):
        receiver.OwnerProviders(tmp_path, None, torch_image(), None, parents={})


def test_each_owner_task_store_binds_both_parents_and_refuses_a_flip(
    tmp_path, monkeypatch
):
    from test_c08_authenticated_miner_mcp import CONTEXT, _snapshot

    from carbon.chain.models import CARBON_NETUID, CARBON_NETWORK, ChainContext
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
    from carbon.development_session.research_service import DirectFixtureDiscovery

    _allow_windows_receiver_fixture(monkeypatch)
    context = ChainContext(
        CARBON_NETWORK,
        CONTEXT.endpoint,
        CONTEXT.provider,
        CONTEXT.genesis_hash,
        CARBON_NETUID,
    )
    snapshot = _snapshot(sender=OWNER, receiver=RECEIVER, context=context)
    discovery = DirectFixtureDiscovery(bundle_material_v5(), task_admission=True)
    parents = gpu_practice.DirectParents.from_torch(torch_image())
    cpu = parents.for_runtime("python-cpu-py311")

    def pool(root, **extra):
        return receiver.OwnerProviders(
            receiver._private_directory(root),
            discovery,
            torch_image(),
            tmp_path / "cache",
            implementation={"revision": "a" * 40},
            snapshot=snapshot,
            receiver=RECEIVER,
            **extra,
        )

    plain = pool(tmp_path / "plain")
    plain_provider = plain(OWNER)
    two = pool(tmp_path / "two", parents=parents)
    provider = two(OWNER)
    try:
        assert plain_provider.construction_parents is None
        assert provider.construction_parents is parents
        assert provider.image_resolver.parents is parents
        with provider.ledger.db() as db:
            frozen = json.loads(
                db.execute("SELECT manifest FROM campaign").fetchone()[0]
            )
        with plain_provider.ledger.db() as db:
            plain_frozen = json.loads(
                db.execute("SELECT manifest FROM campaign").fetchone()[0]
            )
        assert "construction_parents" not in plain_frozen["receiver_binding"]
        assert frozen["receiver_binding"]["construction_parents"] == {
            "python-cpu-py311": cpu.image_id,
            "torch-cpu-py311": torch_image().image_id,
        }
        assert frozen["runtime"]["images"] == [torch_image().image_id, cpu.image_id]
        assert plain_frozen["runtime"]["images"] == [torch_image().image_id]
        assert frozen["campaign_id"] != plain_frozen["campaign_id"]
    finally:
        provider.close()
        plain_provider.close()
    # A root opened with both parents never reopens with one, nor the reverse.
    for root, extra in (
        (tmp_path / "two", {}),
        (tmp_path / "plain", {"parents": parents}),
    ):
        with pytest.raises(ValueError, match="binding changed"):
            pool(root, **extra)(OWNER)
