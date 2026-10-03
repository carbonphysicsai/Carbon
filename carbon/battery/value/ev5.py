"""EV5, the battery Level 0 combined admission run: engineering before the freeze.

`docs/development/BATTERY_ENGINEERING_VALUE_EV5.md` (DRAFT) §8 lists the
engineering that may proceed before the freeze. This module is that work. It
is the battery adapter of the Challenge-neutral combined run
(`carbon.challenge_readiness.combined_run`), and it reads every value from a
registered record:

- **Conditions** (§3): 12 development and 12 verification conditions
  (`ev5_protected_conditions`), inside the battery Challenge's published input
  box and fresh against every EV1, EV2 and EV4 decision condition, read from
  their contracts (`conditions`).
- **Contract** (§2): EV4's contract with EV5's scenarios, case prefix and
  panel (`contract`). The decision contract, costs, bands, baseline, candidate
  grid, reference, models and scoring set are EV4's, unchanged. It is written
  to `CONTRACT` only at the freeze.
- **Panel** (§6): EV4's 100 members and 5 controls, unchanged, plus the Track A
  harness's admitted constructions as ATTACK_CONSTRUCTION members
  (`panel.attack_constructions`).
- **Plans** (§5): references and panel (`plans`), and optimizer verification
  after selection (`optimizer_plans`), built as EV4's were. The optimizer
  keeps EV4's maxima.
- **Confirmation** (§3): the public skeleton of the sealed set
  (`confirmation`). No case, input, seed or root is here. The batch is made
  and committed on the validator host (`seal_confirmation`), outside the
  testnet pool; only its public fingerprint enters the manifest.
- **Campaign**: `pod_control` campaign `ev5`. Its ceiling and the balance
  floor are operator configuration (POD-LEDGER-PRIVATE-01).
- **Freeze manifest** (`freeze_manifest`): refuses while the gate cutoff is
  unset, while a condition repeats one EV4 protects, while the panel's
  reconstructed members differ from EV4's frozen panel, or while the
  confirmation batch is unsealed.

Nothing here dispatches, spends or freezes, and no value is chosen here. H3's
localized measurement is near-limit false acceptance (`H3_MEASUREMENT`,
`h3_report`), descriptive and with no cutoff.

    python -m carbon.battery.value.ev5 seal-confirmation --config DEPLOYMENT.json
    python -m carbon.battery.value.ev5 freeze-manifest --out FILE \
        --confirmation-fingerprint sha256:<hex> --confirmation-sequence N
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import sys
from pathlib import Path

from carbon.challenge_readiness import combined_run as cr

from . import contract as ev
from . import ev5_protected_conditions as conditions_record
from . import false_acceptance as fa
from . import optimizer as op
from . import panel as pn
from .divergence import DECIDING_RULE

REPOSITORY = Path(__file__).resolve().parents[3]
SCHEMA = "carbon.battery.ev5.freeze-manifest.v1"
SOURCE = "docs/development/BATTERY_ENGINEERING_VALUE_EV5.md"
STUDY_SHEET = "docs/development/evidence/track-a-battery-l0-2026-10-02/study-sheet.json"
EVIDENCE = "docs/development/evidence/ev5-2026-10-03"
PLANS = f"{EVIDENCE}/plans"
CONTRACT = "carbon/battery/value/contracts/ev5-charge-protocol-selection.v1.json"
EV4_CONTRACT = ev.CONTRACTS / "ev4-charge-protocol-selection.v1.json"
EV4_FREEZE_MANIFEST = "docs/development/evidence/ev4-2026-10-01/freeze-manifest.json"
#: SR-2's run on EV4: the candidate EV5 compares with the deciding rule.
CANDIDATE_RECORD = "docs/development/evidence/sr-ev4-2026-10-02/sr2/results.json"
CAMPAIGN = "ev5"

#: Earlier studies whose decision conditions EV5 must not repeat (§3).
PRIOR_STUDIES = ("ev1", "ev2", "ev4")
#: What a condition must be fresh against before the freeze: every EV1, EV2
#: and EV4 decision condition, and every condition EV4 protects
#: (`ev4_protected_conditions`, which adds EV4's optimizer grids).
FRESH_AGAINST = (*PRIOR_STUDIES, "ev4_protected")

#: Pods per phase, from §7's table: references 2, panel 1, optimizer 3.
REFERENCE_SHARDS, PANEL_SHARDS, OPTIMIZER_SHARDS = 2, 1, 3

#: The confirmation batch's role on the validator host (an engineering label;
#: the role seeds the draws, so a fresh role gives a fresh batch).
CONFIRMATION_ROLE = "ev5-confirmation"

#: H2's constructed controls (§4): the one the gate must fail, and those it
#: must pass.
GATE_MUST_FAIL = ("boundary_optimist",)
GATE_MUST_PASS = ("oracle", "conservative", "rank_preserving_delay")
SIGN_ERROR_CONTROL = "localized_sign_error"

#: H3's localized measurement (OWNER-EXEC-APPROVALS-01, §8 item 3): near-limit
#: false acceptance (`false_acceptance.py`), registered descriptive. No cutoff
#: exists; making it a gate needs one, a science value (HUMAN_INPUT). The
#: SciML/technical lead may amend the definition before the freeze; the freeze
#: manifest pins the module's digest, so what is frozen is exactly what runs.
H3_MEASUREMENT = {
    "module": "carbon/battery/value/false_acceptance.py",
    "schema": fa.SCHEMA,
    "quantity": (
        "the worst constraint's near-limit false-acceptance rate: of the cases "
        "the reference resolves as FAIL (with the contract's bands), the share "
        "the model calls PASS (without bands)"
    ),
    "region": "the scoring set's published important region (near.near_cases)",
    "unmeasured": "a member missing any important case is None, never clean",
    "cutoff": None,
    "state": "DESCRIPTIVE",
    "amendable_before_freeze_by": "the SciML/technical lead (§8 item 3)",
}
H3_REPORT_SCHEMA = "carbon.battery.ev5.h3-report.v1"

#: OWNER-EV5-CAP-01, as recorded. The ceiling and the balance floor stay in the
#: operator's configuration, never here.
CAP = {
    "decision": "OWNER-EV5-CAP-01",
    "record": ".agent/DECISIONS.md",
    "option": "A: no in-run agents",
    "hard_cap_usd": 6,
    "inside": "OWNER-TRACK-A-L0-02's USD 25 Level 0 cap",
    "pods": (
        "RunPod A40 at no more than USD 0.49 per hour, at most 3 in parallel, "
        "termination verified"
    ),
    "campaign": CAMPAIGN,
    "ceiling_and_balance_floor": (
        "operator configuration (~/.runpod/campaigns.json), never committed "
        "(POD-LEDGER-PRIVATE-01)"
    ),
}
COMPUTE = (
    "RunPod A40 (<= USD 0.49/h), at most 3 in parallel; hard cap USD 6 "
    "(OWNER-EV5-CAP-01), counted inside OWNER-TRACK-A-L0-02's USD 25 Level 0 cap"
)
AUTHORITY_RECORD = (
    'OWNER-EV5-CAP-01, the owner on 2026-10-03: "Approve the cap". Option A of '
    "BATTERY_ENGINEERING_VALUE_EV5.md §7, with no in-run agents. The approval "
    "freezes nothing and dispatches nothing."
)
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}\Z")
_MISSING = object()


# --- conditions --------------------------------------------------------------------


def _contract_conditions(name):
    document, _ = ev.load(ev.CONTRACTS / f"{name}-charge-protocol-selection.v1.json")
    return tuple(tuple(c) for s in ev.scenarios(document) for c in s["conditions"])


def prior_conditions():
    """Conditions earlier studies used, by source, read from their records:
    each study's contract, and EV4's protected set."""
    from . import ev4_protected_conditions

    out = {name: _contract_conditions(name) for name in PRIOR_STUDIES}
    out["ev4_protected"] = tuple(sorted(ev4_protected_conditions.PROTECTED))
    return out


def box():
    """The battery Challenge's published input box for (t_amb, soc0)."""
    from ..challenge import INPUT_BOUNDS

    return (tuple(INPUT_BOUNDS["t_amb_c"]), tuple(INPUT_BOUNDS["soc0"]))


