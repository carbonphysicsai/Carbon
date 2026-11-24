"""The build half of the exam registry: closed blocks, code-served versions never read from a row, live rows byte-equal."""

from __future__ import annotations

import builtins
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import carbon
from carbon.challenge_kit import (
    physical_material,
    physical_pack,
    physical_public_train,
    version_overlay,
    version_registry,
)
from carbon.challenge_kit.task_wall_overrides import total_wall_seconds
from carbon.challenge_registry import code_served, exam_build, exam_registry
from carbon.development_session import direct_graph_construction_worker as worker
from carbon.development_session import physical_graph_adapter_v2 as adapter
from carbon.development_session.research_service import _practice_dtype

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
    real_require = exam_registry.require
    monkeypatch.setattr(
        exam_registry,
        "require",
        lambda cid, version, name: (
            copy.deepcopy(held.get("block"))
            if (cid, version) == KEY
            else real_require(cid, version, name)
        ),
    )
    real_overlay, real_entry = version_overlay.is_overlay, version_registry.entry
    monkeypatch.setattr(
        version_overlay, "is_overlay", lambda *key: key == KEY or real_overlay(*key)
    )
    monkeypatch.setattr(
        version_registry,
        "entry",
        lambda *key: (
            SimpleNamespace(
                rebuild_wall_seconds=648,
                graph_adapter=held.get("adapter", "v2"),
                train=held.get("train"),
                predecessor=None,
            )
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
    """Every overlay version a code table serves (a Spec, or a TRAIN the code loads) is named; a later version is a row."""
    served = {
        key for key in version_registry.VERSIONS if version_overlay.is_overlay(*key)
    }
    assert served <= code_served.CODE_SERVED_OVERLAY
    trains = {
        *physical_public_train.EXTENDED,
        *physical_public_train.FRESH_LAMBDA,
        *physical_public_train.MAGNET_TRAIN,
    }
    for key in served:
        assert key in adapter.SPECS or version_registry.entry(*key).train in trains
    assert len(code_served.CODE_SERVED_OVERLAY) == 5


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
        _block(total_wall_seconds=version_registry.task_wall_seconds(648) - 1),
        _block(total_wall_seconds=2000.0),
        _block(total_wall_seconds=None),
        _block(nonfinite_rule="always_free"),
        _block(nonfinite_rule=None),
        _block(graph_spec=_spec(trust_outputs=1), inference_program="per_case"),
    ],
)
def test_a_bad_block_refuses_itself(row, block):
    row["block"] = block
    with pytest.raises(exam_build.ExamBuildRefused):
        exam_build.block(*KEY)
    with pytest.raises(exam_build.ExamBuildRefused):
        exam_build.module(*KEY)
    assert exam_build.keys() == ()
    assert KEY in exam_build.refused()
    assert not issubclass(exam_build.ExamBuildRefused, ValueError)


#: A NEW version of a built-in family: an overlay entry no code names, whose row is refused.
_NEXT_PROGRAM = r"""
import json, sys
from pathlib import Path
import carbon
from carbon.challenge_kit import version_overlay
folder = Path(sys.argv[1])
version_overlay.install(path=folder / "overlay.json")
from carbon.challenge_registry import exam_build, exam_registry
exam_registry.install(path=folder / "exams.json")
from carbon.challenge_kit import physical_material, physical_pack, physical_public_train
from carbon.development_session import bundle_construction_worker, physical_graph_adapter_v2
KEY = tuple(sys.argv[2:4])
binding = {"id": KEY[0], "version": KEY[1]}
SITES = {
    "kit": lambda: physical_material.construction_kit(*KEY),
    "limits": lambda: physical_material.construction_limits_document(*KEY),
    "bundle": lambda: physical_material.bundle_material(*KEY),
    "physics": lambda: physical_pack.physics_contract(*KEY),
    "roles": lambda: physical_pack.public_roles(*KEY),
    "bank": lambda: physical_pack.development_bank(*KEY),
    "train": lambda: physical_public_train.load_public_train(*KEY),
    "spec": lambda: physical_graph_adapter_v2.spec_for(*KEY),
    "policy": lambda: bundle_construction_worker.verify_direct_resource_policy(binding, {}),
}
out = {}
for name, ask in SITES.items():
    try:
        ask()
        out[name] = "SERVED"
    except exam_build.ExamBuildRefused:
        out[name] = "refused"
    except BaseException as error:
        out[name] = type(error).__name__
out["live"] = physical_material.construction_kit(sys.argv[2], sys.argv[4])["version"]
print(json.dumps(out))
"""


