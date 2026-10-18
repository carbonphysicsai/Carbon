"""Installed direct CLI keeps old kits while routing prospective v1.3."""

from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.challenge_kit import synthetic_linear_field_2d as kit
from carbon.development_session.research_ledger import CampaignLedger
from carbon.miner_mcp import standard_cli as cli
from carbon.reconstruction.worker.model import WorkerImageIdentity


def test_registered_kit_selection_preserves_old_material(monkeypatch):
    prospective = lambda: {"challenge_key": "prospective-test-only"}
    monkeypatch.setattr(kit, "bundle_material_v5", prospective, raising=False)
    assert cli._direct_material("1.1") is kit.bundle_material_v3
    assert cli._direct_material("1.2") is kit.bundle_material_v4
    assert cli._direct_material("1.3") is prospective
    for unknown in ("1.4", "", [], None):
        with pytest.raises(cli.AttachRefused) as refused:
            cli._direct_material(unknown)
        assert refused.value.code == "direct_development_kit_unavailable"


def test_missing_prospective_material_fails_closed_without_affecting_old_kits(
    monkeypatch,
):
    monkeypatch.delattr(kit, "bundle_material_v5", raising=False)
    assert cli._direct_material("1.1") is kit.bundle_material_v3
    assert cli._direct_material("1.2") is kit.bundle_material_v4
    with pytest.raises(cli.AttachRefused) as refused:
        cli._direct_material("1.3")
    assert refused.value.code == "direct_development_kit_unavailable"


