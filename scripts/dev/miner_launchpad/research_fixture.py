"""A synthetic campaign for seeing the research surface (RSURF-D7).

SYNTHETIC FIXTURE. Nothing here is a campaign, a result or evidence:
- the runner refuses every operation that starts work, and every control;
- it opens no ledger, writes no campaign root and reads no chain;
- every document it serves says `SYNTHETIC_FIXTURE`, and its ids start with
  `fixture-`;
- it lives under `scripts/dev`, outside the `carbon` package, so no research,
  evaluation or settlement path can import it.

It is Challenge-neutral: it picks the first implemented Challenge whose
campaign declares a research view (battery, today) and draws through that
view, exactly as a real campaign does. The practice predictions, scores,
spend, journal and outcomes are made up here. The per-case references are
the Challenge's own public practice references, read through its view.
"""

from __future__ import annotations

import functools
import math
import random
import time

from scripts.dev.miner_launchpad.campaign_view import (
    NOTE_KINDS,
    NOTE_SCHEMA,
    build,
    contract_section,
    note_text,
    research_view_for,
)
from scripts.dev.miner_launchpad.controller import Rejected

CAMPAIGN = "fixture-demo-campaign-0001"
PRINCIPAL = "fixture-principal"
EVIDENCE = "SYNTHETIC_FIXTURE"
RUNS = 7
NOTES_MAX = 200
#: Made-up practice scores by run: descriptive, lower is better.
SCORES = (0.412, 0.371, 0.388, 0.247, 0.229, 0.214, 0.196)
COMPONENT_SHAPE = (1.10, 0.85, 1.30, 0.75)


def fixture_challenge():
    """The first implemented Challenge whose campaign declares a research
    view, as {"id", "version"}; None when there is none."""
    from carbon.challenge_registry.campaigns import implemented_campaigns

    for entry, campaign in implemented_campaigns():
        if campaign.research_view is not None:
            return {"id": entry.challenge_id, "version": entry.version}
    return None


def _strategy(challenge, backbone, width):
    return {
        "schema_version": "1.0",
        "challenge_id": challenge["id"],
        "backbone": backbone,
        "parameters": {"steps": 2000, "width": width, "depth": 3},
    }


