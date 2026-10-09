"""The canary runner (CANARY-01 S1): one cycle of the real miner path.

    python -m scripts.dev.canary.runner once --config <file>

A Carbon-owned miner, `carbon-canary` (OWNER-CANARY-LIST-01), drives the
Launchpad's MCP door exactly as a miner's own agent does, with no LLM and no
model spend. One cycle:

1. `door`: read the intake's public facts (`intake_client.read_intake`) and
   check them against testnet 567, the config's Challenge and its receiver;
2. `window`: read `submission_rule.current_window`; it never goes backward;
3. pick the next recipe from the registered variant list (`variants.json`).
   The cursor only moves forward: a variant is claimed once, before its
   campaign is launched, and never used again; when the list runs out the
   runner stops `variant_list_exhausted` and never wraps;
4. launch (or resume) an `agent: none` campaign, practise once, freeze;
5. `commit`: `carbon_commit`, then observe until the commitment reads back on
   chain. The canary's signer auto-confirms an allow-listed testnet hotkey
   (OWNER-SIGNER-TESTNET-AUTOCONFIRM-01); this runner confirms nothing, and
   signs nothing;
6. `admission`, `scoring`, `verdict`: `carbon_submit`, and submit again to
   poll a queued result (LA-F18: a replayed submit polls the recorded
   submission id, with no second admission), until a sealed verdict;
7. `weights` is S2: reported NOT_BUILT.

What it sees comes only from the Launchpad's readback (`carbon_observe`) and
the intake outcome a submit reports (QUEUED, UNAVAILABLE or REFUSED). The
Launchpad's submit itself waits for a verdict (`remote_submission.WAIT_S`)
before it answers `evaluation_queued`, so admission is seen at the first
readback that shows the intake holding or finishing the submission; when the
verdict arrives on the first submit, admission and scoring are not separable
and the journal says so.

A run that cannot finish within `poll.max_wait_seconds` leaves the cycle open
(PENDING) for the next run, which resumes it: the same campaign, variant and
idempotency keys. Every run appends one journal line, and pings as
`report` says. Deadlines are owner-set (HUMAN_INPUT); a null deadline only
measures.

Never: a Docker prune, the AX42 or the distribution host, hidden material, a
signature or a confirmation, or any hotkey but a registered canary.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import datetime
import json
import os
import re
import secrets
import sys
import time
import urllib.error
from pathlib import Path

from scripts.dev.canary import report
from scripts.dev.canary import variants as variant_list
from scripts.dev.canary.config import STAGES, ConfigRefused, owner_only_bytes
from scripts.dev.canary.config import load as load_config

CURSOR_SCHEMA = "carbon.canary.cursor.v1"
#: A stage's outcomes.
OK, FAILED, UNAVAILABLE, PENDING, SKIPPED, NOT_BUILT = (
    "OK",
    "FAILED",
    "UNAVAILABLE",
    "PENDING",
    "SKIPPED",
    "NOT_BUILT",
)
#: A run's results.
COMPLETED, DEFERRED = "COMPLETED", "DEFERRED"
#: Exit codes: done, pending or deferred; a failure or a missed deadline; the
#: runner refused to run (config, list, cursor); another run holds the lock.
EXIT_OK, EXIT_FAILED, EXIT_REFUSED, EXIT_BUSY = 0, 1, 2, 3
#: Refusals that clear by themselves: wait a poll, then ask again.
TRANSIENT = frozenset({"campaign_busy", "campaign_not_prepared"})
#: Campaign states a resume moves on; states that end the cycle.
RESUMABLE = frozenset({"PAUSED", "INTERRUPTED", "PAUSE_REQUESTED"})
FINISHED = frozenset(
    {
        "COMPLETED",
        "STOPPED",
        "STOPPING",
        "RECONCILIATION_REQUIRED",
        "READBACK_UNAVAILABLE",
    }
)
COMMITTED = frozenset({"COMMITTED", "ALREADY_ON_CHAIN"})
_CODE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,79}")
_CAMPAIGN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
_CODE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
HYPOTHESIS = (
    "Canary liveness cycle (CANARY-01): baseline kNN, {neighbours} neighbours, "
    "train_fraction {train_fraction}."
)
REASON = (
    "Canary liveness check (CANARY-01): registered variant {index}, practised "
    "once. A monitor, never a competitor."
)


def _closed(code, fallback):
    return code if type(code) is str and _CODE.fullmatch(code) else fallback


def iso(moment):
    if moment is None:
        return None
    return datetime.datetime.fromtimestamp(moment, datetime.timezone.utc).isoformat()


class Refused(Exception):
    """A closed refusal from the Launchpad's door."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class StageFailed(Exception):
    """A stage ended without success: its closed code. `close` ends the cycle
    (its variant is never used again either way)."""

    def __init__(self, stage, code, *, outcome=FAILED, close=False, step=None):
        super().__init__(f"{stage}: {code}")
        self.stage, self.code, self.outcome = stage, code, outcome
        self.close, self.step = close, step


