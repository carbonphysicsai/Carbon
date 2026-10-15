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


def test_one_journal_directory_failure_does_not_suppress_its_peer(
    tmp_path, wire, monkeypatch
):
    from pathlib import Path

    blocked = targets.journal(tmp_path, PAIRS[0])
    mkdir = Path.mkdir

    def refuse_one_directory(path, *args, **kwargs):
        if path == blocked:
            raise PermissionError("fixture private filesystem detail")
        return mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", refuse_one_directory)
    context = prepared(tmp_path)
    feedback = asyncio.run(campaign.evaluate_candidate(context, 1, RECORD))
    first, second = feedback["validators"]
    assert (
        first["state"] == "FAILED_INFRA" and first["code"] == "evaluation_failed_infra"
    )
    assert second["state"] == "SCORED"
    assert all(url == PAIRS[1]["intake_url"] for url, _, _ in wire.sent)
    assert "private filesystem detail" not in json.dumps(feedback)
    # Recovery attempts only the previously failed peer; the other verdict is cached.
    sent = len(wire.sent)
    monkeypatch.setattr(Path, "mkdir", mkdir)
    again = asyncio.run(campaign.evaluate_candidate(context, 1, RECORD))
    assert [row["state"] for row in again["validators"]] == ["SCORED", "SCORED"]
    assert len(wire.sent) > sent
    assert all(url == PAIRS[0]["intake_url"] for url, _, _ in wire.sent[sent:])


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


def test_review_writes_every_published_validator_and_reuses_legacy_primary_fields(
    tmp_path, monkeypatch
):
    from test_miner_launchpad_environment_setup import Checks, Onboarding, completed

    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    environment = setup.EnvironmentSetup(root, onboarding=Onboarding(), checks=Checks())
    completed(tmp_path, environment)
    entry = {**PAIRS[0], "validators": list(PAIRS)}
    monkeypatch.setattr(
        setup,
        "published_endpoints",
        lambda: {"endpoints": {CHALLENGE: entry}, "problem": None},
    )
    environment.review({"confirm": True})
    cfg = runner.validated_profile(json.loads(environment.profile_path.read_bytes()))
    assert cfg["intake_targets"][CHALLENGE] == PAIRS
    assert cfg["intakes"][CHALLENGE] == PAIRS[0]["intake_url"]
    assert cfg["receivers"][CHALLENGE] == PAIRS[0]["receiver_hotkey"]
    assert (
        environment._evaluation(environment._record())["challenges"][0]["validators"]
        == PAIRS
    )


def test_review_checks_each_own_receiver_and_preserves_the_list_for_reinstall(
    tmp_path, monkeypatch
):
    from test_miner_launchpad_environment_setup import Checks, Onboarding, completed

    calls = []

    def read(self, url, campaign=None):
        assert campaign.intake_check is not None
        calls.append(url)
        return {
            "receiver": next(
                pair["receiver_hotkey"] for pair in PAIRS if pair["intake_url"] == url
            )
        }

    monkeypatch.setattr(Checks, "intake", read, raising=False)
    monkeypatch.setattr(
        setup, "published_endpoints", lambda: {"endpoints": {}, "problem": None}
    )
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    environment = setup.EnvironmentSetup(root, onboarding=Onboarding(), checks=Checks())
    completed(tmp_path, environment)
    environment.review({"confirm": True, "intake_targets": {CHALLENGE: PAIRS}})
    assert calls == [pair["intake_url"] for pair in PAIRS]
    assert environment._own_target_lists(environment._record()) == {CHALLENGE: PAIRS}
    environment.review(
        {
            "confirm": True,
            "intakes": {CHALLENGE: PAIRS[0]["intake_url"]},
            "receiver_hotkey": PAIRS[0]["receiver_hotkey"],
        }
    )
    assert "intake_targets" not in json.loads(environment.profile_path.read_bytes())


