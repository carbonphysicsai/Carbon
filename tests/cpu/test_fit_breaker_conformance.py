"""CONFORMANCE: every NEW exam version turns on all four fit-breaker rules on the pool path, or names an owner waiver.

OWNER-FIT-BREAKER-RULES-LOCK-01 (owner, 4 Nov, Lead session): "lock those 4 rules back in". The four rules are required
in every new version (Motor 1.7, BT 3.0, Cooling 1.8, RB 2.0 and every later one) on the path it actually grades with,
so they cannot drop silently again. A version passes when, for each rule, its registered pool constants
(`scripts/validator_host_classes/pool_constants.json`) turn it on, or its ``fit_breaker.waivers`` names an owner record
id that resolves to a tracked owner decision (``.agent/decisions/*-<ID>.md``, "DECIDED by the owner"):

1. ``separation_read``: a separation-read evidence pointer, ``fit_breaker.separation_read_sha256`` (64 hex; the report
   itself is custody material, resolved by the Validator's receipt).
2. ``engineer_shortcut_d_zero``: ``optimizer.d_zero`` of kind ``engineer_shortcut`` (OWNER-DESIGN-VALUE-ENGINEER-BASELINE-01
   part 1), with the off-step / shell-edge target classes graded on their own: ``optimizer.d_aggregate`` =
   ``balanced_region_mean`` and a registered coverage plan (that the plan carries those classes is a custody data check).
3. ``ood_min_accuracy``: ``a_rule`` = min, ``optimizer.a_gen_aggregate`` = ``ood_class_mean`` with its
   ``a_gen_min_class_cases`` (OWNER-ACCURACY-OOD-MIN-01). Under its amendment 2 the min applies only when three
   conditions hold, and "poorly" / "well above" are owner values picked per version; the amendment itself waives no
   version. So min OFF needs that version's OWN owner record AND its Validator-receipted 3-condition report:
   ``{"record": <owner record id>, "conditions_report_sha256": <64 hex>}`` (Validator 4 Nov 22:03); a plain id fails.
4. ``v_var``: ``optimizer.variant_rule`` of kind ``limit_shift`` (OWNER-DESIGN-DECISION-FIDELITY-01).

AMENDMENT (owner, 5 Nov: OWNER-EXAM-DESIGN-DECISIONS-BATCH-01, items A10-A14 and D6-D11; ruled by the Validator (exam
science) 5 Nov 18:13): for every NEW version, rules 2 and 3 are met ONLY in their 5 Nov form; the 4 Nov form passes only
with that version's OWN owner record choosing it (the waiver form above). Both new forms also need the batch record in
``.agent/decisions`` (until it lands on main they fail closed: no stale pass, no new pass):

2'. ``engineer_shortcut_d_zero``: the zero stays the owner's ENGINEER SHORTCUT at his budget B
    (OWNER-DESIGN-VALUE-ENGINEER-BASELINE-01; ``optimizer.d_zero.kind`` = ``engineer_shortcut``), and D is built only
    where it separates (owner D6: "Prove fixed-optimizer design value first: ~10 solves per version on custody hosts, fit
    vs physics-informed model; build only where it separates"): its design-value proof pointer
    (``optimizer.d_zero.dv_proof_sha256``, 64 hex, the D6 or D9 adjacent-task proof, custody-resolved by the Validator's
    receipt) is required; the region classes stay graded on their own (``d_aggregate`` = ``balanced_region_mean`` and a
    registered coverage plan). A fixed-optimizer zero is an open owner question (Sat 7): only with that version's OWN
    owner record. No D scored = that version's own owner record.
3'. ``ood_min_accuracy``: the generalization battery, owner A10: "Physics scoring: score only classes/outputs where the
    fit loses. Outside the training data"; A11: "In-range accuracy is a gate, threshold from the curves"; A13 (each family
    scored only where the fit loses, surviving families weighted equally); A14 (the gate records full aggregates). The
    version's ``physics`` block (a sibling of ``a_rule``) enters as A outright (``enters`` = "a"; the in-range legs are
    record-only), names its sealed fit-loses cells (``cells_sha256``), declares its gate statistic and cases, keeps the
    coverage plan, and has no ``a_gen_aggregate`` beside it. And the grader must be able to grade it honestly: it grades
    the physics block, it refuses a scored-cell map with no cell (the fit wins everywhere: no A to score is the owner's
    call, like no D), and the weekly fresh-draw SE is built (``physics_se_not_built`` is a launch blocker).

The fit-breaker intent is unchanged: a fit scores nothing from in-range accuracy, A counts only cells the fit loses, and
D is scored only where a proof shows it separates, above the engineer-shortcut zero.

A rule is ON when its switch is registered; its owner values may still be HUMAN_INPUT (the grade then refuses, fail
closed). A new version that is not graded on the pool path at all fails every rule unless waived. The versions that
existed when the lock was recorded are exempt (``EXEMPT``, frozen here: adding to it needs an owner record).
Field names follow the conformance table (Exam Quality, Thu 5 Nov); a rename there changes them here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
CONSTANTS = REPOSITORY / "scripts" / "validator_host_classes" / "pool_constants.json"
DECISIONS = REPOSITORY / ".agent" / "decisions"
RULES = ("separation_read", "engineer_shortcut_d_zero", "ood_min_accuracy", "v_var")

#: Every (challenge, version) registered when OWNER-FIT-BREAKER-RULES-LOCK-01 was recorded (4 Nov 2026): live or
#: earlier versions, exempt. Never extended to let a new version through.
EXEMPT = frozenset(
    {
        ("burgers-dynamics-v1", "1.0"),
        ("battery-fastcharge-ageing-development-v1", "1.0"),
        ("chip-cold-plate", "1.0"),
        ("chip-cold-plate", "1.2"),
        ("chip-cold-plate", "1.3"),
        ("chip-cold-plate", "1.4"),
        ("chip-cold-plate", "1.5"),
        ("chip-cold-plate", "1.6"),
        ("chip-cold-plate", "1.7"),
        ("electric-motor-magnetics", "1.0"),
        ("electric-motor-magnetics", "1.2"),
        ("electric-motor-magnetics", "1.3"),
        ("electric-motor-magnetics", "1.4"),
        ("electric-motor-magnetics", "1.5"),
        ("electric-motor-magnetics", "1.6"),
        ("f08-ribbed-bracket", "1.4"),
        ("f08-ribbed-bracket", "1.5"),
        ("f08-ribbed-bracket", "1.6"),
        ("f08-ribbed-bracket", "1.7"),
        ("f02", "2.3"),
        ("f02", "2.4"),
        ("f02", "2.5"),
        ("photonic-coupler", None),
        ("power-magnetics", None),
        ("airfoil", None),
    }
)
_HEX64 = re.compile(r"[0-9a-f]{64}")
_RECORD_ID = re.compile(r"[A-Z0-9][A-Z0-9-]*-[0-9]{2}(-AMENDMENT(-[0-9]+)?)?")


#: The owner record of the 5 Nov design (lead-records 53375256, blob 15d5f970): rules 2' and 3' need it in the tree.
BATCH_RECORD = "OWNER-EXAM-DESIGN-DECISIONS-BATCH-01"
#: The battery's gate statistics and case sources (the grader's ``physics`` block).
_GATE_STATISTICS = frozenset({"median", "p90", "max"})
_GATE_CASES = frozenset({"agen", "pool"})


def physics_grading():
    """None when the grader can grade a physics version honestly, else the typed reason (read from the code itself, so
    it clears on its own when the missing piece lands): ``physics_not_graded`` (no physics scoring in the grader),
    ``empty_cell_map_accepted`` (a map with no scored cell would grade), ``physics_se_not_built``.
    """
    try:
        from carbon.scoring import pool_exam, pool_physics_score
    except ImportError:
        return "physics_not_graded"
    empty = {
        "schema": pool_physics_score.SCORING_CELLS_SCHEMA,
        "families": {"beyond_range": ["class"]},
        "scored": [],
    }
    refusal = getattr(pool_physics_score, "PhysicsRefused", ValueError)
    refused = False
    try:
        pool_physics_score.cell_map(empty)
    except refusal:  # the fit-wins-everywhere map never grades
        refused = True
    if not refused:
        return "empty_cell_map_accepted"
    try:
        pool_exam.target_bootstrap_se(
            {"gated": False, "physics": True, "sets": []}, "sha256:" + "0" * 64
        )
    except Exception as refused:  # noqa: BLE001
        if "physics_se_not_built" in str(refused):
            return "physics_se_not_built"
    return None


def _rule_state(rule, entry, decisions, grader):
    """None when ``rule`` is ON for a NEW version's ``entry``, else why not ("rule_off", or a typed reason)."""
    optimizer = entry.get("optimizer") if type(entry.get("optimizer")) is dict else {}
    breaker = entry.get("fit_breaker") if type(entry.get("fit_breaker")) is dict else {}
    if rule == "separation_read":
        sha = breaker.get("separation_read_sha256")
        return None if type(sha) is str and _HEX64.fullmatch(sha) else "rule_off"
    if rule == "v_var":
        variant = optimizer.get("variant_rule")
        on = type(variant) is dict and variant.get("kind") == "limit_shift"
        return None if on else "rule_off"
    if rule == "engineer_shortcut_d_zero":
        zero = optimizer.get("d_zero")
        proof = zero.get("dv_proof_sha256") if type(zero) is dict else None
        on = (
            type(zero) is dict
            and zero.get("kind") == "engineer_shortcut"
            and type(proof) is str
            and bool(_HEX64.fullmatch(proof))
            and optimizer.get("d_aggregate") == "balanced_region_mean"
            and optimizer.get("coverage_plan_sha256") is not None
        )
        if not on:
            return "rule_off"
        return (
            None
            if _waiver_resolves(BATCH_RECORD, decisions)
            else "owner_record_not_in_tree"
        )
    if rule == "ood_min_accuracy":
        physics = entry.get("physics")
        cells = physics.get("cells_sha256") if type(physics) is dict else None
        on = (
            type(physics) is dict
            and physics.get("enters") == "a"
            and type(cells) is str
            and bool(_HEX64.fullmatch(cells))
            and physics.get("gate_statistic") in _GATE_STATISTICS
            and physics.get("gate_cases") in _GATE_CASES
            and "gate_threshold" in physics
            and "a_gen_aggregate" not in optimizer
            and optimizer.get("coverage_plan_sha256") is not None
        )
        if not on:
            return "rule_off"
        if not _waiver_resolves(BATCH_RECORD, decisions):
            return "owner_record_not_in_tree"
        return grader
    raise AssertionError(rule)


