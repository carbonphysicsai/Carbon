"""CLI composition fixtures; no provider, native numerical worker or campaign run."""

import asyncio
import copy
import json
from types import SimpleNamespace

import pytest
from test_advection_science import prepared_advection
from test_authored_julia import fixture_image
from test_julia_research import prepared

from carbon.development_session.advection_research import PublicAdvectionMaterial
from carbon.development_session.julia_envelope import JuliaEnvelopeMaterial
from carbon.development_session.julia_research import JuliaPublicMaterial
from carbon.development_session.profile import canonical
from carbon.development_session.research_carrier import ACTIVE_TASK
from carbon.development_session.research_material import PublicMaterial
from carbon.development_session.research_workspace import ResearchWorkspace
from carbon.miner_mcp import standard_cli as cli


def configuration(tmp_path, monkeypatch, kind):
    if kind == "advection":
        from carbon.development_session import research_data

        authored = fixture_image()
        ledger = prepared_advection(tmp_path, authored)
        image = SimpleNamespace(image_id=authored.parent.parent_image)
        roles = tmp_path / "roles"
        monkeypatch.setattr(
            research_data, "IsolatedBurgersReferenceController", lambda **kw: None
        )
    else:
        data, ledger, calls = prepared(
            tmp_path,
            monkeypatch,
            approved=kind != "legacy",
            envelope=kind == "envelope",
        )
        image, roles, authored = data.image, data.role_root, None
        assert calls == []
    return ledger, image, roles, authored


def attach(config, *, cleanup=False, owner="test-miner"):
    ledger, image, roles, authored = config
    return cli._science(
        ledger, owner, image, roles, authored=authored, cleanup_only=cleanup
    )[0]


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("legacy", PublicMaterial),
        ("burgers", JuliaPublicMaterial),
        ("envelope", JuliaEnvelopeMaterial),
        ("advection", PublicAdvectionMaterial),
    ],
)
def test_exact_material_discovery_and_reference_image_separation(
    tmp_path, monkeypatch, kind, expected
):
    config = configuration(tmp_path, monkeypatch, kind)
    ledger, image, roles, authored = config
    material, practice = cli._science(
        ledger, "test-miner", image, roles, authored=authored
    )
    assert type(material) is expected
    assert practice.image is image
    if authored is not None:
        assert material.image is authored
        assert material.primary.data.image is image
        assert image.image_id != authored.image_id
    workspace = ResearchWorkspace(ledger, "test-miner")
    token = ACTIVE_TASK.set("fixture-discovery-only")
    try:
        value = material("capabilities", workspace)["document"]
    finally:
        ACTIVE_TASK.reset(token)
    if kind != "legacy":
        assert (
            value["scientific_tasks"]
            == ledger.admission.document["runtime"]["scientific_tasks"]
        )
    with ledger.db() as db:
        assert db.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == 0


@pytest.mark.parametrize(
    "alter",
    [
        lambda scopes: [],
        lambda scopes: None,
        lambda scopes: {},
        lambda scopes: [None],
        lambda scopes: list(reversed(scopes)),
        lambda scopes: scopes[1:],
        lambda scopes: scopes + scopes[:1],
        lambda scopes: scopes + [{"schema": "unknown"}],
        lambda scopes: [{**scopes[0], "image": "wrong"}],
        lambda scopes: [{**scopes[0], "official_eligible": 0}],
    ],
)
def test_rejects_empty_unknown_reordered_extra_and_modified_scopes(
    tmp_path, monkeypatch, alter
):
    ledger, image, roles, authored = configuration(tmp_path, monkeypatch, "envelope")
    runtime = copy.deepcopy(ledger.admission.document["runtime"])
    runtime["scientific_tasks"] = alter(runtime["scientific_tasks"])
    with pytest.raises(ValueError):
        cli._scientific_selection(runtime, image, roles, authored)


@pytest.mark.parametrize("mismatch", ["missing", "worker", "parent", "grant", "mixed"])
def test_advection_requires_exact_separate_authored_runtime(
    tmp_path, monkeypatch, mismatch
):
    ledger, image, roles, authored = configuration(tmp_path, monkeypatch, "advection")
    runtime = copy.deepcopy(ledger.admission.document["runtime"])
    if mismatch == "missing":
        authored = None
    elif mismatch == "worker":
        authored = image
    elif mismatch == "parent":
        image = SimpleNamespace(image_id="sha256:" + "e" * 64)
    elif mismatch == "grant":
        del runtime["authored_research"]
    else:
        runtime["scientific_tasks"].append(
            {"schema": "carbon.public-julia-study.scope.v1"}
        )
    with pytest.raises(ValueError):
        cli._scientific_selection(runtime, image, roles, authored)


