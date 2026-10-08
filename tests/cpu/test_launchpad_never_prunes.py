"""No Launchpad step, test or clean-up ever prunes Docker (LA-F7).

The rule, from the Test Lead on 2026-10-08:
- Never prune on a shared host. On 2026-10-07, a `docker image prune` on
  the shared WSL host deleted another team's images, and with them 100
  finished solves.
- A miner's own dedicated engine may be cleaned only by removing the images
  Carbon built, by their tag (`carbon-c03-worker:`, `carbon-analysis:`,
  `carbon-gpu-worker:`, `carbon-cw1d4-parent:`).

`prune` removes whatever an engine holds that matches, including other
people's images. So it never appears in a command that the miner path
installs, builds, sets up, practises, cleans up or tests with.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: The miner path: what the installer runs, what setup and campaigns run,
#: the remote transports, and the tests of all of these.
SURFACE = (
    "scripts/install_miner.sh",
    "scripts/dev/c03_worker_image.sh",
    "scripts/dev/accelerator_worker_image.sh",
    "scripts/dev/push_worker_image.sh",
    "scripts/dev/bootstrap.sh",
    "scripts/dev/miner_launchpad",
    "carbon/miner_mcp",
    "carbon/development_session",
    "carbon/reconstruction/worker",
    "carbon/compute",
    "carbon_miner_signer",
    "tests/cpu/test_miner_install.py",
    "tests/cpu/test_installer_script_modes.py",
    "tests/service/test_launchpad_production_journey.py",
)

#: A shell command line (not a comment) that runs any `docker ... prune`.
_SHELL = re.compile(r"^(?!\s*#).*\bdocker\b[^#\n]*\bprune\b", re.MULTILINE)
#: A Python argument vector naming `prune` as a word of its own, e.g.
#: `["image", "prune"]` or `("system", "prune", "-f")`.
_ARGV = re.compile(r"""["']prune["']""")


def _files():
    for entry in SURFACE:
        path = ROOT / entry
        assert path.exists(), f"{entry} moved: update this test's surface"
        if path.is_file():
            yield path
        else:
            yield from (
                child
                for child in path.rglob("*")
                if child.suffix in {".py", ".sh", ".js"} and child.is_file()
            )


def _offences(path):
    text = path.read_text(encoding="utf-8")
    found = []
    if path.suffix == ".sh":
        found += [m.group(0).strip() for m in _SHELL.finditer(text)]
    found += [m.group(0) for m in _ARGV.finditer(text)]
    return found


def test_the_patterns_catch_a_prune_and_not_a_mention():
    assert _SHELL.search("  docker image prune -f\n")
    assert _SHELL.search("docker system prune --all\n")
    assert not _SHELL.search("# never run docker image prune here\n")
    assert _ARGV.search('cli.run(["image", "prune", "-f"])')
    assert not _ARGV.search('"""`docker image prune` deletes it"""')


def test_no_miner_path_command_prunes_docker():
    offences = {
        str(path.relative_to(ROOT)).replace("\\", "/"): hits
        for path in _files()
        if path.name != Path(__file__).name
        for hits in [_offences(path)]
        if hits
    }
    assert offences == {}