def _waiver_resolves(record_id, decisions):
    """Whether an owner record id names exactly one tracked owner decision."""
    if type(record_id) is not str or not _RECORD_ID.fullmatch(record_id):
        return False
    found = [p for p in decisions.glob(f"*-{record_id}.md") if p.is_file()]
    if len(found) != 1:
        return False
    return "DECIDED by the owner" in found[0].read_text(encoding="utf-8")


#: The OOD-min record family: the rule's own records, which decide no version's waiver.
OOD_MIN_RECORD = "OWNER-ACCURACY-OOD-MIN-01"


def _waiver_ok(rule, waiver, decisions):
    """A plain owner record id; for OOD-min, ``{"record", "conditions_report_sha256"}`` naming the version's OWN record."""
    if rule == "ood_min_accuracy":
        if type(waiver) is not dict or set(waiver) != {
            "record",
            "conditions_report_sha256",
        }:
            return False
        record, sha = waiver["record"], waiver["conditions_report_sha256"]
        return (
            type(record) is str
            and not record.startswith(OOD_MIN_RECORD)
            and type(sha) is str
            and bool(_HEX64.fullmatch(sha))
            and _waiver_resolves(record, decisions)
        )
    return _waiver_resolves(waiver, decisions)


def conformance_failures(versions, constants, pool_versions, decisions, grader=...):
    """``[(challenge, version, rule, why), ...]`` for every new version and rule that is neither on nor waived.

    ``versions`` are (challenge, version) pairs (the registry's and the constants'), ``constants`` the pool constants
    document, ``pool_versions`` the pairs graded on the pool path, ``decisions`` the owner decision folder, ``grader``
    `physics_grading`'s answer (read from the code when not given).
    """
    if grader is ...:
        grader = physics_grading()
    failures = []
    for challenge, version in sorted(versions, key=lambda p: (p[0], str(p[1]))):
        if (challenge, version) in EXEMPT:
            continue
        entry = constants.get("versions", {}).get(f"{challenge} {version}")
        entry = entry if type(entry) is dict else {}
        breaker = (
            entry.get("fit_breaker") if type(entry.get("fit_breaker")) is dict else {}
        )
        waivers = breaker.get("waivers") if type(breaker.get("waivers")) is dict else {}
        on_pool = (challenge, version) in pool_versions and bool(entry)
        for rule in RULES:
            if rule in waivers:
                if not _waiver_ok(rule, waivers[rule], decisions):
                    failures.append(
                        (challenge, version, rule, "waiver_does_not_resolve")
                    )
                continue
            if not on_pool:
                failures.append(
                    (challenge, version, rule, "not_graded_on_the_pool_path")
                )
            else:
                why = _rule_state(rule, entry, decisions, grader)
                if why is not None:
                    failures.append((challenge, version, rule, why))
        for rule in sorted(set(waivers) - set(RULES)):
            failures.append((challenge, version, rule, "waiver_names_no_rule"))
    return failures