@pytest.mark.parametrize(
    ("candidate_mode", "bad_images", "cpu_only"),
    [
        (False, False, False),
        (True, False, False),
        (True, True, False),
        (True, False, True),
    ],
)
def test_v13_installed_loader_reuses_profile_parent_signer_and_owner(
    monkeypatch, tmp_path, candidate_mode, bad_images, cpu_only
):
    from carbon.chain import external_signer
    from carbon.development_session import (
        gpu_practice,
        miner_network,
        private_records,
        research_campaign,
        research_image,
    )
    from carbon.reconstruction.worker import docker_runtime
    from scripts.dev.miner_launchpad import installed, runner

    digest = "sha256:" + "a" * 64
    parent = SimpleNamespace(image_id=digest)
    direct_parent = parent
    if not candidate_mode:
        from carbon.reconstruction import torch_profile

        root = Path(cli.__file__).resolve().parents[2]
        direct_parent = WorkerImageIdentity(
            "sha256:" + "1" * 64,
            "sha256:" + "1" * 64,
            "sha256:" + "2" * 64,  # Older source than accepted implementation.
            "sha256:" + "3" * 64,
            torch_profile.GPU_LOCK_DIGEST,
            "sha256:" + "4" * 64,
            cli.digest((root / ".devcontainer/torch/Dockerfile.gpu").read_bytes()),
            cli.digest(
                (root / "carbon/reconstruction/worker/entrypoint.py").read_bytes()
            ),
        )
    analysis = SimpleNamespace(parent_image=digest, image_id=digest)
    signer = SimpleNamespace(ss58_address="owner")
    base = (
        tmp_path / "environment" / "campaigns"
        if candidate_mode
        else tmp_path / "campaigns"
    )
    base.mkdir(parents=True)
    public = tmp_path / "public.json"
    public.write_text(json.dumps({"netuid": cli.CARBON_NETUID, "hotkey": "owner"}))
    paths = {
        "image_manifest": str(tmp_path / "image.json"),
        "analysis_image_manifest": str(tmp_path / "analysis.json"),
        "miner_public": str(public),
    }
    cfg = {
        "enabled": True,
        "campaigns_root": str(base),
        "paths": paths,
        "accepted_revision": "a" * 40,
        "runtime": {
            "implementation": {"revision": "a" * 40},
            "images": [digest, digest],
        },
        "principal": "owner",
    }
    if not cpu_only:
        cfg["gpu_image"] = str(tmp_path / "gpu-image.json")
    candidate = {
        "revision": "a" * 40,
        "tree": "b" * 40,
        "source_tree_digest": "sha256:" + "c" * 64,
        "source_authority": "DEVELOPMENT_CANDIDATE",
    }
    if candidate_mode:
        cfg["runtime"]["implementation"] = candidate
        cfg["runtime"]["images"] = [
            "sha256:" + "d" * 64 if bad_images else digest,
            digest,
        ]
    monkeypatch.setattr(
        kit, "bundle_material_v5", lambda: {"challenge_key": "v13"}, raising=False
    )
    monkeypatch.setattr(cli, "private_json", lambda _path: cfg)
    monkeypatch.setattr(private_records, "private_json", lambda _path: cfg)
    monkeypatch.setattr(runner, "validated_profile", lambda value: value)
    monkeypatch.setattr(
        research_campaign,
        "accepted_implementation",
        (
            (lambda _rev: pytest.fail("candidate must not claim main acceptance"))
            if candidate_mode
            else (lambda _rev: {"source_tree_digest": digest})
        ),
    )
    seen_candidate = []
    monkeypatch.setattr(
        installed,
        "candidate_implementation",
        lambda state: seen_candidate.append(state) or candidate,
    )
    monkeypatch.setattr(research_campaign, "private_file", lambda path: path)
    verified_workers = []
    monkeypatch.setattr(
        research_campaign,
        "verify_current_worker",
        lambda *args: verified_workers.append(args),
    )
    compatible_parents = []
    actual_parent_check = cli._direct_development_parent_compatible

    def check_direct_parent(*args):
        compatible_parents.append(args)
        if not candidate_mode:
            actual_parent_check(*args)

    monkeypatch.setattr(
        cli, "_direct_development_parent_compatible", check_direct_parent
    )
    monkeypatch.setattr(research_image, "load_analysis_image", lambda _path: analysis)
    monkeypatch.setattr(research_image, "verify_image", lambda _image: None)
    monkeypatch.setattr(
        docker_runtime,
        "load_image_identity",
        lambda path: parent if path == Path(paths["image_manifest"]) else direct_parent,
    )
    checked_parents = []
    monkeypatch.setattr(
        docker_runtime,
        "doctor",
        lambda **kwargs: checked_parents.append(kwargs["image_identity"])
        or SimpleNamespace(eligible=True),
    )
    monkeypatch.setattr(gpu_practice, "gpu_image_backend", lambda _parent: "jax")
    monkeypatch.setattr(
        miner_network,
        "binding",
        lambda **_kwargs: SimpleNamespace(
            netuid=cli.CARBON_NETUID,
            context=object(),
            publisher_hotkey="publisher",
        ),
    )
    monkeypatch.setattr(external_signer, "miner_signer", lambda *_args: signer)

    profile = (
        tmp_path / "environment" / "runner-profile.json"
        if candidate_mode
        else tmp_path / "profile.json"
    )
    if bad_images:
        with pytest.raises(ValueError, match="profile images differ") as refused:
            cli.load_direct_installed_source(profile, version="1.3")
        assert cli.refusal_code(refused.value) == "carbon_updated_rerun_installer"
        return
    source = cli.load_direct_installed_source(profile, version="1.3")
    assert source.root == (
        base / ".direct-development" / "kit-1.3" / direct_parent.image_id[7:]
    )
    assert source.cache_root == base / ".direct-development" / "library-cache"
    assert source.version == "1.3"
    assert source.parent is direct_parent
    assert source.signer is signer
    expected_implementation = (
        candidate if candidate_mode else {"source_tree_digest": digest}
    )
    assert verified_workers == [(parent, expected_implementation)]
    assert compatible_parents == (
        [] if cpu_only else [(direct_parent, expected_implementation)]
    )
    assert seen_candidate == ([tmp_path] if candidate_mode else [])
    assert checked_parents == [direct_parent]
    if cpu_only:
        cfg["runtime"]["gpu_research"] = {}
        with pytest.raises(ValueError, match="declared GPU direct parent is missing"):
            cli.load_direct_installed_source(profile, version="1.3")