class StagePending(Exception):
    """This run's wait ran out while `stage` waited; the next run resumes."""

    def __init__(self, stage):
        super().__init__(stage)
        self.stage = stage


class _Deferred(Exception):
    """No new cycle this run: the hotkey's window is already used."""


# --- the Launchpad's MCP door ----------------------------------------------------


def stdio_parameters(cfg):
    """The canary's own MCP door, started exactly as setup's snippets start
    it (`environment_setup.mcp_connect`): `python -P -m
    carbon.miner_mcp.standard_cli --state-dir <dir>`, with PYTHONPATH the
    checkout."""
    from mcp.client.stdio import StdioServerParameters

    return StdioServerParameters(
        command=str(cfg.python),
        args=[
            "-P",
            "-m",
            "carbon.miner_mcp.standard_cli",
            "--state-dir",
            str(cfg.state_dir),
        ],
        env={"PYTHONPATH": str(cfg.checkout)},
    )


def refusal_code(result):
    """A refused tool call's closed code: the JSON after the SDK's "Error
    executing tool <name>: " prefix (LP-PROD-B), or `door_refused`."""
    try:
        text = result.content[0].text
        body = json.loads(text.split(": ", 1)[1])
        return _closed(body.get("error"), "door_refused")
    except Exception:  # noqa: BLE001 - a closed code, never the text
        return "door_refused"


class McpDoor:
    """An MCP client session on the Launchpad's door, as an own-agent client.

    `server` is the stdio parameters in production; a test passes an
    in-process server. Every tool call answers its payload or raises
    `Refused` with a closed code."""

    def __init__(self, server, *, mode="auto", read_timeout=180.0):
        self.server = server
        self.mode = mode
        self.read_timeout = read_timeout
        self._client = None
        self.session = None

    async def __aenter__(self):
        from mcp import Client

        self._client = Client(
            self.server, mode=self.mode, read_timeout_seconds=self.read_timeout
        )
        try:
            self.session = await self._client.__aenter__()
        except Exception:  # noqa: BLE001 - a closed code, never a trace
            raise Refused("launchpad_door_unavailable") from None
        return self

    async def __aexit__(self, *exc):
        with contextlib.suppress(Exception):
            await self._client.__aexit__(*exc)
        return False

    async def call(self, tool, arguments):
        try:
            result = await self.session.call_tool(tool, arguments)
        except Exception:  # noqa: BLE001 - a closed code, never a trace
            raise Refused("door_call_failed") from None
        if result.is_error:
            raise Refused(refusal_code(result))
        structured = result.structured_content
        if type(structured) is not dict or type(structured.get("payload")) is not dict:
            raise Refused("door_answer_unrecognised")
        return structured["payload"]


# --- the cursor ------------------------------------------------------------------


def new_cursor(list_digest):
    return {
        "schema": CURSOR_SCHEMA,
        "variants_digest": list_digest,
        "next_index": 0,
        "last_window": None,
        "last_admitted_window_start": None,
        "open": None,
    }


