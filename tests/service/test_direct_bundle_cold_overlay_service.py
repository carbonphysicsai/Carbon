"""Real admitted CPU source-only preparation, fixed TRAIN build and inert inference.

This is DEVELOPMENT engineering evidence through the normal C03 task provider.
The tiny source bundle supplies no fitted state and the test replaces no worker,
Docker, image verifier, resource guard, task completion or bank implementation.
"""

from __future__ import annotations

import io
import json
import os
import tarfile
from pathlib import Path

import numpy as np

from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator import AttemptLedger
from carbon.challenge_validator.interface import Admitted
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
from carbon.challenge_validator.lean_recipe_retention import retain_served_result
from carbon.development_session.library_bundles import (
    BUNDLE_SCHEMA,
    UV_IMAGE,
    _environment_digest,
)
from carbon.development_session.library_environment_cache import (
    stage_pinned_bundle_material,
)
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_ledger import (
    DEVELOPMENT_CEILINGS,
    DEVELOPMENT_ELAPSED_SECONDS,
    VERSION,
    CampaignLedger,
)
from carbon.development_session.research_service import DirectFixtureDiscovery
from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
from carbon.miner_mcp.standard_cli import DirectOwnerImageResolver
from carbon.reconstruction.worker.docker_runtime import DockerCLI, load_image_identity
from carbon.research import DirectTaskStateV3

SOURCE = b"""from pathlib import Path
import numpy as np
import jax.numpy as jnp

def build(train_inputs, train_targets, *, seed, configuration, train_use):
    assert seed == 0 and configuration == {} and train_use == {'cases': 'all'}
    assert not Path('/input/state.npz').exists()
    scale = np.float32(np.sum(train_inputs * train_targets) / np.sum(train_inputs**2))
    return {'framework': 'jax', 'apply': lambda x: x * jnp.asarray(scale), 'parameters': []}
"""


def _stage_cpu_source(root, cache, parent):
    root.mkdir(mode=0o700)
    (root / "wheels").mkdir(mode=0o700)
    license_text = b"MIT\n"
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, raw in (
            ("source/candidate/__init__.py", b""),
            ("source/candidate/build.py", SOURCE),
            ("source/LICENSE", license_text),
        ):
            member = tarfile.TarInfo(name)
            member.size = len(raw)
            archive.addfile(member, io.BytesIO(raw))
    source = output.getvalue()
    lock = b""
    manifest = {
        "schema": BUNDLE_SCHEMA,
        "name": "c03-cold-linear-source",
        "language": "python",
        "source_sha256": digest(source),
        "source_bytes": len(source),
        "runtime_profile_id": "python-cpu-py311",
        "base_environment_digest": parent.lock_digest,
        "environment_digest": _environment_digest(parent.lock_digest, digest(lock)),
        "os": "linux",
        "architecture": "amd64",
        "python_abi": "cp311",
        "accelerator": "cpu",
        "lock_sha256": digest(lock),
        "wheels": {},
        "license_sha256": digest(license_text),
    }
    for name, raw in (
        ("bundle.json", canonical(manifest)),
        ("source.tar.gz", source),
        ("requirements.txt", lock),
        ("LICENSE", license_text),
    ):
        (root / name).write_bytes(raw)
    return stage_pinned_bundle_material(root, cache)