@pytest.mark.parametrize(
    "challenge_id, live", [("f08-ribbed-bracket", "1.7"), ("chip-cold-plate", "1.8")]
)
@pytest.mark.parametrize(
    "row",
    [
        {"build": {"module": MODULE}},
        {"build": _block(sha256="0" * 64)},
        {"build": _block(), "solver_seconds_per_design": {"value": -1}},
    ],
)
def test_a_refused_row_of_a_built_in_family_is_never_served_by_the_family(
    tmp_path, challenge_id, live, row
):
    version = "9.1"
    base = version_registry.entry(challenge_id, live)
    entry = {
        "challenge_id": challenge_id,
        "version": version,
        "train": base.train,
        "allowlist": "v8",
        "step_caps": False,
        "pack_version": "zz-development-1",
        "development_evaluation": None,
        "sealed_evaluation": "zz-sealed-v1",
        "campaign": "catalog",
        "catalog": True,
        "graph_adapter": "v2",
        "catalog_entries_from": [],
        "predecessor": live,
        "rebuild_wall_seconds": 648,
    }
    name = f"{challenge_id} {version}"
    (tmp_path / "overlay.json").write_text(
        json.dumps({"schema": version_overlay.SCHEMA, "versions": {name: entry}})
    )
    (tmp_path / "exams.json").write_text(
        json.dumps(
            {
                "schema": exam_registry.SCHEMA,
                "source": "synthetic",
                "exams": {name: row},
            }
        )
    )
    done = subprocess.run(
        [
            sys.executable,
            "-c",
            _NEXT_PROGRAM,
            str(tmp_path),
            challenge_id,
            version,
            live,
        ],
        cwd=FIXTURES.parents[2],
        capture_output=True,
        text=True,
        timeout=600,
        check=True,
    )
    result = json.loads(done.stdout.strip().splitlines()[-1])
    assert result.pop("live") == live
    assert set(result.values()) == {"refused"}, result


def test_the_row_names_its_own_whole_task_wall_and_no_other_moves(row):
    walls = {
        key: total_wall_seconds(*key, 648) for key in sorted(version_registry.VERSIONS)
    }
    floor = version_registry.task_wall_seconds(648)
    assert total_wall_seconds(*KEY, 648) == floor
    row["block"] = _block(total_wall_seconds=floor + 100)
    assert total_wall_seconds(*KEY, 648) == floor + 100
    assert walls == {key: total_wall_seconds(*key, 648) for key in walls}
    assert walls[("electric-motor-magnetics", "1.8")] == 1590


def test_the_practice_dtype_of_every_code_served_family_is_unchanged():
    for challenge_id, version in version_registry.VERSIONS:
        key = SimpleNamespace(challenge_id=challenge_id, version=version)
        small = challenge_id in ("f08-ribbed-bracket", "f02")
        assert _practice_dtype(key, float64_family=True) == (
            np.float32 if small else np.float64
        )
        assert _practice_dtype(key, float64_family=False) == np.float32


def test_a_version_without_graph_route_v2_names_no_spec(row):
    row["adapter"] = None
    row["block"] = _block()
    with pytest.raises(exam_build.ExamBuildRefused):
        exam_build.block(*KEY)
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


