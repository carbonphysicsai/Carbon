"""Synthetic fail-closed proofs for the canonical invariant CI entrypoint."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

CANONICAL_ARGUMENTS = (
    "-m",
    "pytest",
    "tests/invariants",
    "-m",
    "invariant",
    "-q",
)
COMMITTED_GUARD_PATH = Path(__file__).resolve().with_name("conftest.py")


def _write_config(root: Path, *, include_other_marker: bool = False) -> None:
    markers = ['    "invariant: synthetic invariant marker"']
    if include_other_marker:
        markers.append('    "other: synthetic non-invariant marker"')
    marker_lines = ",\n".join(markers)
    root.joinpath("pyproject.toml").write_text(
        f"""[tool.pytest.ini_options]
addopts = ["--strict-markers"]
markers = [
{marker_lines}
]
""",
        encoding="utf-8",
    )


def _run_canonical_entrypoint(root: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return subprocess.run(
        (sys.executable, *CANONICAL_ARGUMENTS),
        cwd=root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def _combined_output(process: subprocess.CompletedProcess[str]) -> str:
    return process.stdout + process.stderr


def _copy_committed_guard(target: Path) -> None:
    target.joinpath("conftest.py").write_bytes(COMMITTED_GUARD_PATH.read_bytes())


def test_invariant_entrypoint_accepts_marked_passing_test(tmp_path: Path) -> None:
    _write_config(tmp_path)
    target = tmp_path / "tests/invariants"
    target.mkdir(parents=True)
    target.joinpath("test_marked.py").write_text(
        "import pytest\n\n"
        "pytestmark = pytest.mark.invariant\n\n"
        "def test_marked():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    process = _run_canonical_entrypoint(tmp_path)
    assert process.returncode == 0
    assert "1 passed" in _combined_output(process)


def test_invariant_entrypoint_propagates_marked_failure(tmp_path: Path) -> None:
    _write_config(tmp_path)
    target = tmp_path / "tests/invariants"
    target.mkdir(parents=True)
    target.joinpath("test_marked.py").write_text(
        "import pytest\n\n"
        "pytestmark = pytest.mark.invariant\n\n"
        "def test_marked():\n"
        "    assert False\n",
        encoding="utf-8",
    )
    process = _run_canonical_entrypoint(tmp_path)
    assert process.returncode == 1
    assert "1 failed" in _combined_output(process)


def test_invariant_entrypoint_fails_when_target_is_missing(tmp_path: Path) -> None:
    _write_config(tmp_path)
    process = _run_canonical_entrypoint(tmp_path)
    assert process.returncode == 4
    assert "file or directory not found: tests/invariants" in _combined_output(process)


def test_invariant_entrypoint_fails_when_target_is_empty(tmp_path: Path) -> None:
    _write_config(tmp_path)
    tmp_path.joinpath("tests/invariants").mkdir(parents=True)
    process = _run_canonical_entrypoint(tmp_path)
    assert process.returncode == 5
    assert "no tests ran" in _combined_output(process)


def test_invariant_entrypoint_fails_when_only_tests_are_unmarked(
    tmp_path: Path,
) -> None:
    _write_config(tmp_path)
    target = tmp_path / "tests/invariants"
    target.mkdir(parents=True)
    target.joinpath("test_unmarked.py").write_text(
        "def test_unmarked():\n    assert True\n",
        encoding="utf-8",
    )
    process = _run_canonical_entrypoint(tmp_path)
    assert process.returncode == 5
    assert "1 deselected" in _combined_output(process)


def test_invariant_entrypoint_fails_when_zero_marker_matches(tmp_path: Path) -> None:
    _write_config(tmp_path, include_other_marker=True)
    target = tmp_path / "tests/invariants"
    target.mkdir(parents=True)
    target.joinpath("test_other.py").write_text(
        "import pytest\n\n"
        "pytestmark = pytest.mark.other\n\n"
        "def test_other():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    process = _run_canonical_entrypoint(tmp_path)
    assert process.returncode == 5
    assert "1 deselected" in _combined_output(process)


def test_invariant_entrypoint_fails_when_collection_is_completely_deselected(
    tmp_path: Path,
) -> None:
    _write_config(tmp_path)
    target = tmp_path / "tests/invariants"
    target.mkdir(parents=True)
    target.joinpath("test_marked.py").write_text(
        "import pytest\n\n"
        "pytestmark = pytest.mark.invariant\n\n"
        "def test_marked():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    target.joinpath("conftest.py").write_text(
        "def pytest_collection_modifyitems(config, items):\n"
        "    config.hook.pytest_deselected(items=items[:])\n"
        "    items.clear()\n",
        encoding="utf-8",
    )
    process = _run_canonical_entrypoint(tmp_path)
    assert process.returncode == 5
    assert "1 deselected" in _combined_output(process)


def test_invariant_entrypoint_real_guard_fails_partial_deselection(
    tmp_path: Path,
) -> None:
    _write_config(tmp_path)
    target = tmp_path / "tests/invariants"
    target.mkdir(parents=True)
    _copy_committed_guard(target)
    target.joinpath("test_marked.py").write_text(
        "import pytest\n\n"
        "pytestmark = pytest.mark.invariant\n\n"
        "def test_marked():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    target.joinpath("test_unmarked.py").write_text(
        "def test_unmarked():\n    assert True\n",
        encoding="utf-8",
    )
    process = _run_canonical_entrypoint(tmp_path)
    assert process.returncode == 1
    assert "1 passed, 1 deselected" in _combined_output(process)


def test_invariant_entrypoint_real_guard_fails_runtime_skip(tmp_path: Path) -> None:
    _write_config(tmp_path)
    target = tmp_path / "tests/invariants"
    target.mkdir(parents=True)
    _copy_committed_guard(target)
    target.joinpath("test_runtime_skip.py").write_text(
        "import pytest\n\n"
        "pytestmark = pytest.mark.invariant\n\n"
        "def test_runtime_skip():\n"
        "    pytest.skip('synthetic runtime skip')\n",
        encoding="utf-8",
    )
    process = _run_canonical_entrypoint(tmp_path)
    assert process.returncode == 1
    assert "1 skipped" in _combined_output(process)


def test_invariant_entrypoint_real_guard_fails_expected_xfail(
    tmp_path: Path,
) -> None:
    _write_config(tmp_path)
    target = tmp_path / "tests/invariants"
    target.mkdir(parents=True)
    _copy_committed_guard(target)
    target.joinpath("test_expected_xfail.py").write_text(
        "import pytest\n\n"
        "pytestmark = pytest.mark.invariant\n\n"
        "@pytest.mark.xfail(reason='synthetic expected xfail')\n"
        "def test_expected_xfail():\n"
        "    assert False\n",
        encoding="utf-8",
    )
    process = _run_canonical_entrypoint(tmp_path)
    assert process.returncode == 1
    assert "1 xfailed" in _combined_output(process)


def test_invariant_entrypoint_real_guard_fails_non_strict_xpass(
    tmp_path: Path,
) -> None:
    _write_config(tmp_path)
    target = tmp_path / "tests/invariants"
    target.mkdir(parents=True)
    _copy_committed_guard(target)
    target.joinpath("test_non_strict_xpass.py").write_text(
        "import pytest\n\n"
        "pytestmark = pytest.mark.invariant\n\n"
        "@pytest.mark.xfail(reason='synthetic non-strict xpass', strict=False)\n"
        "def test_non_strict_xpass():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    process = _run_canonical_entrypoint(tmp_path)
    assert process.returncode == 1
    assert "1 xpassed" in _combined_output(process)


def test_invariant_entrypoint_real_guard_fails_collection_time_module_skip(
    tmp_path: Path,
) -> None:
    _write_config(tmp_path)
    target = tmp_path / "tests/invariants"
    target.mkdir(parents=True)
    _copy_committed_guard(target)
    target.joinpath("test_collection_skip.py").write_text(
        "import pytest\n\n"
        "pytestmark = pytest.mark.invariant\n\n"
        "pytest.skip('synthetic collection-time skip', allow_module_level=True)\n\n"
        "def test_never_collected():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    process = _run_canonical_entrypoint(tmp_path)
    assert process.returncode == 1
    assert "1 skipped" in _combined_output(process)
