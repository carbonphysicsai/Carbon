"""Graphite's Score Lab research session (GRAPHITE-RESEARCH-SCORELAB-01).

Scripted model only: no live inference, no key, no network, no spend. A test session's answers and report stay in its
temporary root; nothing is committed.

Claims tested:
- a session asks four questions and one synthesis, and writes the report once, status PROPOSED, with no authority;
- every source in a reply must resolve to the brief (or, in the synthesis, to an accepted finding);
- a reply outside the schema is rejected and recorded, and the synthesis waits for the questions;
- the brief refuses a currency figure, a private path, an account-like identifier and protected material;
- a finished session resumes without a new call;
- the grant covers its calls at the planner's settings, and only that grant runs live.
"""

from __future__ import annotations

import datetime
import json
from decimal import Decimal
from pathlib import Path

import pytest
from graphite_fixtures import grant, grant_document

from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.graphite import score_lab_research as sl
from carbon.agent_campaign.graphite.closed_task import TaskRefused
from carbon.agent_campaign.graphite.literature import FIXTURE_INDEX
from carbon.agent_campaign.graphite.model import ScriptedModel, text
from carbon.agent_campaign.graphite.roles import RoleName

REPOSITORY = Path(__file__).resolve().parents[2]
GRANT_FILE = (
    REPOSITORY
    / "docs/development/graphite/grants/GRAPHITE-GRANT-RESEARCH-SCORELAB-1.json"
)
NOW = datetime.datetime(2026, 10, 13, 12, 0, tzinfo=datetime.UTC)
SOURCES = (
    {
        "id": "canon-customer",
        "origin": "Business/Business_Canon.md",
        "text": "A customer decides what to build.",
    },
    {
        "id": "spec-decision",
        "origin": "PRODUCT_SPEC_V2",
        "text": "Decision evidence compares to the customer's workflow.",
    },
)
CARD = "fixture-operator-0001"


def finding(source="excerpt:canon-customer", **changes):
    row = {
        "claim": "A customer screens designs.",
        "basis": "The canon says so.",
        "sources": [source],
    }
    row.update(changes)
    return row


def question_reply(**changes):
    reply = {
        "findings": [finding(), finding(f"card:{CARD}")],
        "source_gaps": ["standard clauses"],
    }
    reply.update(changes)
    return reply


def synthesis_reply(**changes):
    reply = {
        "additions": [
            {
                "rank": 2,
                "addition": "A neighbourhood-weighted value.",
                "customer_value": "Designs change a little.",
                "sources": ["finding:q2.1"],
                "cheapest_test": "Replay the cached members.",
            },
            {
                "rank": 1,
                "addition": "A cheap-map baseline.",
                "customer_value": "The current workflow is the comparator.",
                "sources": ["excerpt:spec-decision", "finding:q1.2"],
                "cheapest_test": "Add the map as a member.",
            },
        ],
        "not_supported": ["a price curve"],
    }
    reply.update(changes)
    return reply


def script(replies):
    return [text(json.dumps(r)) for r in replies]


def good_script():
    return script([question_reply()] * 4 + [synthesis_reply()])


def researcher(tmp_path, steps, **kw):
    kw.setdefault("grant", grant())
    model = ScriptedModel(steps)
    job = sl.ScoreLabResearch(
        root=tmp_path / "research",
        model=model,
        clock=lambda: 1000.0,
        now=lambda: NOW,
        sleep=lambda seconds: None,
        **kw,
    )
    return job, model


def run(tmp_path, steps, *, sources=SOURCES, run_id="research-1"):
    job, model = researcher(tmp_path, steps)
    summary = job.research(
        run_id, sources=sources, index=FIXTURE_INDEX, card_ids=(CARD,)
    )
    return job, model, summary


def test_a_session_answers_every_question_and_writes_the_report_once(tmp_path):
    job, model, summary = run(tmp_path, good_script())
    assert summary["status"] == "COMPLETED" and summary["report_written"] is True
    assert [i["outcome"] for i in summary["items"]] == ["ANSWERED"] * 5
    assert summary["role"] == RoleName.PLANNER.value and summary["model"] == "glm-5.2"
    assert len(model.requests) == 5 and all(r["tools"] == [] for r in model.requests)
    directory = job.task.run_dir("research-1")
    report = json.loads((directory / "report.json").read_bytes())
    assert report["status"] == "PROPOSED" and set(report["answers"]) == set(sl.ITEMS)
    assert report["authority"] == {
        "decision": False,
        "threshold": False,
        "adoption": False,
        "score": False,
    }
    ranks = [a["rank"] for a in report["answers"]["synthesis"]["additions"]]
    assert ranks == [1, 2]
    # Written once: the files cannot be replaced.
    with pytest.raises(ValueError):
        sl.write_once(directory / "report.json", b"{}")


