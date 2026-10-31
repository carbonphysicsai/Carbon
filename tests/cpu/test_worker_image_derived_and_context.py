"""The worker image carries what the DERIVED images run, and its build context does not depend on the builder.

Two Runner findings on the real build of the narrowed image: the torch child image failed its identity `verify` for want of
`carbon.reconstruction.torch_profile` (the allow-list was built from the C03 entrypoint alone, but the derived images run
carbon code at build time); and a Docker without buildx ignores the Dockerfile-specific `.dockerignore`, so every legacy
host sent the whole checkout and failed the smoke. Both are closed here, and these tests pin them.
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

import pytest

from carbon.reconstruction.worker import image_modules

ROOT = Path(__file__).resolve().parents[2]
DERIVED_DIRS = (ROOT / ".devcontainer/torch", ROOT / ".devcontainer/accelerators")


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


# ---- the derived images' programs are closure roots ------------------------------------------------------------


def test_every_carbon_module_a_derived_image_runs_is_in_the_image():
    """An independent scan (not the generator's own): every dotted `carbon.` name in a derived Dockerfile and every
    carbon import of their identity scripts that is a module must be listed, with its parent packages.
    """
    index = image_modules.module_index(ROOT)
    listed = set(image_modules.listed_modules(ROOT))
    wanted = set()
    for folder in DERIVED_DIRS:
        for dockerfile in folder.glob("Dockerfile*"):
            for name in re.findall(
                r"\bcarbon(?:\.[A-Za-z_][A-Za-z0-9_]*)+", dockerfile.read_text("utf-8")
            ):
                if name in index:
                    wanted.add(name)
    for relative in image_modules.DERIVED_SCRIPTS:
        for node in ast.walk(ast.parse((ROOT / relative).read_text("utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                wanted.update(
                    name
                    for name in (
                        node.module,
                        *(f"{node.module}.{a.name}" for a in node.names),
                    )
                    if name in index
                )
            elif isinstance(node, ast.Import):
                wanted.update(a.name for a in node.names if a.name in index)
    assert (
        "carbon.reconstruction.torch_profile" in wanted
    )  # the module the torch child's verify imports
    assert "carbon.reconstruction.accelerators" in wanted
    assert wanted <= listed, sorted(wanted - listed)
    for name in wanted:
        parts = name.split(".")
        assert {".".join(parts[:i]) for i in range(1, len(parts) + 1)} & set(
            index
        ) <= listed | {"carbon"}


def test_the_closure_of_the_derived_roots_is_inside_the_list():
    index = image_modules.module_index(ROOT)
    roots = image_modules.derived_roots(ROOT, index)
    assert {
        "carbon.reconstruction.torch_profile",
        "carbon.reconstruction.accelerators",
    } <= roots
    closure = image_modules.eager_closure(ROOT, index, roots)
    assert closure <= set(image_modules.listed_modules(ROOT))


def test_a_label_that_merely_contains_carbon_is_not_a_root(tmp_path):
    for relative, body in (
        ("carbon/__init__.py", ""),
        ("carbon/reconstruction/__init__.py", ""),
        ("carbon/reconstruction/torch_profile.py", "X = 1\n"),
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    folder = tmp_path / ".devcontainer/torch"
    folder.mkdir(parents=True)
    (folder / "Dockerfile").write_text(
        'LABEL org.opencontainers.image.carbon.c03.lock="x"\n'
        "RUN python -I -c 'from carbon.reconstruction.torch_profile import X'\n"
    )
    (tmp_path / ".devcontainer/accelerators").mkdir(parents=True)
    for relative in image_modules.DERIVED_SCRIPTS:
        script = tmp_path / relative
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("import json\n")
    index = image_modules.module_index(tmp_path)
    assert image_modules.derived_roots(tmp_path, index) == {
        "carbon.reconstruction.torch_profile"
    }


# ---- the staged build context -----------------------------------------------------------------------------------


def _repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "carbon/reconstruction/worker").mkdir(parents=True)
    (repo / "carbon/a.py").write_text("A = 1\n")
    (repo / "carbon/unlisted.py").write_text("B = 1\n")
    (repo / "scripts").mkdir()
    (repo / "scripts/tool.sh").write_text("echo tool\n")
    (repo / "pyproject.toml").write_text("[project]\n")
    (repo / "carbon/reconstruction/worker/build_inputs.txt").write_text(
        "# inputs\npyproject.toml\ncarbon/a.py\n"
        "carbon/reconstruction/worker/build_inputs.txt\n"
    )
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


def test_the_staged_context_is_exactly_the_build_inputs(tmp_path):
    repo = _repo(tmp_path)
    staged = image_modules.stage_context(repo, tmp_path / "context")
    assert staged == sorted(
        [
            "carbon/a.py",
            "carbon/reconstruction/worker/build_inputs.txt",
            "pyproject.toml",
        ]
    )
    on_disk = sorted(
        p.relative_to(tmp_path / "context").as_posix()
        for p in (tmp_path / "context").rglob("*")
        if p.is_file()
    )
    assert on_disk == staged  # nothing else: no unlisted carbon file, no scripts/
    assert (tmp_path / "context/carbon/a.py").read_text() == "A = 1\n"


def test_the_staging_directory_must_be_empty_and_an_unstageable_input_is_refused(
    tmp_path,
):
    repo = _repo(tmp_path)
    busy = tmp_path / "busy"
    busy.mkdir()
    (busy / "x").write_text("x")
    with pytest.raises(ValueError, match="must be empty"):
        image_modules.stage_context(repo, busy)
    # an input `git archive` would silently drop (export-ignore) makes the staged set differ from the digest's listing
    (repo / ".gitattributes").write_text("carbon/a.py export-ignore\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "ignore")
    with pytest.raises(ValueError, match="not exactly the build inputs"):
        image_modules.stage_context(repo, tmp_path / "other")


def test_the_context_a_legacy_builder_gets_equals_what_buildkit_lets_through(tmp_path):
    """BuildKit applies the Dockerfile-specific ignore file to the whole checkout; a legacy builder ignores it. A staged
    context needs no ignore file: applying it changes nothing, so both builders see the same files.
    """
    clean = subprocess.run(
        ["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no"],
        capture_output=True,
        text=True,
        check=False,
    )
    if clean.returncode or clean.stdout.strip():
        pytest.skip(
            "needs a clean git checkout (HEAD must carry the working tree's inputs)"
        )
    staged = image_modules.stage_context(ROOT, tmp_path / "context")
    ignore = (ROOT / image_modules.DOCKERIGNORE).read_text(encoding="utf-8")
    assert image_modules.docker_survivors(ROOT, ignore, staged) == set(staged)
    carbon = {path for path in staged if path.startswith("carbon/")}
    assert carbon == set(image_modules.listed_files(ROOT)) & carbon
    assert {
        p for p in image_modules.listed_files(ROOT) if p.startswith("carbon/")
    } == carbon
    # every file the Dockerfile COPYs from the context is there
    text = (ROOT / ".devcontainer/Dockerfile.reconstruction-worker").read_text("utf-8")
    for line in text.splitlines():
        if line.startswith("COPY ") and "--from" not in line:
            *sources, _destination = line.split()[1:]
            for source in sources:
                assert any(
                    path == source.rstrip("/")
                    or path.startswith(source.rstrip("/") + "/")
                    for path in staged
                ), source


def test_the_build_script_builds_from_the_staged_context_not_the_checkout():
    text = (ROOT / "scripts/dev/c03_worker_image.sh").read_text(encoding="utf-8")
    stage = text.index('"${image_modules_program}" stage "${repo_root}" "${context}"')
    build = text.index("docker build")
    assert stage < build
    assert '--file "${context}/.devcontainer/Dockerfile.reconstruction-worker"' in text
    assert '  "${context}"\n' in text[build:]
    assert '"${repo_root}"\n' not in text[build : build + 700]


def test_the_command_stages_and_reports_a_refusal(tmp_path, capsys):
    repo = _repo(tmp_path)
    assert image_modules.main(["stage", str(repo), str(tmp_path / "context")]) == 0
    assert "staged 3 build-input files" in capsys.readouterr().out
    assert image_modules.main(["stage", str(repo), str(tmp_path / "context")]) == 1
    assert "must be empty" in capsys.readouterr().err
