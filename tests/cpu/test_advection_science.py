"""Closed public advection control; no production threshold or grant authority."""

import json
import struct
from dataclasses import replace
from types import SimpleNamespace

import pytest

from carbon.reference_runtime.julia.advection import (
    AdvectionRequest,
    decode_outputs,
    public_definition,
)
from carbon.scientific_tasks.definitions import Audience, Custody


def test_shared_definition_preserves_time_order_units_and_public_views():
    definition = replace(public_definition(), requested_times=(1.0, 0.0, 0.5, 0.5))
    request = AdvectionRequest(definition)
    assert request.encode().splitlines()[11] == b"1.0,0.0,0.5,0.5"
    assert request.public_view()["definition"]["encoding"]["dtype"] == "float64"
    for role in Audience:
        assert definition.project(role)["inputs"]["initial_field"] == list(
            definition.initial_field
        )
    assert not request.public_view()["training_support_eligible"]


@pytest.mark.parametrize(
    "changes",
    [
        {"custody": Custody.VALIDATOR_INTERNAL},
        {"initial_field": (1.0,) * 17},
        {"requested_times": (0.0,) * 65},
        {"requested_times": (1e30,)},
        {"parameter": 1e300},
    ],
)
def test_request_rejects_unsupported_custody_layout_and_unbounded_work(changes):
    with pytest.raises(ValueError):
        AdvectionRequest(replace(public_definition(), **changes))


def test_native_unit_mismatch_is_not_silently_converted():
    with pytest.raises(ValueError):
        replace(public_definition(), unit_system="dimensionless")


def test_decoder_rejects_partial_unknown_or_oversized_outputs():
    request = AdvectionRequest(public_definition())
    with pytest.raises(ValueError):
        decode_outputs({}, request)
    with pytest.raises(ValueError):
        decode_outputs(
            {
                "result.json": b"{}",
                "fine.f64le": b"",
                "coarse.f64le": b"",
                "extra": b"",
            },
            request,
        )


def test_output_contract_checks_finite_values_units_dtype_layout_and_identity():
    from carbon.reference_runtime.julia.advection import LAYOUT, METHOD_ID, UNITS

    request = AdvectionRequest(
        replace(public_definition(), initial_field=(0.25,) * 64, parameter=0.0)
    )
    metadata = {
        "schema": "carbon.julia.advection-result.v1",
        "method": METHOD_ID,
        "request_digest": request.digest,
        "units": UNITS,
        "layout": LAYOUT,
        "shape": [5, 64],
        "coarse_points": 64,
        "fine_points": 128,
        "coarse_steps": 4,
        "fine_steps": 4,
        "allocated_bytes": 1,
        "coarse_mean_drift": 0.0,
        "fine_mean_drift": 0.0,
        "refinement_rms": 0.0,
        "refinement_max": 0.0,
        "completed_horizon": 1.0,
        "solver_seconds": 0.001,
    }
    files = {
        "result.json": json.dumps(metadata).encode(),
        "coarse.f64le": struct.pack("<d", 0.25) * 320,
        "fine.f64le": struct.pack("<d", 0.25) * 320,
    }
    assert not decode_outputs(files, request)["scientifically_qualified"]
    for changes in (
        {"units": "SI"},
        {"shape": [True, 64]},
        {"coarse_points": 64.0},
        {"refinement_rms": float("nan")},
        {"request_digest": "changed"},
        {"completed_horizon": 0.5},
    ):
        with pytest.raises(ValueError):
            decode_outputs(
                {**files, "result.json": json.dumps({**metadata, **changes}).encode()},
                request,
            )
    for invalid in (
        struct.pack("<d", float("nan")) * 320,
        struct.pack(">d", 0.25) * 320,
        b"short",
    ):
        with pytest.raises(ValueError):
            decode_outputs({**files, "fine.f64le": invalid}, request)
    with pytest.raises(ValueError):
        decode_outputs(
            {"result.json": b" " * 4097, "fine.f64le": b"", "coarse.f64le": b""},
            request,
        )