def _splits():
    return {
        "development": conditions_record.EV5_DEVELOPMENT,
        "verification": conditions_record.EV5_VERIFICATION,
    }


def conditions():
    """EV5's conditions by split: inside the published box, never repeated,
    and fresh against every EV1, EV2 and EV4 decision condition."""
    prior = prior_conditions()
    return cr.check_conditions(
        _splits(), box(), {name: prior[name] for name in PRIOR_STUDIES}
    )


def scenarios():
    """The contract's scenarios: one condition each, as in EV2 and EV4."""
    return {
        split: [
            {"id": f"{split[0].upper()}-T{t:g}-S{s:.2f}", "conditions": [[t, s]]}
            for t, s in group
        ]
        for split, group in conditions().items()
    }


# --- the contract ------------------------------------------------------------------


def contract():
    """EV5's contract: EV4's, with EV5's scenarios, case prefix, panel,
    budgets and authority. The hypotheses are registered in the freeze
    manifest; H1's paired rule is not a contract-declared profile, so the
    contract carries no `paired_comparison`."""
    base, _ = ev.load(EV4_CONTRACT)
    document = copy.deepcopy(base)
    acceptance = {
        k: base["acceptance"][k]
        for k in ("rule_selection", "verification", "success_condition")
    }
    acceptance["hypotheses"] = {
        "registered_in": (
            "the EV5 freeze manifest (carbon.battery.value.ev5.freeze_manifest), "
            f"from {SOURCE} §4"
        )
    }
    cases = sum(len(group) for group in conditions().values())
    document.update(
        contract_id="ev5-battery-charge-protocol-selection",
        case_prefix="ev5",
        panel="ev5",
        scenarios=scenarios(),
        acceptance=acceptance,
        budgets={
            "reference_solves_max": cases * len(ev.candidates(base)),
            "reconstructions_max": len(pn.members("ev5")),
            "compute": COMPUTE,
        },
        authority={
            "record": AUTHORITY_RECORD,
            "chain": False,
            "reward": False,
            "changes_testnet_rule": False,
            "qualification": False,
        },
    )
    return ev.validate(document)


