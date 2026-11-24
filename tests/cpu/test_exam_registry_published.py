"""A new version's published exam comes from the file its exam registry row names, and no published block moves.

The digests are main's blocks, read before the change. Registry cases use synthetic rows and the synthetic fixture file;
the end-to-end case runs in a fresh interpreter.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from carbon.challenge_registry import exam_registry, speed_gate
from carbon.challenge_registry import published_exam as pe

REPOSITORY = Path(__file__).resolve().parents[2]
FIXTURE = "tests/fixtures/exam_registry/zz_published_exam.json"
KEY = ("zz-synthetic", "0.1")
MOTOR = "electric-motor-magnetics"
COOLING = "chip-cold-plate"
F08 = "f08-ribbed-bracket"
#: main d2c356f5: {key: (sha256 of the canonical block, whether its constants are registered)}
BLOCKS = {
    (COOLING, "1.4"): (
        "1b9248793911fc319e24112fce345bf27b6e2b96bc3bf5f576ade33a5c87729e",
        False,
    ),
    (COOLING, "1.5"): (
        "8400c36e298fd30f6fb034487165dd0a673298b2183e4787f02e9b56a4c5c64a",
        False,
    ),
    (COOLING, "1.6"): (
        "111cb1cb71cf5275e7daa7ef399e3dc013a70169c1908d319f23c9b054964cc8",
        True,
    ),
    (COOLING, "1.7"): (
        "1cf2aa786ff45a2dd97aef52c6f45781f46a49817c45e2be59fdb1097bdc6e56",
        False,
    ),
    (COOLING, "1.8"): (
        "688a6da18ec607b9f4b685b1668bb67e71ae67a096647c9a40cb91961d419da3",
        False,
    ),
    (MOTOR, "1.4"): (
        "183571ae6bf19d523ef5b25df1f710b8e9b6aad6366c0b0c5000303b1f8db262",
        False,
    ),
    (MOTOR, "1.5"): (
        "df4fb4fb7ec780e3de8ace7f8df51d0a6a793170a721b9f960ac0696dd9bf4bc",
        True,
    ),
    (MOTOR, "1.6"): (
        "d20e27149881f84debd19d61485e8cc015955d9153a9ac6fbf0efbbd0fc26925",
        False,
    ),
    (MOTOR, "1.8"): (
        "c68499439d0634288e700c4b59e7c032dc29caecc7e707a452e08f7e6f544080",
        True,
    ),
    ("f02", "2.4"): (
        "5322efb8ff6ca7cab897ffe8c00a1a1238e2eb26b2a9a7babe6a729fff991e74",
        False,
    ),
    ("f02", "2.5"): (
        "f023373439b2ddc43bf83ba6bcb8d373b7785f3ee663a6d8e07d59cae4163811",
        True,
    ),
    (F08, "1.5"): (
        "70e63cb99b616032071503a29fdf4a4b0077f2c10686aa75d0892b4f4ecf424c",
        False,
    ),
    (F08, "1.6"): (
        "dd5f549615ddeedafa873432d93d2d356b26f74baff94e32cda47cc5be49a7b5",
        False,
    ),
    (F08, "1.7"): (
        "e5b46336d1c213159269f5a82a3316d9a9f121a00a81b2d7c9dfd9403a8817b4",
        True,
    ),
}

_PROGRAM = r"""
import json, sys
from carbon.challenge_kit import version_overlay
from carbon.challenge_registry import exam_registry
version_overlay.install(path=sys.argv[1])
exam_registry.install(sys.argv[2])
from carbon.challenge_registry import published_exam as pe
key = ("zz-synthetic", "0.1")
print(json.dumps({
    "block": pe.for_version(*key),
    "pool": key in pe._POOL_VERSIONS,
    "registered": pe.registered_pool(*key),
    "from_registry": sorted(pe.FROM_REGISTRY),
    "refused": {" ".join(k): v for k, v in pe.REFUSED.items()},
    "others": [list(k) for k in pe.served() if k != key],
}))
"""


def _digest(key):
    body = json.dumps(
        pe.for_version(*key), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(body.encode()).hexdigest()


def _named(path=FIXTURE):
    raw = (REPOSITORY / path).read_bytes()
    return {"path": path, "sha256": hashlib.sha256(raw).hexdigest()}


def _run(tmp_path, row):
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
    registry = tmp_path / "exam_registry.json"
    document = {
        "schema": exam_registry.SCHEMA,
        "source": "test",
        "exams": {"zz-synthetic 0.1": row},
    }
    registry.write_text(json.dumps(document), encoding="utf-8")
    done = subprocess.run(
        [sys.executable, "-c", _PROGRAM, str(overlay), str(registry)],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    )
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert out["others"] == [list(key) for key in pe.served()]
    return out


@pytest.mark.parametrize("key", sorted(BLOCKS))
def test_every_published_block_is_mains_byte_for_byte(key):
    digest, registered = BLOCKS[key]
    assert _digest(key) == digest
    assert (pe.registered_pool(*key) is not None) == registered
    assert key not in pe.FROM_REGISTRY


def test_the_committed_registry_publishes_no_refused_file():
    assert pe.REFUSED == {}
    assert {key for key in exam_registry.keys("published")} == pe.FROM_REGISTRY


def test_the_code_registrations_are_the_reading_of_their_constants_rows():
    rows = pe._constants_rows()
    for key in sorted(BLOCKS):
        kind = pe.MENU_HEADROOM if key == (MOTOR, "1.8") else pe.PICK_D
        if not BLOCKS[key][1]:
            continue
        own = pe.registered_pool(*key)
        read = pe.registration(kind, rows[" ".join(key)])
        assert {**own, "source": None} == {**read, "source": None}, key
    assert pe.registration(pe.PICK_D, None) is None
    incomplete = {**rows[f"{MOTOR} 1.8"], "menu": "HUMAN_INPUT"}
    assert pe.registration(pe.MENU_HEADROOM, incomplete) is None


def test_a_rows_file_is_published_under_its_own_sealed_evaluation(tmp_path):
    row = {
        "published": _named(),
        "solver_seconds_per_design": {"value": 100, "source": "synthetic"},
    }
    out = _run(tmp_path, row)
    block = out["block"]
    assert out["pool"] and out["from_registry"] == [list(KEY)] and out["refused"] == {}
    assert block["schema"] == pe.SCHEMA_POOL
    assert set(block) <= pe.ALLOWED_FIELDS
    assert block["scope"] == "zz-synthetic 0.1"
    assert block["scoring_version"] == "zz-synthetic-pool-sealed-v1"
    assert [gate["id"] for gate in block["gates"]] == [
        "finite_outputs",
        "physics_pool",
        "speed",
    ]
    assert block["speed_gate"]["solver_seconds_per_design"] == 100
    assert block["speed_gate"]["ceiling_seconds_per_design"] == 0.2
    speed = [line for line in block["how_you_are_tested"] if line["id"] == "speed"]
    assert "0.2 s per design" in speed[0]["text"]
    # no pool-constants row: published, RESERVED, and it grades nothing
    assert out["registered"] is None


@pytest.mark.parametrize(
    "row",
    [
        # no solver seconds: no speed gate, so nothing is published
        {"published": {"path": FIXTURE, "sha256": "FILE"}},
        {"published": {"path": FIXTURE, "sha256": "0" * 64}},
        {"published": {"path": "tests/fixtures/absent.json", "sha256": "0" * 64}},
    ],
)
def test_a_file_that_does_not_hold_up_is_refused_and_its_version_has_no_block(
    tmp_path, row
):
    if row["published"]["sha256"] == "FILE":
        row = {"published": _named()}
    else:
        row = {
            **row,
            "solver_seconds_per_design": {"value": 100, "source": "synthetic"},
        }
    out = _run(tmp_path, row)
    assert out["block"] is None and out["registered"] is None
    assert list(out["refused"]) == ["zz-synthetic 0.1"] and out["from_registry"] == []
    # still pool-graded: an unpublished pool version is never read as another kind
    assert out["pool"]


@pytest.mark.parametrize(
    "change",
    [
        {"schema": "other"},
        {"version": "zz-synthetic 0.2"},
        {"kind": "other"},
        {"a_acc": ""},
        {"gates": []},
        {"gates": [{"id": "speed", "passes_when": "x", "value": None}]},
        {"gates": [{"id": "a", "passes_when": "x"}]},
        {"sections": {}},
        {"sections": {"minimums": {"rule": "x"}, "score": {}}},
        {"sections": {"minimums": {"rule": "x"}, "koth": {}}},
        {"extra": 1},
    ],
)
def test_a_files_shape_is_closed(tmp_path, monkeypatch, change):
    document = json.loads((REPOSITORY / FIXTURE).read_bytes())
    monkeypatch.setattr(pe, "_ROOT", tmp_path)

    def ask(value):
        raw = json.dumps(value).encode()
        (tmp_path / "file.json").write_bytes(raw)
        named = {"path": "file.json", "sha256": hashlib.sha256(raw).hexdigest()}
        return pe._published_file(KEY, named)

    assert ask(document) == document
    with pytest.raises(ValueError, match="^file_"):
        ask({**document, **change})


def test_the_speed_figures_are_the_gates():
    for key in BLOCKS:
        block = pe.for_version(*key)
        if "speed_gate" in block:
            assert block["speed_gate"]["ceiling_seconds_per_design"] == (
                speed_gate.ceiling_seconds(*key)
            )