def prepared_advection(tmp_path, image):
    from carbon.development_session.advection_research import advection_scope
    from carbon.development_session.julia_analysis import authored_julia_scope
    from carbon.development_session.profile import canonical
    from carbon.development_session.research_admission import (
        MANIFEST,
        PROFILE,
        SCHEMA,
        Admission,
    )
    from carbon.development_session.research_control import CampaignControl
    from carbon.development_session.research_ledger import (
        DEVELOPMENT_CEILINGS,
        DEVELOPMENT_ELAPSED_SECONDS,
        CampaignLedger,
    )

    tmp_path.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp_path.chmod(0o700)
    root = tmp_path / "campaign"
    runtime = {
        "implementation": "fixture",
        "images": [image.image_id],
        "authored_research": [authored_julia_scope(image)],
        "scientific_tasks": [advection_scope(image)],
    }
    grant = {
        "schema": SCHEMA,
        "status": "APPROVED",
        "authority": "ENGINEERING_FIXTURE_ONLY",
        "grant_id": "advection-fixture",
        "campaign_id": "advection-fixture",
        "root": str(root),
        "principal": "fixture-principal",
        "miner_identity": "fixture-miner",
        "profile": PROFILE,
        "runtime": runtime,
        "provider": "openai-responses",
        "account_ref": "fixture-no-credentials",
        "campaign_count": 1,
        "ceilings": dict(DEVELOPMENT_CEILINGS),
        "elapsed_seconds": DEVELOPMENT_ELAPSED_SECONDS,
        "expires_unix": 1000 + DEVELOPMENT_ELAPSED_SECONDS,
        "cleanup": "all-campaign-owned-work; unresolved-reservations-retained",
        "retry_allowance": 0,
    }
    path = tmp_path / "grant.json"
    path.write_bytes(canonical(grant))
    path.chmod(0o600)
    admission = Admission.load(path)
    ledger = CampaignLedger(root, clock=lambda: 1000, admission=admission)
    ledger.generation = CampaignControl(ledger).acquire()
    manifest = {
        "schema": MANIFEST,
        "campaign_id": grant["campaign_id"],
        "authority": grant["authority"],
        "principal": grant["principal"],
        "owner": "test-miner",
        "runtime": runtime,
        "grant": admission.binding(),
        "ceilings": grant["ceilings"],
        "elapsed_seconds": DEVELOPMENT_ELAPSED_SECONDS,
        **{
            key: "fixture"
            for key in (
                "implementation",
                "objective",
                "sampling",
                "control",
                "selection",
                "replica_policy",
                "provider",
            )
        },
    }
    ledger.freeze(manifest)
    return ledger


def test_fixed_material_requires_both_scopes_and_same_owner(tmp_path):
    from test_authored_julia import fixture_image, prepared

    from carbon.development_session.advection_research import PublicAdvectionMaterial

    image = fixture_image()
    ledger, _ = prepared(tmp_path / "authored-only", image=image)
    with pytest.raises(ValueError, match="advection scope"):
        PublicAdvectionMaterial(None, ledger=ledger, owner="test-miner", image=image)
    ledger = prepared_advection(tmp_path / "both", image)
    material = PublicAdvectionMaterial(
        lambda *args: "delegate", ledger=ledger, owner="test-miner", image=image
    )
    assert material("unchanged-material", None) == "delegate"
    for name in ("capabilities", "julia_advection_study_v1"):
        with pytest.raises(ValueError, match="owned admitted"):
            material(name, None)
    with pytest.raises(ValueError):
        PublicAdvectionMaterial(None, ledger=ledger, owner="other", image=image)
    with ledger.db() as db:
        manifest = json.loads(
            db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()[0]
        )
        manifest["runtime"]["scientific_tasks"][0]["method"] = "another"
        db.execute("UPDATE campaign SET manifest=? WHERE id=1", (json.dumps(manifest),))
    with pytest.raises(ValueError):
        material._authorize()


@pytest.mark.parametrize("kind", ["advection", "envelope", "reference"])
def test_integrated_material_allowlists_remain_separate_exact_types(monkeypatch, kind):
    from carbon.development_session.advection_research import MATERIAL as ADVECTION
    from carbon.development_session.advection_research import PublicAdvectionMaterial
    from carbon.development_session.julia_envelope import MATERIAL as ENVELOPE
    from carbon.development_session.julia_envelope import JuliaEnvelopeMaterial
    from carbon.development_session.julia_research import MATERIAL, JuliaPublicMaterial
    from carbon.development_session.profile import canonical
    from carbon.development_session.research_tasks import PublicResearchExecutor

    cls, names = {
        "advection": (PublicAdvectionMaterial, {ADVECTION}),
        "envelope": (JuliaEnvelopeMaterial, {MATERIAL, ENVELOPE}),
        "reference": (JuliaPublicMaterial, {MATERIAL}),
    }[kind]
    # Exercise only the dispatch allowlist; real constructor/grant validation is
    # covered separately. The synthetic callback cannot run scientific work.
    monkeypatch.setattr(cls, "__call__", lambda self, name, workspace: name)
    executor = object.__new__(PublicResearchExecutor)
    executor.workspace = None
    executor.practice = None
    executor.public_material = object.__new__(cls)
    for name in {MATERIAL, ENVELOPE, ADVECTION}:
        spec = SimpleNamespace(
            action="public_material", arguments_json=canonical({"name": name}).decode()
        )
        if name in names:
            assert executor._workspace_action(spec, "fixture") == name
        else:
            with pytest.raises(ValueError, match="public material unavailable"):
                executor._workspace_action(spec, "fixture")
    unregistered = type("UnregisteredMaterial", (cls,), {})
    executor.public_material = object.__new__(unregistered)
    for name in names:
        spec = SimpleNamespace(
            action="public_material", arguments_json=canonical({"name": name}).decode()
        )
        with pytest.raises(ValueError, match="public material unavailable"):
            executor._workspace_action(spec, "fixture")