def test_a_refused_row_met_in_a_build_is_carbon_s_failure():
    """FAILED_INFRA (re-run free), never REFUSED or UNRESOLVED; any other exception keeps its class."""
    from carbon.development_session import research_tasks

    refused = exam_build.ExamBuildRefused("build_block_fields")
    assert research_tasks._failure_is_carbons(refused, [])
    assert research_tasks._failure_is_carbons(refused, ["SUCCEEDED"])
    assert not research_tasks._failure_is_carbons(RuntimeError("other"), [])


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
    assert (key in adapter.SPECS) == ("adapter_block" in golden)
    if key in adapter.SPECS:
        assert _doc(adapter.adapter_block(*key)) == golden["adapter_block"]
        program = worker.v2_infer_query(*key)["program"].encode()
        assert hashlib.sha256(program).hexdigest() == golden["program"]


def test_the_code_declares_every_spec_and_stages_no_extra_file_for_one():
    assert set(adapter.SPECS) == adapter.CODE_SPECS
    key = ("electric-motor-magnetics", "1.8")
    spec = adapter.SPECS[key]
    _, _, files = worker._v2_stage(
        {
            "challenge_id": key[0],
            "challenge_version": key[1],
            "train_digest": "sha256:" + spec.train_sha256,
        },
        physical_material.construction_limits_document(*key),
        adapter.served_allowlist_bytes(*key),
    )
    assert set(files) == {name + ".py" for name in worker.PHYSICAL_V2_STAGED_MODULES}


@pytest.mark.parametrize(
    "module",
    [
        "carbon.challenge_registry.exam_build",
        "carbon.challenge_registry.pinned_module",
        "carbon.challenge_kit.physical_material",
        "carbon.challenge_kit.physical_pack",
        "carbon.challenge_kit.physical_public_train",
        "carbon.challenge_kit.task_wall_overrides",
        "carbon.development_session.bundle_construction_worker",
        "carbon.development_session.direct_graph_construction_worker",
        "carbon.development_session.physical_graph_adapter_v2",
        "carbon.development_session.research_service",
    ],
)
def test_each_build_module_imports_first_in_a_fresh_process(module):
    """No import cycle through `carbon.challenge_registry`, whichever module a process imports first."""
    subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=FIXTURES.parents[2],
        capture_output=True,
        check=True,
        timeout=300,
    )


@pytest.mark.parametrize(
    "missing",
    [
        "carbon.challenge_registry",
        "carbon.challenge_kit",
        "carbon.reconstruction.missing",
        "numpy",
    ],
)
def test_a_broken_host_import_raises_and_never_reads_as_a_container(
    monkeypatch, missing
):
    """A host is the tree that holds the registry package: an import that fails there is a failure, never 'no Specs'."""
    real = builtins.__import__

    def broken(asked, *rest, **more):
        if asked.startswith(("carbon.challenge_kit", "carbon.challenge_registry")):
            raise ModuleNotFoundError(name=missing)
        return real(asked, *rest, **more)

    assert adapter._ON_HOST
    with monkeypatch.context() as patch:
        patch.setattr(builtins, "__import__", broken)
        with pytest.raises(ModuleNotFoundError):
            adapter._registered_specs()


def test_a_tree_without_the_registry_package_is_a_container(tmp_path, monkeypatch):
    """Whatever else the process can import (an editable install of the repository included)."""
    monkeypatch.setattr(adapter, "_ON_HOST", False)
    monkeypatch.setattr(adapter, "_TREE", tmp_path)
    assert adapter._registered_specs() == {}
    spec = adapter.Spec(
        *KEY, "zz-adapter", "zz-train", "0" * 64, 8, 2, 1, "float64", None
    )
    (tmp_path / adapter.STAGED_SPEC).write_bytes(adapter.staged_spec(spec))
    assert adapter._registered_specs() == {KEY: spec}
    (tmp_path / adapter.STAGED_SPEC).write_bytes(b"{}")
    with pytest.raises(ValueError, match="staged graph spec differs"):
        adapter._registered_specs()


