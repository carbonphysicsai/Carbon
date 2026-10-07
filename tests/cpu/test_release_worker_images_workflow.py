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
from types import SimpleNamespace

import pytest
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
    assert set(release.KINDS) == {
        "c03",
        "accelerator",
        "torch",
        "torch-gpu",
        "analysis",
    }
    workflow = load()
    outputs = workflow["jobs"]["build"]["outputs"]
    text = WORKFLOW.read_text()
    for kind in release.KINDS:
        key = kind.replace("-", "_") + "_record"
        assert key in outputs, key
        assert text.count(f"{kind}-worker-image.release.json") >= 2, kind
    assert text.count("for kind in c03 accelerator torch torch-gpu analysis; do") == 3
    script = SCRIPT.read_text()
    assert "torch-gpu:carbon-torch-gpu-worker" in script
    assert "torch-gpu-parent" in script


PARENT_REF = REPOSITORY / "scripts" / "dev" / "worker_parent_ref.sh"
PARENT_ID = "sha256:" + "5c" * 32
SOURCE = "sha256:" + "f07e01414c6600f0" + "0" * 48
CHILDREN = (
    "accelerator_worker_image.sh",
    "torch_worker_image.sh",
    "torch_gpu_worker_image.sh",
    "tpu_worker_image.sh",
)


def parent_ref(*args, repository=None):
    env = {"PATH": "/usr/bin:/bin"}
    if repository is not None:
        env["CARBON_WORKER_PARENT_REPOSITORY"] = repository
    return subprocess.run(
        ["bash", str(PARENT_REF), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_a_local_build_names_the_parent_in_the_local_store():
    done = parent_ref(PARENT_ID, SOURCE)
    assert done.returncode == 0
    assert done.stdout == f"carbon-c03-worker:f07e01414c6600f0@{PARENT_ID}\n"


def test_a_release_builds_on_the_pushed_parent_by_registry_digest():
    """Run 37530387660: the runner's builder resolved the local
    `carbon-c03-worker:<tag>@<id>` on Docker Hub. A release names the pushed
    parent, `<registry>/carbon-c03-worker@<id>`, with no tag."""
    repository = "ghcr.io/carbonphysicsai/carbon-c03-worker"
    done = parent_ref(PARENT_ID, SOURCE, repository=repository)
    assert done.returncode == 0
    assert done.stdout == f"{repository}@{PARENT_ID}\n"
    assert "docker.io" not in done.stdout


@pytest.mark.parametrize(
    ("args", "repository"),
    [
        ((PARENT_ID, SOURCE), "ghcr.io/carbonphysicsai/carbon-c03-worker:v1"),
        ((PARENT_ID, SOURCE), "ghcr.io/carbonphysicsai/other-worker"),
        ((PARENT_ID, SOURCE), "GHCR.io/carbonphysicsai/carbon-c03-worker"),
        ((PARENT_ID, SOURCE), "carbon-c03-worker"),
        ((PARENT_ID, SOURCE), f"ghcr.io/x/carbon-c03-worker@{PARENT_ID}"),
        (("carbon-c03-worker:latest", SOURCE), None),
        ((PARENT_ID, "sha256:short"), None),
        ((PARENT_ID,), None),
    ],
)
def test_a_malformed_parent_reference_is_refused(args, repository):
    done = parent_ref(*args, repository=repository)
    assert done.returncode == 2 and done.stdout == ""


@pytest.mark.parametrize("child", CHILDREN)
def test_every_c03_child_takes_its_from_reference_from_the_one_helper(child):
    text = (REPOSITORY / "scripts" / "dev" / child).read_text()
    assert (
        'parent_ref="$(bash "${script_dir}/worker_parent_ref.sh" "${parent}" '
        '"${source_digest}")"' in text
    )
    assert "carbon-c03-worker:${source_digest" not in text


def test_the_release_pushes_the_c03_parent_before_building_on_it():
    script = SCRIPT.read_text()
    c03 = script.index('bash "${script_dir}/c03_worker_image.sh"')
    push = script.index('docker push --quiet "${c03_repository}:${tag}"')
    checked = script.index('*" ${c03_repository}@${c03_parent} "*')
    export = script.index('export CARBON_WORKER_PARENT_REPOSITORY="${c03_repository}"')
    first_child = min(
        script.index(f'bash "${{script_dir}}/{child}"') for child in CHILDREN[:3]
    )
    assert c03 < push < checked < export < first_child
    assert 'c03_repository="${registry}/carbon-c03-worker"' in script


class _BuildCLI:
    """The docker CLI the analysis builder sees: records every call."""

    def __init__(self):
        self.calls = []

    def run(self, args, timeout=None):
        self.calls.append(list(args))
        if args[0] == "build":
            return SimpleNamespace(stdout=b"sha256:" + b"b" * 64)
        return SimpleNamespace(stdout=b"")

    def json(self, args):
        self.calls.append(list(args))
        return {"Id": PARENT_ID}


@pytest.fixture
def analysis(tmp_path, monkeypatch):
    from carbon.development_session import research_image

    cli = _BuildCLI()
    parent = SimpleNamespace(image_id=PARENT_ID, source_tree_digest=SOURCE)
    monkeypatch.setattr(research_image, "DockerCLI", lambda: cli)
    monkeypatch.setattr(research_image, "load_image_identity", lambda path: parent)
    monkeypatch.setattr(
        research_image, "doctor", lambda **k: SimpleNamespace(eligible=True)
    )
    monkeypatch.setattr(research_image, "verify_image", lambda image, cli: image)

    def build(**kwargs):
        image = research_image.build_analysis_image(
            tmp_path / "parent.json", tmp_path / "root", **kwargs
        )
        dockerfiles = list((tmp_path / "root").glob("*/*/Dockerfile"))
        assert len(dockerfiles) == 1
        return image, dockerfiles[0].read_text().splitlines()[0], cli.calls

    return build


def test_the_miner_path_keeps_its_checked_local_parent_tag(analysis):
    """install_miner.sh: no repository, so the local tag, checked first."""
    image, first, calls = analysis()
    tag = "carbon-cw1d4-parent:" + PARENT_ID[7:]
    assert first == f"FROM {tag}"
    assert ["tag", PARENT_ID, tag] in calls
    assert image.parent_image == PARENT_ID


def test_a_release_builds_the_analysis_image_on_the_pushed_parent(analysis):
    repository = "ghcr.io/carbonphysicsai/carbon-c03-worker"
    image, first, calls = analysis(parent_repository=repository)
    assert first == f"FROM {repository}@{PARENT_ID}"
    assert not any(call[0] == "tag" for call in calls)
    assert image.parent_image == PARENT_ID


@pytest.mark.parametrize(
    "repository",
    [
        "ghcr.io/carbonphysicsai/carbon-c03-worker:v1",
        "ghcr.io/carbonphysicsai/carbon-miner-analysis",
        "carbon-c03-worker",
    ],
)
def test_a_release_refuses_a_parent_repository_the_helper_refuses(analysis, repository):
    with pytest.raises(ValueError, match="release parent reference refused"):
        analysis(parent_repository=repository)


def test_the_release_passes_the_pushed_parent_to_the_analysis_builder():
    script = SCRIPT.read_text()
    export = script.index('export CARBON_WORKER_PARENT_REPOSITORY="${c03_repository}"')
    passed = script.index('--parent-repository "${c03_repository}"')
    assert export < passed < script.index("analysis_manifest=")
    installer = (REPOSITORY / "scripts" / "install_miner.sh").read_text()
    assert "--parent-repository" not in installer
