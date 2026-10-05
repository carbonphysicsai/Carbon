"""The `graphite_practice` pod phase: one proposal, trained and predicted on a pod.

Runs on the pod, from the hash-pinned code ship (`bootstrap.py` verified every
file against its sha256 before anything was imported), as

    python -m scripts.dev.exam_design.runner graphite_practice --out OUT

with its configuration in `PHASE_CONFIG` (`pods.PodJob.config`). It does what
a miner's practice trial does, with Carbon's own code:

0. **probes the GPU backend before any candidate code**
   (`probe_environment`, GRAPHITE-POD-GPU-PROBE-01): Carbon's own probe
   initialises JAX in a child of the same interpreter, with the same flags,
   working-directory shape and environment (`JAX_PLATFORMS` included) the
   program gets (`_python` runs both), and writes its result from that
   process. A failed probe claims stage `environment` and nothing else runs:
   the strategy is not compiled and the program never starts. The probe's
   record goes into the supervisor report (`supervisor.json`,
   `pod_outcome.SUPERVISOR_SCHEMA`), which this phase rewrites at every
   stage, before and after the program;
1. compiles the strategy against its Challenge's recorded construction
   contract and builds the exact staged files of a practice trial, through
   that Challenge's `ChallengeScoring.built_record`. At a development level
   the job names a registered development-only variant
   (`development_variant`), and the strategy compiles through that variant's
   own path (`development_variants.compile_development`) instead;
2. **refuses to run** unless the staged files and the program are exactly the
   ones Carbon pinned before launch (`expected`);
3. runs the Challenge's fixed practice program in a fresh directory, bounded
   by the contract's worker deadline;
4. writes `built.json` (what was built: the recipe document and every digest),
   the program's `predictions.json`, `fit.json` and `runtime.json`, and
   `DONE.json`.

No label reaches the program, nothing is scored here, and the pod holds no
key. Carbon scores on its own host after fetching the files.

`failure.json` names the stage that failed. The program runs under this
process's own user and can reach this directory, so Carbon's host treats the
file as evidence only and types the outcome from its own observations
(`pod_outcome`, OWNER-GRAPHITE-TEST-WAVE-02 §3). The supervisor report is
written by this phase too, under the same uid, so until an image separates
the two (`pod_outcome.SEPARATED_IMAGES`) it is evidence as well; after the
program ends, this phase rewrites both files from its own memory.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .pod_outcome import ENVIRONMENT, SUPERVISOR_SCHEMA

OUTPUTS = ("predictions.json", "fit.json", "runtime.json")
PROBE_SCHEMA = "carbon.graphite.gpu-probe.v1"
#: Engineering allowance for the probe (GRAPHITE-POD-GPU-PROBE-01): JAX's
#: import and backend initialisation take seconds; a hang is an environment
#: failure, never the candidate's, and stays inside the pod's start-up
#: allowance (`pods.STARTUP_MINUTES`).
PROBE_SECONDS = 180
#: The phase's exit for a failed probe (compile 2, verification 3, timeout 4,
#: program 5).
EXIT_ENVIRONMENT = 6
#: Carbon's GPU probe, run as `python -I -c PROBE <result path>`. It
#: initialises the backends `JAX_PLATFORMS` names, as the program will; when
#: they name a GPU platform it requires a GPU device and a small computation
#: on it. It writes its result from its own process and re-raises a failure,
#: so the traceback reaches the phase log.
PROBE = r"""
import json, os, sys
result = {"ok": False, "jax_platforms": os.environ.get("JAX_PLATFORMS")}
platforms = [p.strip() for p in (result["jax_platforms"] or "").split(",")]
result["requires_gpu"] = any(p in ("cuda", "gpu") for p in platforms)


def done():
    with open(sys.argv[1], "w") as stream:
        json.dump(result, stream)


try:
    import jax

    result["jax"] = jax.__version__
    devices = jax.devices()
    result["backend"] = jax.default_backend()
    if result["requires_gpu"]:
        devices = jax.devices("gpu")
    result["devices"] = [
        {"platform": d.platform, "kind": d.device_kind} for d in devices[:16]
    ]
    x = jax.device_put(jax.numpy.arange(8.0), devices[0])
    result["checksum"] = float((x * 2.0).sum().block_until_ready())
    result["ok"] = (
        bool(devices)
        and result["checksum"] == 56.0
        and (not result["requires_gpu"] or result["backend"] == "gpu")
    )
except BaseException as error:
    result["error_type"] = type(error).__name__
    done()
    raise