def test_the_synthesis_request_carries_the_accepted_findings(tmp_path):
    _job, model, _summary = run(tmp_path, good_script())
    last = json.loads(model.requests[-1]["input"][0]["content"])
    assert last["item"] == "synthesis"
    assert set(last["findings"]) == {f"q{n}.{i}" for n in range(1, 5) for i in (1, 2)}


@pytest.mark.parametrize(
    "bad, code",
    [
        (question_reply(findings=[finding("excerpt:nope")]), "source_not_in_the_brief"),
        (question_reply(findings=[finding("card:unknown")]), "source_not_in_the_brief"),
        (question_reply(findings=[finding("finding:q1.1")]), "source_not_in_the_brief"),
        (question_reply(findings=[finding(sources=[])]), "sources_required"),
        (question_reply(status="ACCEPTED"), "reply_keys"),
        (question_reply(findings=[]), "findings_required"),
        (question_reply(findings=[finding(extra="x")]), "finding_shape"),
    ],
)
def test_a_reply_outside_the_rules_is_rejected_and_the_synthesis_waits(
    tmp_path, bad, code
):
    steps = script([bad] + [question_reply()] * 3 + [synthesis_reply()])
    job, model, summary = run(tmp_path, steps)
    outcomes = {i["item"]: i for i in summary["items"]}
    assert outcomes["q1"] == {"item": "q1", "outcome": "REJECTED", "code": code}
    assert outcomes["synthesis"]["outcome"] == "SKIPPED"
    assert summary["report_written"] is False and len(model.requests) == 4
    rejected = json.loads(
        (job.task.run_dir("research-1") / "rejections/q1.json").read_bytes()
    )
    assert rejected["code"] == code


@pytest.mark.parametrize(
    "bad, code",
    [
        (
            synthesis_reply(additions=[synthesis_reply()["additions"][0]]),
            "ranks_not_one_to_n",
        ),
        (
            synthesis_reply(
                additions=[
                    {**synthesis_reply()["additions"][1], "sources": ["finding:q9.9"]}
                ]
            ),
            "source_not_in_the_brief",
        ),
        (synthesis_reply(additions=[]), "additions_required"),
        (synthesis_reply(decision="adopt"), "reply_keys"),
    ],
)
def test_a_synthesis_must_rank_and_cite_accepted_findings(tmp_path, bad, code):
    steps = script([question_reply()] * 4 + [bad])
    _job, _model, summary = run(tmp_path, steps)
    assert summary["items"][-1] == {
        "item": "synthesis",
        "outcome": "REJECTED",
        "code": code,
    }
    assert summary["report_written"] is False


@pytest.mark.parametrize(
    "text_value, code",
    [
        ("The run cost $14.94 in total.", "source_names_a_currency_figure"),
        ("About 12 USD per month.", "source_names_a_currency_figure"),
        ("Kept under /home/miner/private.", "source_names_a_private_path"),
        (
            "Account 5D7wmQVrv3LBjh7yVuoyrcennFCenQPDUVLS1p7Gj6KZwhZP signed.",
            "source_names_an_account_like_identifier",
        ),
        ("It reads the official_seed of the exam.", "source_names_protected_material"),
    ],
)
def test_the_brief_refuses_what_must_not_travel(tmp_path, text_value, code):
    sources = (*SOURCES, {"id": "bad", "origin": "a repo document", "text": text_value})
    job, model = researcher(tmp_path, [])
    with pytest.raises(sl.BriefRefused) as refused:
        job.research(
            "research-1", sources=sources, index=FIXTURE_INDEX, card_ids=(CARD,)
        )
    assert refused.value.code == code and model.requests == []


def test_the_brief_refuses_bad_sources_and_cards(tmp_path):
    job, model = researcher(tmp_path, [])
    for sources, cards, code in (
        ((), (CARD,), "sources_required"),
        ((SOURCES[0], SOURCES[0]), (CARD,), "source_shape"),
        (
            (SOURCES[0], {"id": "Bad Id", "origin": "o", "text": "t"}),
            (CARD,),
            "source_shape",
        ),
        (SOURCES, ("not-a-card",), "unknown_card"),
    ):
        with pytest.raises(sl.BriefRefused) as refused:
            job.research("r", sources=sources, index=FIXTURE_INDEX, card_ids=cards)
        assert refused.value.code == code
    assert model.requests == []


