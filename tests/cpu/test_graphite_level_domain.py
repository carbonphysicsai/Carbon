"""A level's declared domain is rendered for the Constructor and checked early.

Stage A's Constructor L0 runs lost seven proposals to values past a ceiling or names the
level calls something else, and one to a family the pods do not serve. These tests keep
the generated domain equal to the real compile step, make the intersection follow the
scoring record at runtime (never a copied constant), and keep the early refusal limited
to what the pods could not serve anyway.
"""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import graphite_phase3_fixtures as p3f
import pytest
from graphite_phase3_fixtures import BASELINE, SCORING, propose, session, steps, text

from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import level_domain as ld
from carbon.agent_campaign.graphite import phase3
from carbon.battery.compile import compile_recipe
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_catalog import RecipeRejected

BATTERY = "battery-fastcharge-ageing-development-v1"


def _scoring(*backends):
    """A scoring-record stand-in: the intersection must follow the record."""
    return SimpleNamespace(challenge_id=BATTERY, served_backends=tuple(backends))


def _domain(*backends, level=0):
    return ld.for_scoring(_scoring(*backends), SimpleNamespace(level=level))


# -- the grammar --------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text_, expected",
    [
        (
            "uint, 1–4, default 1; applies to mlp, deeponet, fno",
            {"kind": "uint", "min": 1, "max": 4, "default": 1},
        ),
        (
            "float, 1e-05–0.05, default 0.002; applies to mlp",
            {"kind": "float", "min": 1e-05, "max": 0.05, "default": 0.002},
        ),
        ("bool, default false; applies to mlp", {"kind": "bool", "default": False}),
        (
            "choice: all, matrices; default all; applies to mlp",
            {"kind": "choice", "choices": ["all", "matrices"], "default": "all"},
        ),
    ],
)
def test_the_bounds_grammar_is_parsed(text_, expected):
    parsed = ld.parse_bounds(text_)
    assert {k: parsed[k] for k in expected} == expected


def test_a_prose_bound_is_not_parsed_and_not_invented():
    assert ld.parse_bounds("Boolean toggle (on/off), default off") is None
    assert ld.parse_bounds("lab_kind battery_knn; selector knn") is None


# -- the level 0 domain --------------------------------------------------------------------------
def test_the_level_zero_domain_states_the_ceilings_and_the_names():
    domain = _domain("jax")
    parameters = domain["parameters"]
    assert parameters["ensemble_members"]["max"] == 4
    assert parameters["steps"]["max"] == 20000 and parameters["steps"]["min"] == 16
    assert parameters["weight_decay_mask"]["choices"] == ["all", "matrices"]
    assert parameters["normalization"]["choices"] == ["none", "layer_norm"]
    assert domain["schema"] == ld.SCHEMA and domain["level"] == 0
    assert any(
        "divisible by ensemble_members" in r for r in domain["combination_rules"]
    )


def test_the_domain_is_deterministic():
    assert digest(canonical(_domain("jax"))) == digest(canonical(_domain("jax")))


# -- the intersection follows the scoring record ------------------------------------------------
def test_one_served_backend_removes_the_family_and_the_backend_that_need_another():
    domain = _domain("jax")
    assert "fno" not in domain["families"]
    assert domain["families_not_served"] == [
        {"family": "fno", "needs_backend": "pytorch"}
    ]
    assert domain["parameters"]["backend"]["choices"] == ["jax"]
    assert domain["parameters"]["backend"]["declared_choices"] == ["jax", "pytorch"]
    assert "fno" not in domain["parameters"]["n_modes"]["applies_to"]


def test_two_served_backends_open_the_family_and_the_backend():
    domain = _domain("jax", "pytorch")
    assert "fno" in domain["families"] and domain["families_not_served"] == []
    assert domain["parameters"]["backend"]["choices"] == ["jax", "pytorch"]
    assert "fno" in domain["parameters"]["n_modes"]["applies_to"]
    fno = {**BASELINE, "backbone": "fno", "parameters": {"backend": "pytorch"}}
    assert ld.precheck(fno, domain) is None


