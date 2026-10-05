"""Development-only construction-contract variants (GRAPHITE-DEV-VARIANTS-01).

OWNER-GRAPHITE-TEST-WAVE-03 §1 and OWNER-GRAPHITE-DEV-LEVELS-01. Claims tested:

- a variant is a registered, versioned policy: its document is pinned by digest
  in `registry.json`, a re-pinned or altered document is refused, and the
  shipped registry is empty of fixtures;
- the owner's bounds: Levels 1-3 only (4-5 wait for isolation), no participant
  code, Level 3 a declarative `choice` menu only, every widened surface bounded
  and actually new;
- a variant's base is the live miner-facing contract its newest expansion
  record pins; a stale base is refused where the variant is used;
- development expansion records live in `expansions/<token>/dev/NNNN.json`,
  bound to the variant's digest and its base contract record, and the Level 0
  trail never reads them;
- `compile_development` compiles a strategy under a registered variant only:
  the base through `compile_submission`, the widened values within their
  bounds, each rebuilt by Carbon's registered reconstruction; a variant with
  no reconstruction is refused.

Every variant here is a synthetic FIXTURE_NOT_PRODUCTION document in a
temporary registry. None is a real Level 1-3 surface, and nothing here is
scientific or security acceptance. Other test modules import the fixture
helpers (`fixture_document`, `install`, `FIXTURE_DIGESTS`).
"""

from __future__ import annotations

import copy
import datetime
import json

import pytest

from carbon.reconstruction import capability_registry as cr
from carbon.reconstruction import development_variants as dv
from carbon.reconstruction import expansion_record

BATTERY = cr.BATTERY_CHALLENGE
DAY = datetime.date(2026, 10, 4)

#: One synthetic widened capability per level. Their names say they are
#: fixtures; none is a capability Carbon has drafted.
FIXTURE_WIDENED = {
    1: {
        "id": "objective.fixture_only_weighting",
        "summary": "FIXTURE ONLY: a synthetic bounded weight",
        "surface": ["train", "float", 0.0, 1.0, 0.5],
        "applies_to": None,
        "bounds": {"fixture": "a float in [0, 1]"},
    },
    2: {
        "id": "schedule.fixture_only_cycles",
        "summary": "FIXTURE ONLY: a synthetic bounded count",
        "surface": ["train", "uint", 1, 4, 1],
        "applies_to": None,
        "bounds": {"fixture": "an integer in [1, 4]"},
    },
    3: {
        "id": "optimizer.fixture_only_menu",
        "summary": "FIXTURE ONLY: a synthetic fixed menu",
        "surface": ["train", "choice", ["none", "fixture"], None, "none"],
        "applies_to": None,
        "bounds": {"fixture": "one of a fixed two-item menu"},
    },
}


def _base():
    newest = expansion_record.records(BATTERY)[-1]
    return {"digest": newest["contract_digest"], "record_sequence": newest["sequence"]}


def fixture_document(level, *, widened=None, **changes):
    """A synthetic variant document for battery at `level`. Never production."""
    document = {
        "schema": dv.VARIANT_SCHEMA,
        "version": f"fixture-battery-level-{level}-v1",
        "challenge": BATTERY,
        "level": level,
        "scope": dv.SCOPE,
        "status": dv.FIXTURE,
        "authority": "test fixture; not a registered policy",
        "review": {"reviewer": "test fixture", "record": "none: a fixture"},
        "base_contract": _base(),
        "participant_code": False,
        "widened": (
            [copy.deepcopy(FIXTURE_WIDENED[level])] if widened is None else widened
        ),
    }
    document.update(changes)
    return document


#: The fixture variants' digests, computed without installing anything.
FIXTURE_DIGESTS = {level: dv.digest_of(fixture_document(level)) for level in (1, 2, 3)}


def fixture_reconstruction(value, admitted, granted=None):
    """A synthetic reconstruction: records the value against the base recipe."""
    return {"fixture_value": value, "base_recipe": admitted.construction.recipe_digest}


