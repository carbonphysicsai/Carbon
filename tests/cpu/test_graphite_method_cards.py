"""GRAPHITE-01 phase 2: triage, method cards, snapshots and human checks.

Scripted model only: no live inference, no key, no network, no spend.
"""

from __future__ import annotations

import datetime
import json

import pytest
from graphite_fixtures import grant, grant_document
from graphite_phase2_fixtures import (
    GRANT_FILE,
    INJECTION,
    backfill,
    entry,
    replies,
    reply,
    scripted,
    seed,
    tool,
)

from carbon.agent_campaign import grant as grants
from carbon.agent_campaign.controller import SimulatedCrash
from carbon.agent_campaign.graphite import GraphiteProvider, LiveModel, triage
from carbon.agent_campaign.graphite import literature as lit
from carbon.agent_campaign.graphite import method_cards as mc
from carbon.agent_campaign.graphite import tools as gt
from carbon.agent_campaign.graphite.literature_fetch import QUERY_SET
from carbon.agent_campaign.graphite.model import crash, fail
from carbon.agent_campaign.graphite.roles import (
    ROLES,
    TOOL_REGISTRY,
    FailureKind,
    RoleName,
)
from carbon.development_session.model_provider import ENGY_LADDER
from carbon.development_session.profile import canonical, digest

EVIDENCE = "sha256:" + "e" * 64


def _run(tmp_path, count=3, script=None, **kw):
    raw = seed(tmp_path, *(entry(n) for n in range(1, count + 1)))
    model = scripted(script if script is not None else replies(count))
    job = backfill(tmp_path, raw, model, **kw)
    return job, model, job.run("run-1")


# -- triage and cards -------------------------------------------------------------------


def test_triage_makes_unchecked_cards_on_the_cheapest_rung(tmp_path):
    job, model, summary = _run(tmp_path)
    assert summary["status"] == "COMPLETED"
    assert summary["cards_made"] == 3 and summary["pending"] == 0
    assert summary["model"] == ENGY_LADDER[0] == ROLES[RoleName.READER].start_model
    cards = job.cards.cards()
    assert len(cards) == 3
    for card, request in zip(cards, model.requests):
        assert card["status"] == mc.UNCHECKED
        assert card["link"].startswith("https://arxiv.org/abs/2610.")
        assert card["abstract_digest"].startswith("sha256:")
        extraction = card["extraction"]
        assert extraction["prompt_digest"] == mc.PROMPT_DIGEST
        assert extraction["model"] == ENGY_LADDER[0]
        assert extraction["live_inference"] is False
        assert extraction["request_digest"] == digest(canonical(request))
        assert request["tools"] == []
        assert request["instructions"] == mc.READER_EXTRACTION_PROMPT
        assert request["max_output_tokens"] == 1024
    # Every call was metered through the research ledger and settled from the
    # scripted provider charge (100 micro-USD each).
    assert summary["provider_attempts"] == 3
    assert summary["provider_nanodollars"] == 3 * 100 * 1000


def test_injection_inside_an_abstract_is_data(tmp_path):
    raw = seed(
        tmp_path,
        entry(1),
        entry(2, abstract=INJECTION),
        entry(3, abstract=INJECTION),
        entry(4, abstract=INJECTION),
    )
    model = scripted(
        [
            reply(),
            # The model "obeys" the injection: extra fields and a status.
            reply(status="HUMAN_CHECKED", model="kimi-k3", budget="unlimited"),
            # ... or calls a tool it was never offered.
            tool("carbon_research_start_research_task", {"arguments_json": "{}"}),
            # ... or extracts honestly.
            reply(method_name="text that asked to be verified"),
        ]
    )
    job = backfill(tmp_path, raw, model)
    summary = job.run("run-1")
    assert summary["status"] == "COMPLETED"
    clean, *injected = model.requests
    for request in injected:
        # The role, the tools, the model and the bounds are Carbon's, unchanged.
        for key in ("instructions", "tools", "model", "max_output_tokens", "store"):
            assert request[key] == clean[key]
        (message,) = request["input"]
        observation = json.loads(message["content"])
        assert observation["content_is_data"] is True
        assert observation["paper"]["abstract"] == INJECTION
        assert INJECTION not in request["instructions"]
    codes = sorted(r["code"] for r in job.cards.rejections())
    assert codes == ["fields_not_exactly_the_card_fields", "tool_call_in_reply"]
    cards = job.cards.cards()
    assert len(cards) == 2
    assert {card["status"] for card in cards} == {mc.UNCHECKED}
    assert all(job.cards.status(card) == mc.UNCHECKED for card in cards)
    # The run's caps are the grant's, whatever the abstract said.
    record = json.loads((job.root / "runs" / "run-1" / "run.json").read_bytes())
    assert record["ceilings"] == triage.ceilings(grant(), triage.MAX_CALLS_PER_RUN)


