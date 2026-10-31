"""A program inside a directory that holds a stdlib-named module is run isolated (the GPUYard P1 on b81a6e62f).

`carbon/reconstruction/worker/` holds the worker's own `operator.py`. `python carbon/reconstruction/worker/image_modules.py
check` puts that directory FIRST on sys.path, so `import ast` -> `enum` -> `from operator import or_` found it instead of
the standard library's `operator` and failed (the build script reported a misleading "stale files"). It passed on hosts where
something had already imported `operator`. The install scripts, CI and the build script now run these programs with
`-I -B`: isolated mode keeps the script's directory (and the working directory, PYTHON* variables and the user site) off
sys.path on every Python 3, unlike `-P` (3.11+ only; the interpreter can be a host python3); `-B` stands in for the ignored
PYTHONDONTWRITEBYTECODE export.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "carbon/reconstruction/worker"
PROGRAMS = (WORKER / "build_inputs.py", WORKER / "image_modules.py")


def _shadow_directories():
    """Repository-relative directories under carbon/ with a module named like a standard-library module."""
    found = set()
    for path in (ROOT / "carbon").rglob("*.py"):
        if path.stem in sys.stdlib_module_names and "__pycache__" not in path.parts:
            found.add(path.parent.relative_to(ROOT).as_posix())
    return found


def test_the_known_shadowing_directory_is_still_in_the_audit():
    assert "carbon/reconstruction/worker" in _shadow_directories()


def test_every_script_or_workflow_that_runs_a_file_in_such_a_directory_runs_it_isolated():
    """Audit: a non-comment line of a shell script or workflow that runs `python ... <shadow dir>/x.py` must carry -I."""
    directories = sorted(_shadow_directories())
    pattern = re.compile(
        r"(?P<command>(?:python3?|\.venv/bin/python|\$\{?PYTHON\}?\"?)[^\n|;&]*?)"
        r"\s\"?[^\s\"']*(?:"
        + "|".join(re.escape(d) for d in directories)
        + r")/\w+\.py"
    )
    offenders = []
    for folder, patterns in (("scripts", ("*.sh",)), (".github", ("*.yml", "*.yaml"))):
        for glob in patterns:
            for path in sorted((ROOT / folder).rglob(glob)):
                for number, line in enumerate(
                    path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
                ):
                    if line.lstrip().startswith("#"):
                        continue
                    match = pattern.search(line)
                    if match and not re.search(
                        r"\s-[A-Za-z]*I", match.group("command")
                    ):
                        offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert offenders == [], offenders


def test_the_build_script_and_ci_name_the_isolated_flags():
    script = (ROOT / "scripts/dev/c03_worker_image.sh").read_text(encoding="utf-8")
    for call in (
        '"${PYTHON}" -I -B "${image_modules_program}" check',
        '"${PYTHON}" -I -B "${build_inputs_program}" ignored',
        '"${PYTHON}" -I -B "${build_inputs_program}" digest',
        '"${PYTHON}" -I -B "${image_modules_program}" stage',
    ):
        assert call in script, call
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert (
        ".venv/bin/python -I -B carbon/reconstruction/worker/build_inputs.py digest"
        in ci
    )


@pytest.mark.parametrize(
    "arguments",
    [["image_modules.py", "check", str(ROOT)], ["build_inputs.py", "paths"]],
)
def test_the_programs_run_under_a_clean_interpreter_with_the_build_scripts_flags(
    arguments,
):
    """No site import (nothing pre-imports `operator` for us) and the same `-I -B` flags the build script uses."""
    program = WORKER / arguments[0]
    done = subprocess.run(
        [sys.executable, "-S", "-I", "-B", str(program), *arguments[1:]],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr[-400:]


def test_the_digest_and_ignored_commands_run_the_same_way():
    if subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        check=False,
    ).returncode:
        pytest.skip("needs a git checkout")
    program = WORKER / "build_inputs.py"
    digest = subprocess.run(
        [sys.executable, "-S", "-I", "-B", str(program), "digest", str(ROOT)],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert digest.returncode == 0, digest.stderr[-400:]
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", digest.stdout.strip())
    ignored = subprocess.run(
        [sys.executable, "-S", "-I", "-B", str(program), "ignored", str(ROOT)],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert ignored.returncode in (0, 1), ignored.stderr[
        -400:
    ]  # 1 = ignored files listed, never a crash


def test_without_the_isolation_flag_the_shadow_breaks_the_import_which_is_what_the_flag_prevents():
    """The control that keeps the tests above from being vacuous: run as a plain script the worker's `operator.py` wins."""
    done = subprocess.run(
        [sys.executable, "-S", "-B", str(WORKER / "build_inputs.py"), "paths"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if done.returncode == 0:
        pytest.skip(
            "this interpreter does not reach `operator` through the stdlib imports"
        )
    assert "operator" in done.stderr
