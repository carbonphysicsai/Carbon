"""Actual native Julia checks in disposable, bounded local Docker workers.

Primitive controls require CARBON_JULIA_IMAGE, an exact local sha256 image ID.
Controller controls require CARBON_JULIA_WORKER_MANIFEST from the normal image
builder. This lane exercises bounded DEVELOPMENT calculation and the existing
C04 worker lifecycle; it does not qualify security or all three consumer paths.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

from carbon.reference_runtime.julia.protocol import source_digest

COMMON = """
import json, math, os, time
from pathlib import Path
from carbon.reference_runtime.julia import protocol as bridge
def request(points=64, varying=False):
    return bridge.JuliaBurgersRequest(
        case_digest='sha256:'+'a'*64,
        domain_length=2.0*math.pi, viscosity=0.1,
        mean=0.0 if varying else 0.75,
        cosine_coefficients=(0.0,)*12,
        sine_coefficients=((0.1,)+(0.0,)*11) if varying else (0.0,)*12,
        requested_times=(0.0,0.1,0.2), output_points=points,
        units='dimensionless',
    )
def observation(result):
    return {
        'coarse_points':result.coarse_points,'fine_points':result.fine_points,
        'coarse_steps':result.coarse_steps,'fine_steps':result.fine_steps,
        'coarse_mean_drift':result.coarse_mean_drift,
        'fine_mean_drift':result.fine_mean_drift,
        'refinement_rms':result.refinement_rms,
        'refinement_max':result.refinement_max,
        'completed_horizon':result.completed_horizon,
        'solver_seconds':result.solver_seconds,
        'allocated_bytes':result.allocated_bytes,
    }
def emit(value):
    value.update(source_digest=bridge.source_digest(),julia=bridge.JULIA_VERSION,
                 score_eligible=False,scientifically_qualified=False)
    memory=Path('/sys/fs/cgroup/memory.peak')
    value['container_memory_peak_bytes']=int(memory.read_text()) if memory.exists() else None
    print(json.dumps(value,sort_keys=True,allow_nan=False))
"""


def run_worker(program):
    image = os.environ.get("CARBON_JULIA_IMAGE", "")
    assert re.fullmatch(
        r"sha256:[0-9a-f]{64}", image
    ), "exact Julia test image ID required"
    created = subprocess.run(
        [
            "docker",
            "create",
            "--network",
            "none",
            "--read-only",
            "--user",
            "65532:65532",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            "1g",
            "--memory-swap",
            "1g",
            "--pids-limit",
            "128",
            "--cpus",
            "1",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=64m,mode=1777",
            "--label",
            "carbon.test=julia-native-development",
            "--entrypoint",
            "/opt/carbon-worker/bin/python",
            image,
            "-I",
            "-c",
            COMMON + program,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    container = created.stdout.strip()
    assert re.fullmatch(r"[0-9a-f]{64}", container)
    try:
        inspected = json.loads(
            subprocess.run(
                ["docker", "inspect", container],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout
        )[0]
        controls = inspected["HostConfig"]
        assert inspected["Image"] == image
        assert inspected["Config"]["User"] == "65532:65532"
        assert controls["NetworkMode"] == "none"
        assert controls["ReadonlyRootfs"] is True
        assert controls["Memory"] == controls["MemorySwap"] == 1024**3
        assert controls["PidsLimit"] == 128
        assert controls["NanoCpus"] == 1_000_000_000
        assert controls["CapDrop"] == ["ALL"]
        assert "no-new-privileges" in controls["SecurityOpt"]
        assert controls["Binds"] is None
        assert inspected["Mounts"] == []
        started = time.monotonic()
        completed = subprocess.run(
            ["docker", "start", "--attach", container],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        state = json.loads(
            subprocess.run(
                ["docker", "inspect", container],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout
        )[0]["State"]
        assert completed.returncode == 0, completed.stderr
        assert state["ExitCode"] == 0, completed.stderr
        assert state["OOMKilled"] is False
        result = json.loads(completed.stdout)
        assert result["source_digest"] == source_digest()
        result.update(image=image, container_wall_seconds=time.monotonic() - started)
        print(json.dumps(result, sort_keys=True))
        trace = os.environ.get("CARBON_JULIA_TRACE_PATH")
        if trace:
            with Path(trace).open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(result, sort_keys=True) + "\n")
        return result
    finally:
        subprocess.run(
            ["docker", "rm", "--force", container],
            check=True,
            capture_output=True,
            timeout=15,
        )
        assert (
            subprocess.run(
                ["docker", "inspect", container],
                check=False,
                capture_output=True,
                timeout=10,
            ).returncode
            != 0
        )


def test_native_constant_conservation_and_requested_horizon():
    result = run_worker("""
