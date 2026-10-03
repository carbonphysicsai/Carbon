"""Graphite's closed one-shot tasks: one tool-less model call per item, under a grant.

The Reader's method-card extraction (phase 2, `method_cards` and `triage`) set
the pattern, and this module applies it to any task that needs no tools: the
level planner (`level_planner`) and the Optimizer researcher's method proposals
(`optimizer_research`).

- **The request is Carbon's.** A task fixes the prompt (recorded by digest), no
  tools, the model and its bounds. Each item travels as one JSON *data*
  message. Text inside it can change what a reply says, never the role, the
  tools, the model, the budget or what Carbon writes.
- **The model** is the role's current rung on the owner's Engy ladder
  (`ladder.Ladder`), recorded once per run and kept on resume.
- **Metering** is `research_agent.request_model` on a
  `research_ledger.CampaignLedger`: reservation before dispatch, settlement
  from the reported charge, bounded rate-limit retries, replay of a finished
  call without resending it. A run's ledger is frozen with the grant's
  `worst_case_run_cost` and a call cap.
- **The grant** is an exact `SpendingGrant` for provider `graphite`
  (`triage.check_grant`). A new run opens only while the grant permits another
  run and every earlier run's settled and reserved spend, plus this run's worst
  case and the cleanup allowance, stays within the ceiling.
- **Stops are typed**, as in `triage`: `RECONCILIATION_REQUIRED`,
  `PROVIDER_REJECTED`, `STOPPED_CAP`, `STOPPED_INFRA`. An infrastructure stop
  is never a research finding.

Tests drive it with `model.ScriptedModel`. A live run needs the owner's grant
and the owner's authorization of that run.
"""

from __future__ import annotations

import datetime
import json
import time
from decimal import Decimal
from pathlib import Path

from carbon.development_session.data import write_once
from carbon.development_session.model_provider import select
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_agent import (
    ProviderCallFailed,
    request_model,
)
from carbon.development_session.research_ledger import VERSION, CampaignLedger

from ..provider import identifier
from .ladder import Ladder
from .model import ENGY_ADAPTERS
from .roles import RoleName
from .triage import NANO_PER_USD, _stopped, ceilings, check_grant

RUN_SCHEMA = "carbon.graphite.closed-task-run.v1"