def _repository_versions():
    from carbon.challenge_registry import published_exam, registry

    constants = json.loads(CONSTANTS.read_bytes())
    pairs = {(e.challenge_id, e.version) for e in registry.entries()}
    pairs |= {tuple(key.rsplit(" ", 1)) for key in constants["versions"]}
    return pairs, constants, published_exam._POOL_VERSIONS


# ---------------------------------------------------------------- the repository


def test_every_new_version_turns_on_the_four_rules_or_names_an_owner_waiver():
    pairs, constants, pool_versions = _repository_versions()
    failures = conformance_failures(pairs, constants, pool_versions, DECISIONS)
    assert failures == [], (
        "OWNER-FIT-BREAKER-RULES-LOCK-01: a new version must turn on every fit-breaker rule on the pool path or name an "
        f"owner waiver record: {failures}"
    )


def test_the_exempt_set_is_only_versions_that_existed_at_the_lock():
    """A new version cannot be exempted by adding it here without the owner (the set is the 4 Nov registry)."""
    assert len(EXEMPT) == 25
    for challenge, version in EXEMPT:
        assert (challenge, version) not in {
            ("electric-motor-magnetics", "1.7"),
            ("f02", "3.0"),
            ("chip-cold-plate", "1.8"),
            ("f08-ribbed-bracket", "2.0"),
        }