def test_public_v13_direct_torch_parent_reuses_exact_abi_not_old_tree():
    from carbon.reconstruction import torch_profile

    def sha(char):
        return "sha256:" + char * 64

    root = Path(cli.__file__).resolve().parents[2]
    image = WorkerImageIdentity(
        sha("1"),
        sha("1"),
        sha("2"),  # Older Carbon source identity stays in the image record.
        sha("3"),
        torch_profile.GPU_LOCK_DIGEST,
        sha("4"),
        cli.digest((root / ".devcontainer/torch/Dockerfile.gpu").read_bytes()),
        cli.digest((root / "carbon/reconstruction/worker/entrypoint.py").read_bytes()),
    )
    current = {"source_tree_digest": sha("5")}
    cli._direct_development_parent_compatible(image, current)
    for field in ("lock_digest", "entrypoint_digest", "build_recipe_digest"):
        with pytest.raises(ValueError, match="ABI or entrypoint differs"):
            cli._direct_development_parent_compatible(
                replace(image, **{field: sha("f")}), current
            )
    # The exact current source remains eligible without this older-base route.
    cli._direct_development_parent_compatible(
        replace(image, source_tree_digest=current["source_tree_digest"]), current
    )


@pytest.mark.parametrize("role", ("cpu", "jax_gpu", "torch_cpu"))
def test_public_v13_inference_worker_reuses_only_exact_abi(role):
    from carbon.development_session.research_campaign import verify_direct_v13_worker
    from carbon.reconstruction import torch_profile
    from carbon.reconstruction.accelerators import GPU_PROFILE

    def sha(char):
        return "sha256:" + char * 64

    root = Path(cli.__file__).resolve().parents[2]
    lock, recipe = {
        "cpu": (
            cli.digest((root / "uv.lock").read_bytes()),
            ".devcontainer/Dockerfile.reconstruction-worker",
        ),
        "jax_gpu": (
            GPU_PROFILE.environment_lock_digest,
            ".devcontainer/accelerators/Dockerfile",
        ),
        "torch_cpu": (
            torch_profile.requirements_digest(root),
            ".devcontainer/torch/Dockerfile",
        ),
    }[role]
    image = WorkerImageIdentity(
        sha("1"),
        sha("1"),
        sha("2"),
        sha("3"),
        lock,
        sha("4"),
        cli.digest((root / recipe).read_bytes()),
        cli.digest((root / "carbon/reconstruction/worker/entrypoint.py").read_bytes()),
    )
    current = {"source_tree_digest": sha("5")}
    verify_direct_v13_worker(image, current, role=role)
    for field in ("lock_digest", "entrypoint_digest", "build_recipe_digest"):
        with pytest.raises(ValueError, match="ABI or entrypoint differs"):
            verify_direct_v13_worker(
                replace(image, **{field: sha("f")}), current, role=role
            )
    with pytest.raises(ValueError, match="role required"):
        verify_direct_v13_worker(image, current, role="unknown")


def test_v13_candidate_profile_mismatch_refuses_before_image_use(monkeypatch, tmp_path):
    from carbon.development_session import private_records
    from scripts.dev.miner_launchpad import installed, runner

    base = tmp_path / "campaigns"
    base.mkdir()
    cfg = {
        "enabled": True,
        "campaigns_root": str(base),
        "paths": {"image_manifest": str(tmp_path / "image.json")},
        "accepted_revision": "a" * 40,
        "runtime": {"implementation": {"revision": "a" * 40}},
    }
    monkeypatch.setattr(cli, "private_json", lambda _path: cfg)
    monkeypatch.setattr(private_records, "private_json", lambda _path: cfg)
    monkeypatch.setattr(runner, "validated_profile", lambda value: value)
    monkeypatch.setattr(
        installed,
        "candidate_implementation",
        lambda _state: {
            "revision": "a" * 40,
            "tree": "b" * 40,
            "source_tree_digest": "sha256:" + "c" * 64,
            "source_authority": "DEVELOPMENT_CANDIDATE",
        },
    )
    with pytest.raises(
        ValueError, match="development candidate profile differs"
    ) as refused:
        cli.load_direct_installed_source(
            tmp_path / "environment" / "runner-profile.json", version="1.3"
        )
    assert cli.refusal_code(refused.value) == "carbon_updated_rerun_installer"