result=bridge.execute_in_worker(request(),deadline_seconds=60.0)
error=max(abs(value-0.75) for row in result.values() for value in row)
emit({'case':'analytic_constant','maximum_absolute_error':error,**observation(result)})
""")
    # Numerical-control fixture checks, never production scientific thresholds.
    assert result["maximum_absolute_error"] < 1e-12
    assert result["fine_mean_drift"] < 1e-12
    assert result["refinement_max"] < 1e-12
    assert result["completed_horizon"] == 0.2


def test_native_nonconstant_refinement_against_distinct_cole_hopf_method():
    result = run_worker("""
import numpy as np
from carbon.reference_runtime.model import (
    BurgersReferenceRequest, BurgersReferenceRole, execute_reference,
    reference_settings, runtime_environment_digest,
)
errors=[]
observations=[]
initial_errors=[]
for points in (64,128):
    req=request(points=points,varying=True)
    result=bridge.execute_in_worker(req,deadline_seconds=60.0)
    role=BurgersReferenceRole.CANDIDATE_PRIMARY
    reference_request=BurgersReferenceRequest(
        req.case_digest,role,
        tuple(req.domain_length*i/points for i in range(points)),
        req.requested_times,req.domain_length,req.viscosity,req.mean,
        req.cosine_coefficients,req.sine_coefficients,
        runtime_environment_digest(),reference_settings(role,points),
    )
    reference=execute_reference(reference_request)
    assert reference.artifact is not None
    errors.append(float(np.max(np.abs(np.asarray(result.values())-reference.artifact.array()))))
    initial_errors.append(max(abs(result.values()[0][i]-0.1*math.sin(2*math.pi*i/points)) for i in range(points)))
    observations.append(observation(result))
emit({'case':'nonconstant_refinement','cole_hopf_max_discrepancies':errors,
      'initial_max_errors':initial_errors,'runs':observations,
      'correlation_limit':'shared equations and physical inputs; no independent truth qualification'})
""")
    assert max(result["initial_max_errors"]) < 1e-12
    errors = result["cole_hopf_max_discrepancies"]
    assert 0.0 < errors[1] < errors[0]
    assert all(run["fine_mean_drift"] < 1e-12 for run in result["runs"])
    assert all(run["fine_steps"] > 0 for run in result["runs"])


def test_native_malformed_deadline_and_cancellation_are_closed_and_cleaned_up():
    result = run_worker("""
import subprocess
malformed=subprocess.run(bridge.worker_command(),input=b'caller expression'+bytes([10]),
                         capture_output=True,timeout=30,env={
                             'JULIA_LOAD_PATH':'@stdlib','JULIA_DEPOT_PATH':'/nonexistent',
                             'HOME':'/nonexistent',
                         })
assert malformed.returncode==20 and malformed.stdout==b'' and malformed.stderr==b''
from dataclasses import replace
try:
    bridge.execute_in_worker(replace(request(),viscosity=1e308),deadline_seconds=30.0)
    raise AssertionError('unrepresentable numerical timestep should fail')
except bridge.JuliaFailure as failure:
    assert failure.code is bridge.JuliaFailureCode.NUMERICAL
original=bridge.subprocess.Popen
children=[]
def observed(*args,**kwargs):
    process=original(*args,**kwargs);children.append(process);return process
bridge.subprocess.Popen=observed
codes=[]
for cancel in (False,True):
    calls=[0]
    def cancelled():
        calls[0]+=1
        return calls[0]>2
    try:
        bridge.execute_in_worker(request(),deadline_seconds=5.0 if cancel else 0.001,
                                 cancelled=cancelled if cancel else None)
        raise AssertionError('operation should stop')
    except bridge.JuliaFailure as failure:
        codes.append(failure.code.value)
for process in children:
    assert process.poll() is not None
    try:
        os.killpg(process.pid,0)
        raise AssertionError('owned process group remains')
    except ProcessLookupError:
        pass
emit({'case':'process_controls','malformed_exit':malformed.returncode,
      'failure_codes':codes,'numerical_failure':'NUMERICAL_FAILURE',
      'reaped_children':len(children),'process_groups_released':True})
