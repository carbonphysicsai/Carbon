"""Actual fixed Julia advection under isolated, local engineering fixture grants."""

import json
import math
import os
import struct
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests/cpu")]

from test_advection_science import prepared_advection
from test_authored_julia import prepared

from carbon.development_session.advection_research import (
    MATERIAL,
    PublicAdvectionMaterial,
)
from carbon.development_session.julia_analysis import (
    build_julia_analysis_image,
    load_julia_analysis_image,
    run_julia,
    verify_julia_image,
)
from carbon.development_session.research_carrier import ACTIVE_TASK
from carbon.development_session.research_workspace import ResearchWorkspace
from carbon.reconstruction.worker.docker_runtime import DockerCLI
from carbon.reconstruction.worker.model import WorkerFailure
from carbon.reference_runtime.julia.advection import (
    AdvectionRequest,
    decode_outputs,
    public_definition,
    source,
)


@pytest.fixture(scope="module")
def image(tmp_path_factory):
    explicit = os.environ.get("CARBON_ADVECTION_JULIA_IMAGE_MANIFEST")
    if explicit:
        return verify_julia_image(load_julia_analysis_image(Path(explicit)))
    # The normal service script shares the exact operator-built authored image
    # with its containment suite. No solver request installs or builds a runtime.
    return build_julia_analysis_image(
        Path(os.environ["CARBON_JULIA_WORKER_MANIFEST"]),
        Path(
            os.environ.get(
                "CARBON_AUTHORED_JULIA_IMAGE_ROOT",
                str(tmp_path_factory.mktemp("advection-julia-image")),
            )
        ),
    )


def removed(ledger):
    for path in ledger.root.glob("operation-*/intent.json"):
        intent = json.loads(path.read_bytes())
        assert (
            not DockerCLI()
            .run(
                ["ps", "-aq", "--filter", "name=^" + intent["container"] + "$"],
                timeout=10,
            )
            .stdout.strip()
        )


def test_fixed_public_study_native_refinement_and_one_charge_replay(image, tmp_path):
    ledger = prepared_advection(tmp_path, image)
    workspace = ResearchWorkspace(ledger, "test-miner")
    material = PublicAdvectionMaterial(
        None, ledger=ledger, owner="test-miner", image=image
    )
    token = ACTIVE_TASK.set("fixture-advection-task")
    try:
        result = material(MATERIAL, workspace)
        assert material(MATERIAL, workspace) == result
    finally:
        ACTIVE_TASK.reset(token)
    document = result["document"]
    diagnostic = document["diagnostics"]
    assert document["provenance"] == "MINER_SELF_REPORTED"
    assert diagnostic["fine_analytic_rms"] < diagnostic["coarse_analytic_rms"]
    assert diagnostic["fine_analytic_rms"] < 0.01  # Analytic control fixture only.
    assert max(diagnostic["coarse_mean_drift"], diagnostic["fine_mean_drift"]) < 1e-13
    assert diagnostic["completed_horizon"] == 1.0
    assert not diagnostic["scientifically_qualified"]
    with ledger.db() as db:
        operations = db.execute("SELECT state,actual FROM operations").fetchall()
    assert len(operations) == 1 and operations[0][0] == "SUCCEEDED"
    assert json.loads(operations[0][1])["research_trials"] == 1
    removed(ledger)
    print(
        json.dumps(
            {
                "diagnostics": diagnostic,
                "actual": json.loads(operations[0][1]),
                "image": image.image_id,
            }
        )
    )


@pytest.mark.parametrize("speed", [-1.0, 0.0, 1.0])
def test_native_signed_transport_time_order_and_constant_control(
    image, tmp_path, speed
):
    ledger, _ = prepared(tmp_path, image=image)
    d = replace(
        public_definition(),
        parameter=speed,
        requested_times=(0.5, 0.0, 0.5),
        initial_field=(0.25,) * 64,
    )
    request = AdvectionRequest(d)
    result = run_julia(
        ledger,
        owner="test-miner",
        identity="constant-control",
        source=source(),
        files={"request.txt": request.encode()},
        image=image,
        seconds=60,
    )
    snapshot = ledger.root / result["operation"] / "snapshot"
    files = {p.name: p.read_bytes() for p in snapshot.iterdir()}
    diagnostic = decode_outputs(files, request)
    assert diagnostic["shape"] == [3, 64]
    assert {v[0] for v in struct.iter_unpack("<d", files["fine.f64le"])} == {0.25}
    assert diagnostic["refinement_max"] == 0.0
    assert diagnostic["completed_horizon"] == 0.5
    removed(ledger)