# --- the panel ---------------------------------------------------------------------


def panel_entries(panel):
    """Panel members in the form EV4's freeze manifest records them."""
    return [
        {
            "member": member,
            "family": label,
            "backbone": pn.family(strategy),
            "strategy": strategy,
            "seed": seed,
        }
        for member, label, strategy, seed in pn.members(panel)
    ]


def ev4_frozen_panel(repository=REPOSITORY):
    """EV4's frozen panel and controls, from its committed freeze manifest."""
    manifest = json.loads((Path(repository) / EV4_FREEZE_MANIFEST).read_text())
    return manifest["panel"], manifest["controls"]


def panel_record():
    entries = panel_entries("ev5")
    kinds = pn.kinds("ev5")
    real = [e for e in entries if kinds[e["member"]] == cr.RECONSTRUCTED]
    attacks = [e for e in entries if kinds[e["member"]] == cr.ATTACK_CONSTRUCTION]
    return {
        "panel": "ev5",
        "members": len(entries),
        "digest": cr.digest(entries),
        "reconstructed": {
            "members": len(real),
            "digest": cr.digest(real),
            "same_as": EV4_FREEZE_MANIFEST,
        },
        "attack_constructions": {
            "kind": cr.ATTACK_CONSTRUCTION,
            "origin": pn.ATTACK_ORIGIN,
            "families": list(pn.ATTACK_FAMILIES),
            "members": [e["member"] for e in attacks],
            "digest": cr.digest(attacks),
            "refused": pn.attack_constructions()["refused"],
            "participant_code": "out of scope at Level 0, refused by name",
            "graphite": "not added: option A has no in-run agents (OWNER-EV5-CAP-01)",
        },
        "controls": list(pn.CONTROLS),
    }


