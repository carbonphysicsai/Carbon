"""The per-version exam registry (`carbon.challenge_registry.exam_registry`): closed rows, row-wise refusal, add-only.

Each registry case runs in a fresh interpreter, since the registry and the version overlay it follows are process-wide and
add-only. Synthetic rows only; the committed file is read once and must hold no refused row.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from carbon.challenge_registry import exam_registry
from carbon.challenge_validator import direct_receiver

REPOSITORY = Path(__file__).resolve().parents[2]
SHA = "a" * 64
DIGEST = "sha256:" + SHA
GOOD = {
    "rebuild_gpu_lane_hours": {"value": 0.02, "measurement_digest": DIGEST},
    "solver_seconds_per_design": {"value": 100, "source": "synthetic"},
    "terms": {"version": "zz-terms-v0", "sha256": SHA},
    "verify_set": {"path": "kits/zz/verify_set.json", "sha256": SHA},
    "published": {"path": "kits/zz/published.json", "sha256": SHA},
    "build": {"anything": 1},
    "entry": {
        "title": "Synthetic exam",
        "portfolio": "launch",
        "status": "open",
    },
    "launch": {
        "state": "launched",
        "qualified_sealed": {
            "record_sha256": DIGEST,
            "evaluation_pack_digests": [DIGEST],
        },
    },
}
NESTED = 0
for _ in range(exam_registry.MAX_DEPTH + 1):
    NESTED = [NESTED]
ENTRY = {
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

_PROGRAM = r"""
import json, sys
from carbon.challenge_kit import version_overlay
from carbon.challenge_registry import exam_registry as r
for path in json.loads(sys.argv[1]):
    version_overlay.install(path=path)
out = {"steps": []}
for path in json.loads(sys.argv[2]):
    try:
        r.install(path)
        out["steps"].append(None)
    except r.ExamRegistryRefused as failure:
        out["steps"].append(str(failure))
out["fields"] = {n: r.field("zz-synthetic", "0.1", n) for n in sorted(r.FIELDS)}
out["keys"] = {n: [list(k) for k in r.keys(n)] for n in sorted(r.FIELDS)}
out["refused"] = r.refused()
try:
    r.require("zz-synthetic", "0.1", "terms")
    out["require"] = None
except r.ExamRowRefused as failure:
    out["require"] = str(failure)
