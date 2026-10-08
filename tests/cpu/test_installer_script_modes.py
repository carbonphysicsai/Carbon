"""Every script the miner installer runs directly is executable in a clean clone.

Found by the first fresh-machine run (LAUNCHPAD-ACCEPT-01, 2026-10-07):
`install_miner.sh --gpu` stopped with "Permission denied" (exit 126) at
`./scripts/dev/accelerator_worker_image.sh`. That script was 100644 in the
index. `test_miner_install.py`'s sandbox writes its own stand-ins as 0755, so
it could not see the checkout's mode. A miner cannot work around it: a
`chmod` dirties the checkout, and the installer then refuses to run.

This reads the modes from the git index, which is what a clean clone gets.
It covers the installer itself and everything it runs directly, on every
path, `--update` included, followed through the scripts it runs.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = "scripts/install_miner.sh"

#: A repository script in command position: at the start of a line, after
#: optional `NAME=value` assignments, and not passed to an interpreter
#: (`bash x.sh`, `"${python}" x.py`), which would need no mode.
_DIRECT = re.compile(
    r"""^\s*(?:[A-Za-z_][A-Za-z0-9_]*=(?:"[^"]*"|\S+)\s+)*"""
    r"""(?:\./|"?\$\{repo_root\}/|"?\$\{script_dir\}/)"""
    r"""(?P<path>(?:scripts/)?[A-Za-z0-9_./-]+\.(?:sh|py))"?(?:\s|$)""",
    re.MULTILINE,
)


def _index_mode(path: str) -> str:
    listed = subprocess.run(
        ["git", "ls-files", "--stage", "--", path],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert listed, f"{path} is not tracked"
    return listed.split()[0]


def _direct_executions(path: str) -> set[str]:
    text = (ROOT / path).read_text(encoding="utf-8")
    found = set()
    for match in _DIRECT.finditer(text):
        target = match["path"]
        if not target.startswith("scripts/"):
            # `${script_dir}/x.sh` is beside the script that runs it.
            target = str(Path(path).parent / target).replace("\\", "/")
        found.add(target)
    return found


def _run_directly_by_the_installer() -> set[str]:
    seen, queue = set(), [INSTALLER]
    while queue:
        script = queue.pop()
        if script in seen:
            continue
        seen.add(script)
        queue.extend(_direct_executions(script))
    return seen


def test_the_scan_finds_what_the_installer_runs_directly():
    # If the installer's shape changes so that the scan finds none of these,
    # the scan is fixed, not this list loosened.
    assert {
        INSTALLER,
        "scripts/dev/bootstrap.sh",
        "scripts/dev/c03_worker_image.sh",
        "scripts/dev/accelerator_worker_image.sh",
    } <= _run_directly_by_the_installer()


def test_an_interpreter_run_is_not_a_direct_execution():
    assert not _DIRECT.search('bash "${script_dir}/worker_parent_manifest.sh" x\n')
    assert not _DIRECT.search('  "${python}" "${repo_root}/scripts/dev/x.py"\n')
    assert _DIRECT.search('CARBON_UV_GROUPS="a b" ./scripts/dev/bootstrap.sh\n')


def test_every_script_the_installer_runs_directly_is_executable_in_the_index():
    modes = {path: _index_mode(path) for path in _run_directly_by_the_installer()}
    assert {path: mode for path, mode in modes.items() if mode != "100755"} == {}
