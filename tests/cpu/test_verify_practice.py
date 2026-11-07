"""Practice on the data kit's verify set (owner 7 Nov: "Yes, verify set").

Nothing changes while the registry is empty; a registered version practises on its verify set at the receipted
digest only, scored by the same practice measurement, and its result says so.
"""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest
from test_lp_prod_research_tools import ledger

from carbon.challenge_kit import verify_practice
from carbon.challenge_registry.motor import catalog_recipe
from carbon.development_session import bundle_construction_worker as worker
from carbon.motor import catalog_practice, domain

TRAIN = "carbon/challenge_kit/data/motor-dev-train-150-v1.npz"
U = {"mean_torque_nm": 0.0052, "ripple_fraction": 0.026}


def _verify_set(tmp_path, n=3):
    """A stand-in verify set: n public TRAIN rows as designs with their truths (a fixture, never a real set)."""
    data = np.load(TRAIN)
    designs = [
        {
            "case_id": f"verify-{i:02d}",
            "inputs": dict(zip(domain.INPUTS, map(float, data["inputs"][i]))),
            "truth": {"torque_nm": [float(v) for v in data["targets"][i]]},
        }
        for i in range(n)
    ]
    raw = json.dumps({"designs": designs, "u": U}, sort_keys=True).encode()
    path = tmp_path / "verify_set.json"
    path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest(), data["targets"][:n]


def test_only_receipted_versions_practise_on_their_verify_set():
    # Only Motor 1.8 is switched on (its verify set receipted); every other version keeps its practice.
    assert set(verify_practice.REGISTRY) == {(verify_practice.MOTOR, "1.8")}
    assert verify_practice.source(verify_practice.MOTOR, "1.5") is None
    src = verify_practice.source(verify_practice.MOTOR, "1.8")
    assert len(src.case_ids) == 6


def test_a_registered_set_loads_only_at_its_receipted_digest(tmp_path):
    path, sha, _ = _verify_set(tmp_path)
    key = (verify_practice.MOTOR, "9.9")
    src = verify_practice.source(*key, root=tmp_path, registry={key: (path.name, sha)})
    assert src.case_ids == ["verify-00", "verify-01", "verify-02"]
    assert src.query(domain.INPUTS).shape == (3, len(domain.INPUTS))
    with pytest.raises(verify_practice.VerifyPracticeRefused):
        verify_practice.source(
            *key, root=tmp_path, registry={key: (path.name, "0" * 64)}
        )
    with pytest.raises(verify_practice.VerifyPracticeRefused):
        verify_practice.source(
            *key, root=tmp_path, registry={key: ("absent.json", sha)}
        )


def test_motor_scoring_is_the_practice_measurement_on_the_verify_truths(tmp_path):
    from carbon.motor.challenge import PublicMaterial

    path, sha, truths = _verify_set(tmp_path)
    key = (verify_practice.MOTOR, "9.9")
    src = verify_practice.source(*key, root=tmp_path, registry={key: (path.name, sha)})
    train = PublicMaterial.load(".").train
    _, exact, block = verify_practice.score_motor(src, truths.tolist(), train)
    assert exact["eligible"] is True and exact["n_scored"] == 3
    assert exact["score"] == pytest.approx(0.0, abs=1e-12)
    assert block["aggregate"]["accuracy_vs_u"]["n_within_u"] == 3
    assert block["design_value"] == block["minimums"] == verify_practice.NOT_EVALUATED
    assert block["label"] == verify_practice.LABEL and block["verify_set_sha256"] == sha
    _, off, _ = verify_practice.score_motor(src, (truths * 1.5).tolist(), train)
    assert off["score"] > 0
    with pytest.raises(verify_practice.VerifyPracticeRefused):
        verify_practice.score_motor(src, truths[:2].tolist(), train)


def test_motor_practice_switches_to_the_verify_set_when_registered(
    tmp_path, monkeypatch
):
    path, sha, truths = _verify_set(tmp_path)
    calls = []

    def fake(ledger_, **kwargs):
        calls.append(kwargs)
        n = len(kwargs["inputs"])
        rows = [list(map(float, truths[i % len(truths)])) for i in range(n)]
        state = "sha256:" + "5" * 64
        return SimpleNamespace(
            build=SimpleNamespace(state_digest=state),
            inference=SimpleNamespace(state_digest=state, predictions=rows),
        )

    monkeypatch.setattr(worker, "reconstruct_and_infer_public", fake)
    parent = SimpleNamespace(image_id="sha256:" + "7" * 64)
    item = catalog_practice.MotorCatalogPractice(
        ledger=ledger(tmp_path / "ledger"),
        owner="alice",
        parent=parent,
        cache_root=tmp_path / "cache",
        root=".",
        resolver=lambda ref: SimpleNamespace(bundle_ref=ref),
        parents=SimpleNamespace(for_bundle=lambda _ref: parent),
    )
    monkeypatch.setattr(
        verify_practice,
        "REGISTRY",
        {(verify_practice.MOTOR, item.version): (str(path), sha)},
    )
    result = item("motor-catalog-verify", catalog_recipe("neuralop.FNO"))
    (call,) = calls
    assert len(call["inputs"]) == 3  # the verify designs only
    assert result["practice_source"] == verify_practice.LABEL
    assert result["summary"]["n_scored"] == 3 and result["summary"]["eligible"] is True
    assert result["verify"]["aggregate"]["accuracy_vs_u"]["n_within_u"] == 3
    assert result["practice_dual"]["available"] is False
    assert (
        result["provenance"] == "MOTOR_PUBLIC_PRACTICE"
    )  # a practised recipe still supports a freeze
    assert result["final_exam"] is False and result["official_eligible"] is False
