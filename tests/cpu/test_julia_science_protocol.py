"""Protocol/supervision tests are distinct from actual native Julia controls."""

from __future__ import annotations

import io
import math
import struct
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from carbon.reference_runtime.julia import protocol as bridge


def request(**changes):
    defaults = {
        "case_digest": "sha256:" + "a" * 64,
        "domain_length": 2.0 * math.pi,
        "viscosity": 0.1,
        "mean": 0.75,
        "cosine_coefficients": (0.0,) * 12,
        "sine_coefficients": (0.0,) * 12,
        "requested_times": (0.0, 0.01),
        "output_points": 32,
        "units": "dimensionless",
    }
    return bridge.JuliaBurgersRequest(**{**defaults, **changes})


def frame(req, *, fields=None, body=None):
    header = [
        "CARBON_JULIA_BURGERS_RESULT_V1",
        req.request_digest,
        bridge.JULIA_VERSION,
        bridge.METHOD_ID,
        bridge.UNITS,
        bridge.LAYOUT,
        "SUPPORTED",
        str(len(req.requested_times)),
        str(req.output_points),
        str(req.coarse_points),
        str(2 * req.coarse_points),
        "1",
        "2",
        "0.0",
        "0.0",
        "0.0",
        "0.0",
        repr(req.requested_times[-1]),
        "0.05",
        repr(req.requested_times[0]),
        "1024",
    ]
    for index, value in (fields or {}).items():
        header[index] = value
    if body is None:
        body = (
            struct.pack("<d", req.mean) * req.output_points * len(req.requested_times)
        )
    return "\n".join(header).encode("ascii") + b"\n\n" + body


@pytest.mark.parametrize(
    "changes",
    [
        {"case_digest": "sha256:" + "g" * 64},
        {"case_digest": 3},
        {"domain_length": 0.0},
        {"domain_length": -1.0},
        {"domain_length": math.inf},
        {"viscosity": 0.0},
        {"viscosity": -0.1},
        {"viscosity": True},
        {"mean": complex(1, 2)},
        {"mean": math.nan},
        {"cosine_coefficients": [0.0] * 12},
        {"cosine_coefficients": (0.0,) * 11},
        {"sine_coefficients": (0.0,) * 13},
        {"sine_coefficients": (0,) * 12},
        {"sine_coefficients": (math.inf,) * 12},
        {"requested_times": ()},
        {"requested_times": (0.0,) * 257},
        {"requested_times": (0.1, 0.0)},
        {"requested_times": (-0.01, 0.0)},
        {"requested_times": (0.0, 0.0)},
        {"requested_times": (0.0, math.nan)},
        {"output_points": 31},
        {"output_points": 33},
        {"output_points": 2048},
        {"output_points": 32.0},
        {"output_points": True},
        {"units": "m,s,m/s"},
        {"units": None},
    ],
)
def test_reject_ambiguous_or_unsupported_request(changes):
    with pytest.raises(bridge.JuliaFailure) as failure:
        request(**changes)
    assert failure.value.code is bridge.JuliaFailureCode.INVALID


def test_request_identity_covers_physics_units_source_and_fixed_method():
    req = request()
    encoded = req.encode()
    assert encoded.endswith((req.request_digest + "\n").encode())
    assert bridge.source_digest().encode() in encoded
    assert bridge.METHOD_ID.encode() in encoded
    assert len(encoded) < bridge.MAX_INPUT_BYTES
    assert req.request_digest != replace(req, viscosity=0.2).request_digest
    assert (
        req.request_digest != replace(req, requested_times=(0.0, 0.02)).request_digest
    )
    assert req.request_digest == request().request_digest


def test_fixed_state_bytes_preserve_axes_little_endian_and_point_order():
    req = request()
    values = [float(i) / 2 for i in range(64)]
    decoded = bridge.decode_result(frame(req, body=struct.pack("<64d", *values)), req)
    assert decoded.values() == (tuple(values[:32]), tuple(values[32:]))
    assert decoded.shape == (2, 32)
    assert decoded.completed_horizon == 0.01
    assert decoded.allocated_bytes == 1024
    assert not decoded.scientifically_qualified
    assert not decoded.score_eligible
    assert not decoded.protected_execution_eligible


