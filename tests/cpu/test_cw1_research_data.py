"""Reference accounting tests use explicit fake C-04 observations, not science."""

from types import SimpleNamespace

import numpy as np
import pytest
from test_cw1_research_ledger import ledger

from carbon.development_session import research_data as data
from carbon.development_session.profile import digest
from carbon.development_session.research_material import (
    PublicMaterial,
    capabilities,
    objective,
)
from carbon.development_session.research_workspace import ResearchWorkspace
from carbon.evaluation.enums import ReferenceRunOutcome
from carbon.generators.burgers_dynamics import (
    BurgersCaseCoordinates,
    BurgersDevelopmentCase,
    PublicDevelopmentRole,
)


def case():
    return BurgersDevelopmentCase(
        "sha256:" + "a" * 64,
        BurgersCaseCoordinates(PublicDevelopmentRole.TRAIN, 0, 0, 0),
        "harmonic",
        0,
        0.2,
        0.0,
        1.0,
        1.0,
        0.2,
        5.0,
        20.0,
        (0.2,) + (0.0,) * 11,
        (0.0,) * 12,
    )


def fixture(tmp_path, monkeypatch, fail=False):
    meter = ledger(tmp_path)
    monkeypatch.setattr(
        data, "runtime_environment_digest", lambda: "sha256:" + "b" * 64
    )
    service = data.PublicReferenceData(
        ledger=meter,
        owner="alice",
        image=SimpleNamespace(image_id="sha256:" + "c" * 64),
        role_root=tmp_path,
    )
    calls = []

    def execute(request):
        calls.append(request.request_digest)
        if fail:
            raise RuntimeError("uncertain worker transport")
        snapshot = service.root / "c04" / "snapshots" / "fixture"
        snapshot.mkdir(parents=True, exist_ok=True)
        (snapshot / "solution.f64le").write_bytes(
            np.zeros((13, 64), dtype="<f8").tobytes()
        )
        return SimpleNamespace(
            snapshot_path=snapshot,
            snapshot_digest=digest(b"fixture snapshot"),
            result=SimpleNamespace(
                outcome=ReferenceRunOutcome.SUPPORTED,
                artifact_digest=digest(b"fixture artifact"),
                shape=(13, 64),
            ),
            controls={"fixture": True},
            resources={"fixture": True},
            timings={},
        )

    service.controller = SimpleNamespace(execute=execute)
    return service, meter, calls


def test_reference_replay_accounts_once_and_checks_artifact(tmp_path, monkeypatch):
    # Replace only construction for these controller-adapter unit tests.
    monkeypatch.setattr(data, "IsolatedBurgersReferenceController", lambda **kw: None)
    service, meter, calls = fixture(tmp_path, monkeypatch)
    service._reference(case())
    service._reference(case())
    assert len(calls) == 1
    usage = meter.status(owner="alice")["used"]
    assert usage["reference_trajectories"] == usage["reference_invocations"] == 1
    path = service.root / "c04/snapshots/fixture/solution.f64le"
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="association"):
        service._reference(case())
    assert len(calls) == 1


def test_uncertain_reference_retains_reservation_and_never_retries(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(data, "IsolatedBurgersReferenceController", lambda **kw: None)
    service, meter, calls = fixture(tmp_path, monkeypatch, fail=True)
    with pytest.raises(RuntimeError):
        service._reference(case())
    with pytest.raises(ValueError, match="reconcile"):
        service._reference(case())
    assert len(calls) == 1
    assert meter.status(owner="alice")["used"]["numerical_milliseconds"] == 720000


def test_final_roles_denied_before_any_reference(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "IsolatedBurgersReferenceController", lambda **kw: None)
    service, _meter, calls = fixture(tmp_path, monkeypatch)
    for role in ("final-epoch-1", "final-epoch-2", "EVAL", "../private"):
        with pytest.raises(ValueError, match="public"):
            service.prepare(role)
    assert calls == []


def test_case_decode_requires_exact_record():
    value = case().public_record()
    assert data.decode_public_case(value).public_record() == value
    with pytest.raises(ValueError):
        data.decode_public_case({**value, "private": "hidden"})


def test_public_objective_is_actionable_and_has_no_realized_final_state(tmp_path):
    meter = ledger(tmp_path)
    workspace = ResearchWorkspace(meter, "alice")
    material = PublicMaterial(None)
    report = material("objective", workspace)
    assert report["document"] == objective()
    assert len(capabilities()["operations"]) == 12
    assert report["document"]["score_rule"]["id"] == "burgers-development-balanced-v2"
    assert "generator_laws" in report["document"]
    with pytest.raises(ValueError):
        material("final-epoch-1", workspace)
    assert [x["name"] for x in workspace.inventory()] == ["objective.json"]
