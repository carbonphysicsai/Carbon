"""REFERENCE-PACKAGES-01: every package lock pins its base, sources and
checksums, and every manifest names its image and passing smoke cases."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LOCKS = sorted((ROOT / "scripts/dev/reference_packages").glob("*/sources.lock.json"))
MANIFESTS = sorted(
    p
    for p in (ROOT / "docs/development/evidence/reference-packages-01").glob("*.json")
    if json.loads(p.read_text()).get("schema") == "carbon.reference-package.manifest.v1"
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")


@pytest.mark.parametrize("path", LOCKS, ids=lambda p: p.parent.name)
def test_lock_pins_everything(path):
    lock = json.loads(path.read_text())
    assert re.match(r"^[a-z0-9./-]+@sha256:[0-9a-f]{64}$", lock["base_image"])
    assert lock["sources"]
    for source in lock["sources"]:
        assert source["url"].startswith("https://")
        assert SHA256.match(source["sha256"]) and source["size"] > 0
    assert "snapshot.debian.org/archive/debian/" in lock["debian_snapshot"]


@pytest.mark.parametrize("path", MANIFESTS, ids=lambda p: p.stem)
def test_manifest_names_image_and_passing_smoke(path):
    manifest = json.loads(path.read_text())
    assert re.match(r"^sha256:[0-9a-f]{64}$", manifest["image_id"])
    assert manifest["smoke"]
    assert all(s["exit"] == 0 and s["test_passed"] == 1 for s in manifest["smoke"])
    assert "NOT yet demonstrated" in manifest["maturity"]


def test_f08_feature_proof_demonstrates_every_required_feature():
    proof = json.loads(
        (
            ROOT
            / "docs/development/evidence/reference-packages-01/f08-feature-proof.json"
        ).read_text()
    )
    assert proof["schema"] == "carbon.reference-package.feature-proof.v1"
    required = (
        "exact_modal_damping",
        "mass_normalised_projection",
        "mode_ladder",
        "complex_phase",
        "batched_damping_frequency_outputs",
    )
    assert all(proof["proofs"][name] is True for name in required)
    assert "HUMAN_INPUT" in proof["scope"]
