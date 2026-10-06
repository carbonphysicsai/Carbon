"""REF-RESOLVE-01: the settled overlay replaces only settled OK refined
records, stamps them, and never adds or alters anything else."""

import json

from carbon.battery.value import reference_policy as rp


def test_overlay_replaces_only_settled_ok_refined_cases(tmp_path):
    path = tmp_path / rp.SETTLED_NAME
    rows = [
        {"case_id": "a", "refined": True, "status": "OK", "outputs": {"x": 2}},
        {"case_id": "b", "refined": True, "status": "REFERENCE_SOLVER_FAILED"},
        {"case_id": "c", "refined": False, "status": "OK"},
        {"case_id": "z", "refined": True, "status": "OK"},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    base = {
        "a": {"case_id": "a", "status": "OK", "outputs": {"x": 1}},
        "b": {"case_id": "b", "status": "REFERENCE_SOLVER_FAILED"},
        "c": {"case_id": "c", "status": "OK"},
    }
    settled = rp.settled(path)
    assert set(settled) == {"a", "z"}
    out = rp.overlay(base, settled)
    assert out["a"]["outputs"] == {"x": 2} and out["a"]["reference_policy"] == rp.POLICY
    assert out["b"] == base["b"] and out["c"] == base["c"] and "z" not in out
    assert base["a"]["outputs"] == {"x": 1}