def test_observe_reads_only_due_targets_without_signing_another_submission(
    tmp_path, wire, monkeypatch
):
    wire.states[PAIRS[0]["intake_url"]] = "ADMITTED"
    context = prepared(tmp_path)
    with pytest.raises(OperationRefused):
        asyncio.run(campaign.evaluate_candidate(context, 1, RECORD))
    reads, connects = [], []
    answer = [None]

    def read_once(url, signer, **kwargs):
        reads.append((url, kwargs))
        assert kwargs["receiver"] == PAIRS[0]["receiver_hotkey"]
        assert kwargs["once_per_tempo"] is True
        return answer[0]

    monkeypatch.setattr(rs, "read_status_once", read_once)

    def connect():
        connects.append(True)
        return "fixture-read-only-signer"

    sent = list(wire.sent)
    assert (
        multi_intake.queued(
            context.args, tmp_path, 1, connect, PAIRS, now=1000, floor=100
        )
        is None
    )
    assert (
        multi_intake.queued(
            context.args, tmp_path, 1, connect, PAIRS, now=1050, floor=100
        )
        is None
    )
    assert len(reads) == len(connects) == 1
    answer[0] = (
        200,
        {"state": "SCORED", "submission_id": "sub-0", "evidence": "DEVELOPMENT"},
        "sub-0",
    )
    finished = multi_intake.queued(
        context.args, tmp_path, 1, connect, PAIRS, now=1150, floor=100
    )
    assert all(row["state"] == "SCORED" for row in finished["validators"])
    assert wire.sent == sent


def test_malformed_cached_result_does_not_block_another_validator(tmp_path, wire):
    context = prepared(tmp_path)
    asyncio.run(campaign.evaluate_candidate(context, 1, RECORD))
    path = multi_intake._result_path(tmp_path, PAIRS[0], 1)
    path.write_text(
        json.dumps(
            {
                "schema": "carbon.battery.permitted-feedback.v1",
                "epoch": 1,
                "via": None,
                "outcome": {"state": "SCORED"},
            }
        ),
        encoding="utf-8",
    )
    again = asyncio.run(campaign.evaluate_candidate(context, 1, RECORD))
    assert again["validators"][0]["code"] == "intake_answer_unrecognised"
    assert again["validators"][1]["state"] == "SCORED"


def test_queued_mark_failure_preserves_peer_candidate_floor_and_tempo(
    tmp_path, wire, monkeypatch
):
    for pair in PAIRS:
        wire.states[pair["intake_url"]] = "ADMITTED"
    context = prepared(tmp_path)
    with pytest.raises(OperationRefused, match="evaluation_queued"):
        asyncio.run(campaign.evaluate_candidate(context, 1, RECORD))
    sent = len(wire.sent)
    blocked = targets.journal(tmp_path, PAIRS[0])
    write_mark = rs._write_mark

    def fail_one_mark(root, epoch, value):
        if root == blocked:
            raise OSError("fixture private mark failure")
        return write_mark(root, epoch, value)

    monkeypatch.setattr(rs, "_write_mark", fail_one_mark)
    wire.states[PAIRS[1]["intake_url"]] = "SCORED"
    connect = lambda: "fixture-read-only-signer"
    assert (
        multi_intake.queued(
            context.args,
            tmp_path,
            1,
            connect,
            PAIRS,
            now=1000,
            floor=100,
            read=wire.read,
            post=wire.post,
        )
        is None
    )
    shown = projection._multi_validator_outcome(
        1, tmp_path / "epoch-1" / multi_intake.STATUS_NAME
    )
    assert [row["state"] for row in shown["validators"]] == ["QUEUED", "SCORED"]
    assert shown["validators"][0]["code"] == "evaluation_failed_infra"
    assert "private mark failure" not in json.dumps(shown)
    assert [url for url, _, _ in wire.sent[sent:]] == [PAIRS[1]["intake_url"]]
    monkeypatch.setattr(rs, "_write_mark", write_mark)
    assert (
        multi_intake.queued(
            context.args,
            tmp_path,
            1,
            connect,
            PAIRS,
            now=1050,
            floor=100,
            read=wire.read,
            post=wire.post,
        )
        is None
    )
    after_read = len(wire.sent)
    for at in (1060, 1200):
        assert (
            multi_intake.queued(
                context.args,
                tmp_path,
                1,
                connect,
                PAIRS,
                now=at,
                floor=100,
                read=wire.read,
                post=wire.post,
            )
            is None
        )
        assert len(wire.sent) == after_read
    read = wire.read

    def next_tempo(url):
        facts = read(url)
        facts["snapshot"]["finalized_block"] += rs.TEMPO_BLOCKS
        return facts

    wire.states[PAIRS[0]["intake_url"]] = "SCORED"
    done = multi_intake.queued(
        context.args,
        tmp_path,
        1,
        connect,
        PAIRS,
        now=1340,
        floor=100,
        read=next_tempo,
        post=wire.post,
    )
    assert [row["state"] for row in done["validators"]] == ["SCORED", "SCORED"]
    assert all(
        body["call"]["tool"] == "battery_status" for _, body, _ in wire.sent[sent:]
    )
    assert all(url == PAIRS[0]["intake_url"] for url, _, _ in wire.sent[sent + 1 :])