def test_normal_attachment_runtime_uses_exact_installed_candidate(
    monkeypatch, tmp_path
):
    from carbon.challenge_registry import campaigns
    from carbon.development_session import research_campaign, research_image
    from carbon.reconstruction.worker import docker_runtime
    from scripts.dev.miner_launchpad import installed

    digest = "sha256:" + "a" * 64
    implementation = {
        "revision": "b" * 40,
        "tree": "c" * 40,
        "source_tree_digest": "sha256:" + "d" * 64,
        "source_authority": "DEVELOPMENT_CANDIDATE",
    }
    profile_path = tmp_path / "environment" / "runner-profile.json"
    parent = SimpleNamespace(image_id=digest)
    analysis = SimpleNamespace(image_id=digest, parent_image=digest)
    cfg = {
        "accepted_revision": implementation["revision"],
        "paths": {
            "image_manifest": str(tmp_path / "worker.json"),
            "analysis_image_manifest": str(tmp_path / "analysis.json"),
        },
        "runtime": {"implementation": implementation, "images": [digest, digest]},
    }
    profile = cli.OperatorProfile(
        profile_path,
        cfg,
        "e" * 32,
        tmp_path / "environment" / "campaigns" / ("e" * 32),
        {"runtime": cfg["runtime"]},
    )
    monkeypatch.setattr(
        installed,
        "profile_candidate",
        lambda path, document: (
            implementation if path == profile_path and document == cfg else None
        ),
    )
    monkeypatch.setattr(
        research_campaign,
        "accepted_implementation",
        lambda _revision: pytest.fail("normal attach must not claim main acceptance"),
    )
    monkeypatch.setattr(research_campaign, "verify_current_worker", lambda *_: None)
    monkeypatch.setattr(docker_runtime, "load_image_identity", lambda _path: parent)
    monkeypatch.setattr(
        docker_runtime, "doctor", lambda **_kwargs: SimpleNamespace(eligible=True)
    )
    monkeypatch.setattr(research_image, "load_analysis_image", lambda _path: analysis)
    monkeypatch.setattr(research_image, "verify_image", lambda _image: None)
    monkeypatch.setattr(cli, "_authored_image", lambda *_args: None)
    monkeypatch.setattr(cli, "_connection", lambda *_args: "connection")
    seen = []
    monkeypatch.setattr(
        campaigns,
        "campaign_for_manifest",
        lambda _manifest: SimpleNamespace(
            check_attached=lambda *_args, **kwargs: seen.append(kwargs),
            gpu_image=lambda *_args: None,
        ),
    )
    assert cli._runtime(profile) == ("connection", parent, analysis, None)
    assert seen[0]["implementation"] == implementation

    cfg["runtime"]["images"] = ["sha256:" + "f" * 64, digest]
    with pytest.raises(cli.AttachRefused) as refused:
        cli._runtime(profile)
    assert refused.value.code == "carbon_updated_rerun_installer"


def test_old_direct_kit_keeps_main_accepted_source_rule(monkeypatch, tmp_path):
    from carbon.development_session import research_campaign
    from scripts.dev.miner_launchpad import installed, runner

    base = tmp_path / "campaigns"
    base.mkdir()
    cfg = {
        "enabled": True,
        "campaigns_root": str(base),
        "paths": {"image_manifest": str(tmp_path / "image.json")},
        "accepted_revision": "a" * 40,
    }
    monkeypatch.setattr(cli, "private_json", lambda _path: cfg)
    monkeypatch.setattr(runner, "validated_profile", lambda value: value)
    monkeypatch.setattr(
        installed,
        "candidate_implementation",
        lambda _state: pytest.fail("old kit must ignore candidate pin"),
    )
    monkeypatch.setattr(
        research_campaign,
        "accepted_implementation",
        lambda _rev: (_ for _ in ()).throw(ValueError("not in fetched main")),
    )
    with pytest.raises(ValueError, match="not in fetched main") as refused:
        cli.load_direct_installed_source(
            tmp_path / "environment" / "runner-profile.json", version="1.2"
        )
    assert cli.refusal_code(refused.value) == "carbon_updated_rerun_installer"


