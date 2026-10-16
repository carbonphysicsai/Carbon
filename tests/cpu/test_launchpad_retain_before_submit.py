"""DEVELOPMENT fixtures: launch policy, authentic practice provenance and effects.

The real Graphite research loop, ledger, launch host and Battery entrypoints run
against scripted models/public practice records. No provider, chain or validator
is contacted. These checks are engineering controls, not real T07 verdicts.
"""

import asyncio
import copy
import json
import sqlite3
from types import SimpleNamespace

import pytest
from test_commitment_poster import FakeChain
from test_graphite_miner_driver import (
    REAL_STOP,
    RECIPE,
    RoleTransport,
    World,
    practice,
    select,
)
from test_launchpad_graphite import (
    graphite as _graphite,
)
from test_launchpad_graphite import (
    join,
    launch_request,
    perform,
)

from carbon.agent_campaign.graphite.miner import driver, edition
from carbon.battery import campaign as battery
from carbon.battery import multi_intake
from carbon.chain import commitment_poster as cp
from carbon.development_session import research_campaign
from carbon.development_session import submission_policy as policy
from carbon.development_session.profile import canonical, digest
from scripts.dev.miner_launchpad.controller import Rejected
from scripts.dev.miner_launchpad.operations import CHOICES, OPERATIONS
from scripts.dev.miner_launchpad.runner import (
    LaunchChoice,
    RunnerAdapter,
    graphite_launch,
)

# Reuse the existing fixture object without import-shadowing exceptions.
graphite = _graphite


@pytest.fixture
def retained(tmp_path, monkeypatch):
    world = World(
        tmp_path,
        monkeypatch,
        graphite={"mode": "FULL", policy.FIELD: policy.RETAIN_ONLY},
        real=True,
    )
    transport = RoleTransport(
        planner=[REAL_STOP], constructor=[[practice(RECIPE)], [select(RECIPE)]]
    )
    assert world.run(transport) is None
    assert research_campaign.trial_supports_selection(
        world.prepared.ledger, "alice", RECIPE
    )
    return world


def forbidden(*args, **kwargs):
    raise AssertionError("commitment/validator effect was reached")


def test_full_practises_and_retains_without_evaluation_then_resumes_without_a_turn(
    retained,
):
    w = retained
    selected = w.root / "epoch-1" / "selected-recipe.json"
    before = selected.read_bytes()
    spent = w.spent()
    assert json.loads(before)["strategy"] == RECIPE
    assert not w.campaign.evaluated
    assert not (w.root / "campaign-complete.json").exists()
    assert not list(w.root.glob("epoch-*/permitted-final-feedback.json"))
    assert research_campaign.waits_for_its_miner(w.root)
    assert w.stage("build") is None
    view = driver.view(w.root)
    assert view[policy.FIELD] == policy.RETAIN_ONLY and view["stage"] == "retained"
    assert view["stages"][-1]["state"] == "RETAINED"
    from scripts.dev.miner_launchpad.projection import graphite_progress

    exposed = graphite_progress(
        w.prepared.manifest, w.prepared.ledger.status(owner="alice"), w.root
    )
    assert exposed[policy.FIELD] == policy.RETAIN_ONLY
    assert exposed["stage"] == "retained"
    assert exposed["stages"][-1]["state"] == "RETAINED"
    # The real loop must not be entered a second time, even with a new model.
    w.monkeypatch.setattr(driver, "_session", forbidden)
    assert w.run(RoleTransport(planner=[], constructor=[])) is None
    assert selected.read_bytes() == before and w.spent() == spent
    assert not w.campaign.evaluated


def test_historical_full_still_submits_and_keeps_the_old_block_shape(
    tmp_path, monkeypatch
):
    w = World(tmp_path, monkeypatch, graphite={"mode": "FULL"}, real=True)
    assert (
        w.run(
            RoleTransport(
                planner=[REAL_STOP],
                constructor=[[practice(RECIPE)], [select(RECIPE)], REAL_STOP],
            )
        )
        is None
    )
    assert w.campaign.evaluated == [(1, RECIPE)]
    block = w.prepared.manifest["provider"]["graphite"]
    assert set(block) == edition.BLOCK_FIELDS
    assert policy.FIELD not in edition.launch_fields({})
    assert not policy.retains(w.prepared.manifest, root=w.root)
    assert (w.root / "campaign-complete.json").exists()


