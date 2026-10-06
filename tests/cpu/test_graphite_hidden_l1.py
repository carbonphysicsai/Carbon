"""Battery Level 1 through the real validator on the hidden pool (VALIDATOR-13;
the owner's approval, 2026-10-06, with the Test Lead's conditions).

The route is the miner door's own intake, rebuild, scoring and sealing. It
admits a registered development variant only on a deployment that opted in
(`development_only`), only from a `graphite-dev:` identity, and only with the
compile function the Graphite side supplies; the daemon never names the
variant module. A development row is never nominated, its operator record is
stamped with its level and variant, and the winner-weight publisher refuses
a development deployment. Each guard is paired with its guard-off twin.

Fixtures: battery's daemon fixtures (published PyBaMM references,
`DirectBackend` in process). No pod, network or spend.
"""

import dataclasses
import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_validator_daemon import (
    backend,  # noqa: F401 - fixture
    refs,  # noqa: F401 - fixture
)
from test_graphite_hidden_score import TEMPO, deployment, knn

from carbon.agent_campaign.attack.adapters import battery_level1 as atk
from carbon.agent_campaign.graphite import hidden_score
from carbon.battery import deployment as battery_deployment
from carbon.battery import level1_worker, worker
from carbon.battery.daemon import (
    DEVELOPMENT_VARIANT_NOT_SERVED,
    AuthenticatedSubmission,
)
from carbon.reconstruction import development_variants as dv
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE as BATTERY
from carbon.rewards import testnet_winner_publication as twp

VARIANT = dv.variant(BATTERY, 1)
L1 = atk.strategy(atk.VALID["valid_menu_restated"], steps=200)


def submission(hotkey, strategy=L1, digest=VARIANT.digest, block=TEMPO + 5):
    return AuthenticatedSubmission(
        hotkey,
        {"sequence": block, "digest": "0" * 64, "block": block},
        BATTERY,
        "1.0",
        strategy,
        digest,
    )


def failure_code(target, outcome):
    return (outcome.get("failure") or {}).get("code")


# -- the deployment's opt-in field ----------------------------------------------------------


def _config(tmp_path, **fields):
    path = tmp_path / "deployment.json"
    path.write_text(
        json.dumps(
            {
                "schema": "carbon.battery.validator-deployment.v1",
                "state": "s",
                "private_root": "r",
                "journal": "j",
                "work": "w",
                "backend": "direct",
                **fields,
            }
        )
    )
    path.chmod(0o600)
    return path


@pytest.mark.parametrize(
    ("fields", "accepted"),
    [
        ({"development_only": True, "require_commitment": False}, True),
        ({"development_only": True}, False),  # require_commitment defaults true
        ({"development_only": True, "require_commitment": True}, False),
        ({"development_only": "yes", "require_commitment": False}, False),
        ({"require_commitment": False}, True),  # off by default
    ],
)
def test_the_opt_in_field_requires_no_commitment(tmp_path, fields, accepted):
    path = _config(tmp_path, **fields)
    if accepted:
        assert battery_deployment.load_config(path)["schema"]
        return
    with pytest.raises(battery_deployment.EvaluationUnavailable):
        battery_deployment.load_config(path)


# -- admission guards, each with its guard-off twin ----------------------------------------


@pytest.fixture
def target(tmp_path, refs, backend):  # noqa: F811
    return deployment(tmp_path, refs, backend)


def test_a_miner_deployment_refuses_a_variant(target):
    outcome = target.admit(submission("graphite-dev:run:constructor"))
    assert failure_code(target, outcome) == DEVELOPMENT_VARIANT_NOT_SERVED


def test_the_opt_in_alone_is_not_enough_without_the_supplied_compiler(target):
    target.development_only = True
    outcome = target.admit(submission("graphite-dev:run:constructor"))
    assert failure_code(target, outcome) == DEVELOPMENT_VARIANT_NOT_SERVED


def test_a_miner_identity_is_refused_even_when_opted_in(target):
    target.development_only = True
    target.development_compiler = hidden_score._development_compiler
    outcome = target.admit(submission("5MinerHotkey"))
    assert failure_code(target, outcome) == DEVELOPMENT_VARIANT_NOT_SERVED