def test_a_finished_peer_is_visible_while_another_trip_is_waiting(
    tmp_path, monkeypatch
):
    async def scenario():
        release = asyncio.Event()
        finished = asyncio.Event()

        async def trip(
            prepared, epoch, record, url, *, submission_root=None, stale_recommit=None
        ):
            assert stale_recommit is None
            if url == PAIRS[0]["intake_url"]:
                await release.wait()
            else:
                finished.set()
            return campaign.intake_feedback(
                epoch,
                url,
                200,
                {
                    "state": "SCORED",
                    "submission_id": "fixture-sub",
                    "evidence": "DEVELOPMENT",
                },
                "fixture-sub",
            )

        monkeypatch.setattr(campaign, "_evaluate_through_intake", trip)
        task = asyncio.create_task(
            campaign.evaluate_candidate(prepared(tmp_path), 1, RECORD)
        )
        await asyncio.wait_for(finished.wait(), 5)
        await asyncio.sleep(0)
        shown = projection._multi_validator_outcome(
            1, tmp_path / "epoch-1" / multi_intake.STATUS_NAME
        )
        assert [row["state"] for row in shown["validators"]] == ["PENDING", "SCORED"]
        assert not task.done()
        release.set()
        await asyncio.wait_for(task, 5)

    asyncio.run(scenario())


def test_one_commitment_gate_precedes_every_target_send(tmp_path, wire, monkeypatch):
    gates = []

    async def committed(
        gate, root, epoch, record, manifest, *, request, recommit=False
    ):
        gates.append((record["strategy"], manifest["contract_digest"]))
        assert request is False and recommit is False

    original_sign = wire.sign

    def sign(signer, facts, body):
        assert len(gates) == 1
        return original_sign(signer, facts, body)

    monkeypatch.setattr(campaign, "_committed", committed)
    monkeypatch.setattr(rs, "_signed", sign)
    context = prepared(tmp_path)
    context.args.commitment_gate = object()
    asyncio.run(campaign.evaluate_candidate(context, 1, RECORD))
    assert gates == [(RECORD["strategy"], DIGEST)]


def _paired_stale_fixture(
    tmp_path,
    wire,
    monkeypatch,
    indexes,
    *,
    repeated=False,
    confirm=True,
    agent="graphite",
    state="SCORED",
):
    """Real gate decision/client flow; confirmation and remote replies are fixtures."""
    import threading
    from collections import Counter

    from carbon.chain import commitment_poster as cp
    from carbon.reconstruction.capability_registry import contract_digest

    context = prepared(tmp_path)
    context.agent = agent
    context.sdk.connection.miner_key = SimpleNamespace(ss58_address="fixture-miner")
    record = {
        "strategy": {
            "schema_version": "1.0",
            "challenge_id": CHALLENGE,
            "backbone": "knn",
            "parameters": {"neighbours": 6},
        },
        "contract_digest": contract_digest(CHALLENGE),
    }
    context.manifest["contract_digest"] = record["contract_digest"]
    expected = campaign.frozen_commitment(record, context.manifest)
    stale_urls = {PAIRS[index]["intake_url"] for index in indexes}
    first_stale, ready = set(), threading.Event()
    calls, submits = Counter(), Counter()

    class Gate(cp.CommitmentGate):
        def __init__(self):
            self.checked, self.requests, self.refreshed = [], [], False

        def check(self, digest):
            assert digest == expected
            self.checked.append(digest)

        def request(self, root, digest, *, epoch=None, recommit=False, by="agent"):
            assert root == tmp_path and digest == expected and epoch == 1
            assert recommit and by == "agent"
            assert ready.wait(
                5
            ), "all first stale trips must finish before confirmation"
            self.requests.append((digest, epoch, recommit))
            self.refreshed = confirm
            return {"code": cp.PostCode.COMMITTED if confirm else cp.PostCode.FAILED}

    gate = context.args.commitment_gate = Gate()
    sid = intake_client.submission_id(
        context.sdk.connection.miner_key.ss58_address,
        record["strategy"],
        record["contract_digest"],
    )
    admitted = set()
    post = wire.post

    def reply(url, body, headers):
        status, answer = post(url, body, headers)
        answer = {**answer, "submission_id": sid}
        tool = json.loads(body)["call"]["tool"]
        if tool == "battery_submit":
            submits[url] += 1
            if submits[url] > 1 and gate.refreshed:
                admitted.add(url)
        elif url in stale_urls:
            if repeated or url not in admitted:
                answer = {
                    "submission_id": sid,
                    "state": "REFUSED",
                    "failure": {"code": cp.STALE},
                }
            else:
                answer["state"] = state
        return status, answer

    monkeypatch.setattr(wire, "post", reply)
    submit = campaign.submit_through_intake

    def checked_submit(url, *args, **kwargs):
        calls[url] += 1
        assert kwargs["strategy"] == record["strategy"]
        assert kwargs["contract_digest"] == record["contract_digest"]
        result = submit(url, *args, **kwargs)
        if calls[url] == 1 and result[1].get("state") == "REFUSED":
            first_stale.add(url)
            if stale_urls <= first_stale:
                ready.set()
        return result

    monkeypatch.setattr(campaign, "submit_through_intake", checked_submit)
    return context, record, expected, gate, calls, submits, sid


