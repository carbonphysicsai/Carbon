"""Offline Graphite CI sizing, including the declared L4 transport budget.

Only public tracked source and public DEVELOPMENT scoring paths are used.
No provider, credentials, training, or submission execution is involved.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import inspect
import json
import platform
import subprocess
from pathlib import Path

from .pod_env import ENV_LIMIT_CHARS, env_chars, largest_variable

# Preserve the existing test_graphite_pod_env_size reserve (PLT-29 authority).
CI_RESERVE_CHARS = 8_000
HISTORY_REF = "97037df6d3bb76d81372fa22280322234c4fc2cc"
REPOSITORY = Path(__file__).resolve().parents[4]


def measurement(env):
    """Counts only: never return a configuration, credential, or manifest."""
    values = dict(env)
    total = env_chars(values)
    carrier = values.get("CODE_MANIFEST_GZ_B64")
    return {
        "total_chars": total,
        "limit_chars": ENV_LIMIT_CHARS,
        "reserve_chars": CI_RESERVE_CHARS,
        "ci_limit_chars": ENV_LIMIT_CHARS - CI_RESERVE_CHARS,
        "headroom_chars": ENV_LIMIT_CHARS - total,
        "largest_variable": largest_variable(values) if values else None,
        "manifest_carrier_chars": len(
            carrier if carrier is not None else values.get("CODE_MANIFEST", "")
        ),
        "manifest_compressed_bytes": (
            len(base64.b64decode(carrier, validate=True)) if carrier else None
        ),
        "phase_config_chars": len(values.get("PHASE_CONFIG", "")),
        "status": ("PASS" if total < ENV_LIMIT_CHARS - CI_RESERVE_CHARS else "FAIL"),
    }


def failure_detail(result):
    return (
        "pod_environment_ci_headroom: "
        f"{result['total_chars']} characters; CI requires under "
        f"{result['ci_limit_chars']} (limit {result['limit_chars']}, "
        f"reserve {result['reserve_chars']}); largest variable "
        f"{result['largest_variable']}"
    )


def _commit(ref, repository):
    return subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "--verify", f"{ref}^{{commit}}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def profiles(ref="HEAD", *, repository=REPOSITORY):
    """The same current factory applied to one public Git source snapshot."""
    from carbon.agent_campaign.graphite import pod_phase, pods
    from carbon.battery.research import SCAFFOLD
    from carbon.challenge_validator import scoring as challenge_scoring

    from . import pod_control

    repository = Path(repository)
    commit = _commit(ref, repository)
    scoring = challenge_scoring.scoring_for(SCAFFOLD["challenge_id"])
    paths = pods.ship_list(commit, repository, scoring)
    manifest = pods.code_manifest(commit, paths, repository)
    backend = object.__new__(pods.RunPodPods)
    backend.code_ref, backend.manifest = commit, manifest
    backend.economics = pods.prices()
    record = {"token": "t" * 32, "deadline_at": 1_001_800}
    results = []
    for execution_backend in ("jax", "pytorch"):
        for profile in ("small", "l4-transport-budget"):
            job = pods.PodJob(
                "environment-ci",
                SCAFFOLD,
                "sha256:" + "0" * 64,
                7,
                {"files": {}},
                30,
                600,
                backend=execution_backend,
                # Sizing only: not a valid graph and never decoded/executed.
                level4_envelope=(
                    "A" * pod_phase.LEVEL4_TRANSPORT_CHARS
                    if profile == "l4-transport-budget"
                    else None
                ),
            )
            result = measurement(backend._env(job, record))
            result.update(profile=profile, backend=execution_backend)
            results.append(result)
    ca_roots_present = sum(
        Path(f"/etc/ssl/certs/{name}.pem").is_file() for name in pod_control.CA_ROOTS
    )
    recipe = (
        "\n".join(
            inspect.getsource(function)
            for function in (
                pods.ship_list,
                pods.code_manifest,
                pods.RunPodPods._env,
                pods.PodJob.config,
                pods._ca_bundle,
                pod_control.manifest_env,
            )
        ).encode()
        + Path(__file__).read_bytes()
    )
    return {
        "schema": "carbon.graphite.environment-ci.v1",
        "source_ref": commit,
        "measurement_recipe": "frozen-current-builder-and-codec",
        "factory_source_sha256": hashlib.sha256(recipe).hexdigest(),
        "host_system": platform.system(),
        "ca_roots_present": ca_roots_present,
        "ca_roots_configured": len(pod_control.CA_ROOTS),
        # The existing factory intentionally skips absent roots. An empty
        # Windows CA bundle is incomplete; not every optional root is required.
        "complete_environment": ca_roots_present > 0,
        "shipped_files": len(manifest),
        "manifest_json_bytes": len(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ),
        "profiles": results,
    }, manifest


def compare(base, head, base_manifest, head_manifest):
    """Aggregate source deltas under one recipe; no paths/digests disclosed."""
    same_fields = (
        "measurement_recipe",
        "factory_source_sha256",
        "host_system",
        "ca_roots_present",
        "ca_roots_configured",
    )
    if any(base[field] != head[field] for field in same_fields):
        raise ValueError("pod_environment_comparison_recipe_differs")
    for old, new in zip(base["profiles"], head["profiles"], strict=True):
        if any(
            old[field] != new[field]
            for field in ("profile", "backend", "phase_config_chars")
        ):
            raise ValueError("pod_environment_comparison_job_differs")
    before, after = set(base_manifest), set(head_manifest)
    return {
        "base_source_ref": base["source_ref"],
        "head_source_ref": head["source_ref"],
        "comparison_basis": "historical sources under one frozen current recipe",
        "added_files": len(after - before),
        "added_python_files": sum(path.endswith(".py") for path in after - before),
        "added_nonpython_files": sum(
            not path.endswith(".py") for path in after - before
        ),
        "removed_files": len(before - after),
        "changed_files": sum(
            base_manifest[path] != head_manifest[path] for path in before & after
        ),
        "shipped_file_delta": head["shipped_files"] - base["shipped_files"],
        "manifest_json_byte_delta": (
            head["manifest_json_bytes"] - base["manifest_json_bytes"]
        ),
        "profile_char_deltas": [
            {
                "profile": new["profile"],
                "backend": new["backend"],
                "total_char_delta": new["total_chars"] - old["total_chars"],
                "manifest_carrier_char_delta": (
                    new["manifest_carrier_chars"] - old["manifest_carrier_chars"]
                ),
            }
            for old, new in zip(base["profiles"], head["profiles"], strict=True)
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--base-ref", help="Optional public source ref for comparison.")
    args = parser.parse_args(argv)
    current, manifest = profiles(args.ref)
    result = {"current": current}
    if args.base_ref:
        old, old_manifest = profiles(args.base_ref)
        result["baseline"] = old
        result["comparison"] = compare(old, current, old_manifest, manifest)
    print(json.dumps(result, sort_keys=True))
    return int(
        not current["complete_environment"]
        or any(row["status"] != "PASS" for row in current["profiles"])
    )


if __name__ == "__main__":
    raise SystemExit(main())