# --- plans -------------------------------------------------------------------------


def plans():
    """EV5's reference and panel plans, named as committed at the freeze."""
    from scripts.dev.exam_design import value_plans as vp

    return {
        **vp.refs_plans(REFERENCE_SHARDS, CONTRACT, "ev5"),
        **vp.panel_plans(PANEL_SHARDS, CONTRACT, "ev5"),
    }


def optimizer_plans(jobs, shards=OPTIMIZER_SHARDS):
    """The optimizer's verification plans, after selection. Refuses more jobs
    than Mode D and Mode X may solve (EV4's maxima, unchanged)."""
    from scripts.dev.exam_design import value_plans as vp

    vp.refuse_over_maxima(jobs)
    return vp.verify_plans(shards, f"{PLANS}/optimizer-jobs.json")


def optimizer_maxima():
    """EV4's optimizer maxima, which EV5 keeps (§2, §5)."""
    return {
        "mode_d_solves": op.MAX_MODE_D_SOLVES,
        "mode_x_solves": op.MAX_MODE_X_SOLVES,
        "designs": op.MAX_DESIGNS,
        "k": op.K,
    }


# --- the confirmation set ------------------------------------------------------------


def confirmation(repository=REPOSITORY):
    """The sealed confirmation set's public skeleton, from the frozen L0 study
    sheet. It holds no case, input, seed or root."""
    sheet = json.loads((Path(repository) / STUDY_SHEET).read_text())
    population = sheet["population"]["confirmation"]
    return {
        "study_sheet": STUDY_SHEET,
        "source": population["source"],
        "cases": population["cases"],
        "hidden_duplicates": population["hidden_duplicates"],
        "batch_size": population["cases"] + population["hidden_duplicates"],
        "law": population["law"],
        "subgroups": population["subgroups"],
        "custody": population["custody"],
        "role": CONFIRMATION_ROLE,
        "made_on": (
            "the validator host only (seal_confirmation: seeds.make_batch from "
            "the deployment's committed root, then SeedJournal.commit before any "
            "use); never in the repository, never in the testnet pool"
        ),
        # OWNER-EV5-Q3-01: private inputs never enter a committed plan or
        # rented compute (POOLS-D2).
        "solved_on": (
            "the operator host only (OWNER-EV5-Q3-01): the private cases are "
            "solved and the panel's predictions on them made there; never in "
            "a committed pod plan, never on rented compute"
        ),
    }


def sealed(commitment):
    """The batch's public commitment, checked, or None: its journal
    fingerprint and sequence, both public."""
    if (
        type(commitment) is not dict
        or set(commitment) != {"fingerprint", "journal_sequence"}
        or type(commitment["fingerprint"]) is not str
        or not _FINGERPRINT.fullmatch(commitment["fingerprint"])
        or type(commitment["journal_sequence"]) is not int
        or commitment["journal_sequence"] < 0
    ):
        return None
    return dict(commitment)


