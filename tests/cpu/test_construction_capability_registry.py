"""The construction capability registry is the one source of what can be submitted.

Claims tested: an entry cannot claim more than it carries (no rebuildable entry
without its implementation, no owner blocker without its trigger, no admission
at all); every consumer - research catalog, reconstruction profile, capability
catalogue - derives from the registry; and the public projection carries only
registry-defined text. Each refusal is paired with the valid entry it differs
from.
"""

import json
from pathlib import Path

import pytest

from carbon.reconstruction import capability_registry as r
from carbon.reconstruction.capability_registry import (
    REGISTRY,
    Blocker,
    Capability,
    Dimension,
    Status,
    Surface,
    Trigger,
)

SURFACE = Surface("model", "uint", 1, 8, 2)


def valid(**overrides):
    fields = {
        "capability_id": "architecture.example",
        "dimension": Dimension.ARCHITECTURE,
        "summary": "An example field",
        "status": Status.REBUILDABLE_DEVELOPMENT,
        "surface": SURFACE,
    }
    return Capability(**{**fields, **overrides})


def test_the_specimen_entry_is_valid():
    assert valid().status is Status.REBUILDABLE_DEVELOPMENT


@pytest.mark.parametrize(
    "overrides",
    [
        # No entry may claim admission: that needs qualification evidence.
        {"status": Status.ADMITTED},
        # A rebuildable field carries its surface; a blocker contradicts it.
        {"surface": None},
        {"blocker": Blocker.ENGINEERING},
        # Research-only work carries no implementation and is blocked.
        {"status": Status.RESEARCH_ONLY, "blocker": Blocker.ENGINEERING},
        {"status": Status.RESEARCH_ONLY, "surface": None},
        # An owner blocker names its trigger; an engineering one does not.
        {
            "status": Status.RESEARCH_ONLY,
            "surface": None,
            "blocker": Blocker.OWNER_DECISION,
        },
        {
            "status": Status.RESEARCH_ONLY,
            "surface": None,
            "blocker": Blocker.ENGINEERING,
            "trigger": Trigger.COMPARISON_REGIME,
        },
        # An exclusion is blocked as excluded and names its trigger.
        {"status": Status.EXCLUDED, "surface": None, "blocker": Blocker.ENGINEERING},
        # The id is <dimension>.<name>.
        {"capability_id": "optimizer.example"},
        {"capability_id": "architecture"},
    ],
)
def test_an_entry_cannot_claim_more_than_it_carries(overrides):
    with pytest.raises((ValueError, TypeError)):
        valid(**overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "status": Status.RESEARCH_ONLY,
            "surface": None,
            "blocker": Blocker.ENGINEERING,
        },
        {
            "status": Status.RESEARCH_ONLY,
            "surface": None,
            "blocker": Blocker.OWNER_DECISION,
            "trigger": Trigger.EVIDENCE_DESIGN,
        },
        {
            "status": Status.EXCLUDED,
            "surface": None,
            "blocker": Blocker.EXCLUDED,
            "trigger": Trigger.EXECUTABLE_SUBMISSION,
        },
    ],
)
def test_each_non_rebuildable_shape_is_constructible(overrides):
    """Specimens: the refusals above are about the combination, not the status."""
    assert valid(**overrides).surface is None


def test_a_rebuildable_family_names_its_selector_and_lab_kind():
    family = {
        "capability_id": "model_family.example",
        "dimension": Dimension.MODEL_FAMILY,
        "summary": "An example family",
        "status": Status.REBUILDABLE_DEVELOPMENT,
    }
    with pytest.raises(ValueError):
        Capability(**family, selector="example")
    assert Capability(**family, selector="example", lab_kind="example1d").lab_kind


def test_ids_and_field_names_are_unique():
    ids = [c.capability_id for c in REGISTRY]
    assert len(ids) == len(set(ids))
    fields = [c.capability_id.partition(".")[2] for c in REGISTRY if c.surface]
    assert len(fields) == len(set(fields))


def test_no_entry_is_admitted_and_every_escalation_names_a_trigger():
    assert not [c for c in REGISTRY if c.status is Status.ADMITTED]
    for c in REGISTRY:
        if c.blocker in (Blocker.OWNER_DECISION, Blocker.EXCLUDED):
            assert type(c.trigger) is Trigger, c.capability_id


def test_every_consumer_derives_from_the_registry():
    from carbon.development_session import research_catalog
    from carbon.reconstruction import profile
    from carbon.reconstruction.catalogue import reconstruction_capabilities

    families = r.rebuildable_families()
    selectors = tuple(s for s, _ in families)
    assert research_catalog.RESEARCH_BACKBONES == selectors
    assert research_catalog.SURFACES == r.catalog_surfaces()
    assert {s: k for s, (_, k) in profile._BACKBONES.items()} == dict(families)
    lab = [c for c in reconstruction_capabilities() if c.current_research_selection]
    assert [(c.architecture_family, c.backbone_kind) for c in lab] == list(families)
    # Specimen: the registry also holds families that are not rebuildable,
    # and none of them leaked into any consumer.
    pending = [
        c.capability_id
        for c in REGISTRY
        if c.dimension is Dimension.MODEL_FAMILY
        and c.status is not Status.REBUILDABLE_DEVELOPMENT
    ]
    assert "model_family.foundax_deeponet" in pending
    assert "foundax_deeponet" not in selectors


def test_every_rebuildable_family_is_in_the_strategy_vocabulary():
    from carbon.schema.strategy import _SUPPORTED_BACKBONES

    selectors = {
        s for challenge in r.CONTRACTS for s, _ in r.rebuildable_families(challenge)
    }
    assert selectors <= _SUPPORTED_BACKBONES
    # The structural vocabulary still holds legacy names with no rebuild path;
    # per-Challenge admission refuses them by name (test_challenge_contracts).
    assert _SUPPORTED_BACKBONES - selectors == {"uno", "physicsnemo_fno"}


def test_the_public_projection_is_registry_text_only():
    document = r.public_registry()
    json.dumps(document)  # serializable, no enums or objects
    assert len(document["capabilities"]) == len(REGISTRY)
    statuses = {c["status"] for c in document["capabilities"]}
    assert statuses <= {s.value for s in Status}
    assert Status.ADMITTED.value not in statuses
    by_id = {c["id"]: c for c in document["capabilities"]}
    assert by_id["model_family.transolver"]["status"] == "rebuildable_development"
    assert by_id["model_family.pretrained_weights"]["status"] == "excluded"
    assert by_id["training_data.case_count_and_resolution"]["trigger"] == (
        "new_comparison_or_resource_regime"
    )


def test_importing_the_registry_initializes_no_numerical_runtime():
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import carbon.reconstruction.capability_registry; "
                "bad = {'jax', 'numpy', 'torch'} & "
                "{m.split('.')[0] for m in sys.modules}; assert not bad, bad"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    assert result.returncode == 0, result.stderr
