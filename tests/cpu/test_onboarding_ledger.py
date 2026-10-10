"""The brief-to-product ledger generator is deterministic and cites real artefacts.

The ledger is documentation data produced from repository artefacts. These tests keep it
honest: the generator's output is byte-identical on repeated runs, every field that is not
UNMEASURED cites an existing artefact, every UNMEASURED field names an owner and a question,
and no hidden-pool or account material enters it.
"""

import importlib.util
import json
import re
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
SCRIPT = REPOSITORY / "scripts/dev/onboarding/build_ledger.py"
BATTERY = "battery-fastcharge-ageing-development-v1"
COMMITTED = (
    REPOSITORY
    / "docs/development/challenge_pipeline/onboarding/ledger"
    / f"{BATTERY}.json"
)
CHALLENGES = (BATTERY, "electric-motor-magnetics", "f02")
FORBIDDEN_KEYS = {
    "seed",
    "draw_id",
    "sealed_batch",
    "hidden_pool",
    "account",
    "balance",
}


def _generator():
    spec = importlib.util.spec_from_file_location("onboarding_build_ledger", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fields(node, path=""):
    """Every dict that is a ledger field: it carries a `value` key."""
    if isinstance(node, dict):
        if "value" in node:
            yield path, node
        for key, child in node.items():
            yield from _fields(child, f"{path}/{key}")
    elif isinstance(node, list):
        for index, child in enumerate(node):
            yield from _fields(child, f"{path}[{index}]")


def _keys(node):
    if isinstance(node, dict):
        for key, child in node.items():
            yield key
            yield from _keys(child)
    elif isinstance(node, list):
        for child in node:
            yield from _keys(child)


def test_the_output_is_deterministic():
    module = _generator()
    first = module.render(module.build(BATTERY))
    second = module.render(module.build(BATTERY))
    assert first == second
    assert json.loads(first) == module.build(BATTERY)


def test_the_four_record_types_are_present():
    ledger = _generator().build(BATTERY)
    assert ledger["schema"] == "carbon.challenge-pipeline.brief-product-ledger.v1"
    assert {"inputs", "process", "outputs", "network"} <= set(ledger)
    assert set(ledger["inputs"]) == {
        "decision_definition",
        "requirements",
        "design_space",
        "material_data",
        "solver",
        "acceptance_criteria",
    }


@pytest.mark.parametrize("which", ["generated", "committed"])
def test_every_measured_field_cites_an_existing_artefact(which):
    ledger = (
        _generator().build(BATTERY)
        if which == "generated"
        else json.loads(COMMITTED.read_text(encoding="utf-8"))
    )
    measured = 0
    for path, field in _fields(ledger):
        if field["value"] == "UNMEASURED":
            assert field.get("owner", "").strip(), path
            if field["kind"] == "measurement":
                assert field.get("tool", "").strip(), path
                assert "question" not in field, path
            else:
                assert field["kind"] == "decision", path
                assert field.get("question", "").strip(), path
            continue
        measured += 1
        source = field.get("source", "")
        assert source and (REPOSITORY / source).exists(), (path, source)
    assert measured > 0


def test_every_cited_artefact_in_a_nested_record_exists():
    ledger = _generator().build(BATTERY)
    for grant in ledger["process"]["grant_caps"]["value"]:
        assert (REPOSITORY / grant["source"]).is_file()
    assert (REPOSITORY / ledger["process"]["grant_caps"]["source"]).exists()


def test_no_hidden_or_account_material_and_no_spend_figure():
    ledger = _generator().build(BATTERY)
    assert not FORBIDDEN_KEYS & {key.lower() for key in _keys(ledger)}
    text = json.dumps(ledger)
    assert not re.search(r"\$\s?\d|USD\s?\d|\d\s?USD", text)


def test_an_unregistered_challenge_is_refused():
    with pytest.raises(SystemExit):
        _generator().build("no-such-challenge")


def test_the_committed_ledger_matches_the_generators_shape():
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    generated = _generator().build(BATTERY)
    assert set(committed) == set(generated)
    assert set(committed["inputs"]) == set(generated["inputs"])
    assert set(committed["outputs"]) == set(generated["outputs"])
    assert set(committed["network"]) == set(generated["network"])


@pytest.mark.parametrize("which", ["generated", "committed"])
def test_v4_is_required_for_tested_and_flagged_when_unmeasured(which):
    ledger = (
        _generator().build(BATTERY)
        if which == "generated"
        else json.loads(COMMITTED.read_text(encoding="utf-8"))
    )
    field = ledger["outputs"]["decision_quality_vs_cheap_baseline"]
    assert field["required_for_tested"] is True
    if field["value"] == "UNMEASURED":
        assert field["flag"] == "required for TESTED"


def test_the_ledger_sets_no_onboarding_speed_target():
    process = json.dumps(_generator().build(BATTERY)["process"]).lower()
    for word in ("target", "threshold", "must be faster", "at least"):
        assert word not in process, word


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_passes_value_has_five_required_conditions_all_flagged_when_unmeasured(
    challenge,
):
    value = _generator().build(challenge)["outputs"]["passes_value"]
    keys = [k for k in value if k[0] in "abcde" and k[1] == "_"]
    assert [k[0] for k in keys] == list("abcde")
    assert "models never beat the solver on accuracy" in value["framing"].lower()
    for key in keys:
        field = value[key]
        assert field["required_for"] == "PASSES VALUE"
        if field["value"] == "UNMEASURED":
            assert field["flag"] == "required for PASSES VALUE"
            assert field["kind"] == "measurement"
            assert field["owner"].strip() and field["tool"].strip()
    assert (REPOSITORY / value[keys[4]]["harness"]).is_file()


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_each_first_challenge_builds_and_its_committed_ledger_matches_the_shape(
    challenge,
):
    generated = _generator().build(challenge)
    committed = json.loads(
        (COMMITTED.parent / f"{challenge}.json").read_text(encoding="utf-8")
    )
    assert set(committed) == set(generated)
    assert generated["brief"]["current_decision"]["value"] != "UNMEASURED"


def test_the_named_prs_are_cited_and_a_measurement_never_asks_a_question():
    module = _generator()
    value = module.build(BATTERY)["outputs"]["passes_value"]
    tools = {
        k: v["tool"] for k, v in value.items() if isinstance(v, dict) and "tool" in v
    }
    assert "994" in tools["b_regret_below_cheap_baseline_paired_bootstrap_ci"]
    assert "1003" in tools["b_regret_below_cheap_baseline_paired_bootstrap_ci"]
    assert "998" in tools["e_equal_budget_screen_then_verify_beats_solver"]
    assert "939" in tools["d_value_and_volume_ranges"]
    measurements = json.loads(
        (REPOSITORY / module.REGISTRY).read_text(encoding="utf-8")
    )["measurements"]
    for key, tool in measurements.items():
        assert tool["owner"].strip() and tool["tool"].strip(), key
        assert "question" not in tool, key


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_each_solver_has_three_credibility_layers_named_in_a_real_artefact(challenge):
    layers = _generator().build(challenge)["outputs"]["credibility_layers"]
    assert layers["solvers"], challenge
    for name, solver in layers["solvers"].items():
        source = solver["named_in"]["source"]
        assert name.lower() in (REPOSITORY / source).read_text(encoding="utf-8").lower()
        for key in ("code_verification", "solution_verification", "validation"):
            assert solver[key]["value"] == "UNMEASURED", (name, key)
            assert solver[key]["kind"] == "measurement"
        assert solver["code_verification"]["flag"] == (
            "required for the reference stage exit"
        )