def test_normal_cpu_source_only_task_cold_prepares_builds_and_retains(tmp_path):
    manifest = os.environ.get("CARBON_C03_IMAGE_MANIFEST")
    assert manifest, "required service lane must supply the exact C03 image manifest"
    parent = load_image_identity(Path(manifest))
    cli = DockerCLI()
    # The maintained offline provisioner copies /uv from this exact local image.
    # Provision that existing pinned tool as host setup, outside every worker.
    cli.run(["pull", UV_IMAGE], timeout=120)
    material = bundle_material_v5()
    cache = tmp_path / "cache"
    cache.mkdir(mode=0o700)
    bundle = _stage_cpu_source(tmp_path / "source", cache, parent)
    assert sorted(path.name for path in cache.iterdir()) == ["materials"]
    ledger = CampaignLedger(tmp_path / "campaign")
    owner = "c03-cold-overlay-engineering"
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": DEVELOPMENT_CEILINGS,
            "elapsed_seconds": DEVELOPMENT_ELAPSED_SECONDS,
            **{
                name: owner
                for name in (
                    "campaign_id",
                    "implementation",
                    "objective",
                    "sampling",
                    "control",
                    "selection",
                    "replica_policy",
                    "provider",
                    "owner",
                )
            },
        }
    )
    discovery = DirectFixtureDiscovery(material, task_admission=True)
    provider = DirectDevelopmentTasksV3(
        root=tmp_path / "tasks",
        requester=owner,
        ledger=ledger,
        owner=owner,
        discovery=discovery,
        image_resolver=DirectOwnerImageResolver(
            cache, parent, material_cache_bytes=16 * 1024**2
        ),
        inference_image=parent,
        construction_parent=parent,
    )
    try:
        adapter = LeanRecipeAdapter(
            discovery,
            lambda selected: provider if selected == owner else None,
            AttemptLedger(tmp_path / "attempts.sqlite3"),
            measure_query=True,
        )
        recipe = {
            "schema": "carbon.construction-recipe.v1",
            "challenge": material["construction_kit"],
            "source": {"kind": "bundle", "bundle_ref": bundle.to_dict()},
            "procedure": {
                "entrypoint": {"module": "candidate.build", "name": "build"},
                "configuration": {},
                "train_use": {"cases": "all"},
                "initial_state": None,
            },
            "output": {
                "format": "carbon.numeric-graph.v1",
                "interface_digest": material["construction_kit"]["interface_digest"],
            },
        }
        task_id = adapter.evaluate(
            Admitted(
                owner,
                {},
                adapter.challenge_id,
                adapter.challenge_version,
                recipe,
                adapter.contract_digest,
            )
        )["task_id"]
        queued = provider._views[task_id]
        assert queued.state is DirectTaskStateV3.QUEUED
        assert json.loads(provider._task_image_bindings[task_id]) == [
            "BUNDLE_SOURCE",
            bundle.to_dict(),
        ]
        assert ledger.status(owner=owner)["operations"] == []
        finished = provider.run_queued_task(queued.task_id)
        operations = ledger.status(owner=owner)["operations"]
        failure_diagnostic = None
        if finished.state is not DirectTaskStateV3.SUCCEEDED:
            closed_states = {
                None,
                "RESERVED",
                "SUCCEEDED",
                "FAILED_INFRA",
                "FAILED_MINER",
                "CANCELLED",
            }
            child_states = tuple(
                (
                    stage,
                    state if state in closed_states else "UNKNOWN",
                )
                for stage, child in zip(
                    ("build", "inference", "prep"),
                    provider._all_children(queued.task_id),
                )
                for state in (ledger.operation_state(child, owner=owner),)
            )
            receipt = finished.terminal_receipt
            failure_diagnostic = {
                "task_state": finished.state.value,
                "failure_type": (
                    receipt.infrastructure_failure_class.value
                    if receipt is not None
                    and receipt.infrastructure_failure_class is not None
                    else "NONE"
                ),
                "failed_stage": tuple(
                    stage for stage, state in child_states if state == "FAILED_INFRA"
                ),
                "child_states": child_states,
            }
        assert finished.state is DirectTaskStateV3.SUCCEEDED, failure_diagnostic
        evidence = provider.private_attempt(queued.task_id)
        assert evidence["schema"] == "carbon.direct-private-attempt.overlay.v1"
        assert evidence["parent_image_id"] == parent.image_id
        assert evidence["inference_image_id"] == parent.image_id
        assert evidence["build_receipt"]["train_digest"] == digest(material["train"])
        assert evidence["prediction_comparison"]["exact_equal"] is True
        assert len(operations) == 3
        assert {item["state"] for item in operations} == {"SUCCEEDED"}
        expected_provenance = {
            "prep": "DIRECT_BUNDLE_DEPENDENCY_PREP",
            "build": "DIRECT_BUNDLE_OVERLAY_RECONSTRUCTION",
            "inference": "DIRECT_BUNDLE_PUBLIC_INFERENCE",
        }
        policy = material["construction_limits_document"][
            "reconstruction_resource_policy"
        ]
        for phase, provenance in expected_provenance.items():
            operation = ledger.root / evidence[phase + "_operation"]
            intent = json.loads((operation / "intent.json").read_bytes())
            assert intent["request"]["image"] == parent.image_id
            assert intent["request"]["provenance"] == provenance
            controls_raw = json.loads((operation / "resources.json").read_bytes())
            controls = controls_raw["controls"]
            assert (
                controls_raw["controls_digest"] == evidence[phase + "_controls_digest"]
            )
            assert controls_raw["controls_digest"] == digest(canonical(controls))
            host = controls["daemon_host_config"]
            assert host["network_mode"] == "none"
            assert host["read_only_root"] is True
            assert host["memory"] == policy["memory_bytes_max"]
            assert host["memory_swap"] == host["memory"]
            assert host["nano_cpus"] == policy["cpu_count_max"] * 10**9
            assert host["pids_limit"] == policy["pids_max"]
            assert not cli.run(
                ["ps", "-aq", "--filter", "name=^" + intent["container"] + "$"],
                timeout=10,
            ).stdout.strip()
        build = ledger.root / evidence["build_operation"]
        assert (build / "input/train.npz").read_bytes() == material["train"]
        assert (
            build / "input/overlay/source/candidate/build.py"
        ).read_bytes() == SOURCE
        inference = ledger.root / evidence["inference_operation"]
        inference_files = {
            path.relative_to(inference / "input").as_posix()
            for path in (inference / "input").rglob("*")
            if path.is_file()
        }
        assert {"state.npz", "inputs.npz"} <= inference_files
        assert not {"train.npz", "train.gz", "source.tar.gz"} & inference_files
        assert not any(
            "candidate" in name or name.startswith("overlay/")
            for name in inference_files
        )
        with np.load(io.BytesIO(material["train"]), allow_pickle=False) as train:
            scale = np.float32(
                np.sum(train["inputs"] * train["targets"])
                / np.sum(train["inputs"] ** 2)
            )
        np.testing.assert_array_equal(
            np.asarray(evidence["predictions"], dtype=np.float32),
            material["practice_inputs"] * scale,
        )
        artifacts, entries = tmp_path / "bank-artifacts", tmp_path / "bank-entries"
        artifacts.mkdir(mode=0o700)
        entries.mkdir(mode=0o700)
        saved = retain_served_result(
            adapter, task_id, artifact_directory=artifacts, entry_directory=entries
        )
        assert saved["status"] == "CREATED"
        assert saved["score_state"] == "NOT_COMPUTED"
        assert saved["official_eligible"] is False
        assert saved["measurement_state"] == "DEVELOPMENT_UNRANKED"
        measured_path = saved["measurement_path"]
        assert measured_path.parent != saved["artifact_path"]
        assert measured_path.stat().st_mode & 0o077 == 0
        measured = json.loads(measured_path.read_bytes())
        entry = json.loads(saved["entry_path"].read_bytes())
        assert (
            measured["schema"] == "carbon.lean-recipe.public-development-measurement.v1"
        )
        assert measured["task_id"] == task_id
        assert measured["entry_id"] == entry["entry_id"] == saved["entry_id"]
        assert entry["state_digest"] == finished.terminal_receipt.state_digest
        assert (
            entry["prediction_digest"] == finished.terminal_receipt.predictions_digest
        )
        assert entry["prediction_digest"] == evidence["predictions_digest"]
        reduced = measured["result"]
        assert reduced["entry_id"] == entry["entry_id"]
        assert reduced["state_digest"] == entry["state_digest"]
        assert reduced["status"] == "BENCHMARK_REDUCED"
        assert reduced["score_status"] == "PACK_NOT_READY"
        assert measured["accuracy_ceiling"] is None and measured["ranking"] is None
        assert measured["speedup_comparability"] == "NOT_ESTABLISHED"
        assert measured["model_timing_scope"] == (
            "COLD_SINGLE_WORKER_QUERY_INCLUDES_GRAPH_LOAD_AND_JAX_COMPILE"
        )
        assert (
            measured["reference_timing_scope"]
            == "IN_PROCESS_PUBLIC_REFERENCE_ARRAY_ONLY"
        )
        assert (saved["artifact_path"] / "state.npz").read_bytes() == (
            build / "snapshot/state.npz"
        ).read_bytes()
        assert (
            json.loads(
                (saved["artifact_path"] / "prediction-comparison.json").read_bytes()
            )
            == evidence["prediction_comparison"]
        )
        assert len(ledger.status(owner=owner)["operations"]) == 3
    finally:
        provider.close()