@pytest.mark.parametrize(
    "bad",
    [
        reply(relevant="yes"),
        reply(construction_claims="one claim"),
        reply(method_name=""),
        reply(required_inputs=["x"] * (mc.MAX_ITEMS + 1)),
        {"text": "not json"},
    ],
)
def test_a_malformed_extraction_makes_no_card(tmp_path, bad):
    job, _, summary = _run(tmp_path, count=1, script=[bad])
    assert summary["cards_made"] == 0 and summary["rejected"] == 1
    assert job.cards.cards() == []


def test_a_fenced_json_reply_is_read():
    body = reply()["text"]
    response = {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "```json\n" + body}],
            }
        ]
    }
    with pytest.raises(mc.ExtractionRejected):
        mc.parse_extraction(response)
    response["output"][0]["content"][0]["text"] += "\n```"
    assert mc.parse_extraction(response)["relevant"] is True


# -- the grant ----------------------------------------------------------------------------


def test_the_phase2_grant_document_is_the_owners_grant():
    document = json.loads(GRANT_FILE.read_bytes())
    assert document["provider"] == "graphite"
    assert document["currency"] == "USD"
    assert document["monetary_ceiling"] == "9.00"
    assert document["account"] == "Carbon-Account"
    assert document["expires_at"] == "2026-12-31T23:59:59Z"
    assert document["permitted_runs"] == 40  # OWNER-GRAPHITE-02 amendment
    assert document["worst_case_run_cost"] == "2.49"
    assert set(document) == set(grants.FIELDS)
    grants.SpendingGrant.from_document(document)


def test_the_phase2_grant_fails_closed_while_any_field_is_human_input():
    for field in ("account", "expires_at", "worst_case_run_cost"):
        document = json.loads(GRANT_FILE.read_bytes())
        document[field] = "HUMAN_INPUT"
        with pytest.raises(grants.GrantError, match="grant_value_missing"):
            grants.SpendingGrant.from_document(document)


def test_a_backfill_refuses_without_an_exact_grant(tmp_path):
    raw = seed(tmp_path, entry(1))
    for bad in (
        None,
        grant_document(),
        grants.template("graphite"),
        json.loads(GRANT_FILE.read_bytes()),
    ):
        with pytest.raises(triage.BackfillRefused, match="spending_grant_required"):
            backfill(tmp_path, raw, scripted(replies(1)), grant=bad)
    with pytest.raises(triage.BackfillRefused, match="grant_provider_mismatch"):
        backfill(tmp_path, raw, scripted([]), grant=grant(provider="other"))
    with pytest.raises(triage.BackfillRefused, match="grant_expired"):
        backfill(
            tmp_path,
            raw,
            scripted([]),
            now=lambda: datetime.datetime(2100, 1, 1, tzinfo=datetime.UTC),
        )
    key = tmp_path / "key"
    key.write_text("fixture")
    live = LiveModel(
        grant=grant(grant_id="another-grant"),
        credential_file=str(key),
        provider="graphite",
    )
    with pytest.raises(triage.BackfillRefused, match="live_model_grant_mismatch"):
        backfill(tmp_path, raw, live)
    with pytest.raises(grants.GrantError):
        grants.SpendingGrant.from_document(grants.template("graphite"))