def install(
    root,
    monkeypatch,
    documents=None,
    *,
    current=None,
    record=True,
    reconstruct=True,
):
    """Install a temporary variant registry: the documents, a registry pinning
    each, the current one per (challenge, level), development records under a
    temporary expansions root and fixture reconstructions. Returns the
    variants by level."""
    documents = (
        [fixture_document(level) for level in (1, 2, 3)]
        if documents is None
        else documents
    )
    folder = root / "variants"
    folder.mkdir(parents=True, exist_ok=True)
    versions = {}
    for document in documents:
        (folder / f"{document['version']}.json").write_text(json.dumps(document))
        versions[document["version"]] = dv.digest_of(document)
    current = (
        [
            {"challenge": d["challenge"], "level": d["level"], "version": d["version"]}
            for d in documents
        ]
        if current is None
        else current
    )
    (folder / "registry.json").write_text(
        json.dumps(
            {
                "schema": cr.DEVELOPMENT_VARIANT_REGISTRY_SCHEMA,
                "scope": dv.SCOPE,
                "rule": "fixture registry",
                "versions": versions,
                "current": current,
            }
        )
    )
    monkeypatch.setattr(cr, "DEVELOPMENT_VARIANT_DIR", folder)
    monkeypatch.setattr(dv, "DEV_ROOT", root / "expansions")
    if reconstruct:
        for document in documents:
            for widened in document["widened"]:
                monkeypatch.setitem(
                    dv.RECONSTRUCTIONS,
                    (document["challenge"], widened["id"]),
                    fixture_reconstruction,
                )
    found = {}
    for entry in current:
        variant = dv.load().current[(entry["challenge"], entry["level"])]
        if record:
            dv.record_development(
                entry["challenge"],
                entry["level"],
                "fixture: a synthetic development variant for tests",
                today=DAY,
            )
        found[entry["level"]] = variant
    return found


@pytest.fixture
def variants(tmp_path, monkeypatch):
    return install(tmp_path, monkeypatch)


# --- the shipped registry -----------------------------------------------------------


def test_the_shipped_registry_is_registered_pinned_and_holds_no_fixture():
    registry = dv.load()
    assert dv.load(dv.SHIPPED_DIR) == registry
    for variant in registry.by_version.values():
        assert variant.status == dv.REGISTERED
        assert variant.digest not in {c.digest for c in cr.CONTRACTS.values()}
    assert dict(dv.DEV_VARIANTS) == registry.current
    assert dv.dev_unrecorded() == {}
    assert dv.dev_problems() == []
    assert dv.main(["check"]) == 0
    # The shipped registry is the one the capability registry reads.
    raw = cr.development_variant_registry()
    assert raw["schema"] == cr.DEVELOPMENT_VARIANT_REGISTRY_SCHEMA
    assert cr.development_variant_names() == frozenset(raw["versions"]) | frozenset(
        raw["versions"].values()
    )


def test_a_fixture_is_refused_in_the_shipped_registry(tmp_path, monkeypatch):
    install(tmp_path, monkeypatch, record=False)
    monkeypatch.setattr(dv, "SHIPPED_DIR", tmp_path / "variants")
    with pytest.raises(dv.VariantRefused) as refused:
        dv.load()
    assert refused.value.code == dv.FIXTURE_SHIPPED


# --- a registered, versioned policy pinned by digest --------------------------------


def test_a_variant_is_registered_by_level_and_pinned_by_digest(variants):
    for level, variant in variants.items():
        assert dv.DEV_VARIANTS[(BATTERY, level)] == variant
        assert variant.digest == FIXTURE_DIGESTS[level]
        assert variant.schema == dv.VARIANT_SCHEMA
        assert (
            variant.document()["schema"] == "carbon.construction-development-variant.v1"
        )
        assert variant.base_contract_digest == cr.contract(BATTERY).digest
        assert variant.permissions() == (FIXTURE_WIDENED[level]["id"],)
        assert dv.registered(variant.digest) == variant
        assert dv.registered(variant.digest, BATTERY) == variant
    # Held outside CONTRACTS: no variant is a construction contract.
    assert not set(FIXTURE_DIGESTS.values()) & {c.digest for c in cr.CONTRACTS.values()}
    assert set(dv.DEV_VARIANTS) == {(BATTERY, 1), (BATTERY, 2), (BATTERY, 3)}
    with pytest.raises(dv.VariantRefused) as refused:
        dv.variant(BATTERY, 4)
    assert refused.value.code == dv.UNREGISTERED
    with pytest.raises(dv.VariantRefused) as refused:
        dv.registered("sha256:" + "e" * 64)
    assert refused.value.code == dv.UNREGISTERED
    with pytest.raises(dv.VariantRefused) as refused:
        dv.registered(variants[1].digest, cr.BURGERS_CHALLENGE)
    assert refused.value.code == dv.UNREGISTERED


