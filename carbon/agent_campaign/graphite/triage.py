"""The phase-2 backfill: triage and method-card extraction under a grant.

GRAPHITE-01 phase 2 (plan §4 steps 2-3; §7 phase 2). One Reader call per
stored abstract, through the existing metered path:

- **Model.** The Reader's current rung from the phase-1 ladder (cheapest by
  default; escalation only by the ladder's rule), on an Engy adapter, with
  `TRIAGE_SETTINGS` (GRAPHITE-D13). The run records its selection once and
  keeps it on resume.
- **Metering.** Every call goes through `research_agent.request_model` on a
  `research_ledger.CampaignLedger`: reservation before dispatch, settlement
  from Engy's reported charge, bounded rate-limit retries under new
  reservations, typed failures, and replay of a finished call without
  resending it. This module adds no metering of its own.
- **Grant.** A run needs an exact `SpendingGrant` for provider `graphite`
  (so a `HUMAN_INPUT` document is refused) that has not expired. A new run is
  opened only while the grant permits another run and while every earlier
  run's settled and reserved spend, plus this run's worst case and the
  cleanup allowance, stays within the ceiling: the controller's arithmetic
  (`controller.CampaignController.launch`), applied to backfill runs
  (GRAPHITE-D15). Each run's ledger is frozen with the grant's
  `worst_case_run_cost` as its money cap and `max_calls` as its call cap, so
  the run stops when the next reservation would pass either.
- **Resume.** A record with a card or a rejection is skipped. A call that
  finished before a crash replays from the ledger without being paid again.
  A call in flight at a crash keeps its full reservation and stops the run
  as `RECONCILIATION_REQUIRED`; it is never resent.
- **Stops are typed.** `COMPLETED`, `STOPPED_CAP` (with the dimension),
  `RECONCILIATION_REQUIRED`, `PROVIDER_REJECTED` (with the typed outcome).
  Infrastructure stops are never literature findings.
"""

from __future__ import annotations

import datetime
import json
import time
from decimal import ROUND_FLOOR, Decimal
from pathlib import Path

from carbon.development_session.data import write_once
from carbon.development_session.model_provider import select
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_agent import (
    ProviderCallFailed,
    request_model,
)
from carbon.development_session.research_ledger import VERSION, CampaignLedger

from ..grant import SpendingGrant
from ..provider import identifier
from . import method_cards
from .ladder import Ladder
from .literature_fetch import QUERY_SET, RawStore
from .model import ENGY_ADAPTERS
from .provider import PROVIDER
from .roles import RoleName

RUN_SCHEMA = "carbon.graphite.backfill-run.v1"
OWNER = "graphite-reader"
NANO_PER_USD = Decimal(10) ** 9
#: Triage settings (GRAPHITE-D13). An abstract request is a few kilobytes, so
#: the smallest input window the selection accepts holds it; 1,024 output
#: tokens hold a card. Each call's reservation is computed from these and the
#: model's listed price (`ModelSelection.reservation_nano`).
TRIAGE_SETTINGS = {
    "max_input_tokens": 16384,
    "max_output_tokens": 1024,
    "reasoning_effort": "low",
    "timeout_seconds": 120,
}
#: The most model calls one backfill run makes (rate-limit retries count).
MAX_CALLS_PER_RUN = 3000
_LIMITS = {
    "provider timeout cannot fit remaining campaign time": "elapsed_seconds",
    # The request outgrew the input bound: a size limit, not an outage.
    "cumulative history/schema token reservation exhausted": "input_tokens",
    "campaign elapsed-time exhausted or clock regressed": "elapsed_seconds",
}


def _stopped(text, unresolved):
    """A typed stop for a refusal raised by the metered call path. The texts
    are Carbon's own messages, never provider text."""
    if text.startswith("miner budget: "):
        return {"status": "STOPPED_CAP", "dimension": text[len("miner budget: ") :]}
    if text in _LIMITS:
        return {"status": "STOPPED_CAP", "dimension": _LIMITS[text]}
    if unresolved or "reconcil" in text or "uncertain" in text:
        return {"status": "RECONCILIATION_REQUIRED"}
    return {"status": "STOPPED_INFRA", "detail": "provider_response_incomplete"}