def test_the_spend_cap_stops_the_run_mid_backfill(tmp_path):
    raw = seed(tmp_path, *(entry(n) for n in range(1, 21)))
    model = scripted(replies(20), charged_micro=800)
    job = backfill(tmp_path, raw, model, grant=grant(worst_case_run_cost="0.01"))
    summary = job.run("run-1")
    assert summary["status"] == "STOPPED_CAP"
    assert summary["dimension"] == "provider_nanodollars"
    assert summary["run_cap_nanodollars"] == 10_000_000
    assert 0 < summary["cards_made"] < 20
    assert summary["pending"] == 20 - summary["cards_made"]
    assert len(model.requests) == summary["cards_made"]
    # Settled from the provider's reported charge, 800 micro-USD a call;
    # the run stops when the next reservation would pass the cap.
    reservation = 16384 * 45 + 1024 * 90
    made = summary["cards_made"]
    assert made * 800_000 + reservation > 10_000_000
    assert (made - 1) * 800_000 + reservation <= 10_000_000
    assert summary["provider_nanodollars"] == made * 800_000


def test_the_call_cap_stops_the_run(tmp_path):
    _, model, summary = _run(tmp_path, count=4, max_calls=2)
    assert summary["status"] == "STOPPED_CAP"
    assert summary["dimension"] == "provider_attempts"
    assert summary["cards_made"] == 2 and len(model.requests) == 2


def test_runs_are_limited_by_the_grant(tmp_path):
    raw = seed(tmp_path, entry(1), entry(2))
    job = backfill(
        tmp_path, raw, scripted(replies(1)), grant=grant(permitted_runs=1), max_calls=1
    )
    assert job.run("run-1")["status"] == "STOPPED_CAP"
    assert job.run("run-1")["status"] == "STOPPED_CAP"  # a resume is not a new run
    with pytest.raises(triage.BackfillRefused, match="run_limit_reached"):
        job.run("run-2")
    # A ceiling that cannot hold another run's worst case refuses it.
    other = tmp_path / "other"
    raw = seed(other, entry(1))
    job = backfill(
        other,
        raw,
        scripted(replies(1)),
        grant=grant(
            monetary_ceiling="0.60",
            cleanup_allowance="0.10",
            worst_case_run_cost="0.50",
        ),
    )
    assert job.run("run-1")["status"] == "COMPLETED"
    with pytest.raises(triage.BackfillRefused, match="grant_ceiling_reached"):
        job.run("run-2")


def test_a_resumed_run_replays_a_paid_call_without_paying_again(tmp_path, monkeypatch):
    raw = seed(tmp_path, entry(1), entry(2), entry(3))
    model = scripted(replies(3))
    job = backfill(tmp_path, raw, model)
    put = mc.CardStore.put_card
    calls = []

    def dies_once(self, card):
        calls.append(card["card_id"])
        if len(calls) == 2:
            raise SimulatedCrash("after the call, before the card")
        return put(self, card)

    monkeypatch.setattr(mc.CardStore, "put_card", dies_once)
    with pytest.raises(SimulatedCrash):
        job.run("run-1")
    assert len(model.requests) == 2
    monkeypatch.setattr(mc.CardStore, "put_card", put)
    model.script.extend(replies(1))  # only paper 3 still needs a call
    resumed = backfill(tmp_path, raw, model)
    summary = resumed.run("run-1")
    assert summary["status"] == "COMPLETED"
    assert summary["cards_made"] == 2
    assert len(model.requests) == 3  # paper 2 replayed from the ledger
    assert summary["provider_attempts"] == 3
    assert summary["provider_nanodollars"] == 3 * 100 * 1000


RESERVATION = 16384 * 45 + 1024 * 90


def _crashed(tmp_path, count=4):
    """Run 1 makes one card, then dies with paper 2's call in flight."""
    raw = seed(tmp_path, *(entry(n) for n in range(1, count + 1)))
    model = scripted([reply(), crash()])
    job = backfill(tmp_path, raw, model)
    with pytest.raises(SimulatedCrash):
        job.run("run-1")
    return raw, model, job


def _stuck(job):
    return [
        op
        for op in job._ledger("run-1").status(owner=triage.OWNER)["operations"]
        if op["state"] == "RESERVED"
    ]


def test_a_crash_mid_call_leaves_the_call_reserved(tmp_path):
    raw, model, job = _crashed(tmp_path)
    stuck = _stuck(job)
    second = raw.addresses()[1]
    assert [op["id"] for op in stuck] == ["card-" + second[7:47]]
    assert stuck[0]["reservation"]["provider_nanodollars"] == RESERVATION
    assert job.committed_nano() == 100_000 + RESERVATION
    assert len(model.requests) == 2


