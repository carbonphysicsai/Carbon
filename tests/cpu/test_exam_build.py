"""The build half of the exam registry: closed blocks, code-served versions never read from a row, live rows byte-equal."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import carbon
from carbon.challenge_kit import (
    physical_material,
    physical_pack,
    version_overlay,
    version_registry,
)
from carbon.challenge_registry import exam_build, exam_registry
from carbon.development_session import physical_graph_adapter_v2 as adapter

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "exam_registry"
#: Every registered version's build documents on main d2c356f5, read BEFORE the build sites asked the registry
#: (release ran the golden reader on a clean checkout). Public digests only.
GOLDENS = json.loads((FIXTURES / "build_goldens.json").read_bytes())
KEY = ("zz-synthetic", "0.1")
MODULE = "carbon.zz_synthetic_build"
SOURCE = FIXTURES / "zz_synthetic_build.py"


def _block(**changes):
    block = {
        "module": MODULE,
        "sha256": hashlib.sha256(
            SOURCE.read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "graph_spec": {
            "train_sha256": "0" * 64,
            "rows": 8,
            "inputs": 2,
            "outputs": 1,
            "dtype": "float64",
            "trainer": "v2",
            "layout": None,
            "trust_outputs": 0,
        },
        "inference_program": "compiled",
    }
    block.update(changes)
    return block


@pytest.fixture
def row(monkeypatch):
    """A registered synthetic version whose exam registry row carries the block the test puts in it."""
    held = {}
    monkeypatch.setattr(exam_build, "_REFUSED", {})
    monkeypatch.setattr(carbon, "__path__", [*carbon.__path__, str(FIXTURES)])
    monkeypatch.setattr(
        exam_registry,
        "field",
        lambda cid, version, name: (
            copy.deepcopy(held.get("block")) if (cid, version) == KEY else None
        ),
    )
    monkeypatch.setattr(
        exam_registry, "keys", lambda name: (KEY,) if "block" in held else ()
    )
    real_overlay, real_entry = version_overlay.is_overlay, version_registry.entry
    monkeypatch.setattr(
        version_overlay, "is_overlay", lambda *key: key == KEY or real_overlay(*key)
    )
    monkeypatch.setattr(
        version_registry,
        "entry",
        lambda *key: (
            SimpleNamespace(graph_adapter=held.get("adapter", "v2"))
            if key == KEY
            else real_entry(*key)
        ),
    )
    yield held
    sys.modules.pop(MODULE, None)


def test_the_repository_registers_no_build_row():
    assert exam_build.keys() == ()
    assert exam_build.graph_specs() == {}
    assert exam_build.versions_running(*exam_build.PROGRAMS) == frozenset()


def test_every_version_the_code_serves_is_code_served():
    for key in version_registry.VERSIONS:
        assert exam_build.code_serves(*key), key
        assert exam_build.block(*key) is None
    assert set(adapter.SPECS) <= {
        key for key in version_registry.VERSIONS if exam_build.code_serves(*key)
    }


def test_the_code_served_overlay_list_is_closed():
    """It names the versions the code's tables serve on the host overlay; a later version is a registry row."""
    assert len(exam_build.CODE_SERVED_OVERLAY) == 5


def test_a_good_block_serves_its_module(row):
    row["block"] = _block()
    assert exam_build.keys() == (KEY,)
    module = exam_build.module(*KEY)
    assert module.__name__ == MODULE
    assert exam_build.graph_specs()[KEY]["rows"] == 8
    assert exam_build.versions_running("compiled", "per_case") == {KEY}
    assert exam_build.versions_running("eager") == frozenset()
    with pytest.raises(KeyError):
        exam_build.versions_running("fast")


def _spec(**changes):
    return {**_block()["graph_spec"], **changes}


@pytest.mark.parametrize(
    "block",
    [
        {},
        {"module": MODULE},
        _block(extra=1),
        _block(sha256="0" * 64),
        _block(module="carbon.no_such_module"),
        _block(module="os"),
        _block(graph_spec=None),
        _block(inference_program=None),
        _block(inference_program="fast"),
        _block(graph_spec=_spec(rows=0)),
        _block(graph_spec=_spec(rows=8.0)),
        _block(graph_spec=_spec(dtype="float16")),
        _block(graph_spec=_spec(trainer="v9")),
        _block(graph_spec=_spec(layout={"slices": 1})),
        _block(graph_spec=_spec(trust_outputs=-1)),
        _block(graph_spec=_spec(train_sha256="00")),
        _block(graph_spec={"rows": 8}),
        _block(graph_spec=_spec(trust_outputs=1), inference_program="per_case"),
    ],
)
def test_a_bad_block_refuses_itself(row, block):
    row["block"] = block
    assert exam_build.block(*KEY) is None
    assert exam_build.module(*KEY) is None
    assert exam_build.keys() == ()
    assert KEY in exam_build.refused()


def test_a_version_without_graph_route_v2_names_no_spec(row):
    row["adapter"] = None
    row["block"] = _block()
    assert exam_build.block(*KEY) is None
    row["block"] = _block(graph_spec=None, inference_program=None)
    assert exam_build.keys() == (KEY,)
    assert exam_build.graph_specs() == {}


def test_a_code_served_version_is_never_read_from_a_row(row, monkeypatch):
    live = ("electric-motor-magnetics", "1.8")
    monkeypatch.setattr(exam_registry, "field", lambda *asked: _block())
    assert exam_build.block(*live) is None
    assert exam_build.refused()[live] == "build_version_is_code_served"
    assert physical_material._public(*live) is physical_material._public(live[0])


def test_an_incomplete_module_refuses(row, monkeypatch):
    row["block"] = _block()
    module = exam_build.module(*KEY)
    monkeypatch.delattr(module, "public_roles")
    with pytest.raises(exam_build.ExamBuildRefused, match="public_roles"):
        exam_build.module(*KEY)


def _doc(value):
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False, default=list
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def _bank(value):
    digest = hashlib.sha256()
    digest.update(
        json.dumps([list(value["case_ids"]), list(value["cohorts"])]).encode()
    )
    for name in ("inputs", "references"):
        digest.update(str(value[name].dtype).encode() + str(value[name].shape).encode())
        digest.update(value[name].tobytes())
    return digest.hexdigest()


@pytest.mark.parametrize("name", sorted(GOLDENS))
def test_every_live_build_document_is_the_one_main_served(name):
    key = tuple(name.split(" "))
    golden = GOLDENS[name]
    assert physical_material.construction_kit(*key) == golden["kit"]
    limits = physical_material.construction_limits_document(*key)
    assert _doc(limits) == golden["limits"]
    assert _doc(physical_pack.physics_contract(*key)) == golden["physics"]
    roles = {
        role: hashlib.sha256(raw).hexdigest()
        for role, raw in physical_pack.public_roles(*key).items()
    }
    assert roles == golden["roles"]
    assert _bank(physical_pack.development_bank(*key)) == golden["bank"]


def test_the_goldens_cover_the_live_rows():
    covered = {tuple(name.split(" ")) for name in GOLDENS}
    assert {
        ("electric-motor-magnetics", "1.8"),
        ("chip-cold-plate", "1.8"),
        ("f08-ribbed-bracket", "1.7"),
    } <= covered
    assert covered <= set(physical_material.REGISTERED)
