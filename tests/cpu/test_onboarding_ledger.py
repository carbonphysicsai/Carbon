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