def test_the_precheck_refuses_only_what_the_intersection_removes():
    one = _domain("jax")
    pytorch_mlp = {
        **BASELINE,
        "parameters": {**BASELINE["parameters"], "backend": "pytorch"},
    }
    refused = ld.precheck(pytorch_mlp, one)
    assert refused["reason_code"] == "backend_not_served:pytorch"
    assert refused["issues"] == [
        ["level_domain.backend_not_served", "/parameters/backend"]
    ]
    assert refused["served_backends"] == ["jax"]
    fno = {**BASELINE, "backbone": "fno", "parameters": {"backend": "pytorch"}}
    assert ld.precheck(fno, one)["issues"][0][0] == "level_domain.backend_not_served"
    fno_jax = {**BASELINE, "backbone": "fno"}
    assert ld.precheck(fno_jax, one)["issues"] == [
        ["level_domain.family_not_served", "/backbone"]
    ]
    # Out-of-range values, bad names and combinations stay with the compile step.
    for strategy in (
        {**BASELINE, "parameters": {"steps": 30000}},
        {**BASELINE, "parameters": {"weight_decay_mask": "weights"}},
        {**BASELINE, "parameters": {"backend": "tpu"}},
        BASELINE,
        "not a strategy",
    ):
        assert ld.precheck(strategy, one) is None
    assert ld.precheck(pytorch_mlp, None) is None


def test_a_challenge_with_no_level_document_has_no_domain():
    other = SimpleNamespace(challenge_id="chip-cold-plate", served_backends=("numpy",))
    assert ld.for_scoring(other, None) is None
    assert ld.precheck(BASELINE, ld.for_scoring(other, None)) is None


def test_a_higher_level_builds_on_level_zero_and_lists_its_additions():
    domain = _domain("jax", level=2)
    assert domain["level"] == 2 and len(domain["source"]) == 2
    assert domain["parameters"]["ensemble_members"]["max"] == 4
    assert "batching.steps" in domain["level_additions"]


# -- the generated domain equals the real compile step -------------------------------------------
BASES = {
    "knn": {"backbone": "knn", "parameters": {"neighbours": 6}},
    "mlp": {"backbone": "mlp", "parameters": dict(BASELINE["parameters"])},
    "deeponet": {"backbone": "deeponet", "parameters": {"steps": 2000, "width": 64}},
    "fno": {
        "backbone": "fno",
        "parameters": {"steps": 2000, "width": 64, "depth": 3, "backend": "pytorch"},
    },
}


def _issues(strategy):
    try:
        compile_recipe(strategy)
    except RecipeRejected as error:
        return str(error)
    return ""


def _strategy(family, **parameters):
    base = copy.deepcopy(BASES[family])
    base["parameters"].update(parameters)
    return {**BASELINE, "backbone": base["backbone"], "parameters": base["parameters"]}


def _family(spec):
    for family in ("mlp", "deeponet", "fno", "knn"):
        if family in spec["applies_to"] or "all" in spec["applies_to"]:
            return family
    raise AssertionError(spec)


def test_every_declared_range_and_name_matches_the_compile_step():
    domain = _domain("jax", "pytorch")
    checked = 0
    for name, spec in domain["parameters"].items():
        family = _family(spec)
        where = f"parameter.domain_mismatch@/parameters/{name}"
        if spec["kind"] == "bool":
            assert where not in _issues(
                _strategy(family, **{name: not spec["default"]})
            )
            continue
        if spec["kind"] == "choice":
            for choice in spec["choices"]:
                assert where not in _issues(_strategy(family, **{name: choice})), (
                    name,
                    choice,
                )
            assert where in _issues(_strategy(family, **{name: "not_a_name"})), name
            checked += 1
            continue
        for edge in (spec["min"], spec["max"]):
            assert where not in _issues(_strategy(family, **{name: edge})), (name, edge)
        above = spec["max"] + 1 if spec["kind"] == "uint" else spec["max"] * 2 + 1
        assert where in _issues(_strategy(family, **{name: above})), (name, above)
        checked += 1
    assert checked > 25


