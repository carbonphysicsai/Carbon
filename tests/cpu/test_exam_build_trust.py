"""The self-trust training registration of a version registered by data: closed values, a pinned derive, live builds unmoved."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import carbon
from carbon.challenge_kit import version_overlay, version_registry
from carbon.challenge_registry import exam_build, exam_registry
from carbon.development_session import direct_graph_construction_worker as worker
from carbon.development_session import physical_graph_adapter_v2 as adapter
from carbon.development_session import physical_graph_trust_registry as registry
from carbon.development_session import registered_trust_derive

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "exam_registry"
KEY = ("zz-synthetic", "0.3")
#: The sha256 of the trust build program. REPIN PENDING (owner G-LEAD-122 removal): the program changed when a
#: version's own trust derive left the staged modules; release reads the new digest from the gate and it is pinned here.
TRUST_PROGRAM_SHA256 = (
    "f9fac9ddf80d8a429e9fe3317f3bb5323fbd939b3176c143b21e2d81eff5b1e0"
)


def _pinned(name):
    raw = (FIXTURES / f"{name}.py").read_bytes().replace(b"\r\n", b"\n")
    return {"module": f"carbon.{name}", "sha256": hashlib.sha256(raw).hexdigest()}


def _trust(**changes):
    return {
        "derive": _pinned("zz_synthetic_trust"),
        "sigma_floor": [0.0],
        "epochs": 3,
        "learning_rate": 0.002,
        **changes,
    }


def _block(trust=None, outputs=1, **changes):
    block = {
        **_pinned("zz_synthetic_build"),
        "graph_spec": {
            "train_sha256": "0" * 64,
            "rows": 8,
            "inputs": 2,
            "outputs": 1,
            "dtype": "float32",
            "trainer": "v2",
            "layout": None,
            "trust_outputs": outputs,
        },
        "inference_program": "compiled",
        **changes,
    }
    if trust is not None:
        block["trust"] = trust
    return block


@pytest.fixture
def row(monkeypatch):
    held = {"block": _block(_trust())}
    monkeypatch.setattr(exam_build, "_REFUSED", {})
    monkeypatch.setattr(carbon, "__path__", [*carbon.__path__, str(FIXTURES)])

    def field(cid, version, name):
        return copy.deepcopy(held["block"]) if (cid, version) == KEY else None

    monkeypatch.setattr(exam_registry, "field", field)
    monkeypatch.setattr(exam_registry, "require", field)
    real_overlay, real_entry = version_overlay.is_overlay, version_registry.entry
    monkeypatch.setattr(
        version_overlay, "is_overlay", lambda *key: key == KEY or real_overlay(*key)
    )
    monkeypatch.setattr(
        version_registry,
        "entry",
        lambda *key: (
            SimpleNamespace(
                graph_adapter="v2",
                rebuild_wall_seconds=648,
                train="zz-train",
                predecessor=None,
            )
            if key == KEY
            else real_entry(*key)
        ),
    )
    yield held
    for name in ("carbon.zz_synthetic_trust", "carbon.zz_synthetic_build"):
        sys.modules.pop(name, None)


def test_a_registered_row_trains_with_its_own_values_and_derive(row):
    entry = registry.registered(*KEY)
    assert entry["sigma_floor"] == (0.0,)
    assert (entry["epochs"], entry["learning_rate"]) == (3, 0.002)
    spec = registry.trust_spec(*KEY, width=1, outputs=1, trust_parameters=[2])
    assert spec.derive is entry["derive"] and spec.derive.__name__ == "derive"


def test_the_staged_bytes_are_the_registered_module_and_its_values(row):
    raw = exam_build.trust_derive_source(*KEY)
    assert hashlib.sha256(raw).hexdigest() == row["block"]["trust"]["derive"]["sha256"]
    values = json.loads(registry.staged_trust(*KEY, exam_build.trust(*KEY)))
    assert values == {
        "challenge_id": KEY[0],
        "version": KEY[1],
        "sigma_floor": [0.0],
        "epochs": 3,
        "learning_rate": 0.002,
    }


@pytest.mark.parametrize(
    "change",
    [
        {"sigma_floor": []},
        {"sigma_floor": [0.0, 0.0]},
        {"sigma_floor": [-1.0]},
        {"sigma_floor": [None]},
        {"sigma_floor": ["HUMAN_INPUT"]},
        {"sigma_floor": [float("nan")]},
        {"sigma_floor": [10**400]},
        {"sigma_floor": [True]},
        {"epochs": 0},
        {"epochs": None},
        {"epochs": 1.0},
        {"epochs": True},
        {"learning_rate": 0},
        {"learning_rate": "HUMAN_INPUT"},
        {"learning_rate": None},
        {"derive": {"module": "carbon.zz_synthetic_trust", "sha256": "0" * 64}},
        {"derive": {"module": "os", "sha256": "0" * 64}},
        {"derive": None},
        {"extra": 1},
    ],
)
def test_a_value_the_owner_has_not_set_or_a_wrong_derive_refuses(row, change):
    row["block"] = _block(_trust(**change))
    with pytest.raises(exam_build.ExamBuildRefused):
        exam_build.block(*KEY)


@pytest.mark.parametrize(
    "block",
    [
        _block(None, outputs=1),
        _block(_trust(), outputs=0),
        _block({}, outputs=1),
        _block(_trust(sigma_floor=[0.0]), outputs=2),
    ],
)
def test_the_trust_registration_is_exactly_the_spec_s_trust_outputs(row, block):
    row["block"] = block
    with pytest.raises(exam_build.ExamBuildRefused):
        exam_build.block(*KEY)


@pytest.mark.parametrize(
    "source",
    [
        b"from carbon.scoring import pool_exam\ndef derive(rows, inputs):\n    return rows\n",
        b"from . import other\ndef derive(rows, inputs):\n    return rows\n",
        b"def derive(rows, inputs):\n    import os\n    return rows\n",
        b"import subprocess\ndef derive(rows, inputs):\n    return rows\n",
        b"derive = None\n",
        b"def other(rows, inputs):\n    return rows\n",
        b"def derive(:\n",
    ],
)
def test_a_derive_that_needs_more_than_its_container_has_is_refused(source):
    with pytest.raises(exam_build.ExamBuildRefused):
        exam_build._check_derive(source)


def test_a_derive_may_import_jax_numpy_and_the_standard_math():
    exam_build._check_derive(
        b"from __future__ import annotations\nimport math\n"
        b"def derive(rows, inputs):\n    import jax.numpy as jnp\n    import numpy as np\n    return rows\n"
    )


def test_the_host_module_holds_no_derive():
    assert registered_trust_derive.derive is None
    assert worker.REGISTERED_TRUST_DERIVE == registered_trust_derive.__name__


def test_the_trust_program_is_pinned_and_a_registry_version_adds_only_its_derive():
    # no version registers trust values in code on this tree (owner G-LEAD-122: they live on carbon-internal)
    assert set(registry.REGISTRATIONS) == set()
    digest = hashlib.sha256(worker.PHYSICAL_V2_TRUST_BUILD_PROGRAM.encode()).hexdigest()
    assert digest == TRUST_PROGRAM_SHA256
    restored = worker.PHYSICAL_V2_REGISTERED_TRUST_BUILD_PROGRAM.replace(
        repr(
            (
                *worker.PHYSICAL_V2_TRUST_STAGED_MODULES,
                worker.REGISTERED_TRUST_DERIVE,
            )
        ),
        repr(worker.PHYSICAL_V2_TRUST_STAGED_MODULES),
    )
    assert restored == worker.PHYSICAL_V2_TRUST_BUILD_PROGRAM
    assert worker.REGISTERED_TRUST_DERIVE not in worker.PHYSICAL_V2_TRUST_STAGED_MODULES


_CONTAINER = r"""
import sys
sys.path.insert(0, sys.argv[1])
from carbon.development_session import physical_graph_trust_registry as registry
assert registry.__file__.startswith(sys.argv[1])
entry = registry.registered("zz-synthetic", "0.3")
print(None if entry is None else (entry["sigma_floor"], entry["epochs"], entry["learning_rate"], entry["derive"].__name__))
try:
    print(registry.registered("zz-synthetic", "0.4"))
