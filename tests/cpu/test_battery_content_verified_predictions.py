"""Content verification of regenerated predictions (OWNER-EV4-REGEN-01).

The claims tested: a regenerated file is accepted only when its recomputed
exam components equal the result's recorded components exactly; a file
that differs, names another member, or a directory that does not cover the
panel is refused.
"""

import gzip
import json

import pytest

from carbon.battery.value import margins
from carbon.battery.value import scoring as sc

RECORDED = {"eligible": True, "E": 0.1, "E_important": 0.2, "decision": {"score": 0.9}}


def _results(*members):
    return {
        "summary": {"members": {m: {"kind": "RECONSTRUCTED"} for m in members}},
        "components": {m: dict(RECORDED) for m in members},
    }


def _write(directory, member, named=None):
    body = {"member": named or member, "predictions": {"c": {}}}
    (directory / f"{member}.json.gz").write_bytes(
        gzip.compress(json.dumps(body).encode())
    )


@pytest.fixture
def recomputed(monkeypatch):
    state = {"components": dict(RECORDED)}
    monkeypatch.setattr(sc, "scoring_set", lambda repo: (None, ["c"], None))
    monkeypatch.setattr(sc, "components", lambda *a, **k: state["components"])
    return state


def test_identical_content_is_accepted_one_member_at_a_time(tmp_path, recomputed):
    _write(tmp_path, "m1")
    loader = margins.content_verified_predictions(tmp_path, _results("m1"), {})
    assert loader["m1"] == {"c": {}}
    assert loader.verified == ["m1"]


def test_different_content_is_refused(tmp_path, recomputed):
    _write(tmp_path, "m1")
    loader = margins.content_verified_predictions(tmp_path, _results("m1"), {})
    recomputed["components"] = {**RECORDED, "E": 0.1 + 1e-15}
    with pytest.raises(ValueError, match="differ in content"):
        loader["m1"]


def test_a_file_naming_another_member_is_refused(tmp_path, recomputed):
    _write(tmp_path, "m1", named="m2")
    loader = margins.content_verified_predictions(tmp_path, _results("m1"), {})
    with pytest.raises(ValueError, match="another member"):
        loader["m1"]


def test_a_directory_that_does_not_cover_the_panel_is_refused(tmp_path, recomputed):
    _write(tmp_path, "m1")
    with pytest.raises(ValueError, match="cover the panel"):
        margins.content_verified_predictions(tmp_path, _results("m1", "m2"), {})