class TaskRefused(ValueError):
    """The task cannot run; nothing was reserved or sent."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class TaskStopped(RuntimeError):
    """A metered call stopped the run; `stop` is the typed stop."""

    def __init__(self, stop):
        super().__init__(stop["status"])
        self.stop = stop


class ClosedTask:
    """Runs of one closed, tool-less task for one Graphite role, under a grant."""

    def __init__(
        self,
        *,
        root,
        grant,
        model,
        role,
        task,
        prompt,
        settings,
        max_calls,
        adapter_id="engy-anthropic",
        clock=time.time,
        now=None,
        sleep=time.sleep,
    ):
        root = Path(root)
        if not root.is_absolute() or root.is_symlink():
            raise ValueError("a task root is private and absolute")
        if type(role) is not RoleName:
            raise TypeError("exact RoleName required")
        if type(max_calls) is not int or max_calls < 1:
            raise ValueError("max_calls is a positive integer")
        if adapter_id not in ENGY_ADAPTERS:
            raise TaskRefused("engy_adapter_required")
        moment = now() if now else datetime.datetime.now(datetime.UTC)
        try:
            check_grant(grant, model, moment)
        except ValueError as error:
            raise TaskRefused(getattr(error, "code", str(error))) from None
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        (root / "runs").mkdir(exist_ok=True, mode=0o700)
        self.root, self.grant, self.model = root, grant, model
        self.role, self.task, self.prompt = role, task, prompt
        self.settings, self.max_calls = dict(settings), max_calls
        self.adapter_id, self.clock, self.sleep = adapter_id, clock, sleep
        self.ladder = Ladder(root / "ladder")
        self.owner = "graphite-" + task

    @property
    def prompt_digest(self):
        return digest(self.prompt.encode("utf-8"))

    def run_dir(self, run_id):
        identifier(run_id, "run_id")
        return self.root / "runs" / run_id

    def _ledger(self, run_id):
        return CampaignLedger(self.run_dir(run_id) / "ledger", clock=self.clock)

    def _selection(self, model_id):
        selection = select(
            provider_id=self.adapter_id,
            model_id=model_id,
            credential={"kind": "file", "reference": self.model.credential_reference},
            settings=self.settings,
        )
        self.model.transport_for(selection)  # refuses before anything is opened
        return selection

    def committed_nano(self):
        """Settled plus still-reserved provider spend of every run."""
        total = 0
        for run in sorted((self.root / "runs").iterdir()):
            if (run / "ledger" / "campaign.sqlite3").exists():
                status = self._ledger(run.name).status(owner=self.owner)
                total += status["used"]["provider_nanodollars"]
        return total

    def open(self, run_id, brief_digest):
        """Open a new run under the grant, or verify the run being resumed.
        Returns `(selection, record)`."""
        directory = self.run_dir(run_id)
        path = directory / "run.json"
        opened = json.loads(path.read_bytes()) if path.exists() else None
        model_id = (
            opened["selection"]["model"] if opened else self.ladder.model(self.role)
        )
        selection = self._selection(model_id)
        record = {
            "schema": RUN_SCHEMA,
            "task": self.task,
            "run_id": run_id,
            "grant_id": self.grant.grant_id,
            "role": self.role.value,
            "rung": opened["rung"] if opened else self.ladder.rung(self.role),
            "selection": selection.record(),
            "prompt_digest": self.prompt_digest,
            "brief_digest": brief_digest,
            "ceilings": ceilings(self.grant, self.max_calls),
            "elapsed_seconds": self.grant.max_runtime_s,
            "live_inference": bool(self.model.live),
        }
        if opened is not None:
            if opened != record:
                raise TaskRefused("run_record_mismatch")
            return selection, opened
        runs = [p for p in (self.root / "runs").iterdir() if p.is_dir()]
        if len(runs) >= self.grant.permitted_runs:
            raise TaskRefused("run_limit_reached")
        committed = Decimal(self.committed_nano()) / NANO_PER_USD
        if (
            committed + self.grant.worst_case_run_cost + self.grant.cleanup_allowance
            > self.grant.monetary_ceiling
        ):
            raise TaskRefused("grant_ceiling_reached")
        directory.mkdir(mode=0o700, exist_ok=True)
        write_once(path, canonical(record))
        return selection, record

    def _manifest(self, record):
        return {
            "schema": VERSION,
            "ceilings": record["ceilings"],
            "elapsed_seconds": record["elapsed_seconds"],
            "campaign_id": record["run_id"],
            "implementation": "graphite-closed-task:" + self.task,
            "objective": f"graphite-{self.role.value}:{self.task}",
            "sampling": "one closed request per item, in the task's order",
            "control": "graphite-closed-task",
            "selection": "none",
            "replica_policy": "none",
            "provider": record["selection"]["provider_id"],
            "owner": self.owner,
        }

    def request(self, selection, item):
        """The closed, stateless request for one item. Only the item varies."""
        effort = selection.settings.reasoning_effort
        return {
            "model": selection.model_id,
            "instructions": self.prompt,
            "input": [{"role": "user", "content": canonical(item).decode()}],
            "tools": [],
            "parallel_tool_calls": False,
            "store": False,
            "max_output_tokens": selection.settings.max_output_tokens,
            "reasoning": None if effort is None else {"effort": effort},
        }

    def session(self, run_id, brief_digest):
        """A metered session for one run: `call(identity, item)`."""
        selection, record = self.open(run_id, brief_digest)
        ledger = self._ledger(run_id)
        ledger.freeze(self._manifest(record))
        return _Session(self, selection, record, ledger)


class _Session:
    def __init__(self, task, selection, record, ledger):
        self.task, self.selection, self.record, self.ledger = (
            task,
            selection,
            record,
            ledger,
        )
        self.transport = task.model.transport_for(selection)

    def _unresolved(self):
        operations = self.ledger.status(owner=self.task.owner)["operations"]
        return any(op["state"] == "RESERVED" for op in operations)

    def call(self, identity, item):
        """One metered call; returns `(request, response)` or raises
        `TaskStopped` with a typed stop."""
        request = self.task.request(self.selection, item)
        try:
            response = request_model(
                self.ledger,
                owner=self.task.owner,
                identity=identity,
                request=request,
                credential_file=None,
                transport=self.transport,
                provider=self.selection,
                sleep=self.task.sleep,
            )
        except ProviderCallFailed as error:
            raise TaskStopped(
                {
                    "status": (
                        "RECONCILIATION_REQUIRED"
                        if self._unresolved()
                        else "PROVIDER_REJECTED"
                    ),
                    "outcome": error.outcome.value,
                }
            ) from None
        except ValueError as error:
            raise TaskStopped(_stopped(str(error), self._unresolved())) from None
        return request, response

    def usage(self):
        used = self.ledger.status(owner=self.task.owner)["used"]
        return {
            "provider_attempts": used["provider_attempts"],
            "provider_nanodollars": used["provider_nanodollars"],
            "run_cap_nanodollars": self.record["ceilings"]["provider_nanodollars"],
        }


def reply_json(response):
    """The one JSON object a closed reply holds, or a typed code (str)."""
    output = response.get("output") if type(response) is dict else None
    if type(output) is not list:
        return None, "no_output"
    parts = []
    for item in output:
        if type(item) is not dict:
            return None, "malformed_output"
        if item.get("type") == "function_call":
            return None, "tool_call_in_reply"  # no tool was offered
        if item.get("type") == "message":
            for block in item.get("content") or []:
                if type(block) is dict and block.get("type") == "output_text":
                    parts.append(block.get("text") or "")
    text = "".join(parts).strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        value = json.loads(text)
    except ValueError:
        return None, "reply_not_json"
    if type(value) is not dict:
        return None, "reply_not_an_object"
    return value, None