def test_an_altered_or_repinned_document_is_refused(tmp_path, monkeypatch):
    install(tmp_path, monkeypatch, record=False)
    path = tmp_path / "variants" / "fixture-battery-level-1-v1.json"
    document = json.loads(path.read_text())
    document["widened"][0]["surface"][3] = 2.0  # widen the bound silently
    path.write_text(json.dumps(document))
    with pytest.raises(dv.VariantRefused) as refused:
        dv.load()
    assert refused.value.code == dv.ALTERED
    # Every lookup reads the pinned registry, so the use is refused too.
    with pytest.raises(dv.VariantRefused):
        dv.DEV_VARIANTS[(BATTERY, 1)]


def test_a_superseded_version_stays_registered_but_does_not_run(tmp_path, monkeypatch):
    old = fixture_document(1)
    new = fixture_document(1, version="fixture-battery-level-1-v2")
    install(
        tmp_path,
        monkeypatch,
        [old, new],
        current=[{"challenge": BATTERY, "level": 1, "version": new["version"]}],
        record=False,
    )
    assert cr.is_development_variant(dv.digest_of(old))  # still refused to miners
    assert dv.variant(BATTERY, 1).version == new["version"]
    with pytest.raises(dv.VariantRefused) as refused:
        dv.registered(dv.digest_of(old))
    assert refused.value.code == dv.UNREGISTERED


# --- the owner's bounds (OWNER-GRAPHITE-DEV-LEVELS-01) ------------------------------


def _surface(level, surface):
    return [dict(FIXTURE_WIDENED[level], surface=surface)]


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"level": 4}, dv.NEEDS_ISOLATION),
        ({"level": 5}, dv.NEEDS_ISOLATION),
        ({"level": 0}, dv.LEVEL_INVALID),
        ({"level": "1"}, dv.LEVEL_INVALID),
        ({"participant_code": True}, dv.PARTICIPANT_CODE),
        ({"participant_code": None}, dv.PARTICIPANT_CODE),
        ({"scope": "MINER_FACING"}, dv.MALFORMED),
        ({"challenge": "no-such-challenge"}, dv.MALFORMED),
        ({"status": "ACCEPTED"}, dv.MALFORMED),
        ({"review": {"reviewer": "HUMAN_INPUT", "record": "x"}}, dv.MALFORMED),
        ({"widened": []}, dv.WIDENS_NOTHING),
        ({"base_contract": {"digest": "level-0", "record_sequence": 1}}, dv.MALFORMED),
    ],
)
def test_the_owners_bounds_are_enforced(changes, code):
    with pytest.raises(dv.VariantRefused) as refused:
        dv.DevContractVariant.from_document({**fixture_document(1), **changes})
    assert refused.value.code == code


def test_level_3_is_a_declarative_menu_only():
    dv.DevContractVariant.from_document(fixture_document(3))
    for surface in (
        ["train", "uint", 1, 4, 1],
        ["train", "float", 0.0, 1.0, 0.5],
        ["train", "bool", None, None, False],
        None,
    ):
        with pytest.raises(dv.VariantRefused) as refused:
            dv.DevContractVariant.from_document(
                fixture_document(3, widened=_surface(3, surface))
            )
        assert refused.value.code == dv.MENU_ONLY
    # The same numeric surface is a valid bounded field at Level 2.
    dv.DevContractVariant.from_document(
        fixture_document(2, widened=_surface(2, ["train", "uint", 1, 4, 1]))
    )


