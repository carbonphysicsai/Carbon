"""Closed bridge for a native Julia Burgers refinement instrument.

This is a worker utility, not an admission API or sandbox. The caller must
already be inside an admitted, independently supervised Linux worker. Existing
controllers own grants, role separation, filesystem/network controls, accounting
and cleanup. No request controls an executable, script, environment or tolerance.
Results are DEVELOPMENT diagnostics, never TruthAssets or qualification.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

JULIA_VERSION = "1.13.0"
METHOD_ID = "julia_periodic_conservative_flux_ssprk3_refinement_v1"
UNITS = "dimensionless"
LAYOUT = "time,x;C;<f8;point_estimate;periodic"
MAX_INPUT_BYTES = 32768
MAX_OUTPUT_BYTES = 1024 * 256 * 8 + 4096
MAX_TIMES = 256
MAX_STEPS = 200_000
MODE_COUNT = 12
_SOURCE = Path(__file__).resolve().parent
_EXECUTABLE = Path("/opt/carbon-julia/bin/julia")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


class JuliaFailureCode(str, Enum):
    INVALID = "INVALID_PROTOCOL"
    UNAVAILABLE = "RUNTIME_UNAVAILABLE"
    ENVIRONMENT = "ENVIRONMENT_MISMATCH"
    NUMERICAL = "NUMERICAL_FAILURE"
    DEADLINE = "DEADLINE_EXCEEDED"
    CANCELLED = "CANCELLED"
    OUTPUT_LIMIT = "OUTPUT_LIMIT"
    PROCESS = "PROCESS_FAILURE"
    CLEANUP = "CLEANUP_UNCONFIRMED"


class JuliaFailure(RuntimeError):
    """Closed error: never echoes solver output, input, paths or exceptions."""

    def __init__(self, code: JuliaFailureCode):
        self.code = code
        super().__init__(code.value)


def source_digest() -> str:
    """Identity of the exact shipped instrument and Base-only project."""
    digest = hashlib.sha256()
    for name in ("Project.toml", "Manifest.toml", "burgers.jl"):
        digest.update(name.encode("ascii") + b"\0")
        digest.update(hashlib.sha256((_SOURCE / name).read_bytes()).digest())
    return "sha256:" + digest.hexdigest()


def _float(value: object) -> bool:
    return type(value) is float and math.isfinite(value)


@dataclass(frozen=True, slots=True)
class JuliaBurgersRequest:
    """Explicit dimensionless periodic Burgers case; units are never inferred.

    Twelve Fourier coefficients and the uniform periodic query grid match the
    existing public Burgers case representation. Role/rights admission remains
    with the caller; a case digest by itself is not authorization.
    """

    case_digest: str
    domain_length: float
    viscosity: float
    mean: float
    cosine_coefficients: tuple[float, ...]
    sine_coefficients: tuple[float, ...]
    requested_times: tuple[float, ...]
    output_points: int
    units: str

    def __post_init__(self) -> None:
        if (
            type(self.case_digest) is not str
            or _DIGEST.fullmatch(self.case_digest) is None
            or not all(
                _float(x) for x in (self.domain_length, self.viscosity, self.mean)
            )
            or self.domain_length <= 0.0
            or self.viscosity <= 0.0
            or type(self.units) is not str
            or self.units != UNITS
            or type(self.output_points) is not int
            or not 32 <= self.output_points <= 1024
            or self.output_points & (self.output_points - 1)
        ):
            raise JuliaFailure(JuliaFailureCode.INVALID)
        for values, minimum, maximum in (
            (self.cosine_coefficients, MODE_COUNT, MODE_COUNT),
            (self.sine_coefficients, MODE_COUNT, MODE_COUNT),
            (self.requested_times, 1, MAX_TIMES),
        ):
            if (
                type(values) is not tuple
                or not minimum <= len(values) <= maximum
                or not all(_float(x) for x in values)
            ):
                raise JuliaFailure(JuliaFailureCode.INVALID)
        if self.requested_times[0] < 0.0 or any(
            b <= a for a, b in zip(self.requested_times, self.requested_times[1:])
        ):
            raise JuliaFailure(JuliaFailureCode.INVALID)

    @property
    def coarse_points(self) -> int:
        return max(64, self.output_points)

    def _lines(self) -> list[str]:
        return [
            "CARBON_JULIA_BURGERS_REQUEST_V1",
            METHOD_ID,
            JULIA_VERSION,
            source_digest(),
            self.case_digest,
            self.units,
            LAYOUT,
            repr(self.domain_length),
            repr(self.viscosity),
            repr(self.mean),
            str(self.output_points),
            ",".join(map(repr, self.cosine_coefficients)),
            ",".join(map(repr, self.sine_coefficients)),
            ",".join(map(repr, self.requested_times)),
        ]

    @property
    def request_digest(self) -> str:
        return "sha256:" + hashlib.sha256("\n".join(self._lines()).encode()).hexdigest()

    def encode(self) -> bytes:
        payload = ("\n".join([*self._lines(), self.request_digest]) + "\n").encode(
            "ascii"
        )
        if len(payload) > MAX_INPUT_BYTES:
            raise JuliaFailure(JuliaFailureCode.INVALID)
        return payload


@dataclass(frozen=True, slots=True)
class JuliaBurgersResult:
    request_digest: str
    shape: tuple[int, int]
    payload: bytes
    coarse_points: int
    fine_points: int
    coarse_steps: int
    fine_steps: int
    coarse_mean_drift: float
    fine_mean_drift: float
    refinement_rms: float
    refinement_max: float
    completed_horizon: float
    solver_seconds: float
    allocated_bytes: int

    @property
    def scientifically_qualified(self) -> bool:
        return False

    @property
    def score_eligible(self) -> bool:
        return False

    @property
    def protected_execution_eligible(self) -> bool:
        return False

    def values(self) -> tuple[tuple[float, ...], ...]:
        values = tuple(x[0] for x in struct.iter_unpack("<d", self.payload))
        width = self.shape[1]
        return tuple(values[i : i + width] for i in range(0, len(values), width))


def decode_result(payload: bytes, request: JuliaBurgersRequest) -> JuliaBurgersResult:
    """Validate the entire worker output before exposing any numerical bytes."""
    if type(payload) is not bytes or type(request) is not JuliaBurgersRequest:
        raise JuliaFailure(JuliaFailureCode.INVALID)
    if len(payload) > MAX_OUTPUT_BYTES:
        raise JuliaFailure(JuliaFailureCode.OUTPUT_LIMIT)
    try:
        header, body = payload.split(b"\n\n", 1)
        if len(header) > 4096:
            raise ValueError()
        fields = header.decode("ascii").split("\n")
        if len(fields) != 21 or fields[:7] != [
            "CARBON_JULIA_BURGERS_RESULT_V1",
            request.request_digest,
            JULIA_VERSION,
            METHOD_ID,
            UNITS,
            LAYOUT,
            "SUPPORTED",
        ]:
            raise ValueError()
        integers = []
        for index in (7, 8, 9, 10, 11, 12, 20):
            if re.fullmatch(r"0|[1-9][0-9]{0,15}", fields[index]) is None:
                raise ValueError()
            integers.append(int(fields[index]))
        nt, nx, coarse, fine, coarse_steps, fine_steps, allocated = integers
        numbers = tuple(float(value) for value in fields[13:20])
        drift_coarse, drift_fine, rms, maximum, horizon, seconds, initial_time = numbers
        if (
            (nt, nx) != (len(request.requested_times), request.output_points)
            or (coarse, fine) != (request.coarse_points, 2 * request.coarse_points)
            or not 0 <= coarse_steps <= MAX_STEPS
            or not 0 <= fine_steps <= MAX_STEPS
            or not all(math.isfinite(x) and x >= 0.0 for x in numbers)
            or maximum < rms
            or horizon != request.requested_times[-1]
            or initial_time != request.requested_times[0]
            or len(body) != nt * nx * 8
            or any(
                not math.isfinite(value[0]) for value in struct.iter_unpack("<d", body)
            )
        ):
            raise ValueError()
        return JuliaBurgersResult(
            request.request_digest,
            (nt, nx),
            body,
            coarse,
            fine,
            coarse_steps,
            fine_steps,
            drift_coarse,
            drift_fine,
            rms,
            maximum,
            horizon,
            seconds,
            allocated,
        )
    except (UnicodeError, ValueError, OverflowError):
        raise JuliaFailure(JuliaFailureCode.INVALID) from None


def worker_command() -> tuple[str, ...]:
    """No request or environment variable can select the executable or source."""
    return (
        str(_EXECUTABLE),
        "--startup-file=no",
        "--history-file=no",
        "--threads=1",
        "--compiled-modules=no",
        "--pkgimages=no",
        f"--project={_SOURCE}",
        str(_SOURCE / "burgers.jl"),
    )


def execute_in_worker(
    request: JuliaBurgersRequest,
    *,
    deadline_seconds: float,
    cancelled: Callable[[], bool] | None = None,
) -> JuliaBurgersResult:
    """Bound one fixed subprocess inside an ALREADY admitted Linux worker.

    The caller's external worker watchdog and accounting must include this
    deadline, Julia startup/compilation and cleanup. This process-group cleanup
    is engineering supervision, not isolation from hostile scripts.
    """
    if (
        type(request) is not JuliaBurgersRequest
        or not _float(deadline_seconds)
        or not 0.0 < deadline_seconds <= 600.0
    ):
        raise JuliaFailure(JuliaFailureCode.INVALID)
    encoded = request.encode()
    if sys.platform != "linux" or not _EXECUTABLE.is_file():
        raise JuliaFailure(JuliaFailureCode.UNAVAILABLE)
    started = time.monotonic()
    if cancelled is not None and cancelled():
        raise JuliaFailure(JuliaFailureCode.CANCELLED)
    # Do not inherit provider credentials, JULIA_* hooks, PATH, or user depots.
    env = {
        "HOME": "/nonexistent",
        "JULIA_LOAD_PATH": "@stdlib",
        "JULIA_DEPOT_PATH": "/nonexistent/carbon-julia-depot",
        "JULIA_PKG_OFFLINE": "true",
        "JULIA_PKG_SERVER": "",
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "LANG": "C",
    }
    blocks: list[bytes] = []
    exceeded = threading.Event()
    reader_failed = threading.Event()
    with tempfile.TemporaryFile() as input_file:
        input_file.write(encoded)
        input_file.seek(0)
        try:
            process = subprocess.Popen(
                worker_command(),
                stdin=input_file,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=env,
                cwd=_SOURCE,
                start_new_session=True,
                close_fds=True,
            )
        except OSError:
            raise JuliaFailure(JuliaFailureCode.UNAVAILABLE) from None

        def read_output() -> None:
            try:
                body = process.stdout.read(MAX_OUTPUT_BYTES + 1)
                blocks.append(body)
                if len(body) > MAX_OUTPUT_BYTES:
                    exceeded.set()
            except OSError:
                reader_failed.set()

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        try:
            while process.poll() is None:
                if exceeded.is_set():
                    raise JuliaFailure(JuliaFailureCode.OUTPUT_LIMIT)
                if cancelled is not None and cancelled():
                    raise JuliaFailure(JuliaFailureCode.CANCELLED)
                remaining = deadline_seconds - (time.monotonic() - started)
                if remaining <= 0.0:
                    raise JuliaFailure(JuliaFailureCode.DEADLINE)
                time.sleep(min(remaining, 0.02))
            reader.join(
                timeout=max(0.0, deadline_seconds - (time.monotonic() - started))
            )
            if reader.is_alive():
                raise JuliaFailure(JuliaFailureCode.DEADLINE)
            if time.monotonic() - started > deadline_seconds:
                raise JuliaFailure(JuliaFailureCode.DEADLINE)
            if exceeded.is_set():
                raise JuliaFailure(JuliaFailureCode.OUTPUT_LIMIT)
            if reader_failed.is_set() or not blocks:
                raise JuliaFailure(JuliaFailureCode.PROCESS)
            if process.returncode != 0:
                code = {
                    20: JuliaFailureCode.INVALID,
                    21: JuliaFailureCode.ENVIRONMENT,
                    22: JuliaFailureCode.NUMERICAL,
                }.get(process.returncode, JuliaFailureCode.PROCESS)
                raise JuliaFailure(code)
            return decode_result(blocks[0], request)
        finally:
            # Kill descendants as well, even when the parent already exited.
            cleanup_failed = False
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError:
                cleanup_failed = True
            try:
                process.wait(timeout=5)
                reader.join(timeout=5)
            except subprocess.TimeoutExpired:
                raise JuliaFailure(JuliaFailureCode.CLEANUP) from None
            if reader.is_alive() or cleanup_failed:
                raise JuliaFailure(JuliaFailureCode.CLEANUP)
            process.stdout.close()
