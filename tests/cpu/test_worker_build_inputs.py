"""The worker image's source digest is scoped to its real build inputs (IMAGE_DIGEST_SCOPE_AND_M9PRIME_RULING_20261029).

One set of paths, one digest function; every Dockerfile COPY source is inside the set (a COPY outside it fails here);
a change outside the set does not move the digest, a change inside does; no verifier still hashes the whole tree.
"""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from carbon.reconstruction.worker import build_inputs

ROOT = Path(__file__).resolve().parents[2]
RULED_SET = (
    "pyproject.toml",
    "uv.lock",
    "README.md",
    "carbon",
    ".devcontainer/Dockerfile.reconstruction-worker",
    ".devcontainer/worker-native-mesh.lock",
    ".devcontainer/install-worker-native-mesh.sh",
    ".devcontainer/accelerators",
    ".devcontainer/torch",
)
DOCKERFILES = (
    ".devcontainer/Dockerfile.reconstruction-worker",
    ".devcontainer/accelerators/Dockerfile",
    ".devcontainer/torch/Dockerfile",
    ".devcontainer/torch/Dockerfile.gpu",
)


def _inside(path: str, inputs) -> bool:
    path = path.removeprefix("./").rstrip("/")
    return any(path == item or path.startswith(item + "/") for item in inputs)


def test_the_set_is_exactly_the_ruled_one():
    assert build_inputs.paths() == RULED_SET
    assert build_inputs.BUILD_SCHEMA == "carbon.c03.worker-image-build.v2"
    # the set file is itself an input (it lives in carbon/), so changing the set moves every image id
    assert _inside(build_inputs.INPUTS_FILE_IN_REPO, RULED_SET)
    assert (ROOT / build_inputs.INPUTS_FILE_IN_REPO).is_file()


def _copy_sources(text: str):
    """The COPY/ADD sources of a Dockerfile (not --from=, not URLs), with line continuations joined."""
    sources = []
    for line in re.sub(r"\\\n", " ", text).splitlines():
        words = shlex.split(line, comments=True) if line.strip() else []
        if not words or words[0].upper() not in ("COPY", "ADD"):
            continue
        flags = [w for w in words[1:] if w.startswith("--")]
        args = [w for w in words[1:] if not w.startswith("--")]
        if any(f.startswith("--from=") for f in flags):
            continue
        sources += [a for a in args[:-1] if not re.match(r"^[a-z]+://", a)]
    return sources


@pytest.mark.parametrize("dockerfile", DOCKERFILES)
def test_every_dockerfile_copy_source_is_inside_the_build_inputs(dockerfile):
    sources = _copy_sources((ROOT / dockerfile).read_text(encoding="utf-8"))
    assert sources, dockerfile  # each of these builds copies something from the context
    outside = [s for s in sources if not _inside(s, RULED_SET)]
    assert outside == [], f"{dockerfile} COPYs {outside} outside build_inputs.txt"
    # and the Dockerfile itself is an input (its recipe digest is also baked, but the set must show it)
    assert _inside(dockerfile, RULED_SET)


def test_the_copy_parser_sees_a_stray_copy():
    text = "FROM x\nCOPY --from=uv /uv /bin/uv\nCOPY a b ./\nCOPY scripts/dev/x.sh /x\nADD https://e.org/f /f\n"
    assert _copy_sources(text) == ["a", "b", "scripts/dev/x.sh"]


def test_the_wheel_only_packages_carbon():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    setuptools = project["tool"]["setuptools"]
    assert setuptools["packages"]["find"]["include"] == ["carbon*"]
    tops = {name.split(".")[0] for name in setuptools.get("package-data", {})}
    # `carbon_miner_signer` is a separate top-level package: no worker Dockerfile copies it (it is outside the set),
    # so it is not in the worker image's build context. Anything else would be a new package in the wheel.
    assert tops <= {"carbon", "carbon_miner_signer"}, tops
    assert not _inside("carbon_miner_signer", RULED_SET)
    copied = _copy_sources(
        (ROOT / ".devcontainer/Dockerfile.reconstruction-worker").read_text(
            encoding="utf-8"
        )
    )
    assert "carbon_miner_signer" not in copied


