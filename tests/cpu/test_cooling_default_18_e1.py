"""Cooling 1.8 shipped default E1 (owner 11 Nov 2026 19:12: 'ship E1 ... recipe b26db091 as the Cooling 1.8 shipped
default'). Validator-2C's ruling (11 Nov 21:17) places it as a kit folder, with:
- R-1: the folder re-stages to its receipted submission;
- R-2: the 1.8 admission of that submission passes, with the 1.8 recipe digest recorded.

The folder is kits/cooling-default-1.8-e1, beside kits/cooling, so the data kit's own guards stay unchanged.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

import carbon.challenge_kit.version_registry  # noqa: F401
from carbon.development_session import graph_adapters
from carbon.development_session import physical_graph_adapter_v2 as v2
from carbon.development_session.construction_recipe import ConstructionRecipe
from carbon.level4 import staging

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "kits" / "cooling-default-1.8-e1"
CHALLENGE = "chip-cold-plate"
#: E1_head_ensemble3: the M2 pick (Test Lead-B 18:33), F3-fresh PASS (Carbon Validator-B 4ecd6345).
SUBMISSION = "sha256:7fa5a63f692e7a780a31d4d31d71294530354abcfbf9ae56dd33f1f85cbc0e59"
CONFIGURATION_SHA256 = (
    "840c856baf2ff050527c0b309a91a04f8c7b8b323781eb9f0b96047b3001c2cf"
)
#: The recipe the 1.8 gate read graded (seeds 0-2, run on the 1.7 route digest).
RECIPE_ON_17 = "sha256:b26db091fb4bf01fa720ffa64031bd0e83d6c09ca432825b914717d5de310d81"
#: The same submission and configuration on the 1.8 route.
RECIPE_ON_18 = "sha256:288986db742bcc9a62009281daf2be9f89f0dfd026a72f922599973d3d2dc982"
INTERFACE = "sha256:849275fb67c5766452d2bbc1f6da691c553630a89026f5bd1048a70b97d2c12a"
FILES = {
    "README.md",
    "config_E_ensemble3.json",
    "spec/d6_spec.py",
    "spec/d6v_spec_head.py",
    "spec/prior.py",
    "submission/manifest.json",
    "submission/3108a1c4a0c772c7273ffbe68952ffe9750635ba25e3e938e4ffa2ec1ddefeee.json",
    "submission/4f6feeb28c03ee8b8802ed3482e95e6b8f8f61cad5729debb9c328b3f74c4a5b.json",
}


def _staged():
    return staging.read_directory(str(FOLDER / "submission"))


def _configuration():
    return json.loads((FOLDER / "config_E_ensemble3.json").read_bytes())


def _recipe(version):
    digest, _, _ = _staged()
    return ConstructionRecipe.from_dict(
        graph_adapters.graph_recipe(
            CHALLENGE, version, digest, configuration=_configuration()
        )
    )


def test_the_folder_holds_exactly_its_files():
    held = {
        p.relative_to(FOLDER).as_posix()
        for p in FOLDER.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }
    assert held == FILES


def test_the_staged_submission_is_e1_on_the_1_8_graph_interface():
    digest, raw_manifest, _ = _staged()
    assert digest == SUBMISSION
    manifest = json.loads(raw_manifest)
    assert manifest["challenge"] == CHALLENGE
    assert manifest["interface"] == INTERFACE
    spec = v2.spec_for(CHALLENGE, "1.8")
    assert v2.graph_interface(spec).digest() == INTERFACE


def test_the_configuration_is_the_receipted_one():
    raw = (FOLDER / "config_E_ensemble3.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == CONFIGURATION_SHA256


def test_the_recipe_digests_are_the_graded_one_and_the_1_8_one():
    assert _recipe("1.7").digest == RECIPE_ON_17
    assert _recipe("1.8").digest == RECIPE_ON_18


def test_the_1_8_graph_route_admits_it():
    """R-2: admitted exactly as Cooling 1.8 admits a graph submission (its served allowlist and TRAIN size)."""
    _, raw_manifest, files = _staged()
    model = v2.build_validated_graph(
        _recipe("1.8"),
        raw_manifest,
        files,
        allowlist_bytes=v2.served_allowlist_bytes(CHALLENGE, "1.8"),
        train_cases=v2.spec_for(CHALLENGE, "1.8").rows,
    )
    assert model is not None


def test_the_spec_lowers_to_the_shipped_submission(tmp_path):
    """R-1: lowering the folder's spec gives the shipped submission, byte for byte."""
    pytest.importorskip("jax")
    out = tmp_path / "lowered"
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "carbon.level4.tooling",
            "lower",
            str(FOLDER / "spec" / "d6v_spec_head.py"),
            str(out),
            "--challenge",
            CHALLENGE,
            "--challenge-version",
            "1.8",
            "--interface",
            INTERFACE,
            "--batch",
            "366",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    assert json.loads(done.stdout.strip().splitlines()[-1])["submission"] == SUBMISSION
    for path in (FOLDER / "submission").iterdir():
        assert (out / path.name).read_bytes() == path.read_bytes(), path.name