except ValueError as refused:
    print("refused", refused)
"""


def test_the_build_container_reads_the_staged_values_and_derive(row, tmp_path):
    """The container's tree holds only the staged modules; without the staged files a version registers nothing there."""
    for package in (
        "carbon",
        "carbon/challenge_validator",
        "carbon/level4",
        "carbon/development_session",
    ):
        (tmp_path / package).mkdir(parents=True, exist_ok=True)
        (tmp_path / package / "__init__.py").write_text("")
    root = Path(adapter.__file__).resolve().parents[2]
    for name in worker.PHYSICAL_V2_TRUST_STAGED_MODULES:
        path = name.replace(".", "/") + ".py"
        (tmp_path / path).write_bytes((root / path).read_bytes())

    def ask():
        done = subprocess.run(
            [sys.executable, "-c", _CONTAINER, str(tmp_path)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=300,
            check=True,
        )
        return done.stdout.split("\n")[:2]

    assert ask() == ["None", "None"]
    derive = worker.REGISTERED_TRUST_DERIVE.replace(".", "/") + ".py"
    (tmp_path / derive).write_bytes(exam_build.trust_derive_source(*KEY))
    (tmp_path / registry.STAGED_TRUST).write_bytes(
        registry.staged_trust(*KEY, exam_build.trust(*KEY))
    )
    first, second = ask()
    assert first == "((0.0,), 3, 0.002, 'derive')"
    # another version's staged values are never read as this one's
    assert second == "refused staged graph trust differs"