# ---------------------------------------------------------------- the check itself (synthetic entries)

NEW = ("electric-motor-magnetics", "1.7")
KEY = "electric-motor-magnetics 1.7"
DECIDED = "# X\n\nStatus: DECIDED by the owner, directly in the Lead session.\n"


def _all_on():
    """A new version in the 5 Nov form: every rule on (the physics gate threshold still the owner's: fail closed)."""
    return {
        "optimizer": {
            "budget": "HUMAN_INPUT",
            "d_zero": {
                "kind": "engineer_shortcut",
                "budget": "HUMAN_INPUT",
                "dv_proof_sha256": "d6" * 32,
            },
            "d_aggregate": "balanced_region_mean",
            "coverage_plan_sha256": "ab" * 32,
            "variant_rule": {"kind": "limit_shift", "limits": ["HUMAN_INPUT"]},
        },
        "physics": {
            "cells_sha256": "9a" * 32,
            "gate_statistic": "p90",
            "gate_threshold": "HUMAN_INPUT",
            "gate_cases": "agen",
            "enters": "a",
            "ad_split": 0.5,
            "d_separates": True,
            "cell_scale": "agen_scales",
        },
        "fit_breaker": {"separation_read_sha256": "cd" * 32},
    }


def _old_form():
    """The 4 Nov form (engineer-shortcut zero, OOD-min over A_bank): scores in-range accuracy under the 5 Nov words."""
    entry = _all_on()
    entry.pop("physics")
    entry["a_rule"] = {"kind": "min"}
    entry["optimizer"]["d_zero"] = {
        "kind": "engineer_shortcut",
        "budget": "HUMAN_INPUT",
    }
    entry["optimizer"]["a_gen_aggregate"] = "ood_class_mean"
    entry["optimizer"]["a_gen_min_class_cases"] = "HUMAN_INPUT"
    return entry


def _record(tmp_path, record=BATCH_RECORD):
    (tmp_path / f"2026-11-05-{record}.md").write_text(DECIDED, encoding="utf-8")


def _check(entry, tmp_path, pool=True, grader=None, batch=True):
    if batch:
        _record(tmp_path)
    return conformance_failures(
        {NEW},
        {"versions": {KEY: entry}},
        {NEW} if pool else set(),
        tmp_path,
        grader=grader,
    )


def test_a_new_version_in_the_5_nov_form_passes(tmp_path):
    assert _check(_all_on(), tmp_path) == []


