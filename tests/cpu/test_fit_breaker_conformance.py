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

2'. ``engineer_shortcut_d_zero``: D's zero is the BEST OF the cheap ways to a design (owner, batch record: EQ's
    recommendation "the zero is the best of all three [registered engineer shortcut, the cheap fit's design, the best
    design already in TRAIN]", owner "approved your decisions there"; ruled by the Validator 5 Nov 18:31):
    ``optimizer.d_zero`` = ``{"kind": "best_of", "components": [...]}`` whose component kinds are EXACTLY ``fit_pick``
    (the TRAIN-only fit's solved pick under the fixed optimizer) and ``train_best`` (the best TRAIN design meeting the
    target's limits, within-U exclusion), plus ``engineer_shortcut`` (with its ``budget`` B, HUMAN_INPUT = fail closed)
    exactly when the version registers a shortcut screen (``scripts/dev/exam_reads/dv_curve.SHORTCUT_SCREENS``); D is
    built only where it separates (owner D6: "Prove fixed-optimizer design value first: ~10 solves per version on custody
    hosts, fit vs physics-informed model; build only where it separates"), so its design-value proof pointer
    (``optimizer.d_zero.dv_proof_sha256``, 64 hex, the D6 or D9 adjacent-task proof, custody-resolved by the Validator's
    receipt) is required, and the region classes stay graded on their own (``d_aggregate`` = ``balanced_region_mean``
    and a registered coverage plan). The 4 Nov engineer-shortcut zero alone, or a fixed-optimizer zero alone, passes
    only with that version's OWN owner record. No D scored = that version's own owner record, and a physics
    ``total_rule`` of ``a_only`` (TOTAL = A, D dropped) IS no D scored (Validator 18:3x: that decision is deferred).
3'. ``ood_min_accuracy``: the generalization battery, owner A10: "Physics scoring: score only classes/outputs where the
    fit loses. Outside the training data"; A11: "In-range accuracy is a gate, threshold from the curves"; A13 (each family
    scored only where the fit loses, surviving families weighted equally); A14 (the gate records full aggregates). The
    version's ``physics`` block (a sibling of ``a_rule``) enters as A outright (``enters`` = "a"; the in-range legs are
    record-only), names its sealed fit-loses cells (``cells_sha256``), declares its gate statistic and cases, keeps the
    coverage plan, declares its ``total_rule`` (``half_a_half_d`` or ``a_only``), and has no ``a_gen_aggregate``
    beside it. And the grader must be able to grade it honestly: it grades
    the physics block, it refuses a scored-cell map with no cell (the fit wins everywhere: no A to score is the owner's
    call, like no D), and the weekly fresh-draw SE is built (``physics_se_not_built`` is a launch blocker).

