"""Prospective authored Julia boundaries; synthetic tests create no runtime evidence."""

import json
import struct
from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest
from test_cw1_research_tasks import compose, request

from carbon import research
from carbon.development_session import julia_analysis as julia
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_admission import (
    MANIFEST,
    PROFILE,
    SCHEMA,
    Admission,
)
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_image import ResearchImageIdentity
from carbon.development_session.research_ledger import (
    DEVELOPMENT_CEILINGS,
    DEVELOPMENT_ELAPSED_SECONDS,
    CampaignLedger,
)


def fixture_image():
    parent = ResearchImageIdentity(
        "sha256:" + "a" * 64, "sha256:" + "b" * 64, "sha256:" + "c" * 64
    )
    return julia.JuliaResearchImageIdentity(
        "sha256:" + "d" * 64, parent, digest(canonical(julia.runtime_document(parent)))
    )


def prepared(
    tmp_path, *, image=None, approved=True, owner="test-miner", clock=lambda: 1000
):
    tmp_path.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp_path.chmod(0o700)
    root = tmp_path / "campaign"
    image = image or fixture_image()
    runtime = {"implementation": "fixture", "images": [image.image_id]}
    if approved:
        runtime["authored_research"] = [julia.authored_julia_scope(image)]
    grant = {
        "schema": SCHEMA,
        "status": "APPROVED",
        "authority": "ENGINEERING_FIXTURE_ONLY",
        "grant_id": "authored-julia-fixture",
        "campaign_id": "authored-julia-fixture",
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
        "expires_unix": clock() + DEVELOPMENT_ELAPSED_SECONDS,
        "cleanup": "all-campaign-owned-work; unresolved-reservations-retained",
        "retry_allowance": 0,
    }
    path = tmp_path / "grant.json"
    path.write_bytes(canonical(grant))
    path.chmod(0o600)
    admission = Admission.load(path)
    ledger = CampaignLedger(root, clock=clock, admission=admission)
    ledger.generation = CampaignControl(ledger).acquire()
    ledger.freeze(
        {
            "schema": MANIFEST,
            "campaign_id": grant["campaign_id"],
            "authority": grant["authority"],
            "principal": grant["principal"],
            "owner": owner,
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
    )
    return ledger, image


def test_v1_bytes_stay_fixed_and_julia_requires_distinct_v2():
    original = research.DevelopmentWorkspaceTaskSpecV1(
        "carbon.autoresearch.workspace.v1", "run_python", "{}"
    )
    encoded = research.canonical_bytes(original)
    # Observed from the unchanged pre-C-CORE-07 CPU source snapshot.
    assert (
        digest(encoded)
        == "sha256:9fed37f82906c610d4aadfdec982fe16e34d286aa8108e8ccb46666354b154e4"
    )
    assert research.load_canonical(encoded, type(original)) == original
    with pytest.raises(ValueError, match="unsupported development workspace action"):
        research.DevelopmentWorkspaceTaskSpecV1(original.version, "run_julia", "{}")
    prospective = research.DevelopmentWorkspaceTaskSpecV2(
        "carbon.autoresearch.workspace.v2", "run_julia", "{}"
    )
    assert research.canonical_bytes(prospective) != encoded
    assert (
        research.load_canonical(
            research.canonical_bytes(prospective), type(prospective)
        )
        == prospective
    )
    with pytest.raises(ValueError):
        research.DevelopmentWorkspaceTaskSpecV2(prospective.version, "run_python", "{}")


def test_prospective_campaign_discovery_copies_frozen_tool_schemas(tmp_path):
    from carbon.development_session.research_tools import TOOLS, tools_for_sdk

    before = canonical(TOOLS)
    assert tools_for_sdk(SimpleNamespace()) is TOOLS
    ledger, image = prepared(tmp_path)
    sdk = SimpleNamespace(
        ledger=ledger,
        owner="test-miner",
        composition=SimpleNamespace(executor=SimpleNamespace(julia_image=image)),
    )
    result = tools_for_sdk(sdk)
    task = next(tool for tool in result if tool["name"].endswith("start_research_task"))
    assert "run_julia" in task["parameters"]["properties"]["action"]["enum"]
    task["parameters"]["properties"]["action"]["enum"].clear()
    assert canonical(TOOLS) == before
    sdk.owner = "other-principal"
    with pytest.raises(ValueError):
        tools_for_sdk(sdk)
    with ledger.db() as db:
        assert db.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == 0


def test_operator_composition_requires_exact_private_image_record(
    tmp_path, monkeypatch
):
    from carbon.development_session.research_campaign import registered_julia_image

    image = fixture_image()
    observed = []
    monkeypatch.setattr(
        julia, "verify_julia_image", lambda item: observed.append(item) or item
    )
    assert registered_julia_image(tmp_path, {}, image.parent) is None
    runtime = {"authored_research": [julia.authored_julia_scope(image)]}
    with pytest.raises((ValueError, FileNotFoundError)):
        registered_julia_image(tmp_path, runtime, image.parent)
    path = tmp_path / "authored-julia-image.json"
    path.write_bytes(canonical(dict(schema=julia.SCHEMA, **asdict(image))))
    path.chmod(0o600)
    assert registered_julia_image(tmp_path, runtime, image.parent) == image
    assert observed == [image]
    with pytest.raises(ValueError, match="differs"):
        registered_julia_image(tmp_path, {"authored_research": []}, image.parent)
    with pytest.raises(ValueError, match="differs"):
        registered_julia_image(
            tmp_path, runtime, replace(image.parent, image_id="sha256:" + "f" * 64)
        )
    path.chmod(0o644)
    with pytest.raises(ValueError):
        registered_julia_image(tmp_path, runtime, image.parent)
    assert observed == [image]


@pytest.mark.parametrize(
    "violation", ["absent", "owner", "image", "revoked", "expired"]
)
def test_ungranted_authored_code_never_reaches_carrier(
    tmp_path, monkeypatch, violation
):
    ledger, image = prepared(tmp_path, approved=violation != "absent")
    from carbon.development_session import research_carrier

    monkeypatch.setattr(
        research_carrier,
        "_run",
        lambda *args, **kwargs: pytest.fail("unadmitted dispatch"),
    )
    owner = "other" if violation == "owner" else "test-miner"
    if violation == "image":
        image = replace(image, image_id="sha256:" + "f" * 64)
    if violation == "revoked":
        ledger.admission.path.write_bytes(
            canonical(dict(ledger.admission.document, status="REQUESTED_NOT_GRANTED"))
        )
    if violation == "expired":
        ledger.clock = lambda: 1000 + DEVELOPMENT_ELAPSED_SECONDS + 1
    with pytest.raises(ValueError):
        julia.run_julia(
            ledger,
            owner=owner,
            identity="admission-test",
            source="1+1",
            files={},
            image=image,
        )
    with ledger.db() as db:
        assert db.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == 0


def test_admitted_route_binds_language_bootstrap_and_existing_trial_charge(
    tmp_path, monkeypatch
):
    ledger, image = prepared(tmp_path)
    from carbon.development_session import research_carrier

    observed = []
    monkeypatch.setattr(
        research_carrier, "_run", lambda *args, **kwargs: observed.append(kwargs) or {}
    )
    julia.run_julia(
        ledger,
        owner="test-miner",
        identity="bound",
        source="1+1",
        files={},
        image=image,
        seconds=90,
    )
    assert observed[0]["program_name"] == "program.jl"
    assert observed[0]["bootstrap"] == julia.BOOTSTRAP
    assert observed[0]["execution_contract"] == {
        **julia.authored_julia_scope(image),
        "selected_environment": "current",
    }
    assert observed[0]["extra_resources"] == {"research_trials": 1}
    token = research_carrier.PRECHARGED_TRIAL.set("original-trial")
    try:
        julia.run_julia(
            ledger,
            owner="test-miner",
            identity="bound",
            source="1+1",
            files={},
            image=image,
            seconds=90,
        )
    finally:
        research_carrier.PRECHARGED_TRIAL.reset(token)
    assert observed[1]["extra_resources"] == {}


@pytest.mark.parametrize(
    "files",
    [
        {"program.jl": b"override"},
        {"program.py": b"override"},
        {"../private": b"x"},
        {"input.txt": "not-bytes"},
    ],
)
def test_stage_bounds_reject_before_reservation_or_docker(tmp_path, files):
    ledger, image = prepared(tmp_path)
    with pytest.raises(ValueError):
        julia.run_julia(
            ledger,
            owner="test-miner",
            identity="invalid-stage",
            source="1+1",
            files=files,
            image=image,
        )
    assert ledger.status(owner="test-miner")["operations"] == []


def test_v2_uses_same_durable_provider_and_unadmitted_source_fails_closed(tmp_path):
    f, provider, executor = compose(tmp_path)
    req = replace(
        request(f, "inventory", {}),
        task_spec=research.DevelopmentWorkspaceTaskSpecV2(
            "carbon.autoresearch.workspace.v2",
            "run_julia",
            canonical(
                {
                    "source": "1+1",
                    "files": [],
                    "seconds": 90,
                    "hypothesis": "fixture",
                    "expected_effect": "fixture",
                }
            ).decode(),
        ),
    )
    with pytest.raises(research.ResearchTaskProviderError):
        f.provider.start_research_task(req)
    task = provider.start_research_task(req).task
    assert (
        task.immutable_bindings.task_kind
        is research.ResearchTaskKind.DEVELOPMENT_WORKSPACE_V2
    )
    assert task.immutable_bindings.strategy_bindings == ()
    assert provider.start_research_task(req).task.task_id == task.task_id
    done = provider.run_queued_task(task.task_id)
    assert done.state is research.ResearchTaskState.FAILED_INFRA
    assert executor.public_result(done) is None
    provider.close()


@pytest.mark.parametrize(
    "name,body",
    [
        ("result.json", b'{"x":NaN}'),
        ("result.json", b'{"x":1e999}'),
        ("result.json", b'{"x":1,"x":2}'),
        ("result.json", b"broken"),
        ("values.f64le", struct.pack("<d", float("inf"))),
        ("values.f64le", b"123"),
        ("values.f32", b"1234"),
        ("notes.txt", b"\xff"),
    ],
)
def test_malformed_or_undeclared_numerical_exports_are_rejected(tmp_path, name, body):
    (tmp_path / name).write_bytes(body)
    with pytest.raises((ValueError, UnicodeError)):
        julia.validate_julia_output(tmp_path)


def test_finite_portable_exports_are_self_report_only(tmp_path):
    (tmp_path / "result.json").write_text(json.dumps({"energy": 0.5, "shape": [2]}))
    (tmp_path / "values.f64le").write_bytes(struct.pack("<2d", 1.0, 2.0))
    (tmp_path / "notes.txt").write_text("observed hypothesis")
    julia.validate_julia_output(tmp_path)
    assert julia.authored_julia_scope(fixture_image())["official_eligible"] is False


def test_the_miner_chooses_an_environment_and_nothing_else(tmp_path, monkeypatch):
    """`pde` runs the pde bootstrap and records that it did; any other name is
    refused before the carrier is reached. The environment is a name from a
    closed set, never a path, project or flag."""
    ledger, image = prepared(tmp_path)
    from carbon.development_session import research_carrier

    observed = []
    monkeypatch.setattr(
        research_carrier, "_run", lambda *args, **kwargs: observed.append(kwargs) or {}
    )
    arguments = {
        "owner": "test-miner",
        "identity": "pde",
        "source": "1+1",
        "files": {},
        "image": image,
    }
    julia.run_julia(ledger, environment="pde", **arguments)
    assert observed[0]["bootstrap"] == julia.bootstrap_for("pde")
    assert "/opt/carbon-julia-analysis/pde" in observed[0]["bootstrap"]
    assert observed[0]["execution_contract"]["selected_environment"] == "pde"
    for refused in ("/opt/elsewhere", "current;rm", "", None):
        with pytest.raises(ValueError, match="environment"):
            julia.run_julia(ledger, environment=refused, **arguments)
    assert len(observed) == 1


def test_every_environment_is_a_committed_pinned_manifest():
    """The runtime identity binds each environment's exact manifest bytes."""
    document = julia.runtime_document(fixture_image().parent)
    assert set(document["environments"]) == set(julia.ENVIRONMENTS)
    for name in julia.ENVIRONMENTS:
        _project, manifest = julia.environment_files(name)
        assert b'julia_version = "1.13.0"' in manifest
        assert document["environments"][name]["manifest"] == digest(manifest)
    scope = julia.authored_julia_scope(fixture_image())
    assert scope["schema"] == "carbon.authored-julia.scope.v2"
    assert set(scope["bootstrap"]) == set(julia.ENVIRONMENTS)