print(json.dumps(out))
"""


def _registry(tmp_path, name, rows):
    path = tmp_path / name
    document = {"schema": exam_registry.SCHEMA, "source": "test", "exams": rows}
    path.write_text(json.dumps(document), encoding="utf-8")
    return str(path)


def _run(tmp_path, registries, *, registered=True):
    overlays = []
    if registered:
        overlay = tmp_path / "overlay.json"
        document = {
            "schema": "carbon.challenge-kit.version-overlay.v1",
            "versions": {"zz-synthetic 0.1": ENTRY},
        }
        overlay.write_text(json.dumps(document), encoding="utf-8")
        overlays.append(str(overlay))
    done = subprocess.run(
        [sys.executable, "-c", _PROGRAM, json.dumps(overlays), json.dumps(registries)],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    )
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_the_committed_file_loads_refuses_no_row_and_is_a_grading_path():
    document = json.loads(exam_registry.REGISTRY.read_bytes())
    assert document["schema"] == exam_registry.SCHEMA
    assert exam_registry.refused() == {}
    committed = exam_registry.REGISTRY.relative_to(REPOSITORY).as_posix()
    assert direct_receiver.grading_path(committed)
    assert direct_receiver.grading_path("carbon/challenge_registry/exam_registry.py")


def test_a_row_answers_every_field_of_a_registered_version(tmp_path):
    assert set(GOOD) == set(exam_registry.FIELDS)
    out = _run(tmp_path, [_registry(tmp_path, "r.json", {"zz-synthetic 0.1": GOOD})])
    assert out["fields"] == GOOD
    for name in GOOD:
        assert ["zz-synthetic", "0.1"] in out["keys"][name]
    assert out["refused"] == {} and out["require"] is None


def test_a_row_of_an_unregistered_version_answers_nothing(tmp_path):
    registry = _registry(tmp_path, "r.json", {"zz-synthetic 0.1": GOOD})
    out = _run(tmp_path, [registry], registered=False)
    assert set(out["fields"].values()) == {None}
    assert ["zz-synthetic", "0.1"] not in out["keys"]["terms"]


@pytest.mark.parametrize(
    "change",
    [
        {"unknown": 1},
        {"launch": {**GOOD["launch"], "state": "open"}},
        {"launch": {"state": "launched"}},
        {"launch": {**GOOD["launch"], "extra": 1}},
        {"launch": {**GOOD["launch"], "qualified_sealed": None}},
        {
            "launch": {
                "state": "launched",
                "qualified_sealed": {
                    "record_sha256": SHA,
                    "evaluation_pack_digests": [DIGEST],
                },
            }
        },
        {
            "launch": {
                "state": "launched",
                "qualified_sealed": {
                    "record_sha256": DIGEST,
                    "evaluation_pack_digests": [],
                },
            }
        },
        {
            "launch": {
                "state": "launched",
                "qualified_sealed": {
                    "record_sha256": DIGEST,
                    "evaluation_pack_digests": [DIGEST, DIGEST],
                },
            }
        },
        {"rebuild_gpu_lane_hours": {"value": 0, "measurement_digest": DIGEST}},
        {"rebuild_gpu_lane_hours": {"value": True, "measurement_digest": DIGEST}},
        {"rebuild_gpu_lane_hours": {"value": 1, "measurement_digest": SHA}},
        {"solver_seconds_per_design": {"value": -1, "source": "s"}},
        {"solver_seconds_per_design": {"value": 1, "source": " "}},
        {"solver_seconds_per_design": 1},
        {"terms": {"version": "v", "sha256": "short"}},
        {"verify_set": {"path": "../outside", "sha256": SHA}},
        {"verify_set": {"path": "kits/../outside", "sha256": SHA}},
        {"verify_set": {"path": "/absolute", "sha256": SHA}},
        {"verify_set": {"path": "a//b", "sha256": SHA}},
        {"published": {"path": "a\\b", "sha256": SHA}},
        {"build": {}},
        {"entry": {"title": "x", "portfolio": "launch", "status": "live"}},
        # an integer too large for a float, an infinite number, a value nested deeper than the bound
        {"solver_seconds_per_design": {"value": 10**400, "source": "s"}},
        {"rebuild_gpu_lane_hours": {"value": 10**400, "measurement_digest": DIGEST}},
        {"build": {"nested": NESTED}},
    ],
)
def test_a_malformed_row_refuses_itself_and_no_other_row(tmp_path, change):
    rows = {"zz-synthetic 0.1": {**GOOD, **change}, "zz-other 0.1": GOOD}
    out = _run(tmp_path, [_registry(tmp_path, "r.json", rows)])
    assert list(out["refused"]) == ["zz-synthetic 0.1"]
    assert set(out["fields"].values()) == {None}
    assert out["require"].startswith("zz-synthetic 0.1: ")
    assert out["steps"] == [None]


def test_an_infinite_number_in_a_row_refuses_that_row(tmp_path):
    path = tmp_path / "r.json"
    good = json.dumps(GOOD)
    text = '{"zz-synthetic 0.1": {"build": {"x": 1e999}}, "zz-other 0.1": ' + good
    path.write_text(_HEAD + text + "}}", encoding="utf-8")
    out = _run(tmp_path, [str(path)])
    assert list(out["refused"]) == ["zz-synthetic 0.1"] and out["steps"] == [None]


def test_a_key_that_names_no_version_is_refused_alone(tmp_path):
    rows = {"zz-synthetic": GOOD, "zz-synthetic 0.1a": GOOD, "zz-synthetic 0.1": GOOD}
    out = _run(tmp_path, [_registry(tmp_path, "r.json", rows)])
    assert sorted(out["refused"]) == ["zz-synthetic", "zz-synthetic 0.1a"]
    assert out["fields"] == GOOD


def test_an_installed_row_never_changes_and_a_repeat_is_the_same_row(tmp_path):
    name = "zz-synthetic 0.1"
    other = {**GOOD, "solver_seconds_per_design": {"value": 7, "source": "s"}}
    first = _registry(tmp_path, "a.json", {name: GOOD})
    changed = _registry(tmp_path, "b.json", {name: other, "zz-other 0.1": GOOD})
    broken = _registry(tmp_path, "c.json", {name: {"unknown": 1}})
    out = _run(tmp_path, [first, first, changed, broken])
    refusal = f"exam_registry_row_changed: {name}"
    assert out["steps"] == [None, None, refusal, refusal]
    assert out["fields"] == GOOD and out["refused"] == {}


def test_a_refused_row_never_becomes_a_good_one_in_one_process(tmp_path):
    name = "zz-synthetic 0.1"
    broken = _registry(tmp_path, "a.json", {name: {"unknown": 1}})
    good = _registry(tmp_path, "b.json", {name: GOOD})
    out = _run(tmp_path, [broken, good])
    assert out["steps"] == [None, f"exam_registry_row_changed: {name}"]
    assert set(out["fields"].values()) == {None}


_HEAD = (
    '{"schema": "carbon.challenge-registry.exam-registry.v1", "source": "", "exams": '
)


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[]",
        '{"schema": "other", "source": "", "exams": {}}',
        _HEAD + '{"zz-a 1": {}, "zz-a 1": {}}}',
        _HEAD + '{"zz-a 1": {"build": {"x": NaN}}}}',
        # nesting beyond the JSON reader's own limit
        pytest.param(
            _HEAD + '{"zz-a 1": {"build": ' + "[" * 200_000 + "]" * 200_000 + "}}}",
            id="nested-too-deep",
        ),
    ],
)
def test_a_file_that_is_not_a_registry_is_refused_whole(tmp_path, text):
    path = tmp_path / "bad.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(exam_registry.ExamRegistryRefused):
        exam_registry.install(path)


def test_a_missing_file_registers_nothing(tmp_path):
    before = exam_registry.install()
    assert exam_registry.install(tmp_path / "absent.json") == before


@pytest.mark.parametrize("name", ["", "unknown"])
def test_a_field_no_row_may_carry_is_an_error_not_an_absence(name):
    for ask in (
        lambda: exam_registry.field("zz-synthetic", "0.1", name),
        lambda: exam_registry.keys(name),
    ):
        with pytest.raises(KeyError):
            ask()