@pytest.mark.parametrize(
    "entry", ["shared", "battery", "frozen", "single", "multi", "commit"]
)
def test_already_on_chain_never_opens_a_commitment_or_validator_path(
    retained, monkeypatch, entry
):
    w = retained
    committed = "sha256:" + "9" * 64
    chain = FakeChain(on_chain={"digest": committed, "block": 7200})
    gate = cp.CommitmentGate(
        SimpleNamespace(chain=chain, hotkey="fixture", plan=forbidden, post=forbidden)
    )
    # Control: an already matching digest needs no TTY and would allow submission.
    assert gate.before_submit(w.root, committed, request=True, epoch=1) is None
    monkeypatch.setattr(gate, "before_submit", forbidden)
    monkeypatch.setattr(chain, "read", forbidden)
    w.prepared.args.commitment_gate = gate
    for name in ("evaluation_config", "_intake", "_level_record_bound"):
        monkeypatch.setattr(battery, name, forbidden)
    record = json.loads((w.root / "epoch-1" / "selected-recipe.json").read_bytes())
    operations = {
        "shared": lambda: research_campaign.submit_candidate(w.prepared, 1, RECIPE),
        "battery": lambda: battery.evaluate_candidate(w.prepared, 1, record),
        "frozen": lambda: battery.evaluate_frozen(w.prepared, 1, RECIPE),
        "single": lambda: battery._evaluate_through_intake(
            w.prepared, 1, record, "https://fixture.invalid"
        ),
        "multi": lambda: multi_intake.evaluate(w.prepared, 1, record, []),
        "commit": lambda: battery._committed(
            gate, w.root, 1, record, w.prepared.manifest, request=True
        ),
    }
    with pytest.raises(research_campaign.OperationRefused) as refused:
        asyncio.run(operations[entry]())
    assert refused.value.code == policy.RETAINED
    assert not chain.prepared and not chain.broadcasts
    assert not (w.root / cp.REQUEST_FILE).exists()
    assert not list(w.root.glob("epoch-*/permitted-final-feedback.json"))


@pytest.mark.parametrize(
    "value", [None, False, 0, {}, [], "", "automatic", "retain_only_v2"]
)
def test_unknown_or_null_policy_is_not_historical_omission(value):
    with pytest.raises(Rejected) as refused:
        graphite_launch({"agent": "graphite", policy.FIELD: value})
    assert refused.value.code == policy.INVALID
    with pytest.raises(edition.LaunchRefused) as refused:
        edition.launch_fields({policy.FIELD: value})
    assert refused.value.code == policy.INVALID


@pytest.mark.parametrize(
    "change",
    [
        "remove",
        "unknown",
        "null",
        "launch",
        "ledger",
        "missing_launch",
        "missing_ledger",
        "downgrade_missing_launch",
        "downgrade_missing_ledger",
    ],
)
def test_resume_and_effect_admission_reject_changed_frozen_policy(retained, change):
    w = retained
    manifest = copy.deepcopy(w.prepared.manifest)
    block = manifest["provider"]["graphite"]
    if change in {"remove", "downgrade_missing_launch", "downgrade_missing_ledger"}:
        del block[policy.FIELD]
    elif change in {"unknown", "null"}:
        block[policy.FIELD] = None if change == "null" else "automatic"
    if change in {
        "remove",
        "unknown",
        "null",
        "downgrade_missing_launch",
        "downgrade_missing_ledger",
    }:
        (w.root / "campaign-manifest.json").write_bytes(canonical(manifest))
    if change in {"launch", "missing_launch", "downgrade_missing_launch"}:
        driver.launch_path(w.root).unlink()
    if change == "ledger":
        modified = copy.deepcopy(manifest)
        del modified["provider"]["graphite"][policy.FIELD]
        with sqlite3.connect(w.prepared.ledger.path) as db:
            db.execute(
                "UPDATE campaign SET manifest=? WHERE id=1", (canonical(modified),)
            )
    if change in {"missing_ledger", "downgrade_missing_ledger"}:
        with sqlite3.connect(w.prepared.ledger.path) as db:
            db.execute("DELETE FROM campaign WHERE id=1")
    with pytest.raises(policy.PolicyInvalid):
        policy.from_root(w.root)
    # Prepared and disk authorities cannot silently diverge either.
    with pytest.raises(research_campaign.OperationRefused) as refused:
        asyncio.run(research_campaign.submit_candidate(w.prepared, 1, RECIPE))
    assert refused.value.code == policy.INVALID


def test_policy_is_frozen_in_block_digest_and_not_in_the_edition(retained):
    block = retained.prepared.manifest["provider"]["graphite"]
    legacy = {k: v for k, v in block.items() if k != policy.FIELD}
    assert edition.check_block(block) is block
    assert edition.check_block(legacy) is legacy
    assert block["edition_digest"] == edition.resolve(block["edition"]).digest
    assert digest(canonical(block)) != digest(canonical(legacy))
    assert json.loads(driver.launch_path(retained.root).read_bytes())[
        "block_digest"
    ] == digest(canonical(block))
    for bad in (None, "automatic"):
        with pytest.raises(policy.PolicyInvalid):
            edition.check_block({**block, policy.FIELD: bad})


