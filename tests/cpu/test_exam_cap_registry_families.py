"""The exam cap's family list comes from the version registry: every live family keeps its place and its answer, and a
family registered only through the host overlay is a Challenge the cap, the koth rows and the health report know.

The literals below were read from main before the change; a family added later comes after them and moves none.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from carbon.challenge_kit import version_registry
from carbon.challenge_validator import exam_cap, registry_version

REPOSITORY = Path(__file__).resolve().parents[2]
BATTERY = "battery-fastcharge-ageing-development-v1"
LAUNCH = ("electric-motor-magnetics", "chip-cold-plate", "f08-ribbed-bracket", "f02")

_PROGRAM = r"""
import json, sys
from carbon.challenge_kit import version_overlay
from carbon.challenge_validator import exam_cap, exam_health, registry_version
before = [list(exam_cap.registered_challenges()), list(exam_cap.lean_challenges())]
version_overlay.install(path=sys.argv[1])
known = exam_cap.registered_challenges()
names = [row["challenge"] for row in exam_health.report(sys.argv[2], block=0)]
out = {
    "before": before,
    "after": [list(known), list(exam_cap.lean_challenges())],
    "known": {
        key: registry_version.known_key(key, known)
        for key in ("zz-synthetic", "zz-synthetic 0.1", "zz-synthetic 0.2", "zz-other")
    },
    "health": names,
}
try:
    exam_cap.require_grading_deadline({}, "zz-synthetic")
    out["deadline"] = None
except exam_cap.ExamCapRefused as refused:
    out["deadline"] = refused.code
print(json.dumps(out))
"""


def test_the_live_families_keep_their_order_and_come_first():
    assert exam_cap._LEAN_CHALLENGES == LAUNCH
    known = exam_cap.registered_challenges()
    assert known[:5] == (*LAUNCH, BATTERY)
    assert exam_cap.lean_challenges()[:4] == LAUNCH
    assert BATTERY not in exam_cap.lean_challenges()
    # whatever follows is a family of the version registry, once, in id order
    others = known[5:]
    assert list(others) == sorted(set(others))
    assert set(known) == {c for c, _ in version_registry.VERSIONS}


@pytest.mark.parametrize(
    "key",
    [
        "electric-motor-magnetics",
        "electric-motor-magnetics 1.8",
        "chip-cold-plate 1.8",
        "f08-ribbed-bracket 1.7",
        "f02 2.5",
        BATTERY,
    ],
)
def test_every_live_key_is_known_and_a_misspelled_version_is_not(key):
    known = exam_cap.registered_challenges()
    assert registry_version.known_key(key, known)
    challenge = key.partition(" ")[0]
    assert not registry_version.known_key(challenge + " 99.99", known)
    assert not registry_version.known_key(challenge + "x", known)


def test_a_family_registered_only_in_the_overlay_is_known_everywhere(tmp_path):
    overlay = tmp_path / "overlay.json"
    entry = {
        "challenge_id": "zz-synthetic",
        "version": "0.1",
        "train": "zz-synthetic-train-v1",
        "allowlist": "v8",
        "step_caps": False,
        "pack_version": "zz-synthetic-normal-construction-development-1",
        "development_evaluation": None,
        "sealed_evaluation": "zz-synthetic-pool-sealed-v1",
        "campaign": "catalog",
    }
    document = {
        "schema": "carbon.challenge-kit.version-overlay.v1",
        "versions": {"zz-synthetic 0.1": entry},
    }
    overlay.write_text(json.dumps(document), encoding="utf-8")
    ledger = tmp_path / "ledger.sqlite3"
    ledger.touch()
    done = subprocess.run(
        [sys.executable, "-c", _PROGRAM, str(overlay), str(ledger)],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    )
    out = json.loads(done.stdout.strip().splitlines()[-1])
    # an unrelated family moves no live family's place (v2's condition (3))
    for before, after in zip(out["before"], out["after"], strict=True):
        assert [name for name in after if name != "zz-synthetic"] == before
        assert "zz-synthetic" in after and "zz-synthetic" not in before
    assert out["known"] == {
        "zz-synthetic": True,
        "zz-synthetic 0.1": True,
        "zz-synthetic 0.2": False,
        "zz-other": False,
    }
    assert "zz-synthetic" in out["health"]
    # a registered Challenge with no grading deadline refuses at start-up, as the launch four do
    assert out["deadline"] == "exam_cap_deadline_unregistered"