@pytest.mark.parametrize(
    ("rule", "drop"),
    [
        ("separation_read", lambda e: e["fit_breaker"].pop("separation_read_sha256")),
        ("engineer_shortcut_d_zero", lambda e: e["optimizer"].pop("d_zero")),
        ("engineer_shortcut_d_zero", lambda e: e["optimizer"]["d_zero"].pop("dv_proof_sha256")),
        ("engineer_shortcut_d_zero", lambda e: e["optimizer"]["d_zero"].update(dv_proof_sha256="x")),
        ("engineer_shortcut_d_zero", lambda e: e["optimizer"].pop("d_aggregate")),
        ("v_var", lambda e: e["optimizer"].pop("variant_rule")),
        ("v_var", lambda e: e["optimizer"].update(variant_rule=None)),
        ("ood_min_accuracy", lambda e: e["physics"].update(enters="a_gen")),  # mixed into the old A
        ("ood_min_accuracy", lambda e: e["physics"].pop("cells_sha256")),  # no sealed fit-loses cells
        ("ood_min_accuracy", lambda e: e["physics"].update(cells_sha256="x")),
        ("ood_min_accuracy", lambda e: e["physics"].update(gate_statistic="mean")),
        ("ood_min_accuracy", lambda e: e["physics"].pop("gate_threshold")),
        ("ood_min_accuracy", lambda e: e["physics"].update(gate_cases=None)),
        ("ood_min_accuracy", lambda e: e["optimizer"].update(a_gen_aggregate="ood_class_mean")),
        ("ood_min_accuracy", lambda e: e.update(physics=None)),
    ],
)  # fmt: skip
def test_a_new_version_missing_one_rule_fails_on_that_rule(tmp_path, rule, drop):
    entry = _all_on()
    drop(entry)
    assert _check(entry, tmp_path) == [(*NEW, rule, "rule_off")]


def test_without_the_coverage_plan_both_region_rules_fail(tmp_path):
    entry = _all_on()
    entry["optimizer"].pop("coverage_plan_sha256")
    assert _check(entry, tmp_path) == [
        (*NEW, "engineer_shortcut_d_zero", "rule_off"),
        (*NEW, "ood_min_accuracy", "rule_off"),
    ]


def test_the_new_rules_fail_closed_until_the_owner_record_is_in_the_tree(tmp_path):
    assert _check(_all_on(), tmp_path, batch=False) == [
        (*NEW, "engineer_shortcut_d_zero", "owner_record_not_in_tree"),
        (*NEW, "ood_min_accuracy", "owner_record_not_in_tree"),
    ]


def test_the_old_4_nov_form_needs_the_versions_own_record(tmp_path):
    """Validator 18:13 (A): no open alternative for the 13 Nov set: the old form scores in-range accuracy, so it passes
    only with that version's OWN owner record choosing it."""
    assert _check(_old_form(), tmp_path) == [
        (*NEW, "engineer_shortcut_d_zero", "rule_off"),
        (*NEW, "ood_min_accuracy", "rule_off"),
    ]
    own = "OWNER-MOTOR-17-OLD-RULES-01"
    _record(tmp_path, own)
    entry = _old_form()
    entry["fit_breaker"]["waivers"] = {
        "engineer_shortcut_d_zero": own,
        "ood_min_accuracy": {"record": own, "conditions_report_sha256": "ef" * 32},
    }
    assert _check(entry, tmp_path) == []


@pytest.mark.parametrize(
    "reason", ["physics_not_graded", "empty_cell_map_accepted", "physics_se_not_built"]
)
def test_a_physics_version_fails_while_the_grader_cannot_grade_it_honestly(
    tmp_path, reason
):
    """Validator 18:13 negative tests: an empty scored-cell map must never grade, and no weekly fresh-draw SE is a launch
    blocker; the reason is the grader's own, typed."""
    assert _check(_all_on(), tmp_path, grader=reason) == [
        (*NEW, "ood_min_accuracy", reason)
    ]


def test_the_grader_probe_reads_the_code_and_an_empty_map_never_grades():
    """The real probe: whatever it answers is one of the typed states, and where the grader scores physics, a map with no
    scored cell (the fit wins everywhere) is refused."""
    assert physics_grading() in {
        None,
        "physics_not_graded",
        "empty_cell_map_accepted",
        "physics_se_not_built",
    }
    assert physics_grading() != "empty_cell_map_accepted"


