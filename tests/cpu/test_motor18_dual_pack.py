"""Motor 1.8's sealed adapter through a version-overlay dispatch (a TEMPORARY overlay file; the production overlay gains
the 1.8 entry only at the TRAIN freeze). Checks: 1.8 routes to its own module, every other version delegates unchanged,
the earlier Motor producer identity does not move, 1.8 refuses to measure until its extended TRAIN is frozen, and its
pool binding (absolute pk-pk) is reached through `pool_version` with `pool_adapters.py` untouched. Test values only.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.scoring import motor18_dual_pack, pool_adapters, pool_version

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "carbon" / "scoring" / "motor18_dual_pack.py"


def _entry():
    return {
        "challenge_id": "electric-motor-magnetics",
        "version": "1.8",
        "train": motor18_dual_pack.TRAIN,
        "allowlist": "v8",
        "step_caps": False,
        "pack_version": "motor-normal-construction-development-test-1p8",
        "development_evaluation": [
            "motor-dual-development-grid-v2",
            "motor-development-grid-8x6",
        ],
        "sealed_evaluation": motor18_dual_pack.POOL_VERSIONS["1.8"][0],
        "campaign": "catalog",
        "catalog": True,
        "graph_adapter": "v2",
        "catalog_entries_from": [],
        "predecessor": "1.6",
        "rebuild_wall_seconds": 648,
        "dispatch": {
            "module": "carbon.scoring.motor18_dual_pack",
            "sha256": hashlib.sha256(
                MODULE.read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest(),
            "config": {},
        },
    }


CODE = "\n".join(  # noqa: FLY002
    [
        "import json, sys",
        "from carbon.challenge_kit import version_overlay, version_registry",
        "from carbon.scoring import motor_sealed_dual_pack as sealed, pool_adapters, pool_version",
        "pa_before = pool_adapters.__file__",
        "before = sealed.producer_digest()",
        "fifteen = sealed.adapter('1.5')",
        "version_overlay.install(sys.argv[1])",
        "from carbon.scoring import motor18_dual_pack as m18",
        "out = {",
        " 'pool': list(sealed.POOL_VERSIONS['1.8']),",
        " 'module_18': sealed.adapter('1.8')._module.__name__,",
        " 'module_16': sealed.adapter('1.6')._module.__name__,",
        " 'module_15': type(sealed.adapter('1.5')).__name__ == type(fifteen).__name__,",
        " 'digest_same': sealed.producer_digest() == before,",
        " 'digest_18_differs': m18.producer_digest() != before,",
        " 'registered': version_registry.find('electric-motor-magnetics', '1.8') is not None,",
        " 'binding_registered': ('motor', '1.8') in pool_version._BINDINGS,",
        " 'binding_16_unregistered': ('motor', '1.6') not in pool_version._BINDINGS,",
        "}",
        "try:",
        "    m18._train()",
        "    out['train'] = 'loaded'",
        "except ValueError as error:",
        "    out['train'] = str(error)",
        "print(json.dumps(out))",
    ]
)


def _run(overlay):
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, "-c", CODE, str(overlay)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


@pytest.fixture
def overlay(tmp_path):
    document = json.loads(
        (
            ROOT / "scripts" / "validator_host_classes" / "version_overlay.json"
        ).read_bytes()
    )
    document["versions"]["electric-motor-magnetics 1.8"] = _entry()
    path = tmp_path / "version_overlay.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


@pytest.fixture
def clean_bindings():
    saved = dict(pool_version._BINDINGS)
    pool_version._BINDINGS.clear()
    yield
    pool_version._BINDINGS.clear()
    pool_version._BINDINGS.update(saved)


def test_motor_1_8_routes_to_its_own_module_and_nothing_else_moves(overlay):
    result = _run(overlay)
    assert result.returncode == 0, result.stderr[-2000:]
    out = json.loads(result.stdout.strip().splitlines()[-1])
    assert out["registered"]
    assert out["pool"] == list(motor18_dual_pack.POOL_VERSIONS["1.8"])
    assert out["module_18"] == "carbon.scoring.motor18_dual_pack"
    assert out["module_16"] == "carbon.scoring.motor_pool_baseline_dual_pack"
    assert out["module_15"]
    assert out["digest_same"] and out["digest_18_differs"]
    assert out["binding_registered"] and out["binding_16_unregistered"]
    assert "not frozen yet" in out["train"]


def test_a_changed_module_file_is_refused_before_import(overlay):
    document = json.loads(overlay.read_bytes())
    document["versions"]["electric-motor-magnetics 1.8"]["dispatch"]["sha256"] = (
        "0" * 64
    )
    overlay.write_text(json.dumps(document), encoding="utf-8")
    result = _run(overlay)
    assert result.returncode != 0 and "sha256 does not match" in result.stderr


def test_the_dispatch_takes_no_config_and_answers_only_1_8(clean_bindings):
    with pytest.raises(ValueError, match="no config"):
        motor18_dual_pack.dispatch({"baseline_box": {}})
    spec = motor18_dual_pack.dispatch({})
    assert spec["version"] == "1.8" and spec["challenge"] == "electric-motor-magnetics"
    assert motor18_dual_pack.sealed_adapter("1.6") is None
    with pytest.raises(ValueError, match="Motor 1.8 packs only"):
        motor18_dual_pack._writer(None, None, version="1.6")
    motor18_dual_pack.dispatch({})  # idempotent: the same factory again


def test_1_8_reads_its_own_train_never_train_150():
    from carbon.challenge_kit import physical_public_train as ppt

    assert motor18_dual_pack.TRAIN != "motor-dev-train-150-v1"
    assert motor18_dual_pack.TRAIN in ppt.EXTENDED


def test_pool_adapters_py_is_untouched_and_still_a_live_producer_file():
    from carbon.scoring import f08_sanity_dual_pack

    assert "pool_adapters.py" in f08_sanity_dual_pack.FILES
    assert "worst_case_torque_ripple_pk_pk_nm" not in (
        ROOT / "carbon" / "scoring" / "pool_adapters.py"
    ).read_text(encoding="utf-8")


# --- the pool binding hook ------------------------------------------------------------------------------------------


def test_an_unregistered_version_keeps_pool_adapters_binding(
    clean_bindings, monkeypatch
):
    seen = []
    monkeypatch.setattr(
        pool_adapters,
        "official_binding",
        lambda kind, version: seen.append((kind, version)) or "theirs",
    )
    assert pool_version.official_binding("motor", "1.6") == "theirs"
    pool_version.register_binding("motor", "1.8", lambda: "mine")
    assert pool_version.official_binding("motor", "1.8") == "mine"
    assert seen == [("motor", "1.6")]


def test_a_registered_binding_is_add_only(clean_bindings):
    def first():
        return 1

    pool_version.register_binding("motor", "1.8", first)
    pool_version.register_binding("motor", "1.8", first)
    with pytest.raises(ValueError, match="already has a different pool binding"):
        pool_version.register_binding("motor", "1.8", lambda: 2)


# --- the absolute pk-pk binding -------------------------------------------------------------------------------------


def _roles():
    names = ["airgap_mm", "magnet_mm"]
    return lambda kind, version: (SimpleNamespace(), {}, {}, names)


def _flat(level, ripple=0.0, extra=0):
    from carbon.motor.domain import ANGLE_STEPS

    return [level + (ripple if i == 0 else 0.0) for i in range(ANGLE_STEPS)] + [
        0.01
    ] * extra


def test_the_binding_derives_absolute_pk_pk_from_the_60_angle_torque(monkeypatch):
    from carbon.motor import exam

    monkeypatch.setattr(pool_adapters, "_roles", _roles())
    monkeypatch.setattr(exam, "gates", lambda outputs: {})
    chosen = motor18_dual_pack.pool_adapter("1.8")
    assert chosen.objective == "ripple_pk_pk_nm" and chosen.sense == "min"
    assert (
        chosen.limits == ()
    )  # no floor or ceiling in code: they are sealed custody values
    derived = chosen.derive({}, _flat(2.0, ripple=0.3))
    assert derived["ripple_pk_pk_nm"] == pytest.approx(0.3)
    assert derived["mean_torque_nm"] == pytest.approx(2.0 + 0.3 / len(_flat(0)))
    assert chosen.derive({}, ["nan"] * len(_flat(0))) is None
    assert chosen.derive({}, _flat(2.0)[:-1]) is None
    # torque only (the owner, 7 Nov): a row carrying anything beyond the 60 torque values is not a 1.8 answer
    assert chosen.derive({}, _flat(2.0, extra=180)) is None


def test_a_gate_failure_derives_nothing_and_the_gates_read_the_torque(monkeypatch):
    from carbon.motor import exam

    seen = []
    monkeypatch.setattr(pool_adapters, "_roles", _roles())
    monkeypatch.setattr(
        exam,
        "gates",
        lambda outputs: seen.append(len(outputs["torque_nm"])) or {"g": exam.FAIL},
    )
    assert motor18_dual_pack.pool_adapter("1.8").derive({}, _flat(2.0)) is None
    gates = motor18_dual_pack.physics_gates()
    assert gates.failed({}, _flat(2.0)) == ("g",)
    assert gates.failed({}, _flat(2.0, extra=180)) == ("schema_finite",)
    assert gates.failed({}, [1.0, 2.0]) == ("schema_finite",)
    assert set(seen) == {len(_flat(0))}


def test_only_1_8_has_this_adapter():
    with pytest.raises(pool_adapters.PoolAdapterRefused, match="for_1.8_only"):
        motor18_dual_pack.pool_adapter("1.6")


def test_the_official_binding_refuses_proof_suite_inputs(monkeypatch):
    monkeypatch.setattr(pool_adapters, "_roles", _roles())
    binding = motor18_dual_pack.official_binding()
    assert binding.kind == "motor" and binding.version == "1.8"
    with pytest.raises(
        pool_adapters.PoolAdapterRefused, match="not_part_of_the_official_grade"
    ):
        binding.serve_default()


def test_no_limit_value_and_no_back_emf_is_in_the_module():
    text = MODULE.read_text(encoding="utf-8")
    assert (
        "import back_emf" not in text
        and "back_emf." not in text
        and "flux_linkage" not in text
    )
    assert "constraints" not in text and "important_limit_definition" not in text
