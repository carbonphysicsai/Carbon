"""The research campaign of a version registered by data: its pinned module's own measurement or none; live campaigns unmoved."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from carbon.challenge_registry import campaigns, exam_build, exam_entry, exam_registry
from carbon.direct_campaign import contracts, facts, practice, registered, research
from carbon.direct_campaign import research_view as direct_view
from carbon.direct_campaign import spec as direct_spec

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "exam_registry"
    / "zz_synthetic_build.py"
)
KEY = ("zz-synthetic", "0.1")
#: main fe148ac4: the sha256 of each live direct version's objective, reference, components, task and limitation label,
#: read from a clean checkout before the shared campaign asked its spec.
LIVE = {
    (
        "f08-ribbed-bracket",
        "1.4",
    ): "601c7a0e537ba6ec8bed522c29a95da8effa8926201b7145aed4540b027d11ab",
    (
        "f08-ribbed-bracket",
        "1.5",
    ): "7ef09f7214569d373a03b397e5693a92a9c0d01f040726172bc4748bbb57a9a7",
    (
        "f08-ribbed-bracket",
        "1.6",
    ): "8c3d36c547beebd09f9a916035b5db2a88d16789686956c74fbb5c6bbec77099",
    (
        "f08-ribbed-bracket",
        "1.7",
    ): "9256476951529cff04a7c541df4e9c775a50691da09226fe1e5a209c48bc8ce4",
    ("f02", "2.3"): "e09a2fb537e8a7f543d7b0bef05c913a336bd774d625c24abfdd1ef451ef74e6",
    ("f02", "2.4"): "352b72f21dbfe8b70eadb350ab347361127703f7065bd45fd7301a41b1b85f41",
    ("f02", "2.5"): "e8527624a1315f196fc4cea479df842a63f2f8196e9d79b2a2d2bb706cea5c41",
}


def _module():
    spec = importlib.util.spec_from_file_location("zz_campaign_fixture", FIXTURE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def rows(monkeypatch):
    """One synthetic version with an entry and a build row; the test changes its module."""
    module = _module()
    held = SimpleNamespace(module=module, digest="sha256:" + "1" * 64)
    monkeypatch.setattr(registered, "REFUSED", {})
    registered._serving.cache_clear()
    held.row = {"title": "Synthetic exam", "status": "open"}
    monkeypatch.setattr(exam_entry, "rows", lambda: {KEY: held.row})
    monkeypatch.setattr(exam_registry, "digest", lambda *key: held.digest)
    monkeypatch.setattr(exam_registry, "field", lambda *asked: held.row)
    monkeypatch.setattr(exam_build, "module", lambda *key: held.module)
    monkeypatch.setattr(
        exam_build, "block", lambda *key: {"graph_spec": module.graph_spec()}
    )
    yield held
    registered._serving.cache_clear()


def _refused(held, reason):
    registered._serving.cache_clear()
    assert registered.keys() == ()
    assert registered.REFUSED == {KEY: reason}
    assert KEY not in campaigns._versioned_campaigns()
    with pytest.raises(ValueError, match="registered direct campaign version"):
        registered.spec_for(*KEY)


# --- live campaigns ------------------------------------------------------------


def test_the_committed_registry_adds_no_campaign():
    assert registered.keys() == ()
    assert set(campaigns._versioned_campaigns()) == set(campaigns._code_campaigns())
    assert registered.PRACTICE_PROVENANCE not in campaigns.practice_provenances()


@pytest.mark.parametrize("key", sorted(LIVE))
def test_every_live_direct_version_serves_mains_documents(key):
    challenge_id, version = key
    spec = direct_spec.SPECS[challenge_id]
    with direct_spec.keyed(spec, direct_spec.key_for(spec, version)):
        document = {
            "objective": research.objective(spec),
            "reference": research.reference_method(spec),
            "components": direct_view.research_view(spec).components,
            "task": facts.value(spec, version, "task"),
            "label": facts.label(spec, version, "known_limitation"),
        }
    body = json.dumps(document, sort_keys=True).encode()
    assert hashlib.sha256(body).hexdigest() == LIVE[key]


def test_no_live_spec_answers_a_registered_question():
    names = (
        "components",
        "dual_feedback",
        "error_scale",
        "fact",
        "fact_label",
        "output_dtype",
        "practice_summary",
        "unit_labels",
    )
    for spec in direct_spec.SPECS.values():
        assert not [name for name in names if hasattr(spec, name)]
    assert all(hasattr(registered.RegisteredSpec, name) for name in names)


# --- a registered campaign -----------------------------------------------------


def test_a_version_with_its_measurement_has_a_campaign(rows):
    assert registered.keys() == (KEY,)
    spec = registered.spec_for(*KEY)
    assert (spec.title, spec.versions, spec.prefix) == (
        "Synthetic exam",
        ("0.1",),
        "registered",
    )
    # one research key per row, and no default version
    assert registered.spec_for(*KEY) is spec
    with pytest.raises(ValueError, match="no default version"):
        direct_spec.research_key(spec)
    with pytest.raises(ValueError, match="direct campaign version required"):
        direct_spec.key_for(spec, "0.2")
    assert KEY in campaigns._versioned_campaigns()
    assert registered.PRACTICE_PROVENANCE in campaigns.practice_provenances()
    assert set(registered.BACKENDS) <= campaigns.implemented_backends()


def test_a_retired_row_has_no_campaign(rows):
    rows.row = {**rows.row, "status": "retired"}
    assert registered.keys() == () and registered.REFUSED == {}
    assert KEY not in campaigns._versioned_campaigns()
    assert registered.PRACTICE_PROVENANCE not in campaigns.practice_provenances()
    with pytest.raises(ValueError, match="registered direct campaign version"):
        registered.spec_for(*KEY)


def test_another_row_is_another_spec(rows):
    first = registered.spec_for(*KEY)
    rows.digest = "sha256:" + "2" * 64
    second = registered.spec_for(*KEY)
    assert first != second and first.key_var is not second.key_var


def test_code_owns_every_version_it_has_a_campaign_for(rows, monkeypatch):
    live = ("f02", "2.5")
    monkeypatch.setattr(registered, "keys", lambda: (live,))
    assert campaigns._versioned_campaigns()[live].func is campaigns._f02_direct


@pytest.mark.parametrize("name", registered.FUNCTIONS)
def test_a_module_without_its_measurement_has_no_campaign(rows, name):
    delattr(rows.module, name)
    _refused(rows, "campaign_needs_its_practice_measurement")


@pytest.mark.parametrize(
    "components",
    [(), [("mean", "Mean")], (("mean",),), (("mean", ""),), (("a", "A"), ("a", "B"))],
)
def test_malformed_components_refuse(rows, components):
    rows.module.PRACTICE_COMPONENTS = components
    with pytest.raises(registered.CampaignRefused):
        registered._check(KEY)
    registered._serving.cache_clear()
    assert registered.keys() == ()


@pytest.mark.parametrize(
    "name, value",
    [
        ("FACTS", {"task": ""}),
        ("FACTS", {"task": None}),
        ("FACTS", {"known_limitation": "stated, with no label"}),
        ("LABELS", {"task": "label_of_no_fact"}),
        ("UNIT_LABELS", {"MPa": 1}),
        ("UNIT_LABELS", [("MPa", "megapascal")]),
    ],
)
def test_malformed_facts_labels_and_units_refuse(rows, name, value):
    setattr(rows.module, name, value)
    _refused(rows, "campaign_facts_malformed")


def test_an_unnamed_unit_refuses_until_the_module_names_it(rows):
    real = rows.module.interface_document

    def interface(*key):
        document = real(*key)
        document["output"]["units"] = ["MPa"]
        return document

    rows.module.interface_document = interface
    _refused(rows, "campaign_interface_unserved")
    rows.module.UNIT_LABELS = {"MPa": "megapascal"}
    registered._serving.cache_clear()
    assert registered.keys() == (KEY,)
    spec = registered.spec_for(*KEY)
    assert contracts._unit_label(spec, "MPa") == "megapascal"
    assert contracts._unit_label(spec, "Hz") == "hertz"
    with pytest.raises(KeyError):
        contracts._unit_label(direct_spec.F02, "MPa")


def test_a_failing_module_takes_no_other_campaign_down(rows):
    def broken(*key):
        raise AttributeError("module bug")

    rows.module.interface_document = broken
    _refused(rows, "campaign_module_failed: AttributeError")
    assert ("f02", "2.5") in campaigns._versioned_campaigns()


def test_an_interface_of_another_dtype_than_the_graph_route_refuses(rows):
    real = rows.module.interface_document
    rows.module.interface_document = lambda *key: {**real(*key), "dtype": "<f8"}
    _refused(rows, "campaign_interface_unserved")


def test_facts_are_the_modules_and_the_rest_is_human_input(rows):
    spec = registered.spec_for(*KEY)
    assert facts.value(spec, "0.1", "task") == direct_spec.HUMAN_INPUT
    assert facts.label(spec, "0.1", "task") is None
    rows.module.FACTS = {"task": "Predict y."}
    rows.module.LABELS = {"task": "predict_y"}
    assert facts.value(spec, "0.1", "task") == "Predict y."
    assert facts.label(spec, "0.1", "task") == "predict_y"


# --- practice -------------------------------------------------------------------


def _material():
    return {
        "interface_document": {"output": {"names": ["y"]}},
        "practice_reference": np.zeros((4, 1)),
    }


def test_practice_reports_the_modules_aggregate(rows):
    spec = registered.spec_for(*KEY)
    material = _material()
    value = practice.summary(
        spec, "0.1", material["interface_document"], np.full((4, 1), 0.25), material
    )
    # the whole served summary: no key of the module's own choosing
    assert value == {
        "cases": 4,
        "outputs": ["y"],
        "dtype": "<f4",
        "n_cases": 4,
        "n_scored": 4,
        "score": 0.25,
        "score_meaning": registered.SCORE_MEANING,
        "aggregate_error": 0.25,
        "components": {"mean": 0.25, "worst": 0.25},
        "error_scale": practice.error_scale(spec, "0.1"),
        "status": "aggregate_on_registered_scale",
    }
    assert list(value["components"]) == ["mean", "worst"]
    assert practice.error_scale(spec, "0.1")["record"] == "synthetic"
    assert practice.components(spec) == (
        ("mean", "Mean error"),
        ("worst", "Worst error"),
    )


@pytest.mark.parametrize(
    "change",
    [
        {"per_case": [0.0, 0.0, 0.0, 0.0]},
        {"outputs": ["y"]},
        {"error_scale": {"record": "the module's copy"}},
        {"score": 0.0},
        {"aggregate_error": float("nan")},
        {"aggregate_error": None},
        {"aggregate_error": [0.0, 0.0]},
        {"cases": 4.0},
        {"cases": True},
        {"cases": 3},
        {"cases": [0.0]},
        {"n_scored": 0},
        {"n_scored": 5},
        {"n_scored": 4.0},
        {"components": {"mean": 0.0}},
        {"components": {"mean": 0.0, "worst": float("inf")}},
        {"components": {"worst": 0.0, "mean": 0.0}},
        {"components": {"mean": 0.0, "worst": [0.0]}},
    ],
)
def test_a_summary_of_another_shape_never_reaches_a_miner(rows, change):
    spec = registered.spec_for(*KEY)
    real = rows.module.practice_summary
    rows.module.practice_summary = lambda *args: {**real(*args), **change}
    material = _material()
    with pytest.raises(ValueError, match="registered_practice_summary_invalid"):
        practice.summary(
            spec, "0.1", material["interface_document"], np.zeros((4, 1)), material
        )


def test_the_exam_dual_says_it_is_not_available(rows):
    block = practice._dual_feedback(registered.spec_for(*KEY), "0.1", [[0.0]])
    assert block["available"] is False
    assert block["reason"] == "practice_version_not_registered"
    assert block["challenge"] == {"kind": "zz-synthetic", "version": "0.1"}


def test_limits_without_a_catalog_bind_the_graph_route_only(rows, monkeypatch):
    spec = registered.spec_for(*KEY)
    limits = {"graph_training_adapter": {"id": "adapter"}}
    monkeypatch.setattr(contracts, "limits_document", lambda asked: limits)
    (source,) = contracts.direct_sources(spec)
    assert source[0] == "direct_adapter"
    limits["backbone_catalog"] = {"digest": "sha256:" + "3" * 64}
    assert [s[0] for s in contracts.direct_sources(spec)] == [
        "direct_adapter",
        "direct_catalog",
    ]
