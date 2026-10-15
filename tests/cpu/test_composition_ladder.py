"""S3 composition door/daemon controls with public data and inert dispatch.

No chain, private material, live deployment or official evaluation is used.
"""

import copy
import json

import pytest
from composition_check_fixtures import accepted_fixture_checks

from carbon.battery import deployment
from carbon.battery.daemon import BatteryValidator
from carbon.battery.pool_store import StateError
from carbon.challenge_validator import Adapters, Validator
from carbon.challenge_validator.battery import BatteryAdapter
from carbon.challenge_validator.interface import Submission
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.development_ladder import operate
from carbon.reconstruction import capability_registry as cr
from carbon.reconstruction import development_composition as dc

BATTERY = cr.BATTERY_CHALLENGE
MINER = "5E49MhzFLBv35AbSPgtwrutCd6yvDm6GK9EC5ocmJ3Czb48N"
OTHER = "5DWznJMnCeoevFSwsck7LXdYBWAbiw1G1qrxnghqSHqQj2qr"


def config(**changes):
    composition = dc.load(BATTERY)
    value = {
        "development_only": True,
        "batch_source": "answer_key",
        "require_commitment": True,
        "commitment_reader": {"network": "testnet", "netuid": 567},
        "ladder": {"hotkeys": [MINER], "variants": [composition.version]},
    }
    value.update(changes)
    return value


def strategy():
    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": "mlp",
        "parameters": {
            "width": 8,
            "depth": 1,
            "steps": 24,
            "batch_size": 32,
            "polish_steps": 4,
            "optimizer_family": "muon",
            "muon_spectral": True,
            "quasi_newton_family": "bfgs",
            "line_search": "backtracking",
        },
    }


def target(tmp_path, *, listed=True):
    # An actual daemon object with inert, public fixture identities. Screen and
    # recompile paths need no seed root, references, worker or evaluation.
    instance = object.__new__(BatteryValidator)
    instance.ladder = deployment.ladder_for(config()) if listed else None
    instance.development_only = listed
    instance.lock_path = str(tmp_path / "writer.lock")
    instance.rule = {}
    instance.identities = lambda: {
        "contract_digest": cr.contract_digest(BATTERY),
        "rule_digest": "sha256:" + "1" * 64,
        "implementation_digest": "sha256:" + "2" * 64,
    }
    instance.development_compiler = None
    if listed:
        operate.setup(instance)
    return instance


def test_operator_can_explicitly_list_composition_without_a_level_permission():
    found = deployment.ladder_for(config())
    composition = dc.load(BATTERY)
    assert found["variants"][composition.digest] == {
        "version": composition.version,
        "level": None,
        "kind": "composition",
    }
    assert found["levels"] == frozenset({1, 2, 3, 4})  # capability labels only
    hint = config()
    hint["ladder"]["levels"] = [1]
    assert deployment.ladder_for(hint)["variants"] == found["variants"]


@pytest.mark.parametrize(
    "mutation",
    ["mainnet", "not_development", "no_commitment", "bad_hotkey", "unregistered"],
)
def test_composition_keeps_deployment_containment(mutation):
    changed = config()
    if mutation == "mainnet":
        changed["commitment_reader"]["network"] = "finney"
    elif mutation == "not_development":
        changed["development_only"] = False
    elif mutation == "no_commitment":
        changed["require_commitment"] = False
    elif mutation == "bad_hotkey":
        changed["ladder"]["hotkeys"] = ["arbitrary"]
    else:
        changed["ladder"]["variants"] = ["unregistered"]
    with pytest.raises(deployment.EvaluationUnavailable):
        deployment.ladder_for(changed)


def test_ladder_compiler_rebuild_record_and_binding_equal_direct_composition(
    accepted_fixture_checks,
):
    composition = dc.load(BATTERY)
    actual = operate.compile_variant(strategy(), composition.digest)
    direct = dc.compile(strategy(), composition)
    assert actual.development == direct.development
    assert actual.record == direct.record
    assert actual.construction.recipe_digest == direct.construction.recipe_digest
    assert actual.derived["level"] == 3 and len(actual.derived["changes"]) == 3


def test_composition_recompile_verifies_all_durable_binding_fields(
    tmp_path, accepted_fixture_checks
):
    instance = target(tmp_path)
    composition = dc.load(BATTERY)
    compiled = instance.development_compiler(strategy(), composition.digest)
    row = {
        "hotkey": MINER,
        "strategy": strategy(),
        "binding": {
            "recipe_digest": compiled.construction.recipe_digest,
            "development": {
                **compiled.development,
                "variant_contract_digest": composition.digest,
            },
        },
    }
    recipe, record = instance._development(row)
    assert recipe == compiled.construction and record == compiled.record
    for key, value in (
        ("composition_digest", "sha256:" + "0" * 64),
        ("variants", {}),
        ("changes", []),
        ("level", True),
    ):
        changed = copy.deepcopy(row)
        changed["binding"]["development"][key] = value
        with pytest.raises(StateError):
            instance._development(changed)
    assert not instance._serves_development(OTHER)


def test_neutral_door_lists_exact_composition_and_main_stays_closed(tmp_path):
    composition = dc.load(BATTERY)
    instance = target(tmp_path)
    adapter = BatteryAdapter(instance)
    declared = {
        composition.digest: {
            "base": adapter.contract_digest,
            "level": None,
            "variant": composition.version,
        }
    }
    ledger = AttemptLedger(tmp_path / "attempts.sqlite3")
    door = Validator(Adapters([adapter]), ledger, development=declared)
    assert {
        "level": None,
        "kind": "composition",
        "variant": composition.version,
        "digest": composition.digest,
    } in door.served_contracts()
    submission = Submission(
        MINER,
        {"sequence": 1, "digest": "0" * 64},
        BATTERY,
        "1.0",
        json.dumps(strategy()),
        composition.digest,
    )
    passed = door.screen(submission)
    assert passed.admitted.contract_digest == composition.digest
    assert passed.adapter is adapter
    main = Validator(Adapters([adapter]), ledger)
    assert main.screen(submission)["code"] == "development_variant_not_served"
    wrong = copy.deepcopy(declared)
    wrong[composition.digest]["variant"] = "wrong-composition"
    with pytest.raises(ValueError, match="registered Challenge and base"):
        Validator(Adapters([adapter]), ledger, development=wrong)


__all__ = ["accepted_fixture_checks"]
