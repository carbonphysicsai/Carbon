"""Actual native Julia checks in disposable, bounded local Docker workers.

Run with CARBON_JULIA_IMAGE set to an exact locally built sha256 image ID.
This lane proves bounded DEVELOPMENT calculations and process supervision;
it is not a security qualification or miner/validator/Workbench integration.
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