def load_cursor(path, list_digest):
    """The runner's cursor, or a new one when none exists yet. A cursor for
    another variant list is refused: a regenerated list starts a new cursor,
    so no index is ever read against a list it was not claimed from."""
    if not os.path.lexists(path):
        return new_cursor(list_digest)
    raw = owner_only_bytes(path, limit=1 << 20, code="cursor_unusable")
    try:
        state = json.loads(raw)
    except ValueError:
        raise ConfigRefused("cursor_unusable") from None
    if (
        type(state) is not dict
        or set(state) != set(new_cursor(list_digest))
        or state["schema"] != CURSOR_SCHEMA
        or type(state["next_index"]) is not int
        or state["next_index"] < 0
    ):
        raise ConfigRefused("cursor_unusable")
    if state["variants_digest"] != list_digest:
        raise ConfigRefused("cursor_names_another_variant_list")
    return state


def save_cursor(path, state):
    """Write the cursor atomically, owner-only."""
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    data = (json.dumps(state, sort_keys=True, indent=1) + "\n").encode()
    fd = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600
    )
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, path)


@contextlib.contextmanager
def held(path):
    """One run at a time per cursor: an exclusive lock beside it."""
    import fcntl

    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(
        path.with_name(path.name + ".lock"),
        os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
        0o600,
    )
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        yield True
    finally:
        os.close(fd)


# --- one cycle -------------------------------------------------------------------


def _expected_submission_id(hotkey, strategy, contract_digest):
    from carbon.battery import intake_client

    try:
        return intake_client.submission_id(hotkey, strategy, contract_digest)
    except Exception:  # noqa: BLE001 - recorded as unknown, never guessed
        return None


def _read_intake(url):
    from carbon.battery import intake_client

    return intake_client.read_intake(url)


def _testnet():
    from carbon.development_session.chain_onboarding import carbon_testnet_context

    context = carbon_testnet_context()
    return context.network, context.genesis_hash, context.netuid