def test_a_resume_writes_off_the_unknown_call_and_completes(tmp_path):
    raw, model, job = _crashed(tmp_path)
    second = raw.addresses()[1]
    model.script.extend(replies(2))  # papers 3 and 4; never paper 2
    summary = backfill(tmp_path, raw, model).run("run-1")
    assert summary["status"] == "COMPLETED"
    assert summary["written_off_unknown"] == 1
    assert summary["cards_made"] == 2 and summary["pending"] == 0
    assert len(model.requests) == 4  # paper 2 was not sent again
    assert model.requests[1] not in model.requests[2:]
    (rejection,) = job.cards.rejections()
    assert rejection == {
        "schema": mc.REJECTION_SCHEMA,
        "record_digest": second,
        "code": "provider_outcome_unknown",
        "run_id": "run-1",
        "operation_id": "card-" + second[7:47],
        "reservation": _stuck(job)[0]["reservation"],
    }
    # The reservation stays booked in run 1's ledger and is still counted.
    assert _stuck(job)[0]["id"] == "card-" + second[7:47]
    assert summary["provider_nanodollars"] == 3 * 100_000 + RESERVATION
    assert job.committed_nano() == 3 * 100_000 + RESERVATION


def test_a_written_off_call_is_never_resent_in_any_run(tmp_path):
    raw, model, _ = _crashed(tmp_path, count=2)
    again = backfill(tmp_path, raw, model)
    first = again.run("run-1")
    assert first["status"] == "COMPLETED" and first["written_off_unknown"] == 1
    assert len(model.requests) == 2
    assert again.pending() == []
    # A new run finds nothing to send and still counts run 1's reservation.
    second = again.run("run-2")
    assert second["status"] == "COMPLETED"
    assert second["written_off_unknown"] == 0 and second["cards_made"] == 0
    assert len(model.requests) == 2
    assert again.committed_nano() == 100_000 + RESERVATION


def test_a_new_run_never_resends_an_unknown_call(tmp_path):
    raw, model, _ = _crashed(tmp_path, count=2)
    model.script.extend(replies(1))  # would answer a resend, if one were made
    summary = backfill(tmp_path, raw, model).run("run-2")
    assert len(model.requests) == 2, "the unknown call was resent"
    assert summary["written_off_unknown"] == 1
    assert summary["status"] == "COMPLETED" and summary["provider_attempts"] == 0


def test_the_write_off_is_idempotent(tmp_path):
    raw, model, _ = _crashed(tmp_path, count=2)
    again = backfill(tmp_path, raw, model)
    assert again.write_off_unknown() == 1
    before = [p.read_bytes() for p in sorted(again.cards.root.rglob("*.json"))]
    assert again.write_off_unknown() == 0
    assert again.run("run-1")["written_off_unknown"] == 0
    assert again.run("run-1")["written_off_unknown"] == 0
    after = [p.read_bytes() for p in sorted(again.cards.root.rglob("*.json"))]
    assert before == after and len(again.cards.rejections()) == 1
    assert len(_stuck(again)) == 1  # the ledger is never settled or deleted
    assert again.committed_nano() == 100_000 + RESERVATION


def test_an_unmapped_unknown_call_refuses_the_run_unchanged(tmp_path):
    _, model, job = _crashed(tmp_path, count=2)
    other = seed(tmp_path / "elsewhere", entry(9))
    stranger = triage.Backfill(
        root=job.root, raw=other, grant=grant(), model=model, clock=lambda: 1000.0
    )
    with pytest.raises(triage.BackfillRefused, match="unresolved_operation_unmapped"):
        stranger.run("run-1")
    assert job.cards.rejections() == []
    assert len(model.requests) == 2


