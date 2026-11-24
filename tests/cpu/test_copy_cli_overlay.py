"""A process that only issues, records or imports a validator's copy knows every overlay pool version (R0c F16).

A pool-graded overlay version (Motor 1.8) is in its sealed module's tables only once the version registry is imported.
The copy command lines are processes of their own: each must register the overlay itself, or it reads the version's pool
batch as not pool-graded and refuses it. Every check runs in a FRESH interpreter, because any other test module in this
process may have imported the registry already.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OVERLAY = ROOT / "scripts/validator_host_classes/version_overlay.json"
#: Every overlay version that is served through a dispatch (its sealed module knows it only through the overlay).
DISPATCHED = sorted(
    (entry["challenge_id"], entry["version"])
    for entry in json.loads(OVERLAY.read_bytes())["versions"].values()
    if "dispatch" in entry
)

_TELL = """
import json, sys
from carbon.scoring import sealed_batch_source as source
print(json.dumps([source._pool_graded(c, v) for c, v in json.loads(sys.argv[1])]))
"""


def _fresh(setup):
    done = subprocess.run(
        [sys.executable, "-c", setup + _TELL, json.dumps(DISPATCHED)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.splitlines()[-1])


def test_the_overlay_has_a_dispatched_pool_version():
    assert ("electric-motor-magnetics", "1.8") in DISPATCHED


def test_without_the_registry_a_dispatched_version_is_unknown():
    """What the copy command lines met before: the batch source alone does not register the overlay."""
    assert not any(_fresh(""))


@pytest.mark.parametrize(
    "module",
    [
        "carbon.challenge_validator.copy_delivery",
        "carbon.challenge_validator.copy_issuance",
        "carbon.challenge_validator.canonicalisation_record",
    ],
)
def test_a_copy_module_registers_the_overlay(module):
    assert all(_fresh(f"import {module}\n"))


def test_the_import_command_registers_the_overlay_before_it_reads_a_copy():
    """`import_copy.main` on a file that is not there: it refuses on the file, with the overlay registered."""
    assert all(_fresh("""
import runpy
tool = runpy.run_path("scripts/dev/sealed_exam/import_copy.py", run_name="import_copy")
assert tool["main"](["--store", "no-store", "--copy", "no-copy.json", "--hotkey", "h"]) == 2
"""))


@pytest.mark.parametrize("challenge,version", DISPATCHED)
def test_every_dispatched_version_has_its_own_grader_once_registered(
    challenge, version
):
    """The same fresh process finds the version in its Challenge's sealed tables by name, so a copy of it can be built."""
    row = DISPATCHED.index((challenge, version))
    assert _fresh("import carbon.challenge_validator.copy_delivery\n")[row] is True
