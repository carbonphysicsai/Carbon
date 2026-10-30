import copy
import hashlib
import importlib.util
import json
import statistics
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("recal_stats", Path(__file__).parents[2] / "scripts" / "dev" / "recal_stats.py")
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)


def H(c):
    return c * 64


def _member(totals, same=True, within=False, fp="a"):
    digests = [H("1")] * 10 if same else [H(str(i)) for i in range(10)]
    return {"reference_fingerprint": H(fp), "seed0_totals": totals, "state_digests": digests, "within_noise": within}


def _doc():
    spec = {
        "pack_digest": H("b"),
        "class_record_digest": H("c"),
        "control_basis_bit_identical": "ten bit-identical",
        "control_basis_within_noise": "smallest sigma within noise",
        "panel": ["mgn", "fc"],
        "members": {
            "mgn": _member([1.0 + 0.01 * i for i in range(10)], same=False, within=True, fp="d"),
            "fc": _member([2.0] * 10, same=True, fp="e"),
        },
        "control_seed_totals": {"fc": [2.0, 2.1, 1.9, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0]},
    }
    return {"schema": rs.SCHEMA_IN, "challenges": {"Cooling": spec}}


def test_values_follow_the_ruling():
    out = rs.measure(_doc())["challenges"]["Cooling"]
    sd = statistics.stdev([1.0 + 0.01 * i for i in range(10)])
    assert out["sigma"] == pytest.approx(sd) and out["sigma_by_member"]["fc"] == 0.0
    assert out["seed_spread"] == pytest.approx(0.2)
    assert out["value"] == pytest.approx(max(5 * sd, 0.2))
    assert out["bit_identical"] == {"mgn": False, "fc": True}
    assert out["control"]["entry_id"] == "fc" and out["control"]["control_basis"] == "ten bit-identical"


def test_control_is_first_bit_identical_member_in_panel_order():
    doc = _doc()
    doc["challenges"]["Cooling"]["members"]["mgn"]["state_digests"] = [H("1")] * 10
    doc["challenges"]["Cooling"]["control_seed_totals"] = {"mgn": [1.0] * 9 + [1.5]}
    c = rs.measure(doc)["challenges"]["Cooling"]["control"]
    assert c["entry_id"] == "mgn"
    assert set(c) == {"entry_id", "reference_fingerprint", "reference_total", "control_basis", "pack_digest", "class_record_digest"}


def test_fallback_is_smallest_sigma_within_noise_and_needs_the_flag():
    doc = _doc()
    spec = doc["challenges"]["Cooling"]
    spec["members"]["fc"] = _member([2.0 + 0.5 * i for i in range(10)], same=False, within=False, fp="e")
    spec["control_seed_totals"] = {"mgn": [1.0, 1.1] * 5}
    c = rs.measure(doc)["challenges"]["Cooling"]["control"]
    assert c["entry_id"] == "mgn" and c["control_basis"] == "smallest sigma within noise"
    spec["members"]["mgn"]["within_noise"] = False
    with pytest.raises(rs.StatsError, match="no control"):
        rs.measure(doc)


def test_both_zero_stops():
    doc = _doc()
    spec = doc["challenges"]["Cooling"]
    spec["control_seed_totals"] = {"mgn": [2.0] * 10}
    spec["members"]["mgn"] = _member([1.0] * 10, same=True)
    with pytest.raises(rs.StatsError, match="both 0"):
        rs.measure(doc)


def test_digest_is_sha256_of_the_body_and_stable():
    out = rs.measure(_doc())
    body = {k: v for k, v in out.items() if k != "measurement_digest"}
    assert out["measurement_digest"] == hashlib.sha256(rs.canonical(body)).hexdigest()
    assert rs.measure(copy.deepcopy(_doc())) == out
    other = _doc()
    other["challenges"]["Cooling"]["pack_digest"] = H("f")
    assert rs.measure(other)["measurement_digest"] != out["measurement_digest"]


@pytest.mark.parametrize(
    "edit",
    [
        lambda s: s["members"]["fc"].update(seed0_totals=[1.0] * 9),
        lambda s: s["members"]["fc"].update(seed0_totals=[float("nan")] * 10),
        lambda s: s["members"]["fc"].update(state_digests=["ab"] * 10),
        lambda s: s.update(pack_digest="abc"),
        lambda s: s.update(panel=["fc"]),
        lambda s: s.update(control_seed_totals={}),
    ],
)
def test_malformed_input_is_refused(edit):
    doc = _doc()
    edit(doc["challenges"]["Cooling"])
    with pytest.raises(rs.StatsError):
        rs.measure(doc)


def test_cli_writes_document_and_prints_digest(tmp_path, capsys):
    src, dst = tmp_path / "in.json", tmp_path / "out.json"
    src.write_text(json.dumps(_doc()))
    assert rs.main([str(src), "--out", str(dst)]) == 0
    assert capsys.readouterr().out.strip() == json.loads(dst.read_text())["measurement_digest"]
    src.write_text("{}")
    assert rs.main([str(src)]) == 2