@pytest.mark.parametrize("step", [crash(), fail(503), fail(500)])
def test_an_unknown_outcome_during_a_live_call_still_stops_the_run(tmp_path, step):
    raw = seed(tmp_path, entry(1), entry(2), entry(3))
    model = scripted([reply(), step])
    job = backfill(tmp_path, raw, model)
    if step.get("crash"):
        with pytest.raises(SimulatedCrash):
            job.run("run-1")
        # The operator sees the stop: a fresh start writes the call off.
        model.script.extend(replies(1))
        summary = backfill(tmp_path, raw, model).run("run-1")
        assert summary["written_off_unknown"] == 1
        assert summary["status"] == "COMPLETED" and len(model.requests) == 3
        return
    summary = job.run("run-1")
    assert summary["status"] == "RECONCILIATION_REQUIRED"
    assert summary["written_off_unknown"] == 0
    assert summary["cards_made"] == 1 and len(model.requests) == 2
    assert job.cards.rejections() == []  # written off only at the next start
    assert summary["provider_nanodollars"] == 100_000 + RESERVATION
    model.script.extend(replies(1))
    resumed = job.run("run-1")
    assert resumed["status"] == "COMPLETED"
    assert resumed["written_off_unknown"] == 1
    assert len(model.requests) == 3  # paper 2 never resent


def test_a_resumed_run_with_a_written_off_call_still_types_a_later_rejection(
    tmp_path,
):
    raw, model, _ = _crashed(tmp_path, count=3)
    model.script.append(fail(401, "auth"))
    summary = backfill(tmp_path, raw, model).run("run-1")
    assert summary["status"] == "PROVIDER_REJECTED"
    assert summary["outcome"] == "auth_credential"
    assert summary["written_off_unknown"] == 1


def test_a_provider_rejection_stops_the_run_typed(tmp_path):
    _, _, summary = _run(tmp_path, count=2, script=[fail(401, "auth")])
    assert summary["status"] == "PROVIDER_REJECTED"
    assert summary["outcome"] == "auth_credential"
    assert summary["cards_made"] == 0


def test_a_run_keeps_its_model_and_the_next_run_takes_the_ladder_rung(tmp_path):
    raw = seed(tmp_path, entry(1), entry(2))
    model = scripted(replies(1))
    job = backfill(tmp_path, raw, model, max_calls=1)
    assert job.run("run-1")["status"] == "STOPPED_CAP"
    failure = job.ladder.record_failure(
        RoleName.READER, FailureKind.CARD_EXTRACTION_ERROR, EVIDENCE
    )
    job.ladder.escalate(RoleName.READER, failure)
    model.script.extend(replies(1))
    assert job.run("run-1")["model"] == ENGY_LADDER[0]  # resume keeps its model
    model.script.extend(replies(1))
    job = backfill(tmp_path, raw, model)
    assert job.run("run-2")["model"] == ENGY_LADDER[1]


# -- snapshots ----------------------------------------------------------------------------


def _snapshot(job):
    return mc.snapshot(
        job.cards, job.raw, label="test-snapshot", query_set_digest=QUERY_SET.digest
    )


def test_a_snapshot_is_deterministic_and_loads_into_the_literature_tools(tmp_path):
    job, _, _ = _run(tmp_path, count=3)
    index, document = _snapshot(job)
    again, document_again = _snapshot(job)
    assert canonical(document) == canonical(document_again)
    assert index.snapshot_digest == again.snapshot_digest
    address = mc.write_snapshot(job.cards, document)
    path = job.cards.root / "snapshots" / (address[7:] + ".json")
    loaded = mc.load_snapshot(path)
    assert type(loaded) is lit.LiteratureIndex
    assert loaded.snapshot_digest == index.snapshot_digest
    hits = loaded.search("physics-informed operator")
    assert {h["card_id"] for h in hits} == {
        "arxiv-2610.00001v1",
        "arxiv-2610.00002v1",
        "arxiv-2610.00003v1",
    }
    card = loaded.card("arxiv-2610.00001v1")
    assert "UNCHECKED" in card["provenance"]
    assert "not Carbon's" in card["provenance"]
    # The phase-1 provider and toolbox serve it unchanged.
    provider = GraphiteProvider(
        root=tmp_path / "graphite",
        grant=grant(),
        model=scripted([]),
        literature_index=loaded,
    )
    assert provider.literature.snapshot_digest == index.snapshot_digest
    path.write_bytes(path.read_bytes().replace(b"Synthetic", b"Tampered"))
    with pytest.raises(ValueError):
        mc.load_snapshot(path)