class FixtureRunner:
    """A read-only stand-in for `RunnerAdapter` that serves one synthetic
    campaign. Every operation that starts or changes work is refused."""

    principal = PRINCIPAL

    def __init__(self, *, clock=time.time):
        self.clock = clock
        self.created = clock()
        self.challenge = fixture_challenge()
        self.view = research_view_for(self.challenge)
        contract = contract_section(self.challenge, "FULL", ("FULL",))
        self.contract = contract
        selectors = [
            m.get("selector")
            for m in (contract or {}).get("rebuildable_models", [])
            if m.get("selector")
        ] or ["mlp"]
        self.backbones = [selectors[i % len(selectors)] for i in range(RUNS)]
        self.notes = [
            {
                "sequence": 40,
                "body": {
                    "schema": NOTE_SCHEMA,
                    "note_kind": "plan",
                    "text": (
                        "Plan from an MCP client: hold the width at 128 and try "
                        "one other family before freezing epoch 2."
                    ),
                },
            },
            {
                "sequence": 41,
                "body": {
                    "schema": NOTE_SCHEMA,
                    "note_kind": "observation",
                    "text": (
                        "Notes are text: <b>this is not bold</b> and "
                        "<script>this never runs</script>."
                    ),
                },
            },
        ]

    # ---- What the controller and the operations table ask of a host.

    def preflight(self):
        return {
            "available": False,
            "status": EVIDENCE,
            "reason": "a_fixture_controller_launches_nothing",
        }

    def recent(self):
        return [self.own()]

    def get(self, identity):
        if identity != CAMPAIGN:
            raise Rejected("research_run_unavailable", 404)
        return self.own()

    def configured(self):
        # New work needs a runnable profile, and a fixture has none.
        raise Rejected("fixture_read_only", 409)

    def owner(self):
        return {"principal": PRINCIPAL}

    def owned_campaign(self, identity):
        if identity != CAMPAIGN:
            raise Rejected("research_run_unavailable", 404)
        # Not a product campaign: the campaign gate refuses new work to it too.
        return {"id": CAMPAIGN, "root": None, "kind": "fixture"}

    def replayed(self, profile, request, operation):
        return None

    def registration(self, profile):
        raise Rejected("fixture_read_only", 409)

    def launch(self, value, key):
        raise Rejected("fixture_read_only", 409)

    def control(self, identity, action):
        raise Rejected("fixture_read_only", 409)

    def observe_admitted(self, admitted, request):
        return self.own()

    def campaign_view_admitted(self, admitted, request):
        return self.view_document(
            practice_case=request.get("practice_case"),
            experiment=request.get("experiment"),
        )

    def note_admitted(self, admitted, request):
        """Kept in memory only, so the journal can be tried in the demo."""
        kind = request["note_kind"]
        if kind not in NOTE_KINDS:
            raise Rejected("note_kind_unknown")
        text = note_text(request["note"])
        sequence = max(n["sequence"] for n in self.notes) + 1
        self.notes.append(
            {
                "sequence": sequence,
                "body": {"schema": NOTE_SCHEMA, "note_kind": kind, "text": text},
            }
        )
        del self.notes[:-NOTES_MAX]
        return {
            "posted": True,
            "note_kind": kind,
            "characters": len(text),
            "shown_as": "untrusted text",
            "evidence": EVIDENCE,
        }

    def halt_admitted(self, admitted, request):
        raise Rejected("fixture_read_only", 409)

    def resume_admitted(self, admitted, request):
        raise Rejected("fixture_read_only", 409)

    def close(self):
        return None

    # ---- The synthetic campaign.

    def view_document(self, *, practice_case=None, experiment=None):
        return build(
            self.own(),
            view=self.view,
            contract=self.contract,
            notes=list(self.notes),
            feedback_mode="FULL",
            predictions=self.predictions,
            practice_case=practice_case,
            experiment=experiment,
            now=self.clock(),
            fixture=True,
        )

    def own(self):
        started = self.created - 47 * 60
        components = [c for c, _ in self.view.components] if self.view else []
        experiments = []
        for run in range(1, RUNS + 1):
            score = SCORES[run - 1]
            experiments.append(
                {
                    "id": f"fixture-run-{run:02d}",
                    "provenance": EVIDENCE,
                    "recipe": _strategy(
                        self.challenge, self.backbones[run - 1], 64 * (1 + run % 3)
                    ),
                    "backbone": self.backbones[run - 1],
                    "recipe_digest": "sha256:" + f"{run:02d}" * 32,
                    "summary": {
                        "score": score,
                        "important_score": round(score * 1.18, 4),
                        "eligible": run != 3,
                        "n_cases": 200,
                        "n_scored": 200 if run != 3 else 194,
                        "n_reference_invalid": 0,
                        "n_failed_infra": 0,
                        "gate_failures": {"voltage_ceiling": 6} if run == 3 else {},
                        "components": {
                            name: round(
                                score
                                * COMPONENT_SHAPE[i % 4]
                                * (1 + 0.04 * ((run + i) % 3)),
                                4,
                            )
                            for i, name in enumerate(components)
                        },
                    },
                    "fit": {
                        "final_loss": round(0.02 * score, 6),
                        "n_params": 12000 * (1 + run % 3),
                        "train_s": 40.0 + 6 * run,
                    },
                    "backend": {"kind": EVIDENCE},
                    # A synthetic learning curve, so the renderer has one to
                    # draw. Real battery practice records none (RSURF-D3).
                    "inline_curve": [
                        {
                            "step": step,
                            "data_loss": round(
                                0.9 * math.exp(-step / (260 + 40 * run))
                                + 0.004 * score,
                                6,
                            ),
                        }
                        for step in range(0, 2001, 125)
                    ],
                    "accepted_improvement": False,
                    "adaptively_seen": True,
                }
            )
        return {
            "schema": "carbon.launchpad.own-research.v1",
            "id": CAMPAIGN,
            "campaign_id": CAMPAIGN,
            "mode": EVIDENCE,
            "execution_label": "Synthetic fixture: not a campaign, not evidence",
            "state": "PRACTICING",
            "selects": "agent",
            "challenge": self.challenge,
            "agent": "carbon-autoresearch",
            "reasoning": "fixture-provider:fixture-model",
            "compute": "local-isolated-cpu",
            "admission": EVIDENCE,
            "runtime_revision": "fixture",
            "started_unix": started,
            "deadline_unix": None,
            "attempted_experiments": RUNS + 1,
            "completed_experiments": RUNS,
            "experiments": experiments,
            "hypotheses": [
                {
                    "sequence": 3,
                    "hypothesis": "A wider MLP lowers the voltage error without hurting temperature.",
                    "expected_effect": "Voltage component down by a tenth.",
                },
                {
                    "sequence": 12,
                    "hypothesis": "A second family fits the capacity checkpoints better.",
                    "expected_effect": "Capacity component down; others flat.",
                },
                {
                    "sequence": 27,
                    "hypothesis": "Fewer steps with a higher rate keep the same score in half the time.",
                    "expected_effect": "Score within 0.01, training time halved.",
                },
            ],
            "current_hypothesis": {
                "hypothesis": "Fewer steps with a higher rate keep the same score in half the time."
            },
            "decisions": [
                {
                    "sequence": 18,
                    "reason": "Run 3 failed the voltage ceiling on 6 cases; discard it.",
                    "evidence": "practice gates",
                },
                {
                    "sequence": 22,
                    "reason": "Freeze run 4 for epoch 1: lowest score among runs that passed every gate.",
                    "evidence": "runs 1 to 4",
                },
            ],
            "capability_requests": [],
            "refusals": [],
            "epoch_outcomes": [
                {
                    "epoch": 1,
                    "status": "SELECTED",
                    "reason": "Run 4 was the best practiced recipe.",
                    "selected_by": "agent",
                }
            ],
            "candidate_freezes": [
                {
                    "epoch": 1,
                    "strategy": experiments[3]["recipe"],
                    "strategy_hash": "sha256:" + "4f" * 32,
                    "reason": "Lowest practice score among runs that passed every gate.",
                    "used_feedback": False,
                    "final_evidence": False,
                }
            ],
            "final_results": [
                {
                    "epoch": 1,
                    "mode": "DEVELOPMENT_EVALUATION",
                    "status": "VALIDATOR_OUTCOME",
                    "result": {
                        "state": "SCORED",
                        "submission_id": "fixture-submission-0001",
                        "evidence": EVIDENCE,
                        "nominated": False,
                        "waiting": None,
                        "screening": {
                            "eligible": True,
                            "gates_failed": [],
                            "score": 0.2531,
                            "important_score": 0.2894,
                            "pool_version": 3,
                        },
                        "finals": [],
                        "qualification": False,
                        "reward": False,
                    },
                }
            ],
            "journey": {
                "submitted_epochs": [1],
                "final_exams_remaining": 1,
                "frozen_awaiting_submission": False,
            },
            "operations": [
                *[
                    {
                        "id": f"fixture-op-{i:04d}",
                        "phase": "research_trial" if i % 2 else "agent_turn",
                        "state": "SUCCEEDED",
                    }
                    for i in range(1, 15)
                ],
                {
                    "id": "fixture-op-0015",
                    "phase": "research_trial",
                    "state": "RESERVED",
                },
            ],
            "usage": {
                "budget": {"provider_nanodollars": 50_000_000, "research_trials": 16},
                "available": {},
                "reserved": {"provider_nanodollars": 120_000, "research_trials": 1},
                "reported": {
                    "provider_nanodollars": 4_210_000,
                    "research_trials": RUNS + 1,
                    "numerical_milliseconds": 812_000,
                },
                "uncertain": {},
                "cost_basis": "Synthetic fixture figures, not a ledger.",
            },
            "official_eligible": False,
        }

    @functools.lru_cache(maxsize=16)  # noqa: B019 - one fixture per process
    def _predicted(self, run):
        """Synthetic predictions near the public references: worse early."""
        if self.view is None or self.view.case_ids is None:
            return None
        error = SCORES[run - 1] * 0.08
        out = {}
        for case in self.view.case_ids():
            reference = (self.view.reference(case) or {}).get("outputs") or {}
            rng = random.Random(f"{run}:{case}")
            phase, tilt = rng.uniform(0, math.pi), rng.uniform(-1, 1)
            predicted = {}
            for output in self.view.outputs:
                value = reference.get(output.name)
                if isinstance(value, (int, float)):
                    predicted[output.name] = value + error * abs(value or 1) * tilt
                elif (
                    isinstance(value, list)
                    and value
                    and isinstance(value[0], (int, float))
                ):
                    n = len(value)
                    spread = (max(value) - min(value)) or abs(value[0]) or 1
                    predicted[output.name] = [
                        v
                        + error
                        * spread
                        * (0.6 * math.sin(phase + 4 * i / n) + 0.4 * tilt)
                        for i, v in enumerate(value)
                    ]
            out[case] = predicted
        return out

    def predictions(self, task):
        if not task.startswith("fixture-run-"):
            return None, "no_worker_record"
        value = self._predicted(int(task.rsplit("-", 1)[1]))
        return (
            (value, None)
            if value is not None
            else (None, "no_public_practice_references")
        )