def test_the_stage_a_refusals_are_outside_the_stated_domain():
    domain = _domain("jax")["parameters"]
    assert 5 > domain["ensemble_members"]["max"]
    assert 24000 > domain["steps"]["max"]
    assert "weights" not in domain["weight_decay_mask"]["choices"]
    assert "layer" not in domain["normalization"]["choices"]
    for name, value in (
        ("ensemble_members", 5),
        ("steps", 24000),
        ("weight_decay_mask", "weights"),
        ("normalization", "layer"),
    ):
        refusal = f"parameter.domain_mismatch@/parameters/{name}"
        assert refusal in _issues(_strategy("mlp", **{name: value}))


def test_each_combination_rule_is_a_real_compile_refusal():
    rules = {
        r["id"]
        for r in json.loads(ld.RULES.read_text(encoding="utf-8"))["challenges"][BATTERY]
    }
    assert rules == {
        "members_divide_steps",
        "member_steps_minimum",
        "weight_decay_mask_needs_decay",
    }
    divide = "parameter.dependency_unsatisfied@/parameters/ensemble_members"
    assert divide in _issues(_strategy("mlp", ensemble_members=3, steps=14000))
    assert divide not in _issues(_strategy("mlp", ensemble_members=3, steps=12000))
    assert "parameter.dependency_unsatisfied@/parameters/steps" in _issues(
        _strategy("mlp", ensemble_members=4, steps=32)
    )
    mask = "parameter.dependency_unsatisfied@/parameters/weight_decay_mask"
    assert mask in _issues(_strategy("mlp", weight_decay_mask="matrices"))
    assert mask not in _issues(
        _strategy("mlp", weight_decay_mask="matrices", weight_decay=0.01)
    )


# -- the brief and the session -------------------------------------------------------------------
def _brief(scoring=SCORING, **options):
    budget = ex.phase3_budget(
        SpendingGrant.from_document(phase3.DRY_RUN_GRANT), scoring
    )
    return phase3.session_brief(
        checkout_commit="0" * 40, budget=budget, scoring=scoring, **options
    )


def test_a_brief_without_the_opt_in_is_exactly_as_it_was():
    observation = _brief().initial_observation
    assert "level_domain" not in observation
    assert "level_domain" not in observation["instructions"]


def test_the_constructor_brief_carries_the_domain_from_the_scoring_record():
    observation = _brief(level_domain_text=True).initial_observation
    domain = observation["level_domain"]
    assert domain["served_backends"] == list(SCORING.served_backends)
    assert domain["parameters"]["ensemble_members"]["max"] == 4
    assert "level_domain" in observation["instructions"]
    again = _brief(level_domain_text=True).initial_observation
    assert digest(canonical(observation)) == digest(canonical(again))


def test_a_fno_request_is_refused_before_the_compile_step_with_the_served_set(tmp_path):
    fno = {**BASELINE, "backbone": "fno", "parameters": {"backend": "pytorch"}}
    account = p3f.ScriptedPods(steps=steps(1.0))
    _result, graphite, _ = session(tmp_path, [propose(fno), text("done")], account)
    [record] = graphite.experiment(p3f.run_id()).records("proposal")
    assert record["status"] == "REFUSED_BACKEND_NOT_SERVED"
    assert record["reason_code"] == "backend_not_served:pytorch"
    assert record["issues"] == [
        ["level_domain.backend_not_served", "/parameters/backend"]
    ]
    assert record["served_backends"] == list(SCORING.served_backends)
    assert account.launched == [] and "finding" not in record