@pytest.mark.parametrize(
    "fields",
    [
        {0: "UNKNOWN"},
        {1: "sha256:" + "b" * 64},
        {2: "1.12.0"},
        {3: "caller_solver"},
        {4: "SI"},
        {5: "x,time;F;>f8;complex;periodic"},
        {6: "QUALIFIED"},
        {7: "3"},
        {8: "64"},
        {9: "128"},
        {10: "64"},
        {11: "200001"},
        {12: "-1"},
        {13: "nan"},
        {14: "inf"},
        {15: "-0.1"},
        {15: "0.2", 16: "0.1"},
        {17: "0.005"},
        {18: "-1.0"},
        {19: "0.001"},
        {20: "1.0"},
        {20: "99999999999999999"},
    ],
)
def test_malformed_result_has_no_partial_solution(fields):
    req = request()
    with pytest.raises(bridge.JuliaFailure) as failure:
        bridge.decode_result(frame(req, fields=fields), req)
    assert failure.value.code is bridge.JuliaFailureCode.INVALID


@pytest.mark.parametrize("body", [b"", b"x", struct.pack("<d", math.nan) * 64])
def test_reject_truncated_or_nonfinite_solution(body):
    req = request()
    with pytest.raises(bridge.JuliaFailure):
        bridge.decode_result(frame(req, body=body), req)


def test_reject_trailing_bytes_and_oversized_output():
    req = request()
    with pytest.raises(bridge.JuliaFailure):
        bridge.decode_result(frame(req) + b"x", req)
    with pytest.raises(bridge.JuliaFailure) as failure:
        bridge.decode_result(b"x" * (bridge.MAX_OUTPUT_BYTES + 1), req)
    assert failure.value.code is bridge.JuliaFailureCode.OUTPUT_LIMIT


def test_command_has_no_caller_expression_or_runtime_package_install():
    command = bridge.worker_command()
    assert command[0] == "/opt/carbon-julia/bin/julia"
    assert "--startup-file=no" in command
    assert "--history-file=no" in command
    assert "--compiled-modules=no" in command
    assert "--pkgimages=no" in command
    assert command[-1].endswith("burgers.jl")
    source = (Path(bridge.__file__).parent / "burgers.jl").read_text()
    assert "Pkg.add" not in source and "eval(" not in source


def install_process(monkeypatch, tmp_path, *, output, returncode=0, running=False):
    executable = tmp_path / "julia"
    executable.write_bytes(b"test-only")
    monkeypatch.setattr(bridge, "_EXECUTABLE", executable)
    monkeypatch.setattr(bridge.sys, "platform", "linux")
    observed = {}

    class Process:
        pid = 12345

        def __init__(self, command, **kwargs):
            self.stdout = io.BytesIO(output)
            self.returncode = None if running else returncode
            observed.update(command=command, **kwargs)

        def poll(self):
            return self.returncode

        def wait(self, timeout):
            observed["waited"] = timeout
            self.returncode = returncode

    def kill(pid, sig):
        observed["killed"] = (pid, sig)

    monkeypatch.setattr(bridge.subprocess, "Popen", Process)
    monkeypatch.setattr(bridge.os, "killpg", kill, raising=False)
    return observed


def test_worker_supervision_strips_credentials_and_kills_owned_process_group(
    monkeypatch, tmp_path
):
    req = request()
    observed = install_process(monkeypatch, tmp_path, output=frame(req))
    monkeypatch.setenv("PROVIDER_API_KEY", "never-inherit")
    result = bridge.execute_in_worker(req, deadline_seconds=1.0)
    assert result.values()[0] == (0.75,) * 32
    assert "PROVIDER_API_KEY" not in observed["env"]
    assert observed["env"]["JULIA_LOAD_PATH"] == "@stdlib"
    assert observed["env"]["JULIA_DEPOT_PATH"] == "/nonexistent/carbon-julia-depot"
    assert observed["start_new_session"] is True
    assert observed["killed"][0] == 12345


