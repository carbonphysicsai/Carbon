"""The public B15 DEVELOPMENT probe plan generator and its host-side check."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from carbon.battery.physics_gate import CONTRACT, REFERENCE_IMAGE, BatteryPhysics

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "b15_public_probes", ROOT / "scripts/dev/battery/b15_public_probes.py"
)
probes = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probes)


def _load(path, raw):
    term = {
        "contract_sha256": hashlib.sha256((ROOT / CONTRACT).read_bytes()).hexdigest(),
        "probes_path": str(path),
        "probes_sha256": hashlib.sha256(raw).hexdigest(),
        "reference_image": REFERENCE_IMAGE,
    }
    return BatteryPhysics(term, ROOT, reference_image=REFERENCE_IMAGE)


def test_the_plan_is_deterministic_and_the_gate_accepts_it(tmp_path):
    raw, provenance = probes.plan(40)
    assert raw == probes.plan(40)[0]
    assert provenance["plan_sha256"] == hashlib.sha256(raw).hexdigest()
    assert provenance["seed"] == probes.PUBLIC_SEED
    assert provenance["count"] == 40 and sum(provenance["axes"].values()) == 40
    assert set(json.loads(raw)) == {"schema", "contract_sha256", "pairs"}
    (tmp_path / "plan.json").write_bytes(raw)
    component = _load(tmp_path / "plan.json", raw)
    assert len(component.inputs()) == 80


def test_host_check_matches_counts_and_reports_overlap_only(tmp_path, monkeypatch):
    public, _ = probes.plan(30)
    monkeypatch.setattr(probes, "PUBLIC_SEED", "stand-in-operator")
    operator, _ = probes.plan(30)
    monkeypatch.undo()
    report = probes.disjoint(operator, public)
    assert report["disjoint"] is True
    assert report["operator_pairs"] == report["public_pairs"] == 30
    assert report["public_plan_sha256"] == hashlib.sha256(public).hexdigest()
    # Only counts, booleans and the public digest: no probe point leaves the host.
    assert set(report) == {
        "operator_pairs",
        "public_pairs",
        "shared_pairs",
        "shared_points",
        "operator_contract_matches",
        "public_plan_sha256",
        "disjoint",
    }
    planted = json.loads(operator)
    planted["pairs"][0] = json.loads(public)["pairs"][5]
    clash = probes.disjoint(json.dumps(planted).encode(), public)
    assert clash["disjoint"] is False and clash["shared_pairs"] == 1