def test_the_dockerfile_writes_the_v2_build_schema_and_the_runtime_checks_it():
    from carbon.compute import remote_container

    text = (ROOT / ".devcontainer/Dockerfile.reconstruction-worker").read_text(
        encoding="utf-8"
    )
    assert build_inputs.BUILD_SCHEMA in text
    assert "worker-image-build.v1" not in text
    assert remote_container.BUILD_SCHEMA == build_inputs.BUILD_SCHEMA


def _git(repo, *args):
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    for path in build_inputs.paths():
        target = repo / path
        if "." in Path(path).name:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(path + "\n")
        else:
            target.mkdir(parents=True, exist_ok=True)
            (target / "f.txt").write_text(path + "\n")
    inputs = repo / build_inputs.INPUTS_FILE_IN_REPO
    inputs.parent.mkdir(parents=True, exist_ok=True)
    inputs.write_text((ROOT / build_inputs.INPUTS_FILE_IN_REPO).read_text())
    for outside in ("scripts/a.sh", "docs/x.md", "tests/t.py", "codex-queue/q.md"):
        (repo / outside).parent.mkdir(parents=True, exist_ok=True)
        (repo / outside).write_text(outside + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


def _commit(repo, path, text):
    (repo / path).write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "change " + path)


def test_a_change_outside_the_inputs_does_not_move_the_digest_and_one_inside_does(
    tmp_path,
):
    repo = _repo(tmp_path)
    base = build_inputs.digest(repo)
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", base)
    for outside in ("scripts/a.sh", "docs/x.md", "tests/t.py", "codex-queue/q.md"):
        _commit(repo, outside, "changed\n")
        assert build_inputs.digest(repo) == base, outside
    for inside in (
        "README.md",
        "uv.lock",
        "carbon/f.txt",
        ".devcontainer/torch/f.txt",
        ".devcontainer/accelerators/f.txt",
        ".devcontainer/worker-native-mesh.lock",
    ):
        before = build_inputs.digest(repo)
        _commit(repo, inside, "changed\n")
        assert build_inputs.digest(repo) != before, inside


def test_changing_the_set_itself_moves_the_digest(tmp_path):
    repo = _repo(tmp_path)
    before = build_inputs.digest(repo)
    inputs = repo / build_inputs.INPUTS_FILE_IN_REPO
    _commit(repo, build_inputs.INPUTS_FILE_IN_REPO, inputs.read_text() + "docs\n")
    assert build_inputs.digest(repo) != before