@pytest.mark.parametrize(
    "returncode,code",
    [(20, "INVALID"), (21, "ENVIRONMENT"), (22, "NUMERICAL"), (23, "PROCESS")],
)
def test_failure_codes_are_not_candidate_physics_failure(
    monkeypatch, tmp_path, returncode, code
):
    install_process(
        monkeypatch, tmp_path, output=b"private solver error", returncode=returncode
    )
    with pytest.raises(bridge.JuliaFailure) as failure:
        bridge.execute_in_worker(request(), deadline_seconds=1.0)
    assert failure.value.code is getattr(bridge.JuliaFailureCode, code)
    assert "private" not in str(failure.value)


def test_deadline_and_cancel_clean_up(monkeypatch, tmp_path):
    observed = install_process(monkeypatch, tmp_path, output=b"", running=True)
    with pytest.raises(bridge.JuliaFailure) as failure:
        bridge.execute_in_worker(request(), deadline_seconds=0.001)
    assert failure.value.code is bridge.JuliaFailureCode.DEADLINE
    assert observed["killed"][0] == 12345
    calls = iter([False, True])
    with pytest.raises(bridge.JuliaFailure) as failure:
        bridge.execute_in_worker(
            request(), deadline_seconds=1.0, cancelled=lambda: next(calls)
        )
    assert failure.value.code is bridge.JuliaFailureCode.CANCELLED


def test_overflow_is_bounded_and_cleaned_up(monkeypatch, tmp_path):
    observed = install_process(
        monkeypatch, tmp_path, output=b"x" * (bridge.MAX_OUTPUT_BYTES + 1)
    )
    with pytest.raises(bridge.JuliaFailure) as failure:
        bridge.execute_in_worker(request(), deadline_seconds=1.0)
    assert failure.value.code is bridge.JuliaFailureCode.OUTPUT_LIMIT
    assert observed["killed"][0] == 12345


@pytest.mark.skipif(
    sys.platform != "linux" or not Path("/opt/carbon-julia/bin/julia").is_file(),
    reason="native Julia 1.13.0 worker executable unavailable; protocol tests are not numerical execution",
)
def test_native_analytic_constant_and_nonconstant_refinement_controls():
    # These test-only tolerances check analytic/numerical controls. They are
    # not a Challenge acceptance threshold, reference qualification or policy.
    constant = bridge.execute_in_worker(request(), deadline_seconds=60.0)
    assert all(
        value == pytest.approx(0.75, abs=1e-12)
        for row in constant.values()
        for value in row
    )
    assert constant.fine_mean_drift < 1e-12
    assert constant.refinement_max < 1e-12
    varying = request(mean=0.0, sine_coefficients=(0.1,) + (0.0,) * 11)
    result = bridge.execute_in_worker(varying, deadline_seconds=60.0)
    expected = tuple(0.1 * math.sin(2 * math.pi * i / 32) for i in range(32))
    assert result.values()[0] == pytest.approx(expected, abs=1e-12)
    assert result.fine_steps > 0
    assert result.refinement_max > 0.0
    assert result.fine_mean_drift < 1e-12
    assert result.completed_horizon == varying.requested_times[-1]


def c04_request(role=None):
    from carbon.reference_runtime.model import (
        BurgersReferenceRequest,
        BurgersReferenceRole,
        reference_settings,
    )

    role = role or BurgersReferenceRole.CANDIDATE_PRIMARY
    return BurgersReferenceRequest(
        "sha256:" + "a" * 64,
        role,
        tuple(6.0 * i / 32 for i in range(32)),
        (0.0, 0.1),
        6.0,
        0.1,
        0.75,
        (0.0,) * 12,
        (0.0,) * 12,
        "sha256:" + "b" * 64,
        reference_settings(role, 32),
    )


def test_all_historical_v1_request_digests_remain_exact():
    from carbon.reference_runtime.model import (
        BurgersReferenceRole,
        decode_reference_request,
    )

    # Produced from merged main 0afbb9d98338353732ba2fce6716dbefd0af9bbc,
    # before the Julia variant existed. These freeze existing method identities.
    digests = (
        "sha256:c8480ee16416a70e8ef8f0e0b559fba3da7ef17c28e31fe3ea44db3e0123020b",
        "sha256:6662bb5556b5f2356a0b7220e0c7607daf4bd0cd88b01a475a69adc44beb8948",
        "sha256:d25e4f9a9c793c9127c1f503aa214da4c096ffc0a6251ce7cc3e77efe3cd8bb0",
    )
    for role, expected in zip(BurgersReferenceRole, digests):
        old = c04_request(role)
        assert old.request_digest == expected
        assert decode_reference_request(old.document()) == old
        assert "units" not in old.document()["query"]


