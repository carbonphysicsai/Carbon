"""The release workflow for the worker images (IMAGE-RELEASE-01), held statically.

The workflow cannot run here (it builds and pushes images), so its contract is
read from the file:
- manual dispatch with a release tag only: never a pull request or a push;
- no default token permissions; each job holds only what it needs (packages
  write to push, packages read to pull, contents write only to attach assets);
- every action pinned by full commit SHA;
- the token reaches a step only through its environment, never a command line,
  and is passed to `docker login` on stdin;
- it checks out the exact tag, requires it on main, builds with the existing
  scripts through `release_worker_images.sh`, tests the pushed digests after
  the push, and attaches without overwriting;
- every `run` block is valid bash.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

REPOSITORY = Path(__file__).resolve().parents[2]
WORKFLOW = REPOSITORY / ".github" / "workflows" / "release-worker-images.yml"
SCRIPT = REPOSITORY / "scripts" / "dev" / "release_worker_images.sh"


def load():
    return yaml.safe_load(WORKFLOW.read_text())


def steps(job):
    return load()["jobs"][job]["steps"]


def test_it_runs_only_on_manual_dispatch_with_a_release_tag():
    triggers = load()[True]  # YAML 1.1 reads the `on` key as True
    assert set(triggers) == {"workflow_dispatch"}
    assert triggers["workflow_dispatch"]["inputs"]["tag"]["required"] is True


def test_every_job_holds_least_privilege():
    workflow = load()
    assert workflow["permissions"] == {}
    assert {name: job["permissions"] for name, job in workflow["jobs"].items()} == {
        "build": {"contents": "read", "packages": "write"},
        "capability": {"contents": "read", "packages": "read"},
        "publish": {"contents": "write"},
    }


def test_every_action_is_pinned_by_full_commit_sha():
    for job in load()["jobs"].values():
        for step in job["steps"]:
            if "uses" in step:
                assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", step["uses"]), step


def test_the_token_reaches_steps_only_through_their_environment():
    text = WORKFLOW.read_text()
    assert set(re.findall(r"secrets\.(\w+)", text)) == {"GITHUB_TOKEN"}
    for job in load()["jobs"].values():
        for step in job["steps"]:
            assert "secrets." not in step.get("run", ""), step["name"]
            if "docker login" in step.get("run", ""):
                assert "--password-stdin" in step["run"]
                assert "set -x" not in step["run"]


def test_it_builds_the_exact_tag_with_the_existing_scripts_then_tests_the_push():
    build = steps("build")
    checkout = next(
        s for s in build if s.get("uses", "").startswith("actions/checkout@")
    )
    assert checkout["with"]["ref"] == "refs/tags/${{ inputs.tag }}"
    assert checkout["with"]["persist-credentials"] is False
    runs = "\n".join(s.get("run", "") for s in build)
    assert "git merge-base --is-ancestor" in runs
    assert (
        "./scripts/dev/release_worker_images.sh --registry ghcr.io/carbonphysicsai"
        in runs
    )
    script = SCRIPT.read_text()
    for existing in (
        "c03_worker_image.sh",
        "accelerator_worker_image.sh",
        "torch_worker_image.sh",
        "torch_gpu_worker_image.sh",
    ):
        assert f'bash "${{script_dir}}/{existing}"' in script
    # The capability matrix runs after the push, on the pulled digests.
    workflow = load()
    assert workflow["jobs"]["capability"]["needs"] == "build"
    capability = "\n".join(s.get("run", "") for s in steps("capability"))
    assert "worker_image_release.py pull" in capability
    assert "worker_image_capability.py" in capability
    publish = "\n".join(s.get("run", "") for s in steps("publish"))
    assert "gh release upload" in publish and "--clobber" not in publish
    assert workflow["jobs"]["publish"]["needs"] == ["build", "capability"]


def test_every_run_block_is_valid_bash(tmp_path):
    for name, job in load()["jobs"].items():
        for index, step in enumerate(job["steps"]):
            if "run" not in step:
                continue
            path = tmp_path / f"{name}-{index}.sh"
            path.write_text(step["run"])
            done = subprocess.run(
                ["bash", "-n", str(path)], capture_output=True, text=True, check=False
            )
            assert done.returncode == 0, (step["name"], done.stderr)
    done = subprocess.run(
        ["bash", "-n", str(SCRIPT)], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr


def test_every_released_kind_flows_through_every_job():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "worker_image_release",
        REPOSITORY / "scripts" / "dev" / "worker_image_release.py",
    )
    release = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(release)
    assert set(release.KINDS) == {"c03", "accelerator", "torch", "torch-gpu"}
    workflow = load()
    outputs = workflow["jobs"]["build"]["outputs"]
    text = WORKFLOW.read_text()
    for kind in release.KINDS:
        key = kind.replace("-", "_") + "_record"
        assert key in outputs, key
        assert text.count(f"{kind}-worker-image.release.json") >= 2, kind
    assert text.count("for kind in c03 accelerator torch torch-gpu; do") == 3
    script = SCRIPT.read_text()
    assert "torch-gpu:carbon-torch-gpu-worker" in script
    assert "torch-gpu-parent" in script