def seal_confirmation(config_path, repository=REPOSITORY):
    """Make and commit the sealed confirmation batch on the validator host.

    The batch is the study sheet's: `cases` fresh draws from the deployment's
    committed private root under `CONFIRMATION_ROLE`, plus `hidden_duplicates`
    (`seeds.make_batch`). It is committed to the deployment's seed journal
    under its writer lock, and never recorded in the validator state, so no
    screening rotation or finalist comparison can claim it. The validator is
    never started or recovered.

    Idempotent: a rerun recalls the same batch and commitment. Refused when the
    journal already holds a different batch under the role, since a second
    batch would share the first one's draws. Returns only public values.
    """
    from carbon.battery import deployment, seeds

    skeleton = confirmation(repository)
    count, duplicates = skeleton["batch_size"], skeleton["hidden_duplicates"]
    target = deployment.validator(config_path, repository=repository, readonly=True)
    with deployment.writer(target):
        batch = seeds.make_batch(
            target.root, target.pin, CONFIRMATION_ROLE, count, duplicates
        )
        prior = {
            e["fingerprint"]
            for e in target.journal.public()
            if e["kind"] == "batch" and e["role"] == CONFIRMATION_ROLE
        }
        if prior - {batch.fingerprint}:
            raise cr.CombinedRunError(
                "confirmation_role_reused",
                "the journal holds another batch under this role",
            )
        committed = target.seal_batch(
            CONFIRMATION_ROLE, count=count, duplicates=duplicates
        )
    return {
        "role": CONFIRMATION_ROLE,
        "cases": skeleton["cases"],
        "hidden_duplicates": duplicates,
        "newly_committed": not prior,
        "commitment": sealed(
            {
                "fingerprint": committed.fingerprint,
                "journal_sequence": committed.sequence,
            }
        ),
    }


# --- rules, hypotheses and the gate cutoff --------------------------------------------


def gate_cutoff():
    """`admissibility.THRESHOLD_BANDS`, read and never set; `_MISSING` when
    the module has no such value."""
    from . import admissibility

    return getattr(admissibility, "THRESHOLD_BANDS", _MISSING)


def cutoff_blocker(cutoff):
    if cutoff is _MISSING:
        return "gate_cutoff_missing"
    if cr.unset({"THRESHOLD_BANDS": cutoff}):
        return "gate_cutoff_unset"
    if type(cutoff) not in (int, float) or not math.isfinite(cutoff):
        return "gate_cutoff_invalid"
    return None


def candidate_rule(repository=REPOSITORY):
    """The SR-2 candidate EV5 compares, from SR-2's run on EV4."""
    record = json.loads((Path(repository) / CANDIDATE_RECORD).read_text())
    return {
        "rule": record["chosen"],
        "weights": record["chosen_weights"],
        "record": CANDIDATE_RECORD,
    }


def rules_compared(cutoff, repository=REPOSITORY):
    candidate = candidate_rule(repository)
    return {
        "deciding": DECIDING_RULE,
        "candidate": candidate,
        "gate": {
            "module": "carbon/battery/value/admissibility.py",
            "measure": "mean near-limit optimism in bands (admissibility.near_optimism)",
            "cutoff_bands": cutoff,
            "rule": (
                "a member at or above the cutoff, or unmeasured, is inadmissible "
                "and scores 0 under the rule (admissibility.gated)"
            ),
        },
        "rules": [
            {"rule": rule, "gate": gate}
            for rule in (DECIDING_RULE, candidate["rule"])
            for gate in (False, True)
        ],
    }