def test_a_finished_session_resumes_without_a_new_call(tmp_path):
    run(tmp_path, good_script())
    again, fresh = researcher(tmp_path, [])
    resumed = again.research(
        "research-1", sources=SOURCES, index=FIXTURE_INDEX, card_ids=(CARD,)
    )
    assert fresh.requests == []
    assert [i["outcome"] for i in resumed["items"]] == ["ANSWERED"] * 5
    # A different brief under the same run id is refused, not mixed in.
    with pytest.raises(TaskRefused, match="run_record_mismatch"):
        again.research(
            "research-1", sources=SOURCES[:1], index=FIXTURE_INDEX, card_ids=(CARD,)
        )


@pytest.mark.parametrize(
    "value, code",
    [
        (None, "spending_grant_required"),
        (grant_document(), "spending_grant_required"),
    ],
)
def test_a_session_needs_an_exact_grant(tmp_path, value, code):
    with pytest.raises(TaskRefused, match=code):
        researcher(tmp_path, [], grant=value)


def _research_grant():
    return SpendingGrant.from_document(json.loads(GRANT_FILE.read_bytes()))


def test_the_research_grant_covers_its_calls_and_stays_inside_the_approval():
    g = _research_grant()
    # One call reserved at the planner's settings on glm-5.2: 680 and 1,500 nanodollars per input and output token.
    call = Decimal(
        sl.SETTINGS["max_input_tokens"] * 680 + sl.SETTINGS["max_output_tokens"] * 1500
    ) / Decimal(10**9)
    assert call == Decimal("0.182845440")
    cap = int(g.worst_case_run_cost // call)
    assert cap == 8 and sl.MAX_CALLS <= cap
    assert call * sl.MAX_CALLS == Decimal("1.46276352") <= g.worst_case_run_cost
    assert g.max_runtime_s == cap * sl.SETTINGS["timeout_seconds"]
    assert g.permitted_runs == 1 == g.max_submissions and g.max_concurrency == 1
    assert (
        g.permitted_runs * g.worst_case_run_cost + g.cleanup_allowance
        <= g.monetary_ceiling
    )
    assert g.monetary_ceiling == Decimal("2.00") <= Decimal("14.94")
    assert g.provider == "graphite" and g.currency == "USD"
    assert sl.RESEARCH_GRANTS == {g.grant_id}
    # The Planner's rung is glm-5.2, so no dearer model opens by default.
    from carbon.agent_campaign.graphite.roles import ROLES

    assert ROLES[sl.ROLE].start_model == "glm-5.2"


def test_the_live_runner_needs_the_research_grant_and_an_owner_only_key(
    tmp_path, capsys
):
    key = tmp_path / "api_key"
    key.write_text("not-a-real-key")
    key.chmod(0o600)
    other = tmp_path / "grant.json"
    other.write_text(json.dumps(grant_document()))
    snapshot = tmp_path / "missing-snapshot.json"
    sources = tmp_path / "sources.json"
    sources.write_text(json.dumps(list(SOURCES)))
    argv = [
        "--root",
        str(tmp_path / "root"),
        "--snapshot",
        str(snapshot),
        "--sources",
        str(sources),
    ]
    argv += ["--grant", str(other), "--credential-file", str(key)]
    assert sl.main(argv, environ={}) == 2
    assert json.loads(capsys.readouterr().out.splitlines()[0]) == {
        "status": "REFUSED",
        "reason_code": "research_grant_required",
    }
    key.chmod(0o640)
    assert sl.main(argv, environ={}) == 2
    assert (
        json.loads(capsys.readouterr().out.splitlines()[0])["reason_code"]
        == "credential_file_not_owner_only"
    )


def test_the_standing_weekly_sum_still_fits_with_the_research_ceiling():
    from carbon.agent_campaign import grant_runs
    from carbon.agent_campaign.graphite import grant_binding

    standing = [
        SpendingGrant.from_document(
            json.loads(
                (REPOSITORY / grant_binding.GRANTS_DIR / (gid + ".json")).read_bytes()
            )
        )
        for gid, registered in grant_binding.PHASE3_GRANTS.items()
        if registered.authority == grant_binding.STANDING_TEST_GRANT_AUTHORITY
    ]
    effective = grant_runs.effective_weekly_cap()
    other_open = Decimal(
        "184.56"
    )  # the weekly-budget record's other open grants (CONFIRM-02 at its amended 37)
    total = (
        other_open
        + sum(g.monetary_ceiling for g in standing)
        + _research_grant().monetary_ceiling
    )
    assert total <= effective
    # Room for the pending open-weight coverage grant (#1257) and the L2 re-attack, at their ceilings.
    assert total + Decimal("14.94") + Decimal("13.47") <= effective
