# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""The decision-aware exam rule, registered as a prospective proposal.

OWNER-BATTERY-DECISION-AWARE-PROPOSAL-01 (2026-10-01): "propose the
decision-aware component prospectively, and keep both rankings reported."

- **A proposal, not a replacement.** The deciding rule stays the frozen,
  approved `carbon.battery.exam.v1` (OD-2, `exam.DEVELOPMENT_RULE`) until the
  proposal's own approval changes that. This record is not in `exam.RULES`,
  so no deployment can select it; a test holds that.
- **Prospective.** Results already scored keep the meaning of the rule they
  were scored with (invariant 10). Nothing here rescores or reinterprets them.
- **No new number.** The profile is EV2's development-chosen
  `dar-p0-r100-a0`, copied from the frozen EV2 contract; its constraints,
  uncertainty bands and mistake costs are that contract's, pinned by its
  digest. Gates stay mandatory and unchanged.
- **Both halves of the evidence travel with it** (`EVIDENCE`): it closes the
  boundary-optimist blind spot, and it did not rank real models better on the
  EV2 panel.

Exploratory engineering evidence feeds this; it is not exam qualification,
and MQ-008 is untouched.
"""

from __future__ import annotations

from .contract import digest

#: The EV2 contract the proposal's decision component reads (constraints,
#: uncertainty bands, mistake costs), pinned by digest.
DECISION_CONTRACT = {
    "path": "carbon/battery/value/contracts/ev2-charge-protocol-selection.v1.json",
    "contract_id": "ev2-battery-charge-protocol-selection",
    "digest": "sha256:1877091055d1dac2515da5aa05bf4f0ad56cf3376045d73086dcf1f0848ce743",
}

#: The profile proposed: EV2's `decision_aware_profiles[0]`, unchanged.
PROFILE_ID = "dar-p0-r100-a0"

#: The deciding rule, and the evidence both rules are reported against.
DECIDING_RULE = {
    "id": "carbon.battery.exam.v1",
    "authority": "OWNER-BATTERY-TESTNET-01 OD-2",
    "value_rule_id": "control-exam-v1",
}

EVIDENCE = {
    "document": "docs/development/BATTERY_ENGINEERING_VALUE_EV2.md",
    "results": "docs/development/evidence/ev2-2026-10-01/results.json",
    "ranking_real_models": {
        "measure": "Kendall tau with the decision-loss ranking, verification conditions",
        "proposed": 0.20193241203216045,
        "deciding": 0.2980907034760464,
        "basis": "results.json comparison.<rule>.tau_verification",
        "reading": "the proposed rule did not rank real models better on this panel",
    },
    "boundary_optimist": {
        "measure": "eligible members scored at or below the boundary-optimist control",
        "proposed": "0 of 14 (the control ranks below every eligible member)",
        "deciding": "14 of 14 (the control ranks at or above every eligible member)",
        "basis": "results.json summary.boundary_optimist_check",
        "reading": "the deciding rule does not catch optimism at the safety limits",
    },
}

PROPOSAL = {
    "schema": "carbon.battery.exam-rule-proposal.v1",
    "id": "carbon.battery.exam.decision-aware.proposed",
    "version": 1,
    "status": "PROPOSED_NOT_DECIDING",
    "authority": "OWNER-BATTERY-DECISION-AWARE-PROPOSAL-01",
    "deciding_rule": DECIDING_RULE,
    "profile_id": PROFILE_ID,
    "decision_contract": DECISION_CONTRACT,
    "gates": "mandatory and unchanged (carbon.battery.exam GATES)",
    "evidence": EVIDENCE,
    "adoption": (
        "needs its own prospective owner approval; until then the deciding "
        "rule is carbon.battery.exam.v1"
    ),
    "qualification": False,
    "reward": False,
}


def proposal_digest():
    return digest(PROPOSAL)


def profile(contract):
    """The proposed profile document, read from the pinned contract."""
    for document in contract["scoring_candidates"]["decision_aware_profiles"]:
        if document["id"] == PROFILE_ID:
            return document
    raise KeyError(PROFILE_ID)
