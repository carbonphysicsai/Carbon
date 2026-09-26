"""CLI composition fixtures; no provider, native numerical worker or campaign run."""

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
    import contextlib

    class FrozenCampaign:
        """Only the frozen manifest `_science` reads its runtime from."""

        @contextlib.contextmanager
        def db(self):
            row = (json.dumps({"runtime": {"scientific_tasks": []}}),)
            yield SimpleNamespace(
                execute=lambda *_: SimpleNamespace(fetchone=lambda: row)
            )

    with pytest.raises(ValueError, match="closed registered"):
        cli._science(FrozenCampaign(), "test-miner", None, None)


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
def test_attaching_a_retired_burgers_campaign_is_refused(tmp_path, monkeypatch, kind):
    """Burgers is retired from the research path. The stdio attach that once
    composed its scientific-task material now refuses a Burgers campaign (one
    frozen before Challenges were named) by code, before any composition."""
    from carbon.challenge_registry import ChallengeRetired
    from carbon.challenge_registry.campaigns import campaign_for_manifest

    ledger, _, _, _ = configuration(tmp_path, monkeypatch, kind)
    with ledger.db() as db:
        manifest = json.loads(db.execute("SELECT manifest FROM campaign").fetchone()[0])
    assert "challenge" not in manifest
    with pytest.raises(ChallengeRetired) as refused:
        campaign_for_manifest(manifest)
    assert refused.value.public()["code"] == "challenge_retired"