class Runner:
    """One `once` run over one config. Every dependency that reaches outside
    the process can be replaced, for tests: the door, the intake read, the
    clock, the sleep, the ping and the variant checks."""

    def __init__(
        self,
        cfg,
        *,
        door=None,
        read_intake=_read_intake,
        clock=time.time,
        sleep=asyncio.sleep,
        opener=None,
        ping_sleep=time.sleep,
        check_entry=variant_list.check_entry,
        contract_digest=variant_list.contract_digest,
        expected_submission_id=_expected_submission_id,
        testnet=_testnet,
    ):
        self.cfg = cfg
        self.door_factory = door or (lambda: McpDoor(stdio_parameters(cfg)))
        self.read_intake = read_intake
        self.clock = clock
        self.sleep = sleep
        self.opener = opener
        self.ping_sleep = ping_sleep
        self.check_entry = check_entry
        self.contract_digest = contract_digest
        self.expected_submission_id = expected_submission_id
        self.testnet = testnet
        self.door = None
        self.state = None
        self.cycle = None
        self.stages = {}
        self.started = self.until = None

    # -- records --

    def save(self):
        save_cursor(self.cfg.cursor, self.state)

    def begin(self, stage):
        record = self.stages.get(stage)
        if record is not None and record["outcome"] == PENDING:
            return record
        record = {
            "started_at": self.clock(),
            "ended_at": None,
            "outcome": PENDING,
            "code": None,
            "note": None,
        }
        self.stages[stage] = record
        return record

    def end(self, stage, outcome, code=None, note=None):
        record = self.stages.get(stage) or self.begin(stage)
        record.update(ended_at=self.clock(), outcome=outcome, code=code, note=note)

    def fail(self, stage, code, step=None, **kwargs):
        """A `StageFailed`, after bumping the step's attempt so the next try
        sends a fresh idempotency key rather than replaying this one."""
        if step is not None and self.cycle is not None:
            attempts = self.cycle["attempts"]
            attempts[step] = attempts.get(step, 0) + 1
        return StageFailed(stage, code, step=step, **kwargs)

    def key(self, step):
        return f"{self.cycle['token']}-{step}-{self.cycle['attempts'].get(step, 0)}"

    # -- waiting --

    async def pause(self, stage):
        if self.clock() + self.cfg.poll_interval > self.until:
            raise StagePending(stage)
        await self.sleep(self.cfg.poll_interval)

    async def call(self, tool, arguments, stage, step=None):
        try:
            return await self.door.call(tool, arguments)
        except Refused as refused:
            raise self.fail(stage, refused.code, step) from None

    async def operate(self, operation, arguments, stage, step):
        while True:
            try:
                return await self.door.call("carbon_" + operation, arguments)
            except Refused as refused:
                if refused.code in TRANSIENT:
                    await self.pause(stage)
                    continue
                raise self.fail(stage, refused.code, step) from None

    async def observe(self, stage):
        return await self.call(
            "carbon_observe", {"campaign": self.cycle["campaign"]}, stage
        )

    async def settle(self, stage):
        """The campaign once no work is in flight for it."""
        while True:
            view = await self.observe(stage)
            if view.get("in_flight") is None:
                return view
            await self.pause(stage)

    async def ready(self, stage, step):
        """The campaign READY for new work: resumed once if paused or
        interrupted, waited for while it moves, refused when it ended."""
        resumed = False
        while True:
            view = await self.settle(stage)
            state = view.get("state")
            if state == "READY":
                return view
            if state in RESUMABLE and not resumed:
                await self.operate(
                    "resume", {"campaign": self.cycle["campaign"]}, stage, step
                )
                resumed = True
                continue
            if state in FINISHED:
                refusal = view.get("last_refusal")
                code = refusal.get("code") if type(refusal) is dict else None
                raise self.fail(
                    stage,
                    _closed(code, "campaign_" + str(state).lower()),
                    step,
                )
            await self.pause(stage)

    @staticmethod
    def refusal_of(view, operation):
        refusal = view.get("last_refusal")
        if type(refusal) is dict and refusal.get("operation") == operation:
            return _closed(refusal.get("code"), None)
        return None

    # -- the stages --

    def door_stage(self):
        self.begin("door")
        try:
            facts = self.read_intake(self.cfg.intake_url)
        except urllib.error.HTTPError:
            raise StageFailed("door", "door_unavailable", outcome=UNAVAILABLE) from None
        except OSError:  # URLError, a timeout, a refused or reset connection
            raise StageFailed("door", "door_unreachable", outcome=UNAVAILABLE) from None
        except ValueError:  # not JSON, or not a battery intake
            raise StageFailed("door", "door_not_an_intake") from None
        if type(facts) is not dict:
            raise StageFailed("door", "door_not_an_intake")
        network = (facts.get("network"), facts.get("genesis"), facts.get("netuid"))
        if network != tuple(self.testnet()):
            raise StageFailed("door", "door_wrong_network")
        challenge = facts.get("challenge")
        if challenge != {
            "id": self.cfg.challenge_id,
            "version": self.cfg.challenge_version,
        }:
            raise StageFailed("door", "door_wrong_challenge")
        if facts.get("receiver") != self.cfg.receiver:
            raise StageFailed("door", "door_wrong_receiver")
        snapshot = facts.get("snapshot")
        if (
            type(snapshot) is not dict
            or type(snapshot.get("finalized_block")) is not int
        ):
            raise StageFailed("door", "door_answer_unrecognised")
        self.end("door", OK)
        return facts

    def window_stage(self, facts):
        self.begin("window")
        rule = facts.get("submission_rule")
        window = rule.get("current_window") if type(rule) is dict else None
        if type(window) is not dict or rule.get("per_hotkey") is None:
            raise StageFailed("window", "window_rule_absent")
        start, end = window.get("start_block"), window.get("end_block")
        if type(start) is not int or type(end) is not int or not 0 <= start <= end:
            raise StageFailed("window", "window_answer_unrecognised")
        last = self.state["last_window"]
        if last is not None and start < last["start_block"]:
            raise StageFailed("window", "window_regressed")
        rotation = rule.get("rotation")
        self.state["last_window"] = {
            "start_block": start,
            "end_block": end,
            "finalized_block": facts["snapshot"]["finalized_block"],
            "rotation": rotation if type(rotation) is int else None,
        }
        self.end("window", OK)
        return self.state["last_window"]

    def claim(self, document):
        """Claim the next variant: the cursor moves past it before anything
        is launched, so it is never used again, whatever happens next."""
        index = self.state["next_index"]
        if index >= len(document["variants"]):
            raise StageFailed("cycle", "variant_list_exhausted")
        entry = document["variants"][index]
        token = "cnry-" + secrets.token_hex(8)
        self.cycle = {
            "id": f"canary-{index:04d}-{token[5:13]}",
            "token": token,
            "variant_index": index,
            "strategy": entry["strategy"],
            "strategy_hash": entry["strategy_hash"],
            "expected_submission_id": None,
            "claimed_at": self.clock(),
            "campaign": None,
            "attempts": {},
            "practised": False,
            "frozen": False,
            "commit_requested": False,
            "committed": False,
            "commit_block": None,
            "confirm_prompt_seen": False,
            "submit_attempts": 0,
            "submit_window_start": None,
            "admitted": False,
            "submission_id": None,
            "verdict": None,
            "stages": self.stages,
        }
        self.state["next_index"] = index + 1
        self.state["open"] = self.cycle
        self.save()
        try:
            self.check_entry(document, index)
        except variant_list.VariantRefused as refused:
            raise StageFailed("cycle", refused.code, close=True) from None
        self.cycle["expected_submission_id"] = self.expected_submission_id(
            self.cfg.hotkey, entry["strategy"], document["contract_digest"]
        )
        self.save()

    async def check_hotkey(self):
        """The Launchpad install is the canary's: its registered hotkey is the
        config's, a registered canary."""
        status = await self.call("carbon_setup_status", {}, "cycle", "setup")
        if status.get("registered_hotkey") != self.cfg.hotkey:
            raise StageFailed("cycle", "launchpad_hotkey_not_canary", step="setup")

    async def campaign(self):
        if self.cycle["campaign"] is None:
            payload = await self.operate(
                "launch",
                {
                    "agent": "none",
                    "challenge": self.cfg.challenge_id,
                    "challenge_version": self.cfg.challenge_version,
                    "idempotency_key": self.key("launch"),
                },
                "cycle",
                "launch",
            )
            identity = payload.get("id")
            if type(identity) is not str or not _CAMPAIGN.fullmatch(identity):
                raise self.fail("cycle", "launch_answer_unrecognised", "launch")
            self.cycle["campaign"] = identity
            self.save()

    async def practise(self):
        if self.cycle["practised"]:
            return
        view = await self.ready("cycle", "practice")
        if (view.get("completed_experiments") or 0) < 1:
            parameters = self.cycle["strategy"]["parameters"]
            await self.operate(
                "practice",
                {
                    "campaign": self.cycle["campaign"],
                    "strategy": self.cycle["strategy"],
                    "hypothesis": HYPOTHESIS.format(**parameters),
                    "idempotency_key": self.key("practice"),
                },
                "cycle",
                "practice",
            )
            view = await self.settle("cycle")
            if (view.get("completed_experiments") or 0) < 1:
                code = self.refusal_of(view, "practice") or "practice_result_missing"
                raise self.fail("cycle", code, "practice")
        self.cycle["practised"] = True
        self.save()

    def frozen_in(self, view):
        return any(
            type(item) is dict
            and (
                item.get("strategy_hash") == self.cycle["strategy_hash"]
                or item.get("strategy") == self.cycle["strategy"]
            )
            for item in view.get("candidate_freezes") or []
        )

    async def freeze(self):
        if self.cycle["frozen"]:
            return
        view = await self.ready("cycle", "freeze")
        if not self.frozen_in(view):
            await self.operate(
                "freeze_candidate",
                {
                    "campaign": self.cycle["campaign"],
                    "strategy": self.cycle["strategy"],
                    "reason": REASON.format(index=self.cycle["variant_index"]),
                    "idempotency_key": self.key("freeze"),
                },
                "cycle",
                "freeze",
            )
            view = await self.settle("cycle")
            if not self.frozen_in(view):
                code = (
                    self.refusal_of(view, "freeze_candidate") or "freeze_not_recorded"
                )
                raise self.fail("cycle", code, "freeze")
        self.cycle["frozen"] = True
        self.save()

    async def commit(self, facts):
        """The frozen candidate's commitment, read back on chain. The signer
        confirms (auto-confirm for the allow-listed canary hotkey); this runner
        only asks and reads."""
        if self.cycle["committed"]:
            return
        fact = facts.get("commitment")
        if not (type(fact) is str and fact.startswith("required")):
            self.begin("commit")
            self.end("commit", SKIPPED, note="the intake requires no commitment")
            self.cycle["committed"] = True
            self.save()
            return
        self.begin("commit")
        view = await self.ready("commit", "commit")
        if not self._committed(view.get("commitment")):
            if not self.cycle["commit_requested"]:
                view = await self.operate(
                    "commit",
                    {
                        "campaign": self.cycle["campaign"],
                        "idempotency_key": self.key("commit"),
                    },
                    "commit",
                    "commit",
                )
                self.cycle["commit_requested"] = True
                self.save()
            while True:
                commitment = view.get("commitment")
                if type(commitment) is dict and commitment.get("human_action_required"):
                    self.cycle["confirm_prompt_seen"] = True
                if self._committed(commitment):
                    break
                if view.get("in_flight") is None and (
                    commitment is None or commitment.get("state") == "NOT_COMMITTED"
                ):
                    self.cycle["commit_requested"] = False
                    code = (
                        _closed((commitment or {}).get("code"), None)
                        or self.refusal_of(view, "commit")
                        or "commitment_not_committed"
                    )
                    raise self.fail("commit", code, "commit")
                await self.pause("commit")
                view = await self.observe("commit")
        commitment = view["commitment"]
        block = (commitment.get("on_chain") or {}).get("block")
        self.cycle["commit_block"] = block if type(block) is int else None
        self.cycle["committed"] = True
        self.end("commit", OK)
        self.save()

    @staticmethod
    def _committed(commitment):
        return (
            type(commitment) is dict
            and commitment.get("state") in COMMITTED
            and type(commitment.get("on_chain")) is dict
        )

    def stage_now(self):
        return "scoring" if self.cycle["admitted"] else "admission"

    @staticmethod
    def verdict_in(view):
        for item in view.get("final_results") or []:
            if type(item) is not dict:
                continue
            if (
                item.get("status") == "VALIDATOR_OUTCOME"
                and type(item.get("result")) is dict
            ):
                return item["result"]
            if item.get("status") == "READBACK_UNAVAILABLE":
                raise StageFailed("verdict", "verdict_readback_unavailable")
        return None

    def admitted(self, note):
        self.end("admission", OK, note=note)
        self.cycle["admitted"] = True
        self.begin("scoring")
        self.save()

    async def submit(self, window):
        """Submit, then submit again to poll a queued result, until a verdict."""
        self.begin("verdict")
        self.begin(self.stage_now())
        view = await self.settle(self.stage_now())
        result = self.verdict_in(view)
        while result is None:
            await self.ready(self.stage_now(), "submit")
            if self.cycle["submit_window_start"] is None:
                self.cycle["submit_window_start"] = window["start_block"]
            attempt = self.cycle["submit_attempts"]
            await self.operate(
                "submit",
                {
                    "campaign": self.cycle["campaign"],
                    "idempotency_key": f"{self.cycle['token']}-submit-{attempt}",
                },
                self.stage_now(),
                "submit",
            )
            self.cycle["submit_attempts"] = attempt + 1
            self.save()
            view = await self.settle(self.stage_now())
            result = self.verdict_in(view)
            if result is not None:
                break
            refusal = view.get("last_refusal")
            if type(refusal) is not dict or refusal.get("operation") != "submit":
                raise StageFailed(self.stage_now(), "submit_outcome_missing")
            code = _closed(refusal.get("code"), "submit_refused")
            outcome = refusal.get("intake_outcome")
            if outcome == "QUEUED":
                if not self.cycle["admitted"]:
                    self.admitted("the intake holds it (evaluation_queued)")
                await self.pause("scoring")
                continue
            if outcome == "UNAVAILABLE":
                raise StageFailed(self.stage_now(), code, outcome=UNAVAILABLE)
            raise StageFailed(self.stage_now(), code, close=outcome == "REFUSED")
        self.verdict(result)

    def verdict(self, result):
        if not self.cycle["admitted"]:
            self.admitted("first seen with the verdict")
            self.end(
                "scoring",
                OK,
                note=(
                    "not separable from admission: the verdict arrived on the "
                    "first submit"
                ),
            )
        else:
            self.end("scoring", OK)
        state = _closed(result.get("state"), "unrecognised")
        submission = result.get("submission_id")
        self.cycle["submission_id"] = (
            submission
            if type(submission) is str and _CODE_ID.fullmatch(submission)
            else None
        )
        self.cycle["verdict"] = {
            "state": state,
            "sealed": (
                result.get("sealed") if type(result.get("sealed")) is bool else None
            ),
        }
        if state != "SCORED":
            raise StageFailed("verdict", "verdict_" + state.lower(), close=True)
        self.end("verdict", OK)

    # -- the run --

    async def once(self):
        """One run. Returns `(journal line, exit code)`; raises
        `ConfigRefused` or `VariantRefused` only before anything is read,
        launched or sent."""
        cfg = self.cfg
        url = (
            None
            if cfg.healthcheck_env_file is None
            else report.ping_url(cfg.healthcheck_env_file)
        )
        document, list_digest = variant_list.load(cfg.variants)
        if document["challenge"] != {
            "id": cfg.challenge_id,
            "version": cfg.challenge_version,
        }:
            raise variant_list.VariantRefused("variant_list_wrong_challenge")
        if document["contract_digest"] != self.contract_digest():
            raise variant_list.VariantRefused("variant_list_stale")
        self.state = load_cursor(cfg.cursor, list_digest)
        self.started = self.clock()
        self.until = self.started + cfg.max_wait
        self.cycle = self.state["open"]
        self.stages = self.cycle["stages"] if self.cycle is not None else {}
        result, failure, pending, deferred = None, None, None, None
        close = False
        try:
            facts = self.door_stage()
            window = self.window_stage(facts)
            if self.cycle is None:
                if self.state["last_admitted_window_start"] == window["start_block"]:
                    deferred = "window_already_used"
                    raise _Deferred()
                self.claim(document)
            async with self.door_factory() as door:
                self.door = door
                await self.check_hotkey()
                await self.campaign()
                await self.practise()
                await self.freeze()
                await self.commit(facts)
                await self.submit(window)
            result = COMPLETED
            close = True
        except _Deferred:
            result = DEFERRED
        except StagePending as waiting:
            result, pending = PENDING, waiting.stage
        except StageFailed as failed:
            result = FAILED
            if failed.stage in self.stages:
                self.end(failed.stage, failed.outcome, code=failed.code)
            failure = {"stage": failed.stage, "code": failed.code, "step": failed.step}
            close = failed.close
        except Refused as refused:  # the door itself could not be opened
            result = FAILED
            failure = {"stage": "cycle", "code": refused.code, "step": "door"}
        except Exception:  # noqa: BLE001 - journalled and pinged by code, never a trace
            result = FAILED
            failure = {"stage": "cycle", "code": "runner_error", "step": None}
        return self.finish(url, result, failure, pending, deferred, close)

    def misses(self, now):
        missed = []
        for stage in STAGES:
            record = self.stages.get(stage)
            deadline = self.cfg.deadlines[stage]
            if record is None or deadline is None:
                continue
            ended = record["ended_at"] if record["ended_at"] is not None else now
            if ended - record["started_at"] > deadline:
                record["missed"] = True
                missed.append(stage)
        return missed

    def finish(self, url, result, failure, pending, deferred, close):
        now = self.clock()
        missed = self.misses(now)
        if failure is None and missed:
            failure = {"stage": missed[0], "code": "deadline_missed", "step": None}
        cycle = self.cycle
        if cycle is not None and close:
            self.state["open"] = None
            if cycle["admitted"] and cycle["submit_window_start"] is not None:
                self.state["last_admitted_window_start"] = cycle["submit_window_start"]
        self.save()
        line = {
            "schema": report.JOURNAL_SCHEMA,
            "run_started_at": iso(self.started),
            "run_ended_at": iso(now),
            "result": result,
            "pending_stage": pending,
            "deferred": deferred,
            "failure": failure,
            "closed": cycle is not None and close,
            "cycle_id": cycle["id"] if cycle else None,
            "variant_index": cycle["variant_index"] if cycle else None,
            "strategy_hash": cycle["strategy_hash"] if cycle else None,
            "campaign": cycle["campaign"] if cycle else None,
            "commit_block": cycle["commit_block"] if cycle else None,
            "confirm_prompt_seen": cycle["confirm_prompt_seen"] if cycle else False,
            "submit_attempts": cycle["submit_attempts"] if cycle else 0,
            "submission_id": cycle["submission_id"] if cycle else None,
            "expected_submission_id": (
                cycle["expected_submission_id"] if cycle else None
            ),
            "verdict": cycle["verdict"] if cycle else None,
            "window": self.state["last_window"],
            "stages": self.stage_lines(now),
            "ping": None,
        }
        line["submission_id_matches"] = (
            None
            if line["submission_id"] is None or line["expected_submission_id"] is None
            else line["submission_id"] == line["expected_submission_id"]
        )
        kind = None
        if failure is not None:
            kind = "fail"
        elif result == COMPLETED:
            kind = "success"
        if kind is not None and url is not None:
            body = (
                report.fail_body(line) if kind == "fail" else report.success_body(line)
            )
            options = {"sleep": self.ping_sleep}
            if self.opener is not None:
                options["opener"] = self.opener
            delivered = report.ping(url, body, fail=kind == "fail", **options)
            line["ping"] = {"kind": kind, "delivered": delivered}
        elif kind is not None:
            line["ping"] = {"kind": kind, "delivered": None}
        report.append(self.cfg.journal, line)
        return line, EXIT_FAILED if failure is not None else EXIT_OK

    def stage_lines(self, now):
        lines = []
        for stage in STAGES:
            deadline = self.cfg.deadlines[stage]
            if stage == "weights":
                lines.append(
                    {
                        "stage": stage,
                        "outcome": NOT_BUILT,
                        "code": "weights_check_not_built",
                        "note": "CANARY-01 S2",
                        "started_at": None,
                        "ended_at": None,
                        "seconds": None,
                        "deadline_seconds": deadline,
                        "missed": False,
                    }
                )
                continue
            record = self.stages.get(stage)
            if record is None:
                continue
            ended = record["ended_at"]
            lines.append(
                {
                    "stage": stage,
                    "outcome": record["outcome"],
                    "code": record["code"],
                    "note": record["note"],
                    "started_at": iso(record["started_at"]),
                    "ended_at": iso(ended),
                    "seconds": round(
                        (ended if ended is not None else now) - record["started_at"], 3
                    ),
                    "deadline_seconds": deadline,
                    "missed": record.get("missed", False),
                }
            )
        return lines


# --- the command -----------------------------------------------------------------


def run(config_path, **options):
    """Load the config, take the lock, run once. Returns `(summary, code)`."""
    try:
        cfg = load_config(config_path)
    except ConfigRefused as refused:
        return {"result": "REFUSED", "code": refused.code, "field": refused.field}, (
            EXIT_REFUSED
        )
    with held(cfg.cursor) as acquired:
        if not acquired:
            return {"result": "BUSY", "code": "runner_busy"}, EXIT_BUSY
        try:
            line, code = asyncio.run(Runner(cfg, **options).once())
        except (ConfigRefused, variant_list.VariantRefused) as refused:
            return {"result": "REFUSED", "code": refused.code}, EXIT_REFUSED
    return {
        "result": line["result"],
        "failure": line["failure"],
        "pending_stage": line["pending_stage"],
        "cycle_id": line["cycle_id"],
        "variant_index": line["variant_index"],
        "submission_id": line["submission_id"],
    }, code


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m scripts.dev.canary.runner")
    commands = parser.add_subparsers(dest="command", required=True)
    once = commands.add_parser("once", help="run one canary cycle (or resume one)")
    once.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    summary, code = run(args.config)
    print(json.dumps(summary, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