def test_no_staged_spec_file_lies_in_the_repository():
    assert adapter._TREE == FIXTURES.parents[2]
    assert not (adapter._TREE / adapter.STAGED_SPEC).exists()


@pytest.mark.parametrize(
    "key",
    [
        ("electric-motor-magnetics", "1.8"),
        ("chip-cold-plate", "1.8"),
        ("chip-cold-plate", "1.2"),
        ("chip-cold-plate", "1.6"),
    ],
)
def test_the_public_train_loader_imports_no_exam_registry_for_a_code_served_version(
    key,
):
    """Main's own closure (3e7a7fcf) plus exactly the three modules that tell which versions the code serves."""
    program = (
        "import json, sys; from carbon.challenge_kit import physical_public_train as p;"
        "p.load_public_train(*sys.argv[1:3]); print(json.dumps(sorted(sys.modules)))"
    )
    done = subprocess.run(
        [sys.executable, "-c", program, *key],
        cwd=FIXTURES.parents[2],
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )
    loaded = json.loads(done.stdout)
    registry = {m for m in loaded if m.startswith("carbon.challenge_registry")}
    assert registry == {
        "carbon.challenge_registry",
        "carbon.challenge_registry.code_served",
        "carbon.challenge_registry.registry",
    }
    for part in (
        "sealed",
        "pool_",
        "custody",
        "challenge_validator",
        "score_feed",
        "ledger",
    ):
        assert [m for m in loaded if part in m] == []


def test_a_registered_spec_reads_back_from_its_row(row):
    row["block"] = _block()
    row["train"] = "zz-train"
    spec = adapter._registered_specs()[KEY]
    assert spec.adapter_id == "zz-synthetic-public-jax-graph-v2"
    assert (spec.train_use, spec.predecessor) == ("zz-train", None)
    assert (spec.rows, spec.inputs, spec.outputs, spec.dtype) == (8, 2, 1, "float64")


def test_a_build_container_reads_the_one_staged_spec(tmp_path):
    """The container holds only the staged modules: a registry version's Spec is the staged file, a code one the code's."""
    spec = adapter.Spec(
        *KEY, "zz-adapter", "zz-train", "0" * 64, 8, 2, 1, "float64", None
    )
    for package in (
        "carbon",
        "carbon/challenge_validator",
        "carbon/level4",
        "carbon/development_session",
    ):
        (tmp_path / package).mkdir(parents=True, exist_ok=True)
        (tmp_path / package / "__init__.py").write_text("")
    root = Path(adapter.__file__).resolve().parents[2]
    for name in worker.PHYSICAL_V2_STAGED_MODULES:
        path = name.replace(".", "/") + ".py"
        (tmp_path / path).write_bytes((root / path).read_bytes())
    program = (
        "import sys; sys.path.insert(0, sys.argv[1])\n"
        "from carbon.development_session import physical_graph_adapter_v2 as a\n"
        "print(sorted(set(a.SPECS) - a.CODE_SPECS), len(a.CODE_SPECS))\n"
    )

    def ask():
        return subprocess.run(
            [sys.executable, "-c", program, str(tmp_path)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=300,
        ).stdout.strip()

    count = len(adapter.CODE_SPECS)
    assert ask() == f"[] {count}"
    (tmp_path / adapter.STAGED_SPEC).write_bytes(adapter.staged_spec(spec))
    assert ask() == f"[{KEY!r}] {count}"


def test_the_goldens_cover_the_live_rows():
    covered = {tuple(name.split(" ")) for name in GOLDENS}
    assert {
        ("electric-motor-magnetics", "1.8"),
        ("chip-cold-plate", "1.8"),
        ("f08-ribbed-bracket", "1.7"),
    } <= covered
    assert covered <= set(physical_material.REGISTERED)