@pytest.mark.parametrize(
    "surface",
    [
        ["train", "uint", 4, 1, 2],
        ["train", "uint", -1, 4, 1],
        ["train", "float", 0.0, 1.0, 2.0],
        ["train", "float", 0.0, "inf", 0.5],
        ["train", "choice", [], None, "none"],
        ["train", "choice", ["a", "a"], None, "a"],
        ["train", "choice", ["a", "b"], None, "c"],
        ["train", "bool", 0, 1, False],
        ["nowhere", "uint", 1, 4, 1],
        ["train", "uint", 1, 4],
    ],
)
def test_every_widened_surface_is_bounded(surface):
    with pytest.raises(dv.VariantRefused) as refused:
        dv.DevContractVariant.from_document(
            fixture_document(2, widened=_surface(2, surface))
        )
    assert refused.value.code == dv.MALFORMED


@pytest.mark.parametrize(
    ("widened", "code"),
    [
        # Already rebuildable at Level 0: nothing widened.
        ({"id": "architecture.width"}, dv.WIDENS_NOTHING),
        # A field the contract already has, under another dimension.
        ({"id": "objective.width"}, dv.MALFORMED),
        ({"id": "not_a_dimension.fixture"}, dv.MALFORMED),
        ({"id": "objective.Fixture"}, dv.MALFORMED),
        ({"bounds": {}}, dv.MALFORMED),
        ({"summary": "TODO"}, dv.MALFORMED),
        ({"applies_to": ["no_such_family"]}, dv.MALFORMED),
    ],
)
def test_a_widening_is_new_bounded_and_stated(widened, code):
    entry = dict(FIXTURE_WIDENED[1], **widened)
    with pytest.raises(dv.VariantRefused) as refused:
        dv.DevContractVariant.from_document(fixture_document(1, widened=[entry]))
    assert refused.value.code == code


def test_a_stale_base_is_refused_where_the_variant_is_used(tmp_path, monkeypatch):
    stale = fixture_document(
        1, base_contract={"digest": "sha256:" + "0" * 64, "record_sequence": 1}
    )
    install(tmp_path, monkeypatch, [stale], record=False)
    for use in (
        lambda: dv.variant(BATTERY, 1),
        lambda: dv.registered(dv.digest_of(stale)),
        lambda: dv.record_development(BATTERY, 1, "a stale base is never recorded"),
    ):
        with pytest.raises(dv.VariantRefused) as refused:
            use()
        assert refused.value.code == dv.BASE_STALE


# --- development expansion records ---------------------------------------------------


def test_development_records_bind_the_variant_and_its_base_record(variants, tmp_path):
    folder = tmp_path / "expansions" / BATTERY / dv.DEV_FOLDER
    assert sorted(p.name for p in folder.iterdir()) == [
        "0000.json",
        "0001.json",
        "0002.json",
    ]
    records = dv.dev_records(BATTERY)
    for record, level in zip(records, (1, 2, 3)):
        assert record["schema"] == dv.DEV_RECORD_SCHEMA
        assert record["scope"] == "DEVELOPMENT_ONLY_NEVER_SERVED_TO_MINERS"
        assert record["variant_digest"] == variants[level].digest
        assert dv.digest_of(record["variant_document"]) == record["variant_digest"]
        newest = expansion_record.records(BATTERY)[-1]
        assert record["base_contract"] == {
            "sequence": newest["sequence"],
            "contract_digest": newest["contract_digest"],
        }
    assert dv.dev_problems() == [] and dv.dev_unrecorded() == {}
    # The Level 0 trail reads only its own 4-digit files, never the subfolder.
    assert expansion_record.records(BATTERY, tmp_path / "expansions") == []
    bound = dv.recorded_variant(variants[2])
    assert bound == {
        "challenge": BATTERY,
        "level": 2,
        "contract_digest": cr.contract(BATTERY).digest,
        "record_sequence": expansion_record.records(BATTERY)[-1]["sequence"],
        "development_variant": variants[2].digest,
        "development_record_sequence": 1,
        "scope": dv.SCOPE,
    }
    with pytest.raises(ValueError, match="already recorded"):
        dv.record_development(BATTERY, 1, "the same variant again, recorded twice")


def test_an_unrecorded_variant_does_not_run(tmp_path, monkeypatch):
    found = install(tmp_path, monkeypatch, record=False)
    assert set(dv.dev_unrecorded()) == {(BATTERY, 1), (BATTERY, 2), (BATTERY, 3)}
    with pytest.raises(dv.VariantRefused) as refused:
        dv.recorded_variant(found[1])
    assert refused.value.code == dv.UNRECORDED
    with pytest.raises(ValueError, match="say what"):
        dv.record_development(BATTERY, 1, "short")