def test_negative_translating_wave_preserves_requested_time_order(image, tmp_path):
    ledger, _ = prepared(tmp_path, image=image)
    d = replace(public_definition(), parameter=-1.0, requested_times=(0.5, 0.0, 0.5))
    request = AdvectionRequest(d)
    result = run_julia(
        ledger,
        owner="test-miner",
        identity="negative-translation",
        source=source(),
        files={"request.txt": request.encode()},
        image=image,
        seconds=60,
    )
    snapshot = ledger.root / result["operation"] / "snapshot"
    files = {p.name: p.read_bytes() for p in snapshot.iterdir()}
    decode_outputs(files, request)
    values = [v[0] for v in struct.iter_unpack("<d", files["fine.f64le"])]
    assert values[:64] == values[128:]
    assert values[64:128] == list(d.initial_field)
    expected = [1.0 + 0.25 * math.sin(2 * math.pi * i / 64 + 0.5) for i in range(64)]
    assert max(abs(a - b) for a, b in zip(values[:64], expected)) < 0.01
    removed(ledger)


def test_native_malformed_units_reject_and_cleanup_without_success(image, tmp_path):
    ledger, _ = prepared(tmp_path, image=image)
    request = AdvectionRequest(public_definition())
    malformed = request.encode().replace(
        b"carbon_advection_definition_native_v1", b"dimensionless"
    )
    with pytest.raises((ValueError, WorkerFailure)):
        run_julia(
            ledger,
            owner="test-miner",
            identity="bad-units",
            source=source(),
            files={"request.txt": malformed},
            image=image,
            seconds=60,
        )
    with ledger.db() as db:
        rows = db.execute("SELECT state FROM operations").fetchall()
    assert rows and all(row[0] != "SUCCEEDED" for row in rows)
    removed(ledger)


def test_public_workspace_task_executes_registered_advection_material(image, tmp_path):
    from b07b_fixtures import make_fixture
    from test_cw1_research_tasks import request

    from carbon import research
    from carbon.development_session.research_material import PublicMaterial
    from carbon.development_session.research_tasks import (
        PublicDevelopmentResearchTasks,
        PublicResearchExecutor,
    )

    ledger = prepared_advection(tmp_path / "admitted", image)
    material = PublicAdvectionMaterial(
        PublicMaterial(None), ledger=ledger, owner="test-miner", image=image
    )
    executor = PublicResearchExecutor(
        ledger=ledger,
        owner="test-miner",
        image=image.parent,
        public_material=material,
        practice=None,
        julia_image=image,
    )
    fixture = make_fixture(tmp_path / "protocol-fixture")
    base = fixture.provider
    provider = PublicDevelopmentResearchTasks(
        root=tmp_path / "tasks",
        requester="test-miner",
        challenge_catalog_provider=base._catalog,
        manifest_provider=base._manifests,
        compilation_resolver=base._compiler,
        prior_resolver=base._priors,
        resource_resolver=base._resources,
        executor=executor,
        task_queue=base._queue,
        clock=base._clock,
        worker_implementation_digest=base._worker_digest,
        environment_digest=base._environment_digest,
    )
    executor.request_resolver = provider.request_for_execution
    try:
        capabilities_task = provider.start_research_task(
            request(fixture, "public_material", {"name": "capabilities"}, 0)
        ).task
        capabilities_done = provider.run_queued_task(capabilities_task.task_id)
        capabilities_result = executor.public_result(capabilities_done)["result"][
            "document"
        ]
        assert capabilities_result["scientific_task_usage"]["arguments"] == {
            "name": MATERIAL
        }
        req = request(fixture, "public_material", {"name": MATERIAL}, 1)
        task = provider.start_research_task(req).task
        done = provider.run_queued_task(task.task_id)
        assert done.state is research.ResearchTaskState.SUCCEEDED
        assert provider.start_research_task(req).task.task_id == task.task_id
        result = executor.public_result(done)
        assert result["result"]["document"]["provenance"] == "MINER_SELF_REPORTED"
        assert (
            provider.get_experiment_record(task.task_id).evidence_class
            is research.ResearchEvidenceClass.STRUCTURAL_ONLY
        )
        removed(ledger)
    finally:
        provider.close()