@pytest.mark.parametrize(("requested", "expected"), [(None, "1.2"), ("1.3", "1.3")])
def test_cli_serves_selected_kit_through_existing_installed_path(
    monkeypatch, requested, expected
):
    seen = []

    async def serve(configuration, *, version="1.2"):
        seen.append((configuration, version))

    monkeypatch.setattr(cli, "serve_installed_direct_development", serve)
    arguments = ["--configuration", "operator.json", "--direct-development"]
    if requested is not None:
        arguments.extend(("--direct-version", requested))
    assert cli.main(arguments) == 0
    assert seen == [(Path("operator.json"), expected)]


def test_unknown_cli_kit_refuses_before_serving(monkeypatch, capsys):
    async def unexpected(*_args, **_kwargs):
        pytest.fail("unknown kit must not serve")

    monkeypatch.setattr(cli, "serve_installed_direct_development", unexpected)
    assert (
        cli.main(
            [
                "--configuration",
                "operator.json",
                "--direct-development",
                "--direct-version",
                "1.4",
            ]
        )
        == 2
    )
    assert "direct_development_kit_unavailable" in capsys.readouterr().err


def test_cleanup_option_reconciles_all_versions(monkeypatch, capsys):
    calls = []

    async def cleanup(configuration):
        calls.append(configuration)
        return {"status": "DIRECT_CLEANUP_COMPLETE", "retained_tasks_checked": 0}

    monkeypatch.setattr(cli, "cleanup_installed_direct_development", cleanup)
    assert (
        cli.main(
            [
                "--configuration",
                "operator.json",
                "--direct-development",
                "--direct-version",
                "1.3",
                "--cleanup-only",
            ]
        )
        == 0
    )
    assert calls == [Path("operator.json")]
    assert "DIRECT_CLEANUP_COMPLETE" in capsys.readouterr().out
    assert cli.DIRECT_KIT_VERSIONS == ("1.1", "1.2", "1.3")


def test_cleanup_reads_legacy_and_graph_parent_image_rows():
    digest = "sha256:" + "a" * 64
    parent = WorkerImageIdentity(
        image_id=digest,
        config_digest=digest,
        source_tree_digest=digest,
        wheel_digest=digest,
        lock_digest=digest,
        base_image_digest=digest,
        build_recipe_digest=digest,
        entrypoint_digest=digest,
    )
    legacy = json.dumps([digest, asdict(parent), "bundle-ref", digest])
    graph = json.dumps(["GRAPH_PARENT", asdict(parent)])
    assert cli._retained_direct_parent(legacy, digest) == parent
    assert cli._retained_direct_parent(graph, digest) == parent
    for row in (
        json.dumps(["GRAPH_PARENT", asdict(parent), "extra"]),
        json.dumps(["UNKNOWN_PARENT", asdict(parent)]),
    ):
        with pytest.raises(ValueError):
            cli._retained_direct_parent(row, digest)
    with pytest.raises(ValueError):
        cli._retained_direct_parent(graph, "sha256:" + "b" * 64)