AMENDMENT 2 (10 Nov; Validator-2B engineering ruling 05:45 'PATH (ii)', Carbon Validator-B science ruling
D_ZERO_MENU_2PRIME_RULING_20261110.md 908e8fe2 conditions (a)-(f), owner record ``MENU_ZERO_RECORD``): for a version that
registers a ``menu`` block, D is graded by the sealed menu records (`pool_menu`), and ``optimizer.d_zero`` grades
nothing, so 2' reads the menu's zero instead: ``fit_breaker.d_zero`` (never read by ``carbon/``) =
``{"kind": "best_of", "components": [...] (the same exact-set rule), "source": "menu_records", "dv_proof_sha256"
(per-task hardness H1-H6 + bunching report, (d)), "arms_sha256" (the TRAIN-only fit panel in every record's arms, (a)),
"zero_records_sha256": {task_id: sha256} (each record's zero record, one per registered menu task, (b))}``, with
``optimizer.d_zero`` ABSENT (one zero only, (f)), ``d_aggregate`` = ``balanced_region_mean``, the coverage plan, and the
menu's aggregate "mean" ((e)). That the records' arms are non-empty and their s_zero equals the zero record's ((a), (b),
(c)) is a custody check, receipted by the version's Validator; this test checks the registration. A version without a
menu is unchanged (2' as above).

The fit-breaker intent is unchanged: a fit scores nothing from in-range accuracy, A counts only cells the fit loses, and
D is scored only where a proof shows it separates, above the best of the fit's pick, TRAIN's best and the shortcut.

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
#: The owner record that reads 2' from the menu's zero for a menu-D version (amendment 2, 10 Nov): it must be in the tree.
MENU_ZERO_RECORD = "OWNER-MENU-D-ZERO-2PRIME-01"
#: The keys of a menu-D version's ``fit_breaker.d_zero`` (amendment 2), exactly.
_MENU_ZERO_KEYS = frozenset(
    {
        "kind",
        "components",
        "source",
        "dv_proof_sha256",
        "arms_sha256",
        "zero_records_sha256",
    }
)
#: The battery's gate statistics and case sources (the grader's ``physics`` block).
_GATE_STATISTICS = frozenset({"median", "p90", "max"})
_GATE_CASES = frozenset({"agen", "pool"})
#: How the physics score enters the total (Graphite's grader; no default: unset refuses).
_TOTAL_RULES = frozenset({"half_a_half_d", "a_only"})


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


def shortcut_screened(challenge, version):
    """Whether (challenge, version) registers a shortcut screen (`dv_curve.SHORTCUT_SCREENS`; an entry whose method is
    not fixed yet still counts: its engineer_shortcut component then fails closed on its HUMAN_INPUT budget).
    """
    from scripts.dev.exam_reads import dv_curve

    return (challenge, version) in dv_curve.SHORTCUT_SCREENS


#: The components of the best-of zero every new version names; the shortcut joins them exactly where screened.
_ZERO_ALWAYS = frozenset({"fit_pick", "train_best"})


def _best_of_zero(zero, screened):
    """Whether ``zero`` is the owner's best-of zero for a version that does (``screened``) or does not register a
    shortcut screen: exactly the applicable components, the shortcut with its budget key.
    """
    components = zero.get("components")
    if type(components) is not list or not all(
        type(c) is dict and type(c.get("kind")) is str for c in components
    ):
        return False
    kinds = [c["kind"] for c in components]
    expected = _ZERO_ALWAYS | ({"engineer_shortcut"} if screened else set())
    if len(kinds) != len(set(kinds)) or set(kinds) != expected:
        return False
    return all("budget" in c for c in components if c["kind"] == "engineer_shortcut")


def _rule_state(rule, entry, decisions, grader, version_key=(None, None)):
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
    if rule == "engineer_shortcut_d_zero" and "menu" in entry:
        return _menu_zero_state(entry, optimizer, breaker, decisions, version_key)
    if rule == "engineer_shortcut_d_zero":
        zero = optimizer.get("d_zero")
        proof = zero.get("dv_proof_sha256") if type(zero) is dict else None
        on = (
            type(zero) is dict
            and zero.get("kind") == "best_of"
            and _best_of_zero(zero, shortcut_screened(*version_key))
            and type(proof) is str
            and bool(_HEX64.fullmatch(proof))
            and optimizer.get("d_aggregate") == "balanced_region_mean"
            and optimizer.get("coverage_plan_sha256") is not None
        )
        physics = entry.get("physics")
        if type(physics) is dict and physics.get("total_rule") == "a_only":
            on = False  # TOTAL = A drops D: no D scored, the version's own record only
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
            and physics.get("total_rule") in _TOTAL_RULES
            and "a_gen_aggregate" not in optimizer
            and optimizer.get("coverage_plan_sha256") is not None
        )
        if not on:
            return "rule_off"
        if not _waiver_resolves(BATCH_RECORD, decisions):
            return "owner_record_not_in_tree"
        return grader
    raise AssertionError(rule)


def _is_hex64(value):
    return type(value) is str and bool(_HEX64.fullmatch(value))


def _menu_zero_state(entry, optimizer, breaker, decisions, version_key):
    """Rule 2' for a menu-D version (amendment 2): None when on, else "rule_off" or "owner_record_not_in_tree"."""
    zero = breaker.get("d_zero")
    menu = entry.get("menu")
    tasks = menu.get("records_sha256") if type(menu) is dict else None
    zeros = zero.get("zero_records_sha256") if type(zero) is dict else None
    physics = entry.get("physics")
    on = (
        "d_zero"
        not in optimizer  # (f) one zero only: the grader's own zero stays unset
        and type(zero) is dict
        and set(zero) == _MENU_ZERO_KEYS
        and zero["kind"] == "best_of"
        and zero["source"] == "menu_records"
        and _best_of_zero(zero, shortcut_screened(*version_key))
        and _is_hex64(zero["dv_proof_sha256"])  # (d)
        and _is_hex64(zero["arms_sha256"])  # (a)
        # (b) one zero record per registered menu task, by sha
        and type(zeros) is dict
        and type(tasks) is dict
        and bool(zeros)
        and set(zeros) == set(tasks)
        and all(_is_hex64(sha) for sha in zeros.values())
        and menu.get("aggregate") == "mean"  # (e)
        and optimizer.get("d_aggregate") == "balanced_region_mean"
        and optimizer.get("coverage_plan_sha256") is not None
        and not (type(physics) is dict and physics.get("total_rule") == "a_only")
    )
    if not on:
        return "rule_off"
    resolved = _waiver_resolves(BATCH_RECORD, decisions) and _waiver_resolves(
        MENU_ZERO_RECORD, decisions
    )
    return None if resolved else "owner_record_not_in_tree"


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
                why = _rule_state(rule, entry, decisions, grader, (challenge, version))
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
                "kind": "best_of",
                "components": [{"kind": "fit_pick"}, {"kind": "train_best"}],
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
            "total_rule": "half_a_half_d",
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


SCREENED = (
    "chip-cold-plate",
    "1.8",
)  # registers a shortcut screen (COOL-ADV-01) in dv_curve.SHORTCUT_SCREENS


def _check_version(version, entry, tmp_path):
    _record(tmp_path)
    return conformance_failures(
        {version},
        {"versions": {" ".join(version): entry}},
        {version},
        tmp_path,
        grader=None,
    )


def test_the_shortcut_registry_decides_which_versions_need_the_shortcut_component():
    assert shortcut_screened(*SCREENED) and not shortcut_screened(*NEW)


def test_a_screened_version_passes_with_all_three_components_and_fails_without_the_shortcut(
    tmp_path,
):
    entry = _all_on()
    entry["optimizer"]["d_zero"]["components"].append(
        {"kind": "engineer_shortcut", "budget": "HUMAN_INPUT"}
    )
    assert _check_version(SCREENED, entry, tmp_path) == []
    entry["optimizer"]["d_zero"][
        "components"
    ].pop()  # the registered shortcut is missing from the zero
    assert _check_version(SCREENED, entry, tmp_path) == [
        (*SCREENED, "engineer_shortcut_d_zero", "rule_off")
    ]
    entry["optimizer"]["d_zero"]["components"].append({"kind": "engineer_shortcut"})
    assert _check_version(
        SCREENED, entry, tmp_path
    ) == [  # the shortcut needs its budget B
        (*SCREENED, "engineer_shortcut_d_zero", "rule_off")
    ]


UNSCREENED_BAD_ZEROS = [
    [{"kind": "fit_pick"}],  # no TRAIN best
    [{"kind": "train_best"}],  # no fit pick
    [
        {"kind": "fit_pick"},
        {"kind": "train_best"},
        {"kind": "engineer_shortcut", "budget": 1},
    ],  # no shortcut screen registered for this version
    [{"kind": "fit_pick"}, {"kind": "fit_pick"}, {"kind": "train_best"}],
    [{"kind": "fit_pick"}, {"kind": "train_best"}, {"kind": "oracle"}],
    "fit_pick,train_best",
    None,
]


@pytest.mark.parametrize("components", UNSCREENED_BAD_ZEROS)
def test_an_unscreened_version_needs_exactly_the_two_components(tmp_path, components):
    """Motor 1.7 registers no shortcut screen: its zero is the best of the fit's pick and TRAIN's best, exactly."""
    entry = _all_on()
    entry["optimizer"]["d_zero"]["components"] = components
    assert _check(entry, tmp_path) == [(*NEW, "engineer_shortcut_d_zero", "rule_off")]


SINGLE_ZEROS = [
    {
        "kind": "engineer_shortcut",
        "budget": "HUMAN_INPUT",
        "dv_proof_sha256": "d6" * 32,
    },
    {"kind": "fixed_optimizer", "dv_proof_sha256": "d6" * 32},
]


@pytest.mark.parametrize("zero", SINGLE_ZEROS)
def test_a_single_component_zero_needs_the_versions_own_record(tmp_path, zero):
    """Validator 18:31: the engineer shortcut alone is no longer the default, nor the fixed optimizer alone: either
    passes only with that version's own owner record."""
    entry = _all_on()
    entry["optimizer"]["d_zero"] = zero
    assert _check(entry, tmp_path) == [(*NEW, "engineer_shortcut_d_zero", "rule_off")]
    _record(tmp_path, "OWNER-MOTOR-17-SINGLE-ZERO-01")
    entry["fit_breaker"]["waivers"] = {
        "engineer_shortcut_d_zero": "OWNER-MOTOR-17-SINGLE-ZERO-01"
    }
    assert _check(entry, tmp_path) == []


def test_a_total_of_a_only_is_no_d_scored_and_needs_the_versions_own_record(tmp_path):
    """Validator 18:3x: TOTAL = A drops D, a deferred owner decision: even with the best-of zero it is no D scored."""
    entry = _all_on()
    entry["physics"]["total_rule"] = "a_only"
    assert _check(entry, tmp_path) == [(*NEW, "engineer_shortcut_d_zero", "rule_off")]
    _record(tmp_path, "OWNER-MOTOR-17-NO-D-01")
    entry["fit_breaker"]["waivers"] = {
        "engineer_shortcut_d_zero": "OWNER-MOTOR-17-NO-D-01"
    }
    assert _check(entry, tmp_path) == []


@pytest.mark.parametrize("total", [None, "missing", "half_a_d", "a"])
def test_a_physics_block_without_a_known_total_rule_fails_the_ood_rule(tmp_path, total):
    entry = _all_on()
    if total == "missing":
        entry["physics"].pop("total_rule")
    else:
        entry["physics"]["total_rule"] = total
    assert _check(entry, tmp_path) == [(*NEW, "ood_min_accuracy", "rule_off")]


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


# ---------------------------------------------------------------- amendment 2: rule 2' for a menu-D version (10 Nov)

MENU_TASKS = ("task-1", "task-2", "task-3")


def _menu_on():
    """A new menu-D version in the amendment-2 form: the zero read from the menu records (fit_breaker.d_zero), the
    grader's own d_zero absent."""
    entry = _all_on()
    zero = entry["optimizer"].pop("d_zero")
    entry["menu"] = {
        "records_sha256": {t: "e1" * 32 for t in MENU_TASKS},
        "epoch": "HUMAN_INPUT",
        "aggregate": "mean",
        "rotation_days": "HUMAN_INPUT",
        "rowcheck": "HUMAN_INPUT",
    }
    entry["fit_breaker"]["d_zero"] = {
        "kind": "best_of",
        "components": zero["components"],
        "source": "menu_records",
        "dv_proof_sha256": "d6" * 32,
        "arms_sha256": "a7" * 32,
        "zero_records_sha256": {t: "20" * 32 for t in MENU_TASKS},
    }
    return entry


def _menu_check(entry, tmp_path, version=NEW, menu_record=True):
    _record(tmp_path)
    if menu_record:
        _record(tmp_path, MENU_ZERO_RECORD)
    return conformance_failures(
        {version},
        {"versions": {" ".join(version): entry}},
        {version},
        tmp_path,
        grader=None,
    )


def test_a_menu_version_passes_with_the_menu_zero_and_the_owner_record(tmp_path):
    assert _menu_check(_menu_on(), tmp_path) == []


def test_a_menu_version_fails_closed_until_the_menu_zero_record_is_in_the_tree(
    tmp_path,
):
    assert _menu_check(_menu_on(), tmp_path, menu_record=False) == [
        (*NEW, "engineer_shortcut_d_zero", "owner_record_not_in_tree")
    ]


def test_a_menu_version_with_the_graders_own_zero_too_has_two_zeros_and_fails(
    tmp_path,
):
    """Condition (f): one zero only."""
    entry = _menu_on()
    entry["optimizer"]["d_zero"] = dict(entry["fit_breaker"]["d_zero"])
    assert _menu_check(entry, tmp_path) == [
        (*NEW, "engineer_shortcut_d_zero", "rule_off")
    ]


@pytest.mark.parametrize(
    "drop",
    [
        lambda e: e["fit_breaker"].pop("d_zero"),
        lambda e: e["fit_breaker"]["d_zero"].update(source="optimizer"),
        lambda e: e["fit_breaker"]["d_zero"].update(kind="engineer_shortcut"),
        lambda e: e["fit_breaker"]["d_zero"].update(dv_proof_sha256="HUMAN_INPUT"),  # (d)
        lambda e: e["fit_breaker"]["d_zero"].pop("arms_sha256"),  # (a)
        lambda e: e["fit_breaker"]["d_zero"].update(arms_sha256=""),  # (a): no fit panel
        lambda e: e["fit_breaker"]["d_zero"].update(zero_records_sha256={}),  # (b)
        lambda e: e["fit_breaker"]["d_zero"]["zero_records_sha256"].pop("task-3"),  # (b): a task without its zero
        lambda e: e["fit_breaker"]["d_zero"]["zero_records_sha256"].update({"task-9": "20" * 32}),
        lambda e: e["fit_breaker"]["d_zero"]["zero_records_sha256"].update({"task-1": "x"}),
        lambda e: e["fit_breaker"]["d_zero"].update(extra=1),
        lambda e: e["fit_breaker"]["d_zero"]["components"].pop(),
        lambda e: e["menu"].update(aggregate="max"),  # (e)
        lambda e: e["optimizer"].pop("coverage_plan_sha256"),  # (e)
        lambda e: e["optimizer"].pop("d_aggregate"),
        lambda e: e["physics"].update(total_rule="a_only"),  # no D scored
    ],
)  # fmt: skip
def test_a_menu_version_missing_any_condition_fails_rule_2prime(tmp_path, drop):
    entry = _menu_on()
    drop(entry)
    failures = _menu_check(entry, tmp_path)
    assert (*NEW, "engineer_shortcut_d_zero", "rule_off") in failures


def test_a_screened_menu_version_needs_the_shortcut_component(tmp_path):
    entry = _menu_on()
    assert _menu_check(entry, tmp_path, version=SCREENED) == [
        (*SCREENED, "engineer_shortcut_d_zero", "rule_off")
    ]
    entry["fit_breaker"]["d_zero"]["components"].append(
        {"kind": "engineer_shortcut", "budget": "HUMAN_INPUT"}
    )
    assert _menu_check(entry, tmp_path, version=SCREENED) == []


def test_a_version_without_a_menu_still_needs_the_graders_best_of_zero(tmp_path):
    """Amendment 2 is for menu-D versions only: the menu zero in fit_breaker does nothing for a version with no menu."""
    entry = _menu_on()
    entry.pop("menu")
    assert _menu_check(entry, tmp_path) == [
        (*NEW, "engineer_shortcut_d_zero", "rule_off")
    ]
    assert _menu_check(_all_on(), tmp_path) == []  # unchanged


def _synthetic(value):
    """A stand-in for one HUMAN_INPUT leaf, by its key (synthetic, test-only; never a registered value)."""
    return {
        "agen_scales": {
            "mean_torque_nm": 1.0,
            "ripple_pk_pk_nm": 1.0,
            "die_peak_c": 1.0,
            "hydraulic_w": 1.0,
        },
        "scale": 1.0,
        "population": None,
        "sigma0": 0.25,
        "budget": 60,
        "limits[]": "synthetic_limit",  # one list element
        "shifts[]": 0.1,
        "min_valid": 1,
        "gate_threshold": {"die_peak_c": 1.0, "hydraulic_w": 1.0},
        "records_sha256": {t: "e1" * 32 for t in MENU_TASKS},
        "zero_records_sha256": {t: "20" * 32 for t in MENU_TASKS},
        "epoch": "synthetic-epoch",
        "rotation_days": 7,
        "rowcheck": {"rel_tol": 0.0, "abs_tol": 0.0, "subset": 3},
    }.get(
        value, "5e" * 32
    )  # every other HUMAN_INPUT leaf is a sha


def _fill(node, key=None):
    if node == "HUMAN_INPUT":
        return _synthetic(key)
    if type(node) is dict:
        return {k: _fill(v, k) for k, v in node.items()}
    if type(node) is list:
        return [_fill(v, f"{key}[]") for v in node]
    return node


def _seed_named_waiver_records(entry, folder):
    """Copy, byte for byte, each REAL tracked owner record the row's waivers name (never a synthetic stub).

    Returns the waived rule names; a named record must exist exactly once in the tracked decisions folder.
    """
    folder.mkdir()
    waivers = entry.get("fit_breaker", {}).get("waivers", {})
    for waiver in waivers.values():
        record = waiver["record"] if type(waiver) is dict else waiver
        found = sorted(DECISIONS.glob(f"*-{record}.md"))
        assert len(found) == 1, (record, found)
        (folder / found[0].name).write_bytes(found[0].read_bytes())
    return sorted(waivers)


@pytest.mark.parametrize(
    "name", ["electric-motor-magnetics 1.8", "chip-cold-plate 1.8"]
)
def test_a_filled_1p8_row_passes_conformance_and_parses_in_the_grader(tmp_path, name):
    """mc-exam-B's 05:42 gap: the registered 1.8 row, with every HUMAN_INPUT filled by a synthetic stand-in, both passes
    the fit-breaker conformance and parses in `pool_version.registered_policies` (one zero, the grader's unset).
    """
    from carbon.scoring import pool_version

    document = json.loads(CONSTANTS.read_bytes())
    entry = _fill(document["versions"][name])
    assert "HUMAN_INPUT" not in json.dumps(entry)
    assert "d_zero" not in entry["optimizer"]
    version = tuple(name.rsplit(" ", 1))
    waived = _seed_named_waiver_records(entry, tmp_path / "with")
    assert _menu_check(entry, tmp_path / "with", version=version) == []
    # V2C 11 Nov 21:32 (option A): a waiver whose record is not in the folder still fails (rule 4 logic untouched).
    (tmp_path / "without").mkdir()
    failures = _menu_check(entry, tmp_path / "without", version=version)
    for rule in waived:
        assert (*version, rule, "waiver_does_not_resolve") in failures
    path = tmp_path / "pool_constants.json"
    path.write_text(
        json.dumps({"schema": document["schema"], "versions": {name: entry}}),
        encoding="utf-8",
    )
    policies = pool_version.registered_policies(*version, path=path)
    assert policies.optimizer.d_zero is None
    assert policies.menu is not None and policies.physics is not None