done()
"""
#: What the probe record keeps of the probe's own result: short typed values.
_PROBE_FIELDS = {
    "jax_platforms": str,
    "requires_gpu": bool,
    "jax": str,
    "backend": str,
    "error_type": str,
}


def _write(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True))


def _python(code, args, *, cwd, stdout, timeout):
    """One child of this interpreter, isolated (`-I`), in `cwd`, with this
    process's environment. The probe and the program both run through it, so
    the probe initialises JAX exactly as the program will."""
    return subprocess.run(
        [sys.executable, "-I", "-c", code, *args],
        cwd=cwd,
        stdout=stdout,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    ).returncode


def _probe_result(path):
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}
    return value if type(value) is dict else {}


def probe_environment(code=None):
    """Run Carbon's GPU probe (`PROBE`, or `code`) before any candidate code
    and return its record: `ok` only when the probe's own process exited 0
    and reported success. Its output goes to this phase's log."""
    code = PROBE if code is None else code
    started = time.monotonic()
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory) / "work"
        work.mkdir()
        target = Path(directory) / "probe.json"
        try:
            exit_code = _python(
                code, [str(target)], cwd=work, stdout=None, timeout=PROBE_SECONDS
            )
            result = _probe_result(target)
        except subprocess.TimeoutExpired:
            exit_code, result = None, {"error_type": "ProbeTimeout"}
    record = {
        "schema": PROBE_SCHEMA,
        "before_program": True,
        "exit": exit_code,
        "seconds": round(time.monotonic() - started, 1),
        "ok": exit_code == 0 and result.get("ok") is True,
    }
    for key, kind in _PROBE_FIELDS.items():
        value = result.get(key)
        if type(value) is kind and (kind is not str or len(value) <= 64):
            record[key] = value
    devices = result.get("devices")
    if type(devices) is list:
        record["devices"] = [
            {k: str(d.get(k))[:64] for k in ("platform", "kind")}
            for d in devices[:16]
            if type(d) is dict
        ]
    if not record["ok"] and "error_type" not in record:
        record["error_type"] = "no_usable_device"
    return record


def _report(out, probe, *, stage, program_started):
    """The supervisor report: the probe's record and the failed stage, if
    any. Rewritten from this phase's memory at every stage."""
    _write(
        Path(out) / "supervisor.json",
        {
            "schema": SUPERVISOR_SCHEMA,
            "stage": stage,
            "probe": probe,
            "program_started": program_started,
        },
    )


def built_record(strategy, contract_digest, seed, root=".", scoring=None):
    """What Carbon builds for `strategy`: the compiled recipe, the staged
    files' digests and the program's digest, from the Challenge's own
    `ChallengeScoring.built_record`. Used on the pod and, for the independent
    rebuild, on Carbon's host. With no scoring named, the strategy's own
    Challenge serves."""
    from carbon.challenge_validator import scoring as challenge_scoring

    if scoring is None:
        named = strategy.get("challenge_id") if type(strategy) is dict else None
        scoring = challenge_scoring.scoring_for(named)
    return scoring.built_record(strategy, contract_digest, seed, root)


def development_built_record(strategy, contract_digest, variant_digest, seed, root="."):
    """What Carbon builds for `strategy` under a registered development-only
    variant (a development level, Graphite only): the variant's own compile
    path, never `compile_submission`. The job's contract digest must be the
    variant's base."""
    from carbon.reconstruction import development_variants

    found = development_variants.registered(variant_digest)
    if contract_digest != found.base_contract_digest:
        raise development_variants.VariantRefused(
            development_variants.BASE_STALE, "the job names another base contract"
        )
    return development_variants.built_record(strategy, variant_digest, seed, root)


def pinned(record, expected):
    """The staged files and program are exactly the ones Carbon pinned."""
    return (
        record["staged"] == expected["files"]
        and record["program"] == expected["program"]
    )


def run(cfg, out, *, root=".", probe=None):
    """`probe` replaces Carbon's probe code (tests only); None runs `PROBE`."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    # Before any candidate code: the strategy is not even compiled yet.
    checked = probe_environment(probe)
    if not checked["ok"]:
        _report(out, checked, stage=ENVIRONMENT, program_started=False)
        _write(
            out / "failure.json",
            {"stage": ENVIRONMENT, "error": checked["error_type"]},
        )
        return EXIT_ENVIRONMENT
    _report(out, checked, stage=None, program_started=False)
    try:
        if "development_variant" in cfg:
            record, files, program = development_built_record(
                cfg["strategy"],
                cfg["contract_digest"],
                cfg["development_variant"],
                cfg["seed"],
                root,
            )
        else:
            record, files, program = built_record(
                cfg["strategy"], cfg["contract_digest"], cfg["seed"], root
            )
    except Exception as failure:  # noqa: BLE001 -- typed, never echoed
        _report(out, checked, stage="compile", program_started=False)
        _write(
            out / "failure.json", {"stage": "compile", "error": type(failure).__name__}
        )
        return 2
    _write(out / "built.json", record)
    if not pinned(record, cfg["expected"]):
        _report(out, checked, stage="verification", program_started=False)
        _write(out / "failure.json", {"stage": "verification", "error": "digest"})
        return 3
    _report(out, checked, stage=None, program_started=True)
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory) / "work"
        output = Path(directory) / "output"
        work.mkdir()
        output.mkdir()
        for name, body in files.items():
            (work / name).write_bytes(body)
        try:
            with open(out / "program.log", "wb") as log:
                code = _python(
                    program, [], cwd=work, stdout=log, timeout=int(cfg["seconds"])
                )
        except subprocess.TimeoutExpired:
            _ended(out, checked, "timeout", "deadline")
            return 4
        for name in OUTPUTS:
            if (output / name).is_file():
                shutil.copyfile(output / name, out / name)
    if code != 0:
        _ended(out, checked, "program", f"exit {code}")
        return 5
    _ended(out, checked, None, None)
    _write(out / "DONE.json", {"phase": "graphite_practice", "exit": 0})
    return 0


def _ended(out, checked, stage, error):
    """After the program: this phase's own claim and report, rewritten from
    its memory, so nothing the program left in `out` names a stage (an
    `environment` claim in particular) in this phase's place."""
    _report(out, checked, stage=stage, program_started=True)
    failure = Path(out) / "failure.json"
    if stage is None:
        failure.unlink(missing_ok=True)
    else:
        _write(failure, {"stage": stage, "error": error})