def test_cleanup_visits_retained_v13_kit(monkeypatch, tmp_path):
    from carbon.chain import external_signer
    from carbon.development_session import direct_research_composition as composition
    from carbon.development_session import miner_network, research_campaign
    from scripts.dev.miner_launchpad import runner

    base = tmp_path / "campaigns"
    (base / ".direct-development" / "kit-1.3").mkdir(parents=True)
    public = tmp_path / "miner-public.json"
    public.write_text(json.dumps({"netuid": cli.CARBON_NETUID, "hotkey": "owner"}))
    config = tmp_path / "profile.json"
    cfg = {
        "campaigns_root": str(base),
        "principal": "owner",
        "paths": {"miner_public": str(public)},
    }
    monkeypatch.setattr(cli, "private_json", lambda _path: cfg)
    monkeypatch.setattr(runner, "validated_profile", lambda value: value)
    monkeypatch.setattr(research_campaign, "private_file", lambda path: path)
    monkeypatch.setattr(
        miner_network,
        "binding",
        lambda **_kwargs: SimpleNamespace(
            netuid=cli.CARBON_NETUID,
            context=object(),
            publisher_hotkey="publisher",
        ),
    )
    monkeypatch.setattr(external_signer, "miner_signer", lambda *_args: object())
    monkeypatch.setattr(
        kit, "bundle_material_v5", lambda: {"challenge_key": "v13"}, raising=False
    )
    seen = []

    class Connection:
        def __init__(self, **kwargs):
            seen.append(kwargs["version"])
            self.challenge = "v13"

    monkeypatch.setattr(composition, "DirectDevelopmentConnection", Connection)

    async def requester(_connection, *, challenge):
        assert challenge == "v13"
        return "owner"

    monkeypatch.setattr(cli, "_requester", requester)
    result = asyncio.run(cli.cleanup_installed_direct_development(config))
    assert result == {"status": "DIRECT_CLEANUP_COMPLETE", "retained_tasks_checked": 0}
    assert seen == ["1.3"]


def test_attached_v13_uses_same_owner_check_and_composition(monkeypatch, tmp_path):
    from carbon.development_session import direct_research_composition as composition
    from scripts.dev.miner_launchpad import controller

    challenge = "prospective-test-only"
    monkeypatch.setattr(
        kit, "bundle_material_v5", lambda: {"challenge_key": challenge}, raising=False
    )
    monkeypatch.setattr(
        controller, "owner_lock", lambda _root: contextlib.nullcontext()
    )

    async def requester(_connection, *, challenge):
        assert challenge == "prospective-test-only"
        return "owner-hotkey"

    monkeypatch.setattr(cli, "_requester", requester)
    seen = []

    def compose(**kwargs):
        seen.append(kwargs)
        tasks = SimpleNamespace(close=lambda: None)
        return SimpleNamespace(tasks=tasks), object()

    monkeypatch.setattr(composition, "compose_synthetic_direct_development", compose)

    class Adapter:
        def __init__(self, **kwargs):
            self.arguments = kwargs

        async def shutdown_tasks(self):
            pass

    monkeypatch.setattr(cli, "DirectResearchMinerTools", Adapter)
    root = tmp_path / "kit-1.3" / ("a" * 64)
    root.mkdir(parents=True)
    ledger = CampaignLedger(root / "ledger")
    connection = SimpleNamespace(service=SimpleNamespace(gateway=object()))
    attachment = cli.DirectDevelopmentAttachment(
        root=root,
        version="1.3",
        owner="owner-hotkey",
        connection=connection,
        ledger=ledger,
        image=None,
        inference_image=object(),
    )

    async def attach():
        async with cli.attached_direct_development(attachment) as (adapter, selected):
            assert selected is attachment
            assert adapter.arguments["owner"] == "owner-hotkey"

    asyncio.run(attach())
    assert len(seen) == 1
    assert seen[0]["version"] == "1.3"
    assert seen[0]["root"] == root / "direct-tasks"
    assert seen[0]["owner"] == "owner-hotkey"

    async def wrong_requester(_connection, *, challenge):
        return "another-owner"

    monkeypatch.setattr(cli, "_requester", wrong_requester)
    with pytest.raises(cli.AttachRefused) as refused:
        asyncio.run(attach())
    assert refused.value.code == "campaign_owner_changed"
    assert len(seen) == 1