class BackfillRefused(ValueError):
    """The backfill cannot run; nothing was reserved or sent."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def check_grant(grant, model, now):
    """The grant authorizes this provider, in USD, now, for this model."""
    if type(grant) is not SpendingGrant:
        # A document, a template full of HUMAN_INPUT, or None: no grant.
        raise BackfillRefused("spending_grant_required")
    if grant.provider != PROVIDER:
        raise BackfillRefused("grant_provider_mismatch")
    if grant.currency != "USD":
        raise BackfillRefused("grant_currency_must_be_usd")
    if now >= grant.expires_at:
        raise BackfillRefused("grant_expired")
    if not callable(getattr(model, "transport_for", None)):
        raise BackfillRefused("model_access_required")
    if model.live and getattr(model, "grant", None) != grant:
        raise BackfillRefused("live_model_grant_mismatch")


def _nano(amount):
    return int((amount * NANO_PER_USD).to_integral_value(rounding=ROUND_FLOOR))


def ceilings(grant, max_calls):
    """A run's ledger caps: the grant's worst case and the call cap."""
    return {
        "epochs": 0,
        "research_trials": 0,
        "final_replicas": 0,
        "numerical_milliseconds": 0,
        "reference_trajectories": 0,
        "reference_invocations": 0,
        "provider_attempts": max_calls,
        "provider_nanodollars": _nano(grant.worst_case_run_cost),
        "retained_bytes": None,
    }


def selection_for(model, *, rung_model, adapter_id):
    if adapter_id not in ENGY_ADAPTERS:
        raise BackfillRefused("engy_adapter_required")
    selection = select(
        provider_id=adapter_id,
        model_id=rung_model,
        credential={"kind": "file", "reference": model.credential_reference},
        settings=TRIAGE_SETTINGS,
    )
    model.transport_for(selection)  # refuses before anything is opened
    return selection


class Backfill:
    """Backfill runs over one raw store, writing into one card store."""

    def __init__(
        self,
        *,
        root,
        raw,
        grant,
        model,
        adapter_id="engy-anthropic",
        max_calls=MAX_CALLS_PER_RUN,
        clock=time.time,
        now=None,
        sleep=time.sleep,
    ):
        root = Path(root)
        if not root.is_absolute() or root.is_symlink():
            raise ValueError("the backfill root is private and absolute")
        if type(raw) is not RawStore:
            raise TypeError("exact RawStore required")
        if type(max_calls) is not int or not 1 <= max_calls <= MAX_CALLS_PER_RUN:
            raise ValueError(f"max_calls is 1-{MAX_CALLS_PER_RUN}")
        moment = now() if now else datetime.datetime.now(datetime.UTC)
        check_grant(grant, model, moment)
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        (root / "runs").mkdir(exist_ok=True, mode=0o700)
        self.root, self.raw, self.grant, self.model = root, raw, grant, model
        self.adapter_id, self.max_calls = adapter_id, max_calls
        self.clock, self.sleep = clock, sleep
        self.cards = method_cards.CardStore(root / "cards")
        self.ladder = Ladder(root / "ladder")

    # -- runs and the grant ---------------------------------------------------------------
    def _run_dir(self, run_id):
        identifier(run_id, "run_id")
        return self.root / "runs" / run_id

    def _ledger(self, run_id):
        return CampaignLedger(self._run_dir(run_id) / "ledger", clock=self.clock)

    def committed_nano(self):
        """Settled plus still-reserved provider spend of every run."""
        total = 0
        for run in sorted((self.root / "runs").iterdir()):
            if (run / "ledger" / "campaign.sqlite3").exists():
                status = self._ledger(run.name).status(owner=OWNER)
                total += status["used"]["provider_nanodollars"]
        return total

    def _open(self, run_id):
        """Open a new run under the grant, or verify the run being resumed."""
        directory = self._run_dir(run_id)
        record_path = directory / "run.json"
        model_id = self.ladder.model(RoleName.READER)
        if record_path.exists():
            opened = json.loads(record_path.read_bytes())
            model_id = opened["selection"]["model"]
        selection = selection_for(
            self.model, rung_model=model_id, adapter_id=self.adapter_id
        )
        record = {
            "schema": RUN_SCHEMA,
            "run_id": run_id,
            "grant_id": self.grant.grant_id,
            "selection": selection.record(),
            "role": RoleName.READER.value,
            "rung": self.ladder.rung(RoleName.READER),
            "prompt_digest": method_cards.PROMPT_DIGEST,
            "query_set_digest": QUERY_SET.digest,
            "ceilings": ceilings(self.grant, self.max_calls),
            "elapsed_seconds": self.grant.max_runtime_s,
            "live_inference": bool(self.model.live),
        }
        if record_path.exists():
            if json.loads(record_path.read_bytes()) != {
                **record,
                "rung": opened["rung"],
            }:
                raise BackfillRefused("run_record_mismatch")
            return selection, opened
        runs = [
            p for p in (self.root / "runs").iterdir() if p.is_dir() and p.name != run_id
        ]
        if len(runs) >= self.grant.permitted_runs:
            raise BackfillRefused("run_limit_reached")
        committed = Decimal(self.committed_nano()) / NANO_PER_USD
        if (
            committed + self.grant.worst_case_run_cost + self.grant.cleanup_allowance
            > self.grant.monetary_ceiling
        ):
            raise BackfillRefused("grant_ceiling_reached")
        directory.mkdir(mode=0o700, exist_ok=True)
        write_once(record_path, canonical(record))
        return selection, record

    def _manifest(self, record):
        return {
            "schema": VERSION,
            "ceilings": record["ceilings"],
            "elapsed_seconds": record["elapsed_seconds"],
            "campaign_id": record["run_id"],
            "implementation": "graphite-phase2-backfill",
            "objective": "graphite-reader:method-card-extraction",
            "sampling": "every stored record in first-retrieval order",
            "control": "graphite-backfill",
            "selection": "none",
            "replica_policy": "none",
            "provider": record["selection"]["provider_id"],
            "owner": OWNER,
        }

    @staticmethod
    def _unresolved(ledger):
        """A call whose outcome is unknown still holds its reservation."""
        return any(
            op["state"] == "RESERVED" for op in ledger.status(owner=OWNER)["operations"]
        )

    # -- the run -------------------------------------------------------------------------------
    def pending(self):
        """Stored records with neither a card nor a rejection, in order."""
        rows = []
        for address in self.raw.addresses():
            record = self.raw.record(address)
            if not self.cards.done(record, address):
                rows.append((address, record))
        return rows

    def run(self, run_id):
        """Run (or resume) one backfill run; returns its typed summary."""
        selection, record = self._open(run_id)
        ledger = self._ledger(run_id)
        ledger.freeze(self._manifest(record))
        transport = self.model.transport_for(selection)
        provenance = {
            "model": selection.model_id,
            "provider_id": selection.provider_id,
            "selection_digest": digest(canonical(selection.record())),
            "prompt_digest": method_cards.PROMPT_DIGEST,
            "run_id": run_id,
            "rung": record["rung"],
            "live_inference": bool(self.model.live),
        }
        made = rejected = 0
        stop = {"status": "COMPLETED"}
        for address, paper in self.pending():
            request = method_cards.extraction_request(selection, paper)
            try:
                response = request_model(
                    ledger,
                    owner=OWNER,
                    identity="card-" + address[7:47],
                    request=request,
                    credential_file=None,
                    transport=transport,
                    provider=selection,
                    sleep=self.sleep,
                )
            except ProviderCallFailed as error:
                stop = {
                    "status": (
                        "RECONCILIATION_REQUIRED"
                        if self._unresolved(ledger)
                        else "PROVIDER_REJECTED"
                    ),
                    "outcome": error.outcome.value,
                }
                break
            except ValueError as error:
                text = str(error)
                if "token reservation exhausted" in text:
                    # This abstract cannot fit the triage window; nothing sent.
                    self.cards.put_rejection(
                        address,
                        {
                            "record_digest": address,
                            "code": "request_exceeds_triage_window",
                            "run_id": run_id,
                        },
                    )
                    rejected += 1
                    continue
                stop = _stopped(text, self._unresolved(ledger))
                break
            call = {
                "request_digest": digest(canonical(request)),
                "response_digest": digest(canonical(response)),
            }
            try:
                extraction = method_cards.parse_extraction(response)
            except method_cards.ExtractionRejected as error:
                self.cards.put_rejection(
                    address,
                    {
                        "record_digest": address,
                        "code": error.code,
                        "run_id": run_id,
                        **call,
                        "prompt_digest": method_cards.PROMPT_DIGEST,
                        "model": selection.model_id,
                    },
                )
                rejected += 1
                continue
            card = method_cards.make_card(
                paper, address, extraction, {**provenance, **call}
            )
            self.cards.put_card(card)
            made += 1
        status = ledger.status(owner=OWNER)
        return {
            **stop,
            "run_id": run_id,
            "model": selection.model_id,
            "cards_made": made,
            "rejected": rejected,
            "pending": len(self.pending()),
            "provider_attempts": status["used"]["provider_attempts"],
            "provider_nanodollars": status["used"]["provider_nanodollars"],
            "run_cap_nanodollars": record["ceilings"]["provider_nanodollars"],
        }