def test_shell_scripts_read_the_same_set_and_digest_through_the_program(tmp_path):
    program = ROOT / build_inputs.INPUTS_FILE_IN_REPO.replace(".txt", ".py")
    listed = subprocess.run(
        [sys.executable, "-I", str(program), "paths"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert tuple(listed) == build_inputs.paths()
    repo = _repo(tmp_path)
    printed = subprocess.run(
        [sys.executable, "-I", str(program), "digest", str(repo)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert printed == build_inputs.digest(repo)


def test_a_malformed_set_is_refused(tmp_path):
    for body in ("", "# only a comment\n", "a\na\n", "/abs\n", "../up\n", "a/../b\n"):
        path = tmp_path / "set.txt"
        path.write_text(body)
        with pytest.raises(ValueError):
            build_inputs.paths(path)


WHOLE_TREE_ARCHIVE = re.compile(r"archive[^\n|]*--format=tar[^\n|]*\bHEAD\b(?! --)")


def test_no_verifier_still_hashes_the_whole_tree():
    """Every place that recomputed `git archive HEAD` of the whole repository now uses the build-inputs digest."""
    offenders = []
    for folder, patterns in (
        ("carbon", ("*.py",)),
        ("scripts", ("*.py", "*.sh")),
        (".github", ("*.yml", "*.yaml")),
    ):
        for pattern in patterns:
            for path in (ROOT / folder).rglob(pattern):
                text = path.read_text(encoding="utf-8", errors="replace")
                if "archive" not in text:
                    continue
                if WHOLE_TREE_ARCHIVE.search(text) or re.search(
                    r'"archive", "--format=tar", "HEAD"\]', text
                ):
                    offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], offenders
    build_script = (ROOT / "scripts/dev/c03_worker_image.sh").read_text()
    assert "build_inputs.py" in build_script
    campaign = (ROOT / "carbon/development_session/research_campaign.py").read_text()
    assert campaign.count("build_inputs.digest(") == 2


def test_the_installers_shell_digest_equals_the_python_digest(tmp_path):
    """install_miner.sh computes the digest in plain shell (no interpreter before the environment exists): the same
    bytes build_inputs.py hashes."""
    import shutil

    if shutil.which("bash") is None or shutil.which("sha256sum") is None:
        pytest.skip("needs bash and sha256sum")
    text = (ROOT / "scripts/install_miner.sh").read_text(encoding="utf-8")
    start = text.index('build_inputs="$(git show HEAD:')
    end = text.index('source_digest="sha256:$(git ls-tree', start)
    end = text.index("\n", end) + 1
    snippet = text[start:end]
    repo = _repo(tmp_path)
    script = (
        'set -euo pipefail\nfail() { echo "$*" >&2; exit 2; }\n'
        + snippet.replace("  ", "", 1)
        + 'printf "%s" "${source_digest}"\n'
    )
    done = subprocess.run(
        ["bash", "-c", script],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert done.stdout == build_inputs.digest(repo)


def test_a_build_input_that_matches_nothing_is_refused_not_just_all_of_them(tmp_path):
    repo = _repo(tmp_path)
    assert build_inputs.digest(repo)  # all present
    _git(repo, "rm", "-r", "-q", ".devcontainer/torch")
    _git(repo, "commit", "-q", "-m", "drop one input")
    with pytest.raises(ValueError, match=r"missing.*\.devcontainer/torch"):
        build_inputs.digest(repo)


def test_the_installers_shell_digest_refuses_a_missing_input_too(tmp_path):
    import shutil

    if shutil.which("bash") is None or shutil.which("sha256sum") is None:
        pytest.skip("needs bash and sha256sum")
    text = (ROOT / "scripts/install_miner.sh").read_text(encoding="utf-8")
    start = text.index('build_inputs="$(git show HEAD:')
    end = text.index('source_digest="sha256:$(git ls-tree', start)
    end = text.index("\n", end) + 1
    repo = _repo(tmp_path)
    _git(repo, "rm", "-r", "-q", ".devcontainer/torch")
    _git(repo, "commit", "-q", "-m", "drop one input")
    script = 'set -euo pipefail\nfail() { echo "$*" >&2; exit 2; }\n' + text[
        start:end
    ].replace("  ", "", 1)
    done = subprocess.run(
        ["bash", "-c", script], cwd=repo, capture_output=True, text=True, check=False
    )
    assert done.returncode == 2 and "build input missing" in done.stderr


def test_git_ignored_files_under_the_inputs_are_found_and_refused(tmp_path):
    repo = _repo(tmp_path)
    assert build_inputs.ignored_files(repo) == []
    (repo / ".gitignore").write_text("*.so\n__pycache__/\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-q", "-m", "ignore")
    (repo / "carbon" / "native.so").write_bytes(b"x")  # inside the inputs, ignored
    (repo / "scripts" / "tool.so").write_bytes(b"y")  # ignored but outside the inputs
    assert build_inputs.ignored_files(repo) == ["carbon/native.so"]
    program = ROOT / build_inputs.INPUTS_FILE_IN_REPO.replace(".txt", ".py")
    done = subprocess.run(
        [sys.executable, "-I", str(program), "ignored", str(repo)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 1 and done.stdout.strip() == "carbon/native.so"
    (repo / "carbon" / "native.so").unlink()
    done = subprocess.run(
        [sys.executable, "-I", str(program), "ignored", str(repo)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0 and done.stdout.strip() == ""


def test_the_image_build_script_refuses_ignored_inputs_before_the_digest():
    text = (ROOT / "scripts/dev/c03_worker_image.sh").read_text(encoding="utf-8")
    assert text.index('build_inputs.py" ignored') < text.index(
        'build_inputs.py" digest'
    )
    assert "unbound by its digest" in text
