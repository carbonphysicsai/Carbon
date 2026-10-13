"""LP-04: fixture validators, paired identities and independent journals/results."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from carbon.battery import campaign, intake_client, multi_intake
from carbon.battery import remote_submission as rs
from carbon.development_session import intake_targets as targets
from carbon.development_session.research_campaign import OperationRefused
from scripts.dev.miner_launchpad import environment_setup as setup
from scripts.dev.miner_launchpad import projection, runner

CHALLENGE = campaign.CHALLENGE.challenge_id
PAIRS = [
    {"intake_url": "https://one.example.test", "receiver_hotkey": "5" + "A" * 47},
    {"intake_url": "https://two.example.test", "receiver_hotkey": "5" + "B" * 47},
]
DIGEST = "sha256:" + "c" * 64


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        [],
        [None],
        [PAIRS[0], PAIRS[0]],
        [{**PAIRS[0], "private": "not allowed"}],
        [{**PAIRS[0], "receiver_hotkey": None}],
        [{**PAIRS[0], "intake_url": "http://remote.example.test"}],
        [PAIRS[0], {**PAIRS[1], "intake_url": PAIRS[0]["intake_url"]}],
        [PAIRS[0], {**PAIRS[1], "receiver_hotkey": PAIRS[0]["receiver_hotkey"]}],
        [PAIRS[0]] * 33,
    ],
)
def test_unpaired_conflicting_and_unbounded_profiles_are_refused(value):
    with pytest.raises(ValueError):
        targets.validate(value)


def test_pair_validation_copies_data_and_legacy_profile_is_unchanged(tmp_path):
    accepted = targets.validate(PAIRS)
    accepted[0]["receiver_hotkey"] = "changed"
    assert PAIRS[0]["receiver_hotkey"] == "5" + "A" * 47
    cfg = {"intakes": {CHALLENGE: PAIRS[0]["intake_url"]}}
    assert targets.for_challenge(cfg, CHALLENGE) is None
    assert runner.intakes(cfg) == cfg["intakes"]
    assert runner.receivers(cfg) == {}
    assert targets.journal(tmp_path, PAIRS[0]) != targets.journal(tmp_path, PAIRS[1])
    assert targets.journal(
        tmp_path, dict(reversed(list(PAIRS[0].items())))
    ) == targets.journal(tmp_path, PAIRS[0])


def test_published_validators_group_by_challenge_without_changing_a_single_entry(
    tmp_path,
):
    from carbon.chain.models import CARBON_NETUID, CARBON_NETWORK

    path = tmp_path / "published.json"
    entries = [
        {
            "network": CARBON_NETWORK,
            "netuid": CARBON_NETUID,
            "challenge": CHALLENGE,
            **pair,
        }
        for pair in PAIRS
    ]

    def write(items):
        path.write_text(
            json.dumps({"schema": setup.PUBLISHED_SCHEMA, "endpoints": items}),
            encoding="utf-8",
        )

    write(entries[:1])
    assert setup.published_endpoints(path)["endpoints"][CHALLENGE] == entries[0]
    write(entries)
    loaded = setup.published_endpoints(path)
    assert loaded["problem"] is None
    assert loaded["endpoints"][CHALLENGE]["validators"] == entries
    write([entries[0], entries[0]])
    assert setup.published_endpoints(path) == {
        "endpoints": {},
        "problem": "published_endpoints_unreadable",
    }


class Wire:
    def __init__(self):
        self.sent, self.signed = [], []
        self.states = {pair["intake_url"]: "SCORED" for pair in PAIRS}
        self.bad_receiver, self.unreachable = set(), set()

    def read(self, url):
        if url in self.unreachable:
            raise OSError("fixture unavailable; private exception must not be shown")
        pair = next(pair for pair in PAIRS if pair["intake_url"] == url)
        return {
            "receiver": (
                "wrong" if url in self.bad_receiver else pair["receiver_hotkey"]
            ),
            "snapshot": {"id": "fixture", "finalized_block": 720},
        }

    def sign(self, signer, facts, body):
        self.signed.append((facts["receiver"], json.loads(body)["call"]["tool"]))
        return {"fixture_receiver": facts["receiver"]}

    def post(self, url, body, headers):
        request = json.loads(body)
        self.sent.append((url, request, headers))
        sid = "sub-" + str(
            next(i for i, pair in enumerate(PAIRS) if pair["intake_url"] == url)
        )
        if request["call"]["tool"] == "battery_submit":
            return 202, {"submission_id": sid, "state": "RECEIVED"}
        return 200, {
            "submission_id": sid,
            "state": self.states[url],
            "evidence": "DEVELOPMENT",
        }


@pytest.fixture
def wire(monkeypatch):
    value = Wire()
    monkeypatch.setattr(rs, "_signed", value.sign)
    monkeypatch.setattr(rs, "_status_read_signed", value.sign)
    monkeypatch.setattr(
        intake_client,
        "submission_message",
        lambda facts, strategy, digest: json.dumps(
            {"call": {"tool": "battery_submit"}, "strategy": strategy, "digest": digest}
        ).encode(),
    )
    monkeypatch.setattr(
        intake_client,
        "status_message",
        lambda facts, sid: json.dumps(
            {"call": {"tool": "battery_status"}, "submission_id": sid}
        ).encode(),
    )
    original_wait = rs.submit_and_wait
    monkeypatch.setattr(
        rs,
        "submit_and_wait",
        lambda *args, **kwargs: original_wait(*args, wait_s=0, **kwargs),
    )
    original_submit = campaign.submit_through_intake
    monkeypatch.setattr(
        campaign,
        "submit_through_intake",
        lambda *args, **kwargs: original_submit(
            *args, read=value.read, post=value.post, **kwargs
        ),
    )
    return value


def prepared(root):
    root.chmod(0o700)
    return SimpleNamespace(
        ledger=SimpleNamespace(root=root),
        agent="none",
        args=SimpleNamespace(
            intakes={CHALLENGE: PAIRS[0]["intake_url"]},
            intake_targets={CHALLENGE: PAIRS},
            receivers={},
            validators={},
        ),
        manifest={"contract_digest": DIGEST},
        sdk=SimpleNamespace(connection=SimpleNamespace(miner_key="fixture-signer")),
    )


RECORD = {"strategy": {"backbone": "knn"}, "contract_digest": DIGEST}


def test_same_model_is_sent_to_each_receiver_once_and_reordering_reuses_both_journals(
    tmp_path, wire
):
    context = prepared(tmp_path)
    feedback = asyncio.run(campaign.evaluate_candidate(context, 1, RECORD))
    assert feedback["schema"] == multi_intake.SCHEMA
    assert feedback["outcome"] == {"state": "MULTI_VALIDATOR"}
    assert [row["state"] for row in feedback["validators"]] == ["SCORED", "SCORED"]
    submitted = [
        (url, body, headers)
        for url, body, headers in wire.sent
        if body["call"]["tool"] == "battery_submit"
    ]
    assert len(submitted) == 2
    for url, body, headers in submitted:
        pair = next(pair for pair in PAIRS if pair["intake_url"] == url)
        assert headers["fixture_receiver"] == pair["receiver_hotkey"]
        assert body["strategy"] == RECORD["strategy"] and body["digest"] == DIGEST
        assert rs._record_path(targets.journal(tmp_path, pair), 1).is_file()
    context.args.intake_targets[CHALLENGE] = list(reversed(PAIRS))
    again = asyncio.run(campaign.evaluate_candidate(context, 1, RECORD))
    assert {row["receiver_hotkey"] for row in again["validators"]} == {
        p["receiver_hotkey"] for p in PAIRS
    }
    assert len(wire.sent) == 4  # Cached verdicts: neither submits nor polls again.
    assert not feedback["official_eligible"] and not feedback["reward"]


@pytest.mark.parametrize(
    "problem,code,state",
    [
        ("bad_receiver", "intake_receiver_mismatch", "REFUSED"),
        ("unreachable", "intake_unreachable", "FAILED_INFRA"),
    ],
)
def test_one_bad_validator_does_not_prevent_the_other_and_nothing_is_signed_to_a_wrong_receiver(
    tmp_path, wire, problem, code, state
):
    getattr(wire, problem).add(PAIRS[0]["intake_url"])
    feedback = asyncio.run(campaign.evaluate_candidate(prepared(tmp_path), 1, RECORD))
    first, second = feedback["validators"]
    assert first["code"] == code and first["state"] == state
    assert second["state"] == "SCORED"
    assert all(url == PAIRS[1]["intake_url"] for url, _, _ in wire.sent)
    assert all(receiver == PAIRS[1]["receiver_hotkey"] for receiver, _ in wire.signed)
    projected = projection._multi_validator_outcome(
        1, tmp_path / "epoch-1" / multi_intake.STATUS_NAME
    )
    assert [row["state"] for row in projected["validators"]] == [state, "SCORED"]
    assert "private exception" not in json.dumps(projected)


def test_queued_target_keeps_the_candidate_and_the_other_verdict_is_visible(
    tmp_path, wire
):
    wire.states[PAIRS[0]["intake_url"]] = "ADMITTED"
    with pytest.raises(OperationRefused) as refused:
        asyncio.run(campaign.evaluate_candidate(prepared(tmp_path), 1, RECORD))
    assert refused.value.code == "evaluation_queued"
    shown = projection._multi_validator_outcome(
        1, tmp_path / "epoch-1" / multi_intake.STATUS_NAME
    )
    assert [row["state"] for row in shown["validators"]] == ["QUEUED", "SCORED"]
    wire.states[PAIRS[0]["intake_url"]] = "SCORED"
    finished = asyncio.run(campaign.evaluate_candidate(prepared(tmp_path), 1, RECORD))
    assert all(row["state"] == "SCORED" for row in finished["validators"])
    assert (
        sum(body["call"]["tool"] == "battery_submit" for _, body, _ in wire.sent) == 2
    )


def test_projection_uses_allow_list_and_refuses_result_identity_drift(tmp_path, wire):
    asyncio.run(campaign.evaluate_candidate(prepared(tmp_path), 1, RECORD))
    path = multi_intake._result_path(tmp_path, PAIRS[0], 1)
    document = json.loads(path.read_bytes())
    document["outcome"]["private_seed"] = "fixture-protected-canary"
    path.write_text(json.dumps(document), encoding="utf-8")
    status = tmp_path / "epoch-1" / multi_intake.STATUS_NAME
    assert "fixture-protected-canary" not in json.dumps(
        projection._multi_validator_outcome(1, status)
    )
    document["epoch"] = 99
    path.write_text(json.dumps(document), encoding="utf-8")
    assert projection._multi_validator_outcome(1, status) is None