def hypotheses(cutoff, repository=REPOSITORY):
    """H1-H3 and the two other verdicts as §4 states them. H1's bootstrap is
    EV4's, carried over unchanged (§2)."""
    base, _ = ev.load(EV4_CONTRACT)
    paired = base["acceptance"]["paired_comparison"]
    candidate = candidate_rule(repository)["rule"]
    return {
        "source": f"{SOURCE} §4",
        "H1": {
            "kind": "ranking, paired",
            "statistic": f"delta_tau = tau({candidate}) - tau({DECIDING_RULE})",
            "split": "verification",
            "pool": "eligible reconstructed members (attack constructions and controls excluded)",
            "bootstrap": {
                k: paired[k]
                for k in (
                    "interval",
                    "level",
                    "resample",
                    "replicates",
                    "rng",
                    "rng_seed",
                )
            },
            "promote_only_if_all": [
                "the interval's lower bound is above 0",
                "delta_tau exceeds the tau noise band (divergence.tau_noise_band)",
                (
                    "the candidate's across-family real-member divergence count "
                    "(real_divergence) is not higher than the deciding rule's"
                ),
            ],
            "otherwise": "the deciding rule is confirmed for ranking",
        },
        "H2": {
            "kind": "admissibility gate",
            "cutoff_bands": cutoff,
            "must_fail": [f"control-{c}" for c in GATE_MUST_FAIL],
            "must_pass": [f"control-{c}" for c in GATE_MUST_PASS],
            "real_members": (
                "the real members that FAIL have a higher mean verification decision "
                "loss than those that PASS, and the 95 % bootstrap interval of the "
                "difference excludes 0"
            ),
            "reported": (
                "the number of real members failed; a cutoff that fails more than "
                "half of them is reported as such, never tuned after the fact"
            ),
        },
        "H3": {
            "kind": "known blind spot, reported",
            "control": f"control-{SIGN_ERROR_CONTROL}",
            "reported": (
                "its rank under each rule, whether anything catches it, and the "
                "localized measurement for every member and control (h3_report), "
                "with no cutoff"
            ),
            "localized_measurement": {
                **H3_MEASUREMENT,
                "module_digest": _file_digest(repository, H3_MEASUREMENT["module"]),
            },
        },
        "adversarial_score": (
            "no Track A or Mode X construction with a reference-verified violation "
            "scores in the top half of eligible members, under the deciding rule "
            "plus the gate"
        ),
        "construction_integrity": (
            "no breach, escape, canary read or forbidden access in any family or "
            "in the worker-boundary scan; every rebuild matches, or is refused typed"
        ),
        "verdicts": ["construction_integrity", "adversarial_score", "value"],
        "blended": False,
    }


def h3_report(contract, member_predictions, kinds, repository=REPOSITORY):
    """H3 as reported: the localized measurement for every panel member and
    each constructed control, on the scoring set's important region.

    `member_predictions` maps a member to its predictions by case, as a panel
    bundle holds them; `kinds` names each member's panel kind. Descriptive:
    no cutoff is applied and no score changes. A member missing any important
    case is reported unmeasured (None), never clean.
    """
    from . import scoring as sc
    from .near import near_cases

    store, case_ids, identity = sc.scoring_set(repository)
    near = near_cases(store, case_ids)
    return {
        "schema": H3_REPORT_SCHEMA,
        "measurement": H3_MEASUREMENT,
        "scoring_set": identity,
        "important_cases": len(near),
        "cutoff": None,
        "state": "DESCRIPTIVE",
        "members": {
            member: {
                "kind": kinds.get(member, "RECONSTRUCTED"),
                "measurement": fa.component(contract, predictions, near, store.refs),
            }
            for member, predictions in sorted(member_predictions.items())
        },
        "controls": {
            "control-"
            + kind: fa.component(
                contract, pn.control_predictions(kind, store.refs), near, store.refs
            )
            for kind in pn.CONTROLS
        },
    }


# --- the freeze manifest ---------------------------------------------------------------


def _file_digest(repository, path):
    return (
        "sha256:" + hashlib.sha256((Path(repository) / path).read_bytes()).hexdigest()
    )


