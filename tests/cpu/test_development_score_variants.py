"""Development score variants (VALIDATOR-09): registered before computed,
re-scored from stored per-case rows, never served to miners.

Fixture variants live in a test directory; the shipped registry is empty and
refuses a fixture.
"""

import json

import pytest

from carbon.challenge_validator.scoring import scoring_for
from carbon.scoring import development_score_variants as dsv

BATTERY = "battery-fastcharge-ageing-development-v1"
COMPONENTS = ("voltage", "temperature", "plating", "capacity")


def document(version="battery-w-test-v1", **changes):
    value = {
        "schema": dsv.SCHEMA,
        "version": version,
        "challenge_id": BATTERY,
        "base_rule": "battery-practice-v1",
        "weights": {
            "voltage": "0.4",
            "temperature": "0.2",
            "plating": "0.3",
            "capacity": "0.1",
        },
        "aggregate_terms": [],
        "gates": {},
        "comparison": None,
        "important_region": None,
        "transform": None,
        "scope": dsv.SCOPE,
        "status": "CANDIDATE",
        "authority": {"registered_by": "test"},
        "fixture": True,
    }
    value.update(changes)
    return value


def register(tmp_path, *documents, pin=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    variants = {}
    for item in documents:
        (tmp_path / f"{item['version']}.json").write_text(json.dumps(item))
        variants[item["version"]] = pin or dsv.digest(item)
    (tmp_path / "registry.json").write_text(
        json.dumps({"schema": dsv.REGISTRY_SCHEMA, "variants": variants})
    )
    return tmp_path


def test_battery_declares_the_components_its_rows_carry():
    from carbon.battery import exam

    assert scoring_for(BATTERY).declared_score_components == exam.COMPONENTS


def test_the_shipped_registry_is_empty_and_refuses_an_unregistered_version():
    assert dsv.registered() == {}
    with pytest.raises(dsv.ScoreVariantRefused) as refused:
        dsv.load_variant("anything")
    assert refused.value.code == "score_variant_unregistered"


def test_a_registered_variant_loads_with_its_identity(tmp_path):
    item = document()
    variant = dsv.load_variant(item["version"], directory=register(tmp_path, item))
    assert variant.weights == (
        ("voltage", 0.4),
        ("temperature", 0.2),
        ("plating", 0.3),
        ("capacity", 0.1),
    )
    identity = variant.identity()
    assert identity["score_variant_digest"] == dsv.digest(item)
    assert identity["label"] == "development_score_result:battery-w-test-v1"


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        (
            {"weights": {"voltage": "0.5", "humidity": "0.5"}},
            "score_variant_component_not_declared",
        ),
        (
            {"weights": {"voltage": "0.5", "plating": "0.4"}},
            "score_variant_weights_not_unit_sum",
        ),
        (
            {"weights": {"voltage": "1.2", "plating": "-0.2"}},
            "score_variant_weights_not_unit_sum",
        ),
        ({"weights": {"voltage": "nan"}}, "score_variant_malformed"),
        ({"aggregate_terms": ["bias_B"]}, "score_variant_aggregate_terms_not_served"),
        (
            {"gates": {"overrides": {"capacity_bound": "0.1"}}},
            "score_variant_gate_overrides_not_served",
        ),
        ({"comparison": {"alpha": 0.1}}, "score_variant_comparison_not_served"),
        ({"scope": "SERVED"}, "score_variant_malformed"),
        ({"status": "ADOPTED"}, "score_variant_malformed"),
        ({"transform": {"kind": "linear"}}, "score_variant_transform_malformed"),
    ],
)
def test_every_malformed_or_unserved_variant_is_refused_by_name(
    tmp_path, changes, code
):
    item = document(**changes)
    with pytest.raises(dsv.ScoreVariantRefused) as refused:
        dsv.load_variant(item["version"], directory=register(tmp_path, item))
    assert refused.value.code == code


def test_an_altered_document_is_refused(tmp_path):
    item = document()
    directory = register(tmp_path, item)
    item["weights"]["voltage"], item["weights"]["capacity"] = "0.1", "0.4"
    (directory / f"{item['version']}.json").write_text(json.dumps(item))
    with pytest.raises(dsv.ScoreVariantRefused) as refused:
        dsv.load_variant(item["version"], directory=directory)
    assert refused.value.code == "score_variant_altered"


def test_a_fixture_is_refused_in_the_shipped_registry(monkeypatch, tmp_path):
    item = document()
    directory = register(tmp_path, item)
    monkeypatch.setattr(dsv, "POLICY_DIR", directory)
    with pytest.raises(dsv.ScoreVariantRefused) as refused:
        dsv.load_variant(item["version"])
    assert refused.value.code == "score_variant_fixture_in_shipped_registry"


def rows():
    def case(state, important=False, **components):
        return {"state": state, "important": important, "components": components}

    return [
        case("SCORABLE", True, voltage=1.0, temperature=0.0, plating=0.0, capacity=0.0),
        case(
            "SCORABLE", False, voltage=0.0, temperature=1.0, plating=1.0, capacity=1.0
        ),
        case("REFERENCE_INVALID"),
    ]


def test_rescore_reweights_the_stored_rows_without_retraining(tmp_path):
    item = document()
    variant = dsv.load_variant(item["version"], directory=register(tmp_path, item))
    result = dsv.rescore(variant, rows())
    # case 1: 0.4; case 2: 0.2 + 0.3 + 0.1 = 0.6; the mean is 0.5.
    assert result["error"] == pytest.approx(0.5)
    assert result["important_error"] == pytest.approx(0.4)
    assert (result["eligible"], result["n_scored"]) == (True, 2)
    assert result["score"] is None
    failed = rows() + [{"state": "GATE_FAILED", "components": {}}]
    assert dsv.rescore(variant, failed)["eligible"] is False


def test_the_transform_maps_error_onto_a_score_where_1_is_best(tmp_path):
    item = document(
        transform={"kind": "tail_logistic", "threshold": "0.5", "sharpness": "4"}
    )
    variant = dsv.load_variant(item["version"], directory=register(tmp_path, item))
    assert dsv.rescore(variant, rows())["score"] == pytest.approx(0.5)
    assert dsv.tail_logistic(0.0, 0.5, 4.0) > dsv.tail_logistic(1.0, 0.5, 4.0)
    assert 0.0 <= dsv.tail_logistic(1e6, 0.5, 4.0) < 1e-6  # no overflow
    assert dsv.tail_logistic(-1e6, 0.5, 4.0) == pytest.approx(1.0)


def test_rescore_directory_reads_owner_only_rows(tmp_path):
    item = document()
    variant = dsv.load_variant(
        item["version"], directory=register(tmp_path / "p", item)
    )
    folder = tmp_path / "rows"
    folder.mkdir()
    path = folder / "member-a.json"
    path.write_text(json.dumps(rows()))
    path.chmod(0o600)
    found = dsv.rescore_directory(variant, folder)
    assert found["members"]["member-a"]["error"] == pytest.approx(0.5)
    path.chmod(0o644)
    with pytest.raises(dsv.ScoreVariantRefused):
        dsv.rescore_directory(variant, folder)