def test_cards_that_name_protected_material_are_withheld(tmp_path):
    raw = seed(
        tmp_path,
        entry(1),
        entry(2, abstract="A study of the EV4 confirmation set."),
        entry(3),
    )
    job = backfill(tmp_path, raw, scripted(replies(2) + [reply(relevant=False)]))
    job.run("run-1")
    try:
        index, document = _snapshot(job)
    except lit.LiteratureError as error:
        pytest.fail("a protected card reached the index: " + str(error))
    assert document["withheld_protected"] == ["arxiv-2610.00002v1"]
    assert document["excluded"] == ["arxiv-2610.00003v1"]
    assert [c["card_id"] for c in index.cards] == ["arxiv-2610.00001v1"]
    assert not any(gt.protected(card) for card in index.cards)


# -- human checks -------------------------------------------------------------------------


def test_a_person_records_a_check_and_it_changes_the_snapshot(tmp_path):
    job, _, _ = _run(tmp_path, count=2)
    before, _ = _snapshot(job)
    cid = "arxiv-2610.00002v1"
    entry_ = mc.record_human_check(
        job.cards,
        cid,
        checker="Ryan",
        verdict="EXTRACTION_ERROR",
        note="claims misread",
        confirm=lambda prompt: cid,
        now="2026-10-02T12:00:00Z",
    )
    assert entry_["checker"] == "Ryan" and entry_["checked_at"].startswith("2026")
    assert job.cards.status(job.cards.card(cid)) == "HUMAN_CHECKED_EXTRACTION_ERROR"
    after, document = _snapshot(job)
    assert after.snapshot_digest != before.snapshot_digest
    assert cid in document["excluded"]
    mc.record_human_check(
        job.cards,
        "arxiv-2610.00001v1",
        checker="Ryan",
        verdict="CORRECT",
        note="",
        confirm=lambda prompt: "arxiv-2610.00001v1",
    )
    listing = {row["card_id"]: row["status"] for row in job.cards.listing()}
    assert listing["arxiv-2610.00001v1"] == "HUMAN_CHECKED_CORRECT"
    assert job.cards.listing(unchecked_only=True) == []


@pytest.mark.parametrize(
    "checker", ["graphite-reader", "reader", "Claude", "deepseek-v4-flash-0731", "bot"]
)
def test_an_agent_or_model_cannot_be_the_checker(tmp_path, checker):
    job, _, _ = _run(tmp_path, count=1)
    with pytest.raises(mc.CheckRefused) as refused:
        mc.record_human_check(
            job.cards,
            "arxiv-2610.00001v1",
            checker=checker,
            verdict="CORRECT",
            note="",
            confirm=lambda prompt: "arxiv-2610.00001v1",
        )
    assert refused.value.code == "checker_names_an_agent_or_model"
    assert job.cards.checks("arxiv-2610.00001v1") == []


def test_a_check_needs_the_person_to_type_the_card_id(tmp_path):
    job, _, _ = _run(tmp_path, count=1)
    cid = "arxiv-2610.00001v1"
    for confirm in (lambda p: "yes", lambda p: "", None, lambda p: cid + "x"):
        with pytest.raises(mc.CheckRefused) as refused:
            mc.record_human_check(
                job.cards,
                cid,
                checker="Ryan",
                verdict="CORRECT",
                note="",
                confirm=confirm,
            )
        assert refused.value.code == "interactive_confirmation_required"
    assert job.cards.checks(cid) == []


def test_the_agent_path_cannot_mark_a_card_checked(tmp_path):
    job, _, _ = _run(tmp_path, count=1)
    card = job.cards.cards()[0]
    with pytest.raises(ValueError, match="UNCHECKED"):
        job.cards.put_card({**card, "card_id": "arxiv-x", "status": "HUMAN_CHECKED"})
    # No role has a tool that writes, and no tool checks a card.
    assert not any("check" in name for name in TOOL_REGISTRY)
    assert set(ROLES[RoleName.READER].tools) == {lit.SEARCH, lit.CARD}
    with pytest.raises(TypeError):
        mc.make_card({}, "", {}, {}, status="HUMAN_CHECKED")