def freeze_manifest(confirmation_commitment=None, repository=REPOSITORY):
    """Everything EV5 freezes, or a refusal naming every blocker.

    Refuses while the gate cutoff is missing, unset (None or HUMAN_INPUT) or
    not a finite number; while a condition repeats one in `FRESH_AGAINST`;
    while the panel's reconstructed members or its controls differ from EV4's
    frozen panel; or while the confirmation batch has no public commitment.
    Builds the manifest and returns it; it writes nothing."""
    cutoff = gate_cutoff()
    blockers = []
    problem = cutoff_blocker(cutoff)
    if problem:
        blockers.append(problem)
    prior = prior_conditions()
    found = cr.repeats(_splits(), {name: prior[name] for name in FRESH_AGAINST})
    if found:
        blockers.append(
            "conditions_not_fresh: "
            + ", ".join(f"{r['condition']} in {'+'.join(r['sources'])}" for r in found)
        )
    record = panel_record()
    ev4_panel, ev4_controls = ev4_frozen_panel(repository)
    if record["reconstructed"]["digest"] != cr.digest(ev4_panel):
        blockers.append("panel_differs_from_ev4")
    if record["controls"] != ev4_controls:
        blockers.append("controls_differ_from_ev4")
    commitment = sealed(confirmation_commitment)
    if commitment is None:
        blockers.append("confirmation_not_sealed")
    cr.refuse_freeze(blockers)

    document = contract()
    built = plans()
    return {
        "schema": SCHEMA,
        "study": "EV5",
        "profile": "level-0",
        "preregistration": {"path": SOURCE, "sha256": _file_digest(repository, SOURCE)},
        "study_sheet": {
            "path": STUDY_SHEET,
            "sha256": _file_digest(repository, STUDY_SHEET),
        },
        "authority": [
            "OWNER-ADMISSION-COMBINED-01",
            "TRACK-B-STUCK-01 outcome",
            "OWNER-TRACK-A-L0-02",
            "OWNER-EV5-CAP-01",
        ],
        "conditions": {
            **{
                split: [list(c) for c in group] for split, group in conditions().items()
            },
            "box": {"t_amb_c": list(box()[0]), "soc0": list(box()[1])},
            "fresh_against": list(FRESH_AGAINST),
        },
        "contract": {
            "path": CONTRACT,
            "digest": ev.digest(document),
            "document": document,
        },
        "panel": record,
        "plans": {
            "directory": PLANS,
            "files": {
                name: {"digest": cr.digest(plan), "plan": plan}
                for name, plan in sorted(built.items())
            },
            "optimizer_verification": (
                "built after selection by ev5.optimizer_plans, refused above the maxima"
            ),
        },
        "optimizer": {"maxima": optimizer_maxima()},
        "confirmation": {**confirmation(repository), "commitment": commitment},
        "rules_compared": rules_compared(cutoff, repository),
        "hypotheses": hypotheses(cutoff, repository),
        "gate_cutoff": {
            "THRESHOLD_BANDS": cutoff,
            "source": "carbon/battery/value/admissibility.py",
        },
        "cap": CAP,
        "campaign": {"name": CAMPAIGN, "evidence": EVIDENCE},
        "claims": {
            "qualification": False,
            "chain": False,
            "reward": False,
            "changes_testnet_rule": False,
            "level_above_0_opened": False,
        },
    }


def main(argv=None):
    from carbon.development_session.data import write_once

    parser = argparse.ArgumentParser(prog="python -m carbon.battery.value.ev5")
    sub = parser.add_subparsers(dest="command", required=True)
    seal = sub.add_parser(
        "seal-confirmation",
        help="Make and commit the sealed confirmation batch (validator host only)",
    )
    seal.add_argument("--config", type=Path, required=True)
    freeze = sub.add_parser("freeze-manifest", help="Build EV5's freeze manifest")
    freeze.add_argument("--out", type=Path, required=True)
    freeze.add_argument("--confirmation-fingerprint", required=True)
    freeze.add_argument("--confirmation-sequence", type=int, required=True)
    args = parser.parse_args(argv)
    if args.command == "seal-confirmation":
        from carbon.battery.deployment import EvaluationUnavailable

        try:
            result = seal_confirmation(args.config)
        except EvaluationUnavailable as unavailable:
            print(json.dumps({"unavailable": unavailable.code}))
            return 2
        except cr.CombinedRunError as refused:
            print(json.dumps({"refused": refused.code}))
            return 2
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    try:
        manifest = freeze_manifest(
            {
                "fingerprint": args.confirmation_fingerprint,
                "journal_sequence": args.confirmation_sequence,
            }
        )
    except cr.CombinedRunError as refused:
        print(json.dumps({"refused": refused.code, "blockers": refused.blockers}))
        return 2
    write_once(
        args.out, (json.dumps(manifest, sort_keys=True, indent=1) + "\n").encode()
    )
    print(json.dumps({"written": str(args.out)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