def test_opted_in_with_the_compiler_and_a_graphite_identity_it_is_admitted(target):
    target.development_only = True
    target.development_compiler = hidden_score._development_compiler
    outcome = target.admit(submission("graphite-dev:run:constructor"))
    assert outcome["state"] == "ADMITTED"
    binding = target.store.submission(outcome["submission_id"])["binding"]
    development = binding["development"]
    assert development["variant_contract_digest"] == VARIANT.digest
    assert development["level"] == 1
    # The base contract binds as for Level 0.
    assert binding["contract_digest"] == target.identities()["contract_digest"]


def test_a_level_0_binding_carries_no_development_stamp(target):
    level0 = submission(
        "graphite-dev:run:baseline",
        strategy=knn(),
        digest=target.identities()["contract_digest"],
    )
    outcome = target.admit(level0)
    binding = target.store.submission(outcome["submission_id"])["binding"]
    assert "development" not in binding


# -- the hidden pool, end to end on rule v2 --------------------------------------------------


def test_a_level_1_construction_is_scored_on_the_hidden_pool_and_kept_apart(
    tmp_path,
    refs,  # noqa: F811
):
    # A plain in-process backend: the daemon fixtures' counting backend
    # predates the Level-1 rebuild argument.
    target = deployment(tmp_path, refs, worker.DirectBackend(REPOSITORY))
    target.development_only = True
    pool = hidden_score.HiddenPool(
        target, run_id="run-l1", clock=lambda: TEMPO + 5, variant=VARIANT
    )
    view, operator = pool.submit("proposal", L1)
    assert view["state"] == "SCORED", view
    assert (operator["level"], operator["variant_digest"]) == (1, VARIANT.digest)
    sid = operator["submission_id"]
    # Rebuilt by the Level-1 trainer, never nominated, never an incumbent.
    fit = target.store.model_state(sid)["reconstruction"]["fit"]
    assert fit["trainer"] == "level1"
    assert target.store.incumbent() is None
    assert operator["nomination"]["excluded"] == "DEVELOPMENT_LEVEL"
    report = hidden_score.report([{**operator, "proposal_id": "p1"}])
    assert report["primary"]["by_pool_version"] == {}
    assert report["development_levels"]["1"]["never_ranked_with_level_0"] is True


def test_a_variant_needs_a_development_only_deployment(target):
    with pytest.raises(hidden_score.HiddenPoolRefused) as refused:
        hidden_score.HiddenPool(target, run_id="r", clock=lambda: 1, variant=VARIANT)
    assert refused.value.code == "hidden_level_needs_a_development_only_deployment"
    target.development_only = True
    assert hidden_score.HiddenPool(target, run_id="r", clock=lambda: 1, variant=VARIANT)


def test_an_unregistered_variant_is_refused(target):
    target.development_only = True
    forged = dataclasses.replace(VARIANT, version="forged-v1")
    with pytest.raises(hidden_score.HiddenPoolRefused) as refused:
        hidden_score.HiddenPool(target, run_id="r", clock=lambda: 1, variant=forged)
    assert refused.value.code == "hidden_variant_unregistered"


# -- weights never come from a development deployment ---------------------------------------


def test_the_winner_publisher_refuses_a_development_deployment(target):
    assert twp.check_weight_source(target) is target
    target.development_only = True
    with pytest.raises(twp.WinnerPublicationRefused) as refused:
        twp.check_weight_source(target)
    assert str(refused.value) == "DEVELOPMENT_DEPLOYMENT_NEVER_SETS_WEIGHTS"


# -- the container rebuild ------------------------------------------------------------------


def test_the_container_stages_level_1_without_changing_level_0(monkeypatch):
    from carbon.battery.compile import compile_recipe

    compiled = dv.compile_development(L1, VARIANT)
    record = level1_worker.expression_record(compiled.reconstruction)
    calls = []

    def call(self, identity, program, files, names, image_backend):
        calls.append((program, set(files)))
        return {"state.npz": b"state", "fit.json": b"{}"}

    monkeypatch.setattr(worker.CarrierBackend, "_call", call)
    carrier = worker.CarrierBackend.__new__(worker.CarrierBackend)
    carrier.root = REPOSITORY
    _state, stats = carrier.reconstruct(
        "i", compiled.construction, 1, development=record
    )
    program, files = calls[-1]
    assert program == worker.level1_reconstruct_program()
    assert {level1_worker.EXPRESSION_FILE, level1_worker.OPERATION_SET_FILE} <= files
    assert stats["trainer"] == "level1"
    _, base = compile_recipe(knn())
    carrier.reconstruct("j", base, 1)
    assert calls[-1][0] == worker.RECONSTRUCT_PROGRAM
    assert level1_worker.EXPRESSION_FILE not in calls[-1][1]
