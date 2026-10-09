"""The canary runner (CANARY-01 S1): config, variants, cursor, stages, reports.

Fixture-level engineering evidence only. A fake Launchpad stands in for the
canary's own install (its campaign host, supervisor and signer), driven both
directly and through the real MCP SDK client against an in-process server;
the intake read, the clock and the ping's HTTP are stubs. No chain, signer,
validator, container, network or spend is reached, and nothing here is
scientific, security or economic evidence.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import pytest
from pydantic import BaseModel

from carbon.challenge_validator.canary import CANARY_HOTKEYS
from scripts.dev.canary import config as canary_config
from scripts.dev.canary import report, runner
from scripts.dev.canary import variants as variant_list

CANARY = CANARY_HOTKEYS[0]
#: A valid ss58 that is not a registered canary (the intake tests' receiver
#: shape; any listed-or-not check is by the registry alone).
OTHER = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
RECEIVER = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
GENESIS = "0x" + "ab" * 32
FAKE_DIGEST = "sha256:" + "c" * 64
CHALLENGE = {"id": "battery-fastcharge-ageing-development-v1", "version": "1.0"}
PING = "https://hc-ping.example/canary-check-uuid"


# --- fixtures --------------------------------------------------------------------


def owner_only(path, text):
    path.write_text(text)
    os.chmod(path, 0o600)
    return path


def fake_variants(path, count=3):
    """A small structurally valid list; compile is stubbed in these tests."""
    entries = [
        {
            "index": i,
            "strategy": variant_list.strategy(i + 1, 1.0),
            "strategy_hash": "sha256:" + f"{i:064x}",
        }
        for i in range(count)
    ]
    document = {
        "schema": variant_list.SCHEMA,
        "challenge": CHALLENGE,
        "contract_digest": FAKE_DIGEST,
        "method": "knn",
        "grid": {"neighbours": [1, count], "train_fraction": [1.0]},
        "variants": entries,
    }
    path.write_bytes(variant_list.render(document))
    return path


def config_document(tmp_path, **changes):
    document = {
        "schema": canary_config.SCHEMA,
        "hotkey": CANARY,
        "launchpad": {
            "state_dir": str(tmp_path / "state"),
            "python": "/usr/bin/python3",
            "checkout": str(tmp_path / "checkout"),
        },
        "challenge": dict(CHALLENGE),
        "intake": {"url": "http://127.0.0.1:8790", "receiver": RECEIVER},
        "variants": str(tmp_path / "variants.json"),
        "cursor": str(tmp_path / "run" / "cursor.json"),
        "journal": str(tmp_path / "run" / "journal.jsonl"),
        "deadlines": {stage: None for stage in canary_config.STAGES},
        "poll": {"interval_seconds": 10, "max_wait_seconds": 3600},
        "healthcheck_env_file": str(tmp_path / "hc.env"),
    }
    document.update(changes)
    return document


def write_config(tmp_path, **changes):
    fake_variants(tmp_path / "variants.json")
    owner_only(tmp_path / "hc.env", "# owner only\nHC_CANARY=" + PING + "\n")
    return owner_only(
        tmp_path / "canary.json", json.dumps(config_document(tmp_path, **changes))
    )


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.0

    def time(self):
        return self.now

    async def sleep(self, seconds):
        self.now += seconds


class Facts:
    """The intake's public facts; `start` is the hotkey window's first block."""

    def __init__(self, start=1000):
        self.start = start
        self.reads = 0
        self.raise_error = None

    def __call__(self, url):
        self.reads += 1
        if self.raise_error is not None:
            raise self.raise_error
        return {
            "schema": "carbon.battery.intake-public.v1",
            "network": "testnet",
            "genesis": GENESIS,
            "netuid": 567,
            "challenge": dict(CHALLENGE),
            "receiver": RECEIVER,
            "snapshot": {"id": "s", "finalized_block": self.start + 5},
            "submission_rule": {
                "per_hotkey": 1,
                "rotation": 1080,
                "current_window": {
                    "start_block": self.start,
                    "end_block": self.start + 359,
                },
            },
            "commitment": "required: read at admission",
        }


class FakeLaunchpad:
    """The canary's Launchpad as its MCP door answers: every operation runs
    in the background for `flight` observes, and observe is the readback.

    `commit`: "COMMITTED" or a NOT_COMMITTED closed code. `submits`: per
    attempt, QUEUED, UNAVAILABLE, REFUSED or VERDICT (the last repeats)."""

    def __init__(self, *, hotkey=CANARY, commit="COMMITTED", submits=("VERDICT",)):
        self.hotkey = hotkey
        self.commit_outcome = commit
        self.submits = list(submits)
        self.submitted = 0
        self.verdict_state = "SCORED"
        self.flight = 2
        self.busy_once = set()
        self.calls = []
        self.keys = {}
        self.campaigns = {}

    def handle(self, tool, arguments):
        self.calls.append((tool, dict(arguments)))
        operation = tool.removeprefix("carbon_")
        if operation in self.busy_once:
            self.busy_once.discard(operation)
            raise runner.Refused("campaign_busy")
        key = arguments.get("idempotency_key")
        if key is not None and key in self.keys:
            return self.view(self.keys[key])
        answer = getattr(self, "op_" + operation)(arguments)
        if key is not None:
            self.keys[key] = answer["id"]
        return answer

    def view(self, identity):
        c = self.campaigns[identity]
        return {
            "id": identity,
            "state": c["state"],
            "in_flight": (
                None
                if c["work"] is None
                else {"operation": c["work"], "state": "RUNNING"}
            ),
            "completed_experiments": c["experiments"],
            "candidate_freezes": c["freezes"],
            "commitment": c["commitment"],
            "last_refusal": c["refusal"],
            "final_results": c["results"],
            "journey": {"submitted_epochs": []},
        }

    def start(self, identity, work, effect):
        c = self.campaigns[identity]
        c.update(work=work, left=self.flight, effect=effect, refusal=None)

    def op_setup_status(self, arguments):
        return {"registered_hotkey": self.hotkey, "id": None}

    def op_launch(self, arguments):
        assert arguments["agent"] == "none"
        identity = f"camp-{len(self.campaigns) + 1}"
        self.campaigns[identity] = {
            "state": "QUEUED",
            "work": None,
            "experiments": 0,
            "freezes": [],
            "commitment": None,
            "refusal": None,
            "results": [],
            "submits": 0,
            "strategy": None,
        }
        self.start(identity, "run", lambda c: c.update(state="READY"))
        return self.view(identity)

    def op_observe(self, arguments):
        c = self.campaigns[arguments["campaign"]]
        if c["work"] is not None:
            c["left"] -= 1
            if c["left"] <= 0:
                work, effect = c["work"], c["effect"]
                c["work"] = None
                effect(c)
                assert work
        return self.view(arguments["campaign"])

    def op_resume(self, arguments):
        c = self.campaigns[arguments["campaign"]]
        c["state"] = "READY"
        return self.view(arguments["campaign"])

    def op_practice(self, arguments):
        c = self.campaigns[arguments["campaign"]]
        c["strategy"] = arguments["strategy"]
        self.start(
            arguments["campaign"],
            "practice",
            lambda c: c.update(experiments=c["experiments"] + 1),
        )
        return self.view(arguments["campaign"])

    def op_freeze_candidate(self, arguments):
        assert (
            arguments["strategy"] == self.campaigns[arguments["campaign"]]["strategy"]
        )
        self.start(
            arguments["campaign"],
            "freeze_candidate",
            lambda c: c["freezes"].append(
                {"epoch": 1, "strategy": arguments["strategy"]}
            ),
        )
        return self.view(arguments["campaign"])

    def op_commit(self, arguments):
        c = self.campaigns[arguments["campaign"]]
        c["commitment"] = {
            "state": "CONFIRM_COMMITMENT",
            "human_action_required": "confirm_commitment",
            "on_chain": None,
            "code": None,
        }
        if self.commit_outcome == "COMMITTED":
            done = {
                "state": "COMMITTED",
                "human_action_required": None,
                "on_chain": {"digest": "sha256:" + "d" * 64, "block": 8178423},
                "code": None,
            }
        else:
            done = {
                "state": "NOT_COMMITTED",
                "human_action_required": None,
                "on_chain": None,
                "code": self.commit_outcome,
            }
        self.start(arguments["campaign"], "commit", lambda c: c.update(commitment=done))
        return self.view(arguments["campaign"])

    def op_submit(self, arguments):
        c = self.campaigns[arguments["campaign"]]
        outcome = self.submits[min(self.submitted, len(self.submits) - 1)]
        self.submitted += 1
        c["submits"] += 1

        def effect(c):
            if outcome == "VERDICT":
                c["results"] = [
                    {
                        "epoch": 1,
                        "status": "VALIDATOR_OUTCOME",
                        "result": {
                            "state": self.verdict_state,
                            "submission_id": "bsub-" + "e" * 24,
                            "sealed": True,
                        },
                    }
                ]
                return
            code, kind = {
                "QUEUED": ("evaluation_queued", "QUEUED"),
                "UNAVAILABLE": ("snapshot_unavailable", "UNAVAILABLE"),
                "REFUSED": ("hotkey_window_used", "REFUSED"),
            }[outcome]
            c["refusal"] = {"code": code, "operation": "submit", "intake_outcome": kind}

        self.start(arguments["campaign"], "submit", effect)
        return self.view(arguments["campaign"])

    def tools(self):
        return [tool for tool, _ in self.calls]


class FakeDoor:
    def __init__(self, launchpad):
        self.launchpad = launchpad

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def call(self, tool, arguments):
        return self.launchpad.handle(tool, arguments)


class Opener:
    """Stub `urlopen`: records each request; answers `statuses` in turn."""

    def __init__(self, *statuses):
        self.statuses = list(statuses) or [200]
        self.requests = []

    def __call__(self, request, timeout):
        import urllib.error

        self.requests.append(
            (request.full_url, request.get_method(), request.data.decode(), timeout)
        )
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        if status >= 400:
            raise urllib.error.HTTPError(request.full_url, status, "x", {}, None)

        class Answer:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        answer = Answer()
        answer.status = status
        return answer


class Harness:
    def __init__(self, tmp_path, launchpad=None, **changes):
        self.path = write_config(tmp_path, **changes)
        self.cfg = canary_config.load(self.path)
        self.launchpad = launchpad or FakeLaunchpad()
        self.facts = Facts()
        self.clock = Clock()
        self.opener = Opener()

    def runner(self, door=None):
        return runner.Runner(
            self.cfg,
            door=door or (lambda: FakeDoor(self.launchpad)),
            read_intake=self.facts,
            clock=self.clock.time,
            sleep=self.clock.sleep,
            opener=self.opener,
            ping_sleep=lambda seconds: None,
            check_entry=lambda document, index: document["variants"][index],
            contract_digest=lambda: FAKE_DIGEST,
            expected_submission_id=lambda hotkey, strategy, digest: "bsub-" + "e" * 24,
            testnet=lambda: ("testnet", GENESIS, 567),
        )

    def once(self, door=None):
        return asyncio.run(self.runner(door).once())

    def cursor(self):
        return json.loads(self.cfg.cursor.read_text())

    def journal(self):
        return [json.loads(line) for line in self.cfg.journal.read_text().splitlines()]


# --- config ----------------------------------------------------------------------


def test_a_valid_config_loads_with_every_deadline_null(tmp_path):
    cfg = canary_config.load(write_config(tmp_path))
    assert cfg.hotkey == CANARY
    assert cfg.deadlines == {stage: None for stage in canary_config.STAGES}
    assert cfg.intake_url == "http://127.0.0.1:8790"
    assert (cfg.poll_interval, cfg.max_wait) == (10.0, 3600.0)


@pytest.mark.parametrize(
    "changes, code",
    [
        ({"extra": 1}, "config_closed_object_required"),
        ({"schema": "carbon.canary.config.v0"}, "config_schema_unknown"),
        ({"hotkey": "not-an-address"}, "config_ss58_required"),
        ({"hotkey": OTHER}, "hotkey_not_registered_canary"),
        ({"cursor": "relative/cursor.json"}, "config_absolute_path_required"),
        (
            {"intake": {"url": "http://192.0.2.7:8790", "receiver": RECEIVER}},
            "config_intake_url_invalid",
        ),
        (
            {"intake": {"url": "https://u:p@door.example", "receiver": RECEIVER}},
            "config_intake_url_invalid",
        ),
        ({"deadlines": {"door": None}}, "config_closed_object_required"),
        (
            {"deadlines": {**{s: None for s in canary_config.STAGES}, "commit": -1}},
            "config_seconds_out_of_bounds",
        ),
        (
            {"deadlines": {**{s: None for s in canary_config.STAGES}, "commit": True}},
            "config_seconds_out_of_bounds",
        ),
        (
            {"poll": {"interval_seconds": 60, "max_wait_seconds": 30}},
            "config_seconds_out_of_bounds",
        ),
    ],
)
def test_the_config_is_strict(tmp_path, changes, code):
    with pytest.raises(canary_config.ConfigRefused) as refused:
        canary_config.load(write_config(tmp_path, **changes))
    assert refused.value.code == code


def test_the_config_file_must_be_owner_only_and_not_a_link(tmp_path):
    path = write_config(tmp_path)
    os.chmod(path, 0o640)
    with pytest.raises(canary_config.ConfigRefused) as refused:
        canary_config.load(path)
    assert refused.value.code == "config_file_unusable"
    os.chmod(path, 0o600)
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(canary_config.ConfigRefused):
        canary_config.load(link)


def test_a_non_canary_hotkey_is_refused_before_anything_runs(tmp_path):
    launchpad, facts = FakeLaunchpad(), Facts()
    path = write_config(tmp_path, hotkey=OTHER)
    summary, code = runner.run(
        path, door=lambda: FakeDoor(launchpad), read_intake=facts
    )
    assert (summary["result"], summary["code"], code) == (
        "REFUSED",
        "hotkey_not_registered_canary",
        runner.EXIT_REFUSED,
    )
    assert launchpad.calls == [] and facts.reads == 0
    assert not (tmp_path / "run").exists()


def test_a_ping_file_that_is_not_owner_only_is_refused(tmp_path):
    h = Harness(tmp_path)
    os.chmod(tmp_path / "hc.env", 0o644)
    with pytest.raises(canary_config.ConfigRefused) as refused:
        h.once()
    assert refused.value.code == "healthcheck_env_unusable"
    assert h.facts.reads == 0 and h.launchpad.calls == []


# --- the variant list ------------------------------------------------------------


def test_the_committed_variant_list_is_the_registered_grid_all_distinct():
    document, _ = variant_list.load(variant_list.LIST_PATH)
    assert [e["strategy"] for e in document["variants"]] == variant_list.strategies()
    assert len(document["variants"]) == 320
    hashes = [e["strategy_hash"] for e in document["variants"]]
    assert len(set(hashes)) == len(hashes)
    assert variant_list.within_registry()
    assert variant_list.registry_bounds() == {
        "neighbours": (1, 64),
        "train_fraction": (0.1, 1.0),
    }
    assert document["contract_digest"] == variant_list.contract_digest()
    assert document["challenge"] == CHALLENGE
    assert variant_list.LIST_PATH.read_bytes() == variant_list.render(document)


def test_committed_variants_compile_to_their_recorded_hash():
    """A deterministic sample: both ends of the grid and of each fraction's
    row. Generation compiled every entry (`variants check` compiles all)."""
    from carbon.battery.contracts import battery_contracts

    document, _ = variant_list.load(variant_list.LIST_PATH)
    contracts = battery_contracts()
    for index in (0, 63, 64, 191, 319):
        entry = document["variants"][index]
        assert variant_list.compiled_hash(entry["strategy"], contracts) == (
            entry["strategy_hash"]
        )


def test_a_list_with_a_repeated_hash_is_refused(tmp_path):
    path = fake_variants(tmp_path / "v.json")
    document = json.loads(path.read_text())
    document["variants"][1]["strategy_hash"] = document["variants"][0]["strategy_hash"]
    with pytest.raises(variant_list.VariantRefused) as refused:
        variant_list.parse(variant_list.render(document))
    assert refused.value.code == "variant_hash_repeated"


def test_a_stale_list_is_refused_before_anything_is_read(tmp_path):
    h = Harness(tmp_path)
    r = h.runner()
    r.contract_digest = lambda: "sha256:" + "f" * 64
    with pytest.raises(variant_list.VariantRefused) as refused:
        asyncio.run(r.once())
    assert refused.value.code == "variant_list_stale"
    assert h.facts.reads == 0


# --- a cycle ---------------------------------------------------------------------


def test_a_cycle_runs_the_journey_in_order_and_pings_success(tmp_path):
    h = Harness(tmp_path)
    line, code = h.once()
    assert (line["result"], line["failure"], code) == (
        "COMPLETED",
        None,
        runner.EXIT_OK,
    )
    tools = [t for t in h.launchpad.tools() if t != "carbon_observe"]
    assert tools == [
        "carbon_setup_status",
        "carbon_launch",
        "carbon_practice",
        "carbon_freeze_candidate",
        "carbon_commit",
        "carbon_submit",
    ]
    assert line["variant_index"] == 0
    assert line["submission_id"] == "bsub-" + "e" * 24
    assert line["submission_id_matches"] is True
    assert line["verdict"] == {"state": "SCORED", "sealed": True}
    assert line["commit_block"] == 8178423
    assert line["confirm_prompt_seen"] is True
    assert line["closed"] is True and h.cursor()["open"] is None
    assert line["ping"] == {"kind": "success", "delivered": True}
    ((url, method, body, timeout),) = h.opener.requests
    assert (url, method, timeout) == (PING, "POST", report.TIMEOUT_S)
    assert "variant 0" in body


def test_journal_lines_carry_every_stage_timed_and_never_the_ping_url(tmp_path):
    h = Harness(tmp_path, launchpad=FakeLaunchpad(submits=("QUEUED", "VERDICT")))
    h.once()
    (line,) = h.journal()
    assert line["schema"] == report.JOURNAL_SCHEMA
    stages = [s["stage"] for s in line["stages"]]
    assert stages == list(canary_config.STAGES)
    by = {s["stage"]: s for s in line["stages"]}
    for stage in ("door", "window", "commit", "admission", "scoring", "verdict"):
        assert by[stage]["outcome"] == "OK", by[stage]
        assert by[stage]["seconds"] >= 0
        assert by[stage]["deadline_seconds"] is None
    assert by["admission"]["note"] == "the intake holds it (evaluation_queued)"
    assert by["scoring"]["seconds"] > 0
    assert by["weights"]["outcome"] == "NOT_BUILT"
    assert by["weights"]["code"] == "weights_check_not_built"
    assert line["submit_attempts"] == 2
    text = h.cfg.journal.read_text()
    assert PING not in text and "hc-ping" not in text
    assert oct(h.cfg.journal.stat().st_mode & 0o777) == "0o600"
    assert oct(h.cfg.cursor.stat().st_mode & 0o777) == "0o600"


def test_a_verdict_on_the_first_submit_says_scoring_is_not_separable(tmp_path):
    h = Harness(tmp_path)
    line, _ = h.once()
    by = {s["stage"]: s for s in line["stages"]}
    assert by["admission"]["note"] == "first seen with the verdict"
    assert by["scoring"]["note"].startswith("not separable")


def test_the_cursor_never_reuses_a_variant_and_never_wraps(tmp_path):
    h = Harness(tmp_path)
    seen = []
    for window in (1000, 1360, 1720):
        h.facts.start = window
        line, code = h.once()
        assert line["result"] == "COMPLETED", line
        seen.append(line["variant_index"])
    assert seen == [0, 1, 2]
    practised = [
        args["strategy"]["parameters"]["neighbours"]
        for tool, args in h.launchpad.calls
        if tool == "carbon_practice"
    ]
    assert practised == [1, 2, 3]
    h.facts.start = 2080
    line, code = h.once()
    assert line["failure"] == {
        "stage": "cycle",
        "code": "variant_list_exhausted",
        "step": None,
    }
    assert code == runner.EXIT_FAILED and h.cursor()["next_index"] == 3
    assert line["ping"]["kind"] == "fail"
    assert h.opener.requests[-1][0] == PING + "/fail"
    assert "code=variant_list_exhausted" in h.opener.requests[-1][2]


def test_a_refused_submission_closes_its_cycle_and_the_next_takes_a_new_variant(
    tmp_path,
):
    h = Harness(tmp_path, launchpad=FakeLaunchpad(submits=("REFUSED", "VERDICT")))
    line, code = h.once()
    assert line["failure"]["stage"] == "admission"
    assert line["failure"]["code"] == "hotkey_window_used"
    assert line["closed"] is True and code == runner.EXIT_FAILED
    h.facts.start = 1360
    line, _ = h.once()
    assert line["variant_index"] == 1 and line["result"] == "COMPLETED"


def test_a_pending_cycle_resumes_with_the_same_variant_and_campaign(tmp_path):
    h = Harness(
        tmp_path,
        launchpad=FakeLaunchpad(submits=("QUEUED", "QUEUED", "QUEUED", "VERDICT")),
        poll={"interval_seconds": 10, "max_wait_seconds": 60},
    )
    first, code = h.once()
    assert (first["result"], first["pending_stage"], code) == (
        "PENDING",
        "scoring",
        runner.EXIT_OK,
    )
    assert first["ping"] is None and h.opener.requests == []
    assert h.cursor()["open"]["variant_index"] == 0
    second, _ = h.once()
    assert second["result"] == "COMPLETED"
    assert (second["variant_index"], second["campaign"]) == (0, first["campaign"])
    launches = [t for t in h.launchpad.tools() if t == "carbon_launch"]
    assert len(launches) == 1
    keys = [a["idempotency_key"] for t, a in h.launchpad.calls if t == "carbon_submit"]
    assert len(keys) == len(set(keys)) == 4
    assert h.cursor()["next_index"] == 1


def test_an_unavailable_intake_is_a_fail_ping_and_the_cycle_stays_open(tmp_path):
    h = Harness(tmp_path, launchpad=FakeLaunchpad(submits=("UNAVAILABLE", "VERDICT")))
    line, code = h.once()
    assert line["failure"]["code"] == "snapshot_unavailable"
    by = {s["stage"]: s for s in line["stages"]}
    assert by["admission"]["outcome"] == "UNAVAILABLE"
    assert line["closed"] is False and code == runner.EXIT_FAILED
    assert "stage=admission code=snapshot_unavailable" in h.opener.requests[-1][2]
    line, _ = h.once()
    assert (line["result"], line["variant_index"]) == ("COMPLETED", 0)


def test_a_commitment_the_signer_refuses_fails_at_commit_naming_its_code(tmp_path):
    h = Harness(tmp_path, launchpad=FakeLaunchpad(commit="auto_confirm_not_allowed"))
    line, _ = h.once()
    assert line["failure"] == {
        "stage": "commit",
        "code": "auto_confirm_not_allowed",
        "step": "commit",
    }
    url, _, body, _ = h.opener.requests[-1]
    assert url == PING + "/fail"
    assert body.startswith("stage=commit code=auto_confirm_not_allowed")
    assert "carbon_submit" not in h.launchpad.tools()
    # The runner confirms nothing: no tool it calls is a confirmation.
    assert not [t for t in h.launchpad.tools() if "confirm" in t]


def test_null_deadlines_never_alert_however_long_a_stage_takes(tmp_path):
    launchpad = FakeLaunchpad()
    launchpad.flight = 40  # every operation spans 40 polls (400 s)
    h = Harness(tmp_path, launchpad=launchpad)
    line, code = h.once()
    assert (line["result"], line["failure"], code) == (
        "COMPLETED",
        None,
        runner.EXIT_OK,
    )
    assert line["ping"]["kind"] == "success"
    assert not any(s["missed"] for s in line["stages"])


def test_a_set_deadline_that_is_missed_is_a_fail_ping_naming_the_stage(tmp_path):
    deadlines = {stage: None for stage in canary_config.STAGES}
    deadlines["commit"] = 5
    h = Harness(tmp_path, deadlines=deadlines)
    line, code = h.once()
    assert line["result"] == "COMPLETED"
    assert line["failure"] == {
        "stage": "commit",
        "code": "deadline_missed",
        "step": None,
    }
    assert code == runner.EXIT_FAILED
    by = {s["stage"]: s for s in line["stages"]}
    assert by["commit"]["missed"] is True and by["commit"]["deadline_seconds"] == 5
    assert "stage=commit code=deadline_missed" in h.opener.requests[-1][2]


def test_an_unreachable_door_fails_at_door_and_claims_no_variant(tmp_path):
    h = Harness(tmp_path)
    h.facts.raise_error = ConnectionRefusedError()
    line, _ = h.once()
    assert line["failure"]["stage"] == "door"
    assert line["failure"]["code"] == "door_unreachable"
    assert h.cursor()["next_index"] == 0 and h.launchpad.calls == []
    assert "stage=door code=door_unreachable" in h.opener.requests[-1][2]


def test_a_window_that_goes_backward_is_a_failure(tmp_path):
    h = Harness(tmp_path)
    h.once()
    h.facts.start = 640
    line, _ = h.once()
    assert line["failure"]["code"] == "window_regressed"


def test_a_new_cycle_waits_for_the_next_window_after_an_admission(tmp_path):
    h = Harness(tmp_path)
    h.once()
    line, code = h.once()
    assert (line["result"], line["deferred"], code) == (
        "DEFERRED",
        "window_already_used",
        runner.EXIT_OK,
    )
    assert line["ping"] is None and h.cursor()["next_index"] == 1


def test_a_launchpad_on_another_hotkey_is_refused_before_launch(tmp_path):
    h = Harness(tmp_path, launchpad=FakeLaunchpad(hotkey=OTHER))
    line, _ = h.once()
    assert line["failure"]["code"] == "launchpad_hotkey_not_canary"
    assert h.launchpad.tools() == ["carbon_setup_status"]


def test_a_busy_campaign_is_waited_for_not_failed(tmp_path):
    launchpad = FakeLaunchpad()
    launchpad.busy_once = {"practice", "submit"}
    h = Harness(tmp_path, launchpad=launchpad)
    line, _ = h.once()
    assert line["result"] == "COMPLETED"
    assert h.launchpad.tools().count("carbon_practice") == 2


def test_a_failed_ping_is_recorded_and_retried_three_times(tmp_path):
    h = Harness(tmp_path)
    h.opener = Opener(503)
    line, code = h.once()
    assert line["ping"] == {"kind": "success", "delivered": False}
    assert len(h.opener.requests) == 1 + report.RETRIES
    assert code == runner.EXIT_OK


# --- through the MCP SDK -----------------------------------------------------------


class Answer(BaseModel):
    """An operation tool's structured result, as the real door's."""

    operation: str
    payload: dict[str, Any]


def mcp_server(launchpad):
    """An in-process MCP server whose tools are the fake Launchpad's, with
    refusals as the real door sends them (JSON after the SDK's prefix)."""
    from mcp.server.mcpserver import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError

    server = MCPServer("fake-launchpad")

    def answer(tool, arguments):
        arguments = {k: v for k, v in arguments.items() if v is not None}
        try:
            return Answer(operation=tool, payload=launchpad.handle(tool, arguments))
        except runner.Refused as refused:
            raise ToolError(
                json.dumps({"error": refused.code, "next_step": "-"})
            ) from None

    @server.tool(name="carbon_setup_status")
    def setup_status() -> Answer:
        return answer("carbon_setup_status", {})

    @server.tool(name="carbon_launch")
    def launch(
        agent: str, challenge: str, challenge_version: str, idempotency_key: str
    ) -> Answer:
        return answer(
            "carbon_launch",
            {
                "agent": agent,
                "challenge": challenge,
                "challenge_version": challenge_version,
                "idempotency_key": idempotency_key,
            },
        )

    @server.tool(name="carbon_observe")
    def observe(campaign: str) -> Answer:
        return answer("carbon_observe", {"campaign": campaign})

    @server.tool(name="carbon_resume")
    def resume(campaign: str) -> Answer:
        return answer("carbon_resume", {"campaign": campaign})

    @server.tool(name="carbon_practice")
    def practice(
        campaign: str, strategy: dict[str, Any], hypothesis: str, idempotency_key: str
    ) -> Answer:
        return answer(
            "carbon_practice",
            {
                "campaign": campaign,
                "strategy": strategy,
                "hypothesis": hypothesis,
                "idempotency_key": idempotency_key,
            },
        )

    @server.tool(name="carbon_freeze_candidate")
    def freeze(
        campaign: str, strategy: dict[str, Any], reason: str, idempotency_key: str
    ) -> Answer:
        return answer(
            "carbon_freeze_candidate",
            {
                "campaign": campaign,
                "strategy": strategy,
                "reason": reason,
                "idempotency_key": idempotency_key,
            },
        )

    @server.tool(name="carbon_commit")
    def commit(campaign: str, idempotency_key: str) -> Answer:
        return answer(
            "carbon_commit", {"campaign": campaign, "idempotency_key": idempotency_key}
        )

    @server.tool(name="carbon_submit")
    def submit(campaign: str, idempotency_key: str) -> Answer:
        return answer(
            "carbon_submit", {"campaign": campaign, "idempotency_key": idempotency_key}
        )

    return server


def test_a_cycle_through_the_mcp_sdk_client(tmp_path):
    """The real MCP client and `McpDoor` against an in-process server: the
    same sequence, a refusal parsed from the SDK's error text and waited out,
    and a queued result polled by submitting again."""
    launchpad = FakeLaunchpad(submits=("QUEUED", "VERDICT"))
    launchpad.busy_once = {"freeze_candidate"}
    h = Harness(tmp_path, launchpad=launchpad)
    server = mcp_server(launchpad)
    line, code = h.once(door=lambda: runner.McpDoor(server, mode="legacy"))
    assert (line["result"], code) == ("COMPLETED", runner.EXIT_OK), line
    tools = [t for t in launchpad.tools() if t != "carbon_observe"]
    assert tools == [
        "carbon_setup_status",
        "carbon_launch",
        "carbon_practice",
        "carbon_freeze_candidate",
        "carbon_freeze_candidate",
        "carbon_commit",
        "carbon_submit",
        "carbon_submit",
    ]
    assert line["submission_id"] == "bsub-" + "e" * 24


def test_the_door_starts_as_setups_snippet_does(tmp_path):
    cfg = canary_config.load(write_config(tmp_path))
    parameters = runner.stdio_parameters(cfg)
    assert parameters.command == "/usr/bin/python3"
    assert parameters.args == [
        "-P",
        "-m",
        "carbon.miner_mcp.standard_cli",
        "--state-dir",
        str(tmp_path / "state"),
    ]
    assert parameters.env == {"PYTHONPATH": str(tmp_path / "checkout")}