@pytest.mark.parametrize("indexes", [[0], [0, 1]])
@pytest.mark.parametrize("state", ["SCORED", "ADMITTED"])
def test_graphite_stale_targets_share_one_confirmed_same_digest_recommit(
    tmp_path, wire, monkeypatch, indexes, state
):
    context, record, expected, gate, calls, submits, sid = _paired_stale_fixture(
        tmp_path, wire, monkeypatch, indexes, state=state
    )
    if state == "ADMITTED":
        with pytest.raises(OperationRefused, match="evaluation_queued"):
            asyncio.run(campaign.evaluate_candidate(context, 1, record))
        shown = projection._multi_validator_outcome(
            1, tmp_path / "epoch-1" / multi_intake.STATUS_NAME
        )
    else:
        shown = asyncio.run(campaign.evaluate_candidate(context, 1, record))
    assert gate.checked == [expected]
    assert gate.requests == [(expected, 1, True)]
    for index, pair in enumerate(PAIRS):
        url = pair["intake_url"]
        assert calls[url] == (2 if index in indexes else 1)
        assert submits[url] <= 4  # Existing client's same-id RECEIVE_AGAIN resends.
        assert (
            json.loads(
                rs._record_path(targets.journal(tmp_path, pair), 1).read_bytes()
            )["submission_id"]
            == sid
        )
        assert shown["validators"][index]["state"] == (
            "QUEUED" if state == "ADMITTED" and index in indexes else "SCORED"
        )


def test_repeated_stale_is_bounded_and_never_requests_another_common_recommit(
    tmp_path, wire, monkeypatch
):
    from carbon.chain.commitment_poster import STALE

    context, record, expected, gate, calls, submits, _sid = _paired_stale_fixture(
        tmp_path, wire, monkeypatch, [0, 1], repeated=True
    )
    with pytest.raises(OperationRefused, match=STALE):
        asyncio.run(campaign.evaluate_candidate(context, 1, record))
    assert gate.requests == [(expected, 1, True)]
    assert all(calls[pair["intake_url"]] == 2 for pair in PAIRS)
    assert all(submits[pair["intake_url"]] <= 4 for pair in PAIRS)


def test_own_selection_stale_never_requests_a_commitment(tmp_path, wire, monkeypatch):
    from carbon.chain.commitment_poster import STALE

    context, record, expected, gate, calls, _submits, _sid = _paired_stale_fixture(
        tmp_path, wire, monkeypatch, [0], agent="none"
    )
    result = asyncio.run(campaign.evaluate_candidate(context, 1, record))
    assert gate.requests == [] and gate.checked == [expected]
    assert result["validators"][0]["code"] == STALE
    assert result["validators"][1]["state"] == "SCORED"
    assert all(calls[pair["intake_url"]] == 1 for pair in PAIRS)


def test_denied_common_recommit_does_not_resubmit_either_target(
    tmp_path, wire, monkeypatch
):
    context, record, expected, gate, calls, _submits, _sid = _paired_stale_fixture(
        tmp_path, wire, monkeypatch, [0, 1], confirm=False
    )
    with pytest.raises(OperationRefused):
        asyncio.run(campaign.evaluate_candidate(context, 1, record))
    assert gate.requests == [(expected, 1, True)]
    assert all(calls[pair["intake_url"]] == 1 for pair in PAIRS)
    assert not gate.refreshed


def test_unknown_challenge_metadata_cannot_relabel_a_cached_validator_result(
    tmp_path, wire
):
    asyncio.run(campaign.evaluate_candidate(prepared(tmp_path), 1, RECORD))
    path = tmp_path / "epoch-1" / multi_intake.STATUS_NAME
    doc = json.loads(path.read_bytes())
    doc["challenge"] = {"id": "fixture-unregistered-challenge", "version": "1.0"}
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert projection._multi_validator_outcome(1, path) is None