def test_a_tampered_development_record_is_a_problem(variants, tmp_path):
    path = tmp_path / "expansions" / BATTERY / dv.DEV_FOLDER / "0001.json"
    record = json.loads(path.read_text())
    record["variant_document"]["widened"][0]["surface"][3] = 40
    path.write_text(json.dumps(record))
    problems = dv.dev_problems()
    assert any("0001.json: digest does not match" in p for p in problems)
    record = json.loads(path.read_text())
    record["base_contract"]["sequence"] = 99
    path.write_text(json.dumps(record))
    assert any("not bound to a recorded base" in p for p in dv.dev_problems())


# --- the development-only compile path -----------------------------------------------


def _strategy(**parameters):
    from carbon.battery.research import SCAFFOLD

    strategy = copy.deepcopy(SCAFFOLD)
    strategy.setdefault("parameters", {}).update(parameters)
    return strategy


def test_compile_development_builds_the_base_and_each_widened_value(variants):
    pytest.importorskip("numpy")
    from carbon.reconstruction.challenge_contracts import compile_submission

    variant = variants[2]
    plain = compile_submission(_strategy())
    built = dv.compile_development(_strategy(fixture_only_cycles=3), variant)
    assert built.contract_digest == cr.contract(BATTERY).digest
    assert built.construction.recipe_digest == plain.construction.recipe_digest
    assert built.widened == {"fixture_only_cycles": 3}
    assert built.reconstruction == {
        "schedule.fixture_only_cycles": {
            "fixture_value": 3,
            "base_recipe": plain.construction.recipe_digest,
        }
    }
    assert built.development["variant_digest"] == variant.digest
    assert built.development["level"] == 2
    other = dv.compile_development(_strategy(fixture_only_cycles=4), variant)
    # Two widened values never share a binding, though their base recipe does.
    assert other.development["widened_digest"] != built.development["widened_digest"]
    # Level 0's own path refuses the widened field by name, unchanged.
    from carbon.reconstruction.challenge_contracts import SubmissionRefused

    with pytest.raises(SubmissionRefused, match="parameter.unknown"):
        compile_submission(_strategy(fixture_only_cycles=3))


@pytest.mark.parametrize(
    ("value", "issue"),
    [
        (0, "development.out_of_bounds"),
        (5, "development.out_of_bounds"),
        (2.0, "development.out_of_bounds"),
        (True, "development.out_of_bounds"),
    ],
)
def test_a_widened_value_outside_its_bounds_is_refused(variants, value, issue):
    with pytest.raises(dv.VariantRefused) as refused:
        dv.compile_development(_strategy(fixture_only_cycles=value), variants[2])
    assert refused.value.code == dv.PARAMETER_REFUSED
    assert refused.value.issues == ((issue, "/parameters/fixture_only_cycles"),)


def test_a_variant_without_its_reconstruction_never_compiles(tmp_path, monkeypatch):
    found = install(tmp_path, monkeypatch, reconstruct=False)
    with pytest.raises(dv.VariantRefused) as refused:
        dv.compile_development(_strategy(), found[1])
    assert refused.value.code == dv.RECONSTRUCTION_MISSING


def test_only_a_registered_variant_compiles(variants):
    unregistered = dv.DevContractVariant.from_document(
        fixture_document(1, version="fixture-battery-level-1-unregistered")
    )
    with pytest.raises(dv.VariantRefused) as refused:
        dv.compile_development(_strategy(), unregistered)
    assert refused.value.code == dv.UNREGISTERED
    with pytest.raises(TypeError):
        dv.compile_development(_strategy(), variants[1].digest)
    wrong = dict(_strategy(), challenge_id=cr.BURGERS_CHALLENGE)
    with pytest.raises(dv.VariantRefused) as refused:
        dv.compile_development(wrong, variants[1])
    assert refused.value.code == dv.WRONG_CHALLENGE


def test_the_variant_module_is_pure_data_at_import():
    import subprocess
    import sys

    code = (
        "import sys, carbon.reconstruction.development_variants\n"
        "bad = [m for m in ('numpy', 'jax', 'torch') if m in sys.modules]\n"
        "print(bad)\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "[]"
