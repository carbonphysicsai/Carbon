"""The public B15 DEVELOPMENT probe plan: the screen's own generator under a
new public seed, at the screened count, disjoint from the screen plan."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from carbon.battery.physics_gate import CONTRACT, REFERENCE_IMAGE, BatteryPhysics

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "b15_public_probes", ROOT / "scripts/dev/battery/b15_public_probes.py"
)
probes = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probes)
EVIDENCE = ROOT / probes.EVIDENCE


def test_the_generator_is_the_screens():
    """Under the screen's own seed it reproduces the screen plan's 100 bases."""
    jobs = json.loads((ROOT / probes.SCREEN_JOBS[0]).read_bytes())["jobs"]
    screen = [
        {k: j[k] for k in ("c1", "c2", "soc0", "t_amb_c")}
        for j in jobs
        if j["case_id"].endswith("-base")
    ]
    assert len(screen) == 100
    assert probes.bases("physics-calibration-01") == screen


def test_committed_plan_regenerates_and_the_gate_accepts_it():
    raw, provenance = probes.plan()
    assert raw == (EVIDENCE / "plan.json").read_bytes()
    assert (EVIDENCE / "provenance.json").read_bytes() == (
        json.dumps(provenance, sort_keys=True, indent=1).encode() + b"\n"
    )
    assert provenance["plan_sha256"] == hashlib.sha256(raw).hexdigest()
    assert provenance["seed"] == probes.PUBLIC_SEED != "physics-calibration-01"
    assert provenance["pairs"] == 200 and provenance["axes"] == {"c1": 100, "c2": 100}
    assert provenance["screened_at"]["pairs_per_base"] == 100
    assert set(json.loads(raw)) == {"schema", "contract_sha256", "pairs"}
    term = {
        "contract_sha256": hashlib.sha256((ROOT / CONTRACT).read_bytes()).hexdigest(),
        "probes_path": probes.EVIDENCE + "/plan.json",
        "probes_sha256": hashlib.sha256(raw).hexdigest(),
        "reference_image": REFERENCE_IMAGE,
    }
    component = BatteryPhysics(term, ROOT, reference_image=REFERENCE_IMAGE)
    assert len(component.inputs()) == 400


def test_disjoint_from_the_screen_plan_and_a_clash_refuses(monkeypatch):
    _, provenance = probes.plan()
    assert provenance["disjoint_from_screen"] == {
        "checked": True,
        "shared_pairs": 0,
        "shared_points": 0,
    }
    monkeypatch.setattr(probes, "PUBLIC_SEED", "physics-calibration-01")
    with pytest.raises(SystemExit, match="shares a point with the screen plan"):
        probes.plan()


def test_a_changed_screen_file_refuses(monkeypatch):
    monkeypatch.setattr(probes, "SCREEN_PLAN", (probes.SCREEN_PLAN[0], "0" * 64))
    with pytest.raises(SystemExit, match="differs from its pin"):
        probes.plan()