def test_launch_choice_carries_the_policy_to_gate_and_freeze(tmp_path, monkeypatch):
    args = SimpleNamespace(root=tmp_path)
    choice = graphite_launch({"agent": "graphite", policy.FIELD: policy.RETAIN_ONLY})
    LaunchChoice(graphite={**choice, "curation_digest": "sha256:" + "c" * 64}).apply(
        args
    )
    assert args.graphite[policy.FIELD] == policy.RETAIN_ONLY
    host = object.__new__(RunnerAdapter)
    monkeypatch.setattr(host, "_campaign_gate", forbidden)
    assert host._launch_commitment_gate({}, args) is None


def test_actual_launch_admission_records_and_replays_policy_without_constructing_gate(
    graphite,
    monkeypatch,
):
    host = graphite.host
    # Use the real empty curation for the real launch freezer, while retaining
    # the host fixture's public registration and numerical-image stand-ins.
    library = driver.open_library(host.library_root)
    monkeypatch.setattr(host, "open_library", lambda path: library)
    monkeypatch.setattr(host, "_campaign_gate", forbidden)

    # The real host applies choices; freeze the real Graphite launch/block in the
    # fixture execution body (its ordinary stand-in Challenge has no driver).
    async def execute(args, *, ledger=None):
        driver.freeze_launch(args, args.root, challenge=graphite.challenge)
        graphite.launched.append(args)

    monkeypatch.setattr(research_campaign, "execute", execute)
    body = launch_request(graphite, **{policy.FIELD: policy.RETAIN_ONLY})
    first = perform(graphite, "launch", body)
    join(host)
    assert len(graphite.launched) == 1
    args = graphite.launched[0]
    assert (
        args.graphite[policy.FIELD] == policy.RETAIN_ONLY
        and args.commitment_gate is None
    )
    row, _, root = host._bound(first["id"])
    assert json.loads(row["launch_request"])[policy.FIELD] == policy.RETAIN_ONLY
    accepted = edition.launch_fields(args.graphite)
    assert accepted[policy.FIELD] == policy.RETAIN_ONLY
    assert driver.launch_path(root).exists()
    assert perform(graphite, "launch", body)["id"] == first["id"]
    changed = {k: v for k, v in body.items() if k != policy.FIELD}
    with pytest.raises(Rejected):
        perform(graphite, "launch", changed)


def test_frozen_runner_gate_and_manual_or_queued_effects_refuse_before_chain(
    retained, monkeypatch
):
    host = object.__new__(RunnerAdapter)
    admitted = SimpleNamespace(
        campaign={"id": "fixture", "root": str(retained.root)}, profile={}
    )
    monkeypatch.setattr(host, "_campaign_gate", forbidden)
    assert host._launch_commitment_gate({}, SimpleNamespace(root=retained.root)) is None
    monkeypatch.setattr(host, "_admissible", lambda value: None)
    monkeypatch.setattr(host, "_require_current_revision", lambda value: None)
    monkeypatch.setattr(host, "_require_frozen", forbidden)
    monkeypatch.setattr(host, "_require_level_served", forbidden)
    monkeypatch.setattr(host, "_poster", forbidden)
    monkeypatch.setattr(host, "_background", forbidden)
    for invoke in (
        lambda: host.commit_admitted(admitted, {}),
        lambda: host.submit_admitted(admitted, {}),
    ):
        with pytest.raises(Rejected) as refused:
            invoke()
        assert refused.value.code == policy.RETAINED
    refusals = []
    monkeypatch.setattr(host, "_refused", lambda *args: refusals.append(args))
    host._commit_thread(admitted, {"digest": "sha256:" + "9" * 64, "recommit": False})
    assert refusals == [("fixture", policy.RETAINED, "commit")]


def test_both_doors_publish_closed_policy_and_mcp_null_is_invalid():
    from pydantic import ValidationError

    from carbon.miner_mcp.mcp_operations import make_operation_tools

    assert policy.FIELD in OPERATIONS["launch"].optional
    assert CHOICES[policy.FIELD] == (policy.RETAIN_ONLY,)
    tool = {t.name: t for t in make_operation_tools(SimpleNamespace())}["carbon_launch"]
    assert "retain_only_v1" in json.dumps(tool.parameters["properties"][policy.FIELD])
    model = tool.fn_metadata.arg_model
    base = {"agent": "graphite"}
    assert model.model_validate(base).submission_policy is None
    assert (
        model.model_validate(
            {**base, policy.FIELD: policy.RETAIN_ONLY}
        ).submission_policy
        == policy.RETAIN_ONLY
    )
    with pytest.raises(ValidationError):
        model.model_validate({**base, policy.FIELD: None})