""")
    assert result["failure_codes"] == ["DEADLINE_EXCEEDED", "CANCELLED"]
    assert result["reaped_children"] == 2
    assert result["process_groups_released"] is True


def _controller_case():
    from carbon.generators.burgers_dynamics import (
        BurgersCaseCoordinates,
        PublicDevelopmentRole,
        generate_development_case,
        requested_times,
    )
    from carbon.reference_runtime.julia.adapter import julia_crosscheck_request
    from carbon.reference_runtime.model import (
        BurgersReferenceRole,
        build_reference_request,
        runtime_environment_digest,
    )
    from carbon.registry import ChallengeKey
    from carbon.seeding import EvaluationBinding, MockContext, MockEntropy, SeedPin

    sha = "sha256:" + "c" * 64
    context = MockContext(
        MockEntropy(b"j" * 32),
        SeedPin(
            ChallengeKey("burgers-dynamics-v1", "1.0"),
            "1.0",
            sha,
            "1.0",
            sha,
            EvaluationBinding(b"k" * 32),
        ),
    )
    case = generate_development_case(
        context,
        BurgersCaseCoordinates(PublicDevelopmentRole.TRAIN, 0, 0),
    )
    primary = build_reference_request(
        case,
        BurgersReferenceRole.CANDIDATE_PRIMARY,
        output_points=32,
        requested_times=requested_times(case, 4),
        environment_digest=runtime_environment_digest(),
    )
    return julia_crosscheck_request(primary, units="dimensionless")


def _controller(tmp_path):
    from carbon.reconstruction.worker.docker_runtime import load_image_identity
    from carbon.reconstruction.worker.model import DevelopmentWorkerProfile
    from carbon.reference_runtime.controller import IsolatedBurgersReferenceController

    manifest = os.environ.get("CARBON_JULIA_WORKER_MANIFEST")
    assert manifest, "exact freshly-built Julia worker identity manifest required"
    image = load_image_identity(Path(manifest))
    return IsolatedBurgersReferenceController(
        state_root=tmp_path.resolve(),
        image=image,
        worker_profile=DevelopmentWorkerProfile(
            "sha256:" + "1" * 64, "sha256:" + "2" * 64
        ),
    )


def test_registered_julia_runs_and_replays_through_existing_c04_controller(tmp_path):
    from carbon.evaluation.enums import ReferenceRunOutcome

    controller = _controller(tmp_path)
    request = _controller_case()
    result = controller.execute(request)
    assert result.result.outcome is ReferenceRunOutcome.SUPPORTED
    assert result.result.shape == (len(request.requested_times), 32)
    diagnostics = dict(result.result.diagnostics)
    assert diagnostics["language"] == "julia"
    assert diagnostics["runtime_version"] == "1.13.0"
    assert diagnostics["completed_horizon"] == request.requested_times[-1]
    assert not result.result.eligible_for_truth_or_score
    replay = controller.execute(request)
    assert replay.snapshot_digest == result.snapshot_digest
    assert replay.result.artifact_digest == result.result.artifact_digest
    assert replay.controls == {"retained_exact_replay": True}
    journal = json.loads(next((tmp_path / "launches").glob("*.json")).read_bytes())
    assert journal["state"] == "ASSOCIATED_DEVELOPMENT_ONLY"
    assert (
        subprocess.run(
            ["docker", "inspect", journal["container_name"]],
            check=False,
            capture_output=True,
            timeout=10,
        ).returncode
        != 0
    )
    record = {
        "case": "c04_registered_julia_public_train",
        "image": result.image_id,
        "request_digest": request.request_digest,
        "snapshot_digest": result.snapshot_digest,
        "artifact_digest": result.result.artifact_digest,
        "timings": result.timings,
        "resources": result.resources,
        "diagnostics": diagnostics,
        "exact_replay": True,
        "cleanup_confirmed": True,
        "score_eligible": False,
        "scientifically_qualified": False,
    }
    print(json.dumps(record, sort_keys=True))
    trace = os.environ.get("CARBON_JULIA_TRACE_PATH")
    if trace:
        with Path(trace).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")


def test_existing_c04_controller_cancels_live_julia_container_and_confirms_release(
    tmp_path,
):
    import pytest

    from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

    controller = _controller(tmp_path)
    checks = 0

    def cancelled():
        nonlocal checks
        journals = list((tmp_path / "launches").glob("*.json"))
        if (
            journals
            and json.loads(journals[0].read_bytes())["state"] == "CONTROLS_VERIFIED"
        ):
            checks += 1
        return checks >= 3

    with pytest.raises(WorkerFailure) as failure:
        controller.execute(_controller_case(), cancelled=cancelled)
    assert failure.value.code is WorkerCode.CANCELLED
    journal = json.loads(next((tmp_path / "launches").glob("*.json")).read_bytes())
    assert journal["terminal_code"] == WorkerCode.CANCELLED.value
    assert journal["cleanup"] == "CONFIRMED"
    assert journal["state"] != "ASSOCIATED_DEVELOPMENT_ONLY"
    assert not list((tmp_path / "staging").iterdir())
    assert (
        subprocess.run(
            ["docker", "inspect", journal["container_name"]],
            check=False,
            capture_output=True,
            timeout=10,
        ).returncode
        != 0
    )
    print(
        json.dumps(
            {
                "case": "c04_registered_julia_cancel",
                "terminal_code": failure.value.code.value,
                "cleanup_confirmed": True,
                "controls_verified_checks": checks,
            },
            sort_keys=True,
        )
    )
