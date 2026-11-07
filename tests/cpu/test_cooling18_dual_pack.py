"""Cooling 1.8's sealed adapter through a version-overlay dispatch (a TEMPORARY overlay file; the production overlay gains
the 1.8 entry only at the TRAIN freeze). Checks: 1.8 routes to its own module, every other version delegates unchanged,
the earlier Cooling producer identity does not move, and 1.8 refuses to measure until its extended TRAIN is frozen."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from carbon.scoring import cooling18_dual_pack

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "carbon" / "scoring" / "cooling18_dual_pack.py"


def _entry():
    return {
        "challenge_id": "chip-cold-plate",
        "version": "1.8",
        "train": cooling18_dual_pack.SERVED_TRAIN,
        "allowlist": "v8",
        "step_caps": False,
        "pack_version": "cooling-normal-construction-development-test-1p8",
        "development_evaluation": [
            "cooling-dual-development-grid-v3",
            "cooling-development-grid-8x6",
        ],
        "sealed_evaluation": cooling18_dual_pack.POOL_VERSIONS["1.8"][0],
        "campaign": "catalog",
        "catalog": True,
        "graph_adapter": "v2",
        "output_encoding": "cooling-law-safe-output-encoding",
        "catalog_entries_from": [],
        "predecessor": "1.7",
        "rebuild_wall_seconds": 648,
        "dispatch": {
            "module": "carbon.scoring.cooling18_dual_pack",
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
        "from carbon.scoring import cooling_encoded_dual_pack as enc",
        "before = enc.producer_digest()",
        "seventeen = enc.sealed_adapter('1.7')",
        "version_overlay.install(sys.argv[1])",
        "from carbon.scoring import cooling18_dual_pack as c18",
        "out = {",
        " 'pool': list(enc.POOL_VERSIONS['1.8']),",
        " 'versions': list(enc.VERSIONS['1.8']),",
        " 'module_18': enc.sealed_adapter('1.8')._module.__name__,",
        " 'module_17': type(enc.sealed_adapter('1.7')).__name__ == type(seventeen).__name__,",
        " 'module_15': enc.sealed_adapter('1.5')._module.__name__,",
        " 'digest_same': enc.producer_digest() == before,",
        " 'digest_18_differs': c18.producer_digest() != before,",
        " 'registered': version_registry.find('chip-cold-plate', '1.8') is not None,",
        "}",
        "try:",
        "    c18._native_train()",
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
    document["versions"]["chip-cold-plate 1.8"] = _entry()
    path = tmp_path / "version_overlay.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_cooling_1_8_routes_to_its_own_module_and_nothing_else_moves(overlay):
    result = _run(overlay)
    assert result.returncode == 0, result.stderr[-2000:]
    out = json.loads(result.stdout.strip().splitlines()[-1])
    assert out["registered"]
    assert (
        out["pool"] == list(cooling18_dual_pack.POOL_VERSIONS["1.8"]) == out["versions"]
    )
    assert out["module_18"] == "carbon.scoring.cooling18_dual_pack"
    assert (
        out["module_17"]
        and out["module_15"] == "carbon.scoring.cooling_encoded_dual_pack"
    )
    assert out["digest_same"] and out["digest_18_differs"]
    assert "not frozen yet" in out["train"]


def test_a_changed_module_file_is_refused_before_import(overlay):
    document = json.loads(overlay.read_bytes())
    document["versions"]["chip-cold-plate 1.8"]["dispatch"]["sha256"] = "0" * 64
    overlay.write_text(json.dumps(document), encoding="utf-8")
    result = _run(overlay)
    assert result.returncode != 0 and "sha256 does not match" in result.stderr


def test_the_dispatch_takes_no_config_and_answers_only_1_8():
    with pytest.raises(ValueError, match="no config"):
        cooling18_dual_pack.dispatch({"box": {}})
    spec = cooling18_dual_pack.dispatch({})
    assert spec["version"] == "1.8" and spec["challenge"] == "chip-cold-plate"
    assert cooling18_dual_pack.sealed_adapter("1.7") is None
    with pytest.raises(ValueError, match="Cooling 1.8 packs only"):
        cooling18_dual_pack._writer(None, None, version="1.7")


def test_1_8_measures_against_its_own_train_name_never_train_400():
    assert cooling18_dual_pack.NATIVE_TRAIN != "cooling-dev-train-400-v1"
    assert cooling18_dual_pack.SERVED_TRAIN.endswith("-encoded")
    from carbon.challenge_kit import physical_public_train as ppt

    assert (
        ppt.EXTENDED[cooling18_dual_pack.SERVED_TRAIN]["encoded_from"]
        == cooling18_dual_pack.NATIVE_TRAIN
    )