def test_a_resolving_owner_waiver_passes_and_any_other_waiver_fails(tmp_path):
    _record(tmp_path, "OWNER-MOTOR-17-NO-VVAR-01")
    (tmp_path / "2026-11-05-LEAD-NOTE-01.md").write_text(
        "Status: recorded by the Lead\n", encoding="utf-8"
    )
    entry = _all_on()
    entry["optimizer"].pop("variant_rule")
    entry["fit_breaker"]["waivers"] = {"v_var": "OWNER-MOTOR-17-NO-VVAR-01"}
    assert _check(entry, tmp_path) == []
    for bad in ("OWNER-NOT-THERE-01", "LEAD-NOTE-01", "*", "../x", None):
        entry["fit_breaker"]["waivers"] = {"v_var": bad}
        assert _check(entry, tmp_path) == [(*NEW, "v_var", "waiver_does_not_resolve")]
    entry["fit_breaker"]["waivers"] = {"v_varr": "OWNER-MOTOR-17-NO-VVAR-01"}
    assert (*NEW, "v_varr", "waiver_names_no_rule") in _check(entry, tmp_path)


def test_no_d_scored_needs_the_versions_own_record(tmp_path):
    entry = _all_on()
    entry["optimizer"].pop("d_zero")
    assert _check(entry, tmp_path) == [(*NEW, "engineer_shortcut_d_zero", "rule_off")]
    _record(tmp_path, "OWNER-MOTOR-17-NO-D-01")
    entry["fit_breaker"]["waivers"] = {
        "engineer_shortcut_d_zero": "OWNER-MOTOR-17-NO-D-01"
    }
    assert _check(entry, tmp_path) == []


def test_a_fixed_optimizer_zero_needs_the_versions_own_record(tmp_path):
    """Validator 18:2x: the owner's zero on record is the engineer shortcut; a fixed-optimizer zero is an open Sat 7
    question, so it passes only with that version's own owner record."""
    entry = _all_on()
    entry["optimizer"]["d_zero"] = {
        "kind": "fixed_optimizer",
        "dv_proof_sha256": "d6" * 32,
    }
    assert _check(entry, tmp_path) == [(*NEW, "engineer_shortcut_d_zero", "rule_off")]
    _record(tmp_path, "OWNER-MOTOR-17-FIXED-OPTIMIZER-ZERO-01")
    entry["fit_breaker"]["waivers"] = {
        "engineer_shortcut_d_zero": "OWNER-MOTOR-17-FIXED-OPTIMIZER-ZERO-01"
    }
    assert _check(entry, tmp_path) == []


def test_a_new_version_off_the_pool_path_or_unregistered_fails_every_rule(tmp_path):
    assert _check(_all_on(), tmp_path, pool=False) == [
        (*NEW, rule, "not_graded_on_the_pool_path") for rule in RULES
    ]
    assert conformance_failures(
        {NEW}, {"versions": {}}, {NEW}, tmp_path, grader=None
    ) == [(*NEW, rule, "not_graded_on_the_pool_path") for rule in RULES]


def test_an_exempt_version_is_never_checked(tmp_path):
    exempt = ("f02", "2.5")
    assert conformance_failures({exempt}, {"versions": {}}, set(), tmp_path) == []


def test_the_ood_min_waiver_names_the_versions_own_record_and_its_conditions_report(
    tmp_path,
):
    own = "OWNER-MOTOR-17-OOD-MIN-OFF-01"
    amendment = "OWNER-ACCURACY-OOD-MIN-01-AMENDMENT-2"
    for record in (own, amendment):
        _record(tmp_path, record)
    entry = _all_on()
    entry.pop("physics")
    good = {"record": own, "conditions_report_sha256": "ef" * 32}
    entry["fit_breaker"]["waivers"] = {"ood_min_accuracy": good}
    assert _check(entry, tmp_path) == []
    for bad in (
        own,  # the record id alone is not enough
        {"record": own},
        {**good, "conditions_report_sha256": "x"},
        {**good, "record": amendment},  # the amendment waives no version itself
        {**good, "record": "OWNER-NOT-THERE-01"},
        {"record": own, "separation_read_sha256": "ef" * 32},  # the superseded form
        {**good, "extra": 1},
    ):
        entry["fit_breaker"]["waivers"] = {"ood_min_accuracy": bad}
        assert _check(entry, tmp_path) == [
            (*NEW, "ood_min_accuracy", "waiver_does_not_resolve")
        ]
    entry = _all_on()
    entry["optimizer"].pop("variant_rule")
    entry["fit_breaker"]["waivers"] = {"v_var": good}  # the report form is OOD-min only
    assert _check(entry, tmp_path) == [(*NEW, "v_var", "waiver_does_not_resolve")]