def test_julia_adapter_has_distinct_policy_method_schema_and_identity():
    from carbon.reference_runtime.julia.adapter import julia_crosscheck_request
    from carbon.reference_runtime.model import (
        JULIA_POLICY_ID,
        JULIA_SCHEMA,
        BurgersReferenceRole,
        decode_reference_request,
    )

    primary = c04_request()
    julia = julia_crosscheck_request(primary, units="dimensionless")
    assert julia.role is BurgersReferenceRole.DEVELOPMENT_CROSSCHECK
    assert julia.policy_id == JULIA_POLICY_ID
    assert julia.document()["schema"] == JULIA_SCHEMA
    assert julia.method_id == bridge.METHOD_ID
    assert julia.case_digest == primary.case_digest
    assert julia.spatial_points == primary.spatial_points
    assert julia.requested_times == primary.requested_times
    assert julia.request_digest != primary.request_digest
    assert julia.environment_digest != primary.environment_digest
    assert decode_reference_request(julia.document()) == julia
    assert primary.role is BurgersReferenceRole.CANDIDATE_PRIMARY
    assert not julia.score_eligible and not julia.protected_execution_eligible


@pytest.mark.parametrize(
    "change", ["role", "units", "schema", "policy", "method", "settings", "script"]
)
def test_julia_registry_cannot_select_primary_script_or_tolerance(change):
    from carbon.reference_runtime.julia.adapter import julia_crosscheck_request
    from carbon.reference_runtime.model import decode_reference_request

    value = julia_crosscheck_request(c04_request(), units="dimensionless").document()
    if change == "role":
        value["role"] = "CANDIDATE_PRIMARY"
    elif change == "units":
        value["query"]["units"] = "SI"
    elif change == "schema":
        value["schema"] = "carbon.c04.burgers-reference.v1"
    elif change == "policy":
        value["policy"]["id"] = "carbon.burgers.reference.candidate.v1"
    elif change == "method":
        value["method"]["id"] = "cole_hopf_fourier_quadrature"
    elif change == "settings":
        value["method"]["settings"]["cfl"] = 0.1
    else:
        value["method"]["script"] = "/caller/code.jl"
    with pytest.raises(ValueError):
        decode_reference_request(value)


@pytest.mark.parametrize("code", tuple(bridge.JuliaFailureCode))
def test_native_failure_maps_to_existing_reference_outcome(monkeypatch, code):
    from carbon.reference_runtime.julia import adapter
    from carbon.reference_runtime.model import execute_reference
    from carbon.evaluation.enums import ReferenceRunOutcome

    def fail(*args, **kwargs):
        raise bridge.JuliaFailure(code)

    monkeypatch.setattr(adapter, "execute_in_worker", fail)
    julia = adapter.julia_crosscheck_request(c04_request(), units="dimensionless")
    result = execute_reference(julia)
    assert result.outcome is not ReferenceRunOutcome.SUPPORTED
    assert result.failure_reason is not None
    assert result.artifact is None
    assert not result.score_eligible
    if code is bridge.JuliaFailureCode.NUMERICAL:
        assert result.outcome is ReferenceRunOutcome.NUMERICAL_FAILURE
    elif code is bridge.JuliaFailureCode.CANCELLED:
        assert result.outcome is ReferenceRunOutcome.CANCELLED
    elif code in (bridge.JuliaFailureCode.INVALID, bridge.JuliaFailureCode.ENVIRONMENT):
        assert result.outcome is ReferenceRunOutcome.MALFORMED_OR_PROVENANCE_FAILURE
    else:
        assert result.outcome is ReferenceRunOutcome.INFRASTRUCTURE_FAILURE