def test_invalid_scope_is_rejected_before_reference_attachment(monkeypatch):
    from carbon.development_session import research_data

    def forbidden(**kwargs):
        pytest.fail("invalid scope reached the reference consumer constructor")

    monkeypatch.setattr(research_data, "PublicReferenceData", forbidden)
    ledger = SimpleNamespace(
        admission=SimpleNamespace(document={"runtime": {"scientific_tasks": []}})
    )
    with pytest.raises(ValueError, match="closed registered"):
        cli._science(ledger, "test-miner", None, None)


@pytest.mark.parametrize("kind", ["burgers", "envelope", "advection"])
def test_expired_owned_cleanup_constructs_but_cannot_execute(
    tmp_path, monkeypatch, kind
):
    config = configuration(tmp_path, monkeypatch, kind)
    ledger = config[0]
    ledger.clock = lambda: ledger.admission.document["expires_unix"] + 1
    with pytest.raises(ValueError):
        attach(config)
    material = attach(config, cleanup=True)
    with pytest.raises(ValueError):
        material("capabilities", ResearchWorkspace(ledger, "test-miner"))
    for scope in ledger.admission.document["runtime"]["scientific_tasks"]:
        with pytest.raises(ValueError):
            material(scope["material"], None)
    with pytest.raises(ValueError):
        attach(config, cleanup=True, owner="other")
    ledger.generation += 1
    with pytest.raises(ValueError):
        attach(config, cleanup=True)
    with ledger.db() as db:
        assert db.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == 0


@pytest.mark.parametrize("kind", ["envelope", "advection"])
@pytest.mark.parametrize("cleanup", [False, True])
def test_normal_stdio_factory_attaches_exact_material_and_shared_image(
    tmp_path, monkeypatch, kind, cleanup
):
    """Real CLI owner/control/service composition, fixture external host and transport."""
    from test_c08_authenticated_miner_mcp import (
        CONTEXT,
        NOW,
        _Adapter,
        _snapshot,
        _Verifier,
    )

    from carbon.development_session.profile import CHALLENGE
    from carbon.development_session.research_service import make_research_service
    from carbon.transport.gateway import AuthenticatedGateway
    from carbon.transport.store import ReceiptJournal

    config = configuration(tmp_path, monkeypatch, kind)
    ledger, image, roles, authored = config
    with ledger.db() as db:
        manifest = json.loads(db.execute("SELECT manifest FROM campaign").fetchone()[0])
    profile_path = tmp_path / "operator.json"
    document = {"principal": manifest["principal"]}
    profile_path.write_bytes(canonical(document))
    profile_path.chmod(0o600)
    profile = cli.OperatorProfile(
        profile_path, document, ledger.admission, ledger.root, manifest, cleanup
    )
    initial = make_research_service(
        root=ledger.root / "research-tasks",
        ledger=ledger,
        owner="test-miner",
        image=image,
        public_material=attach(config),
        practice=None,
        julia_image=authored,
    )
    initial.tasks.close()
    if cleanup:
        ledger.clock = lambda: ledger.admission.document["expires_unix"] + 1

    snapshot = _snapshot()

    async def observe():
        return snapshot

    connection = SimpleNamespace(
        check_registration=observe,
        chain_context=CONTEXT,
        publisher="fixture",
        miner_key=object(),
        service=SimpleNamespace(
            gateway=AuthenticatedGateway(
                CONTEXT,
                CHALLENGE,
                "fixture",
                _Adapter(snapshot),
                _Verifier(),
                ReceiptJournal(ledger.root / "transport.sqlite3", CONTEXT),
                clock_ns=lambda: NOW,
            )
        ),
    )

    async def requester(_connection):
        return "test-miner"

    seen = []

    def server(adapter):
        async def run_async():
            sdk = adapter._sdk
            selected = sdk.composition.executor.public_material
            assert type(selected) is (
                JuliaEnvelopeMaterial if kind == "envelope" else PublicAdvectionMaterial
            )
            assert sdk.composition.executor.julia_image is authored
            if cleanup:
                assert await sdk.connection.check_cleanup_registration()
                with pytest.raises(ValueError, match="cleanup-only"):
                    await sdk.connection.check_registration()
                with pytest.raises(ValueError):
                    selected("capabilities", sdk.composition.executor.workspace)
            else:
                assert await sdk.connection.check_registration()
            seen.append(kind)

        return SimpleNamespace(run_async=run_async)

    monkeypatch.setattr(cli, "load_profile", lambda *a, **kw: profile)
    monkeypatch.setattr(cli, "CampaignLedger", lambda *a, **kw: ledger)
    monkeypatch.setattr(cli, "_runtime", lambda p: (connection, image, image, roles))
    monkeypatch.setattr(cli, "_requester", requester)
    monkeypatch.setattr(cli, "_authored_image", lambda *a: authored)
    monkeypatch.setattr(cli, "create_stdio_server", server)
    asyncio.run(cli.serve(profile_path, cleanup_only=cleanup))
    assert seen == [kind]