def test_julia_staged_execution_uses_existing_artifact_and_validation_owners(
    monkeypatch, tmp_path
):
    import json
    from carbon.reference_runtime.julia import adapter
    from carbon.reference_runtime.protocol import (
        stage_reference_request,
        run_staged_reference_worker,
        validate_reference_snapshot,
    )

    julia = adapter.julia_crosscheck_request(c04_request(), units="dimensionless")

    def fixture_result(req, **kwargs):
        assert kwargs == {"deadline_seconds": 540.0}
        return bridge.decode_result(frame(req), req)

    monkeypatch.setattr(adapter, "execute_in_worker", fixture_result)
    stage, _ = stage_reference_request(tmp_path / "stage", julia)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    assert run_staged_reference_worker(stage, scratch) == 0
    manifest = scratch / "output/result.json"
    value = json.loads(manifest.read_bytes())
    assert value["schema"] == "carbon.c04.burgers-reference-result.v2"
    result = validate_reference_snapshot(scratch / "output", julia)
    assert result.request_digest == julia.request_digest
    assert result.shape == (2, 32)
    assert dict(result.diagnostics)["method"] == bridge.METHOD_ID
    assert not result.eligible_for_truth_or_score
    value["schema"] = "carbon.c04.burgers-reference-result.v1"
    manifest.chmod(0o600)
    manifest.write_text(json.dumps(value))
    from carbon.reconstruction.worker.model import WorkerFailure

    with pytest.raises(WorkerFailure):
        validate_reference_snapshot(scratch / "output", julia)


def test_julia_wrong_environment_never_starts_native_process(monkeypatch):
    from carbon.reference_runtime.julia import adapter
    from carbon.reference_runtime.model import execute_reference
    from carbon.evaluation.enums import ReferenceFailureReason

    julia = replace(
        adapter.julia_crosscheck_request(c04_request(), units="dimensionless"),
        environment_digest="sha256:" + "f" * 64,
    )
    monkeypatch.setattr(
        adapter, "execute_in_worker", lambda *a, **kw: pytest.fail("must not dispatch")
    )
    assert (
        execute_reference(julia).failure_reason
        is ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH
    )


def test_reference_controller_cancellation_uses_existing_exact_cleanup(
    monkeypatch, tmp_path
):
    import json
    from types import SimpleNamespace
    from carbon.reference_runtime import controller as owner
    from carbon.reconstruction.worker.model import (
        DevelopmentWorkerProfile,
        WorkerImageIdentity,
        WorkerFailure,
        WorkerCode,
    )

    digest = "sha256:" + "c" * 64
    image = WorkerImageIdentity(*([digest] * 8))
    profile = DevelopmentWorkerProfile(digest, digest)
    removed = []

    class CLI:
        def run(self, args, **kwargs):
            assert args[0] in {"create", "start"}
            return SimpleNamespace(stdout=b"d" * 64, returncode=0)

    monkeypatch.setattr(
        owner, "doctor", lambda **kwargs: SimpleNamespace(eligible=True, cpuset="0,1")
    )
    monkeypatch.setattr(owner, "spawn_watchdog", lambda **kwargs: None)
    monkeypatch.setattr(
        owner, "remove_exact_container", lambda **kwargs: removed.append(kwargs)
    )
    controller = owner.IsolatedBurgersReferenceController(
        state_root=tmp_path, image=image, worker_profile=profile, cli=CLI()
    )

    def stopped(*args, **kwargs):
        raise WorkerFailure(WorkerCode.CANCELLED)

    monkeypatch.setattr(controller, "_wait_file", stopped)
    with pytest.raises(WorkerFailure) as failure:
        controller.execute(c04_request())
    assert failure.value.code is WorkerCode.CANCELLED
    assert len(removed) == 1
    journal = json.loads(next((tmp_path / "launches").glob("*.json")).read_bytes())
    assert journal["cleanup"] == "CONFIRMED"
    assert journal["terminal_code"] == WorkerCode.CANCELLED.value
    assert journal["state"] != "ASSOCIATED_DEVELOPMENT_ONLY"
    assert not list((tmp_path / "staging").iterdir())


def test_reference_wait_checks_cancellation_before_polling():
    from carbon.reference_runtime.controller import IsolatedBurgersReferenceController
    from carbon.reconstruction.worker.model import WorkerFailure, WorkerCode

    controller = object.__new__(IsolatedBurgersReferenceController)
    with pytest.raises(WorkerFailure) as failure:
        controller._wait_file(
            "not-dispatched", "/scratch/ready", math.inf, lambda: True
        )
    assert failure.value.code is WorkerCode.CANCELLED
