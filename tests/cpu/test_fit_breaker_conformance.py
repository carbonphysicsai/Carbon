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


def _rule_on(rule, entry):
    optimizer = entry.get("optimizer") if type(entry.get("optimizer")) is dict else {}
    breaker = entry.get("fit_breaker") if type(entry.get("fit_breaker")) is dict else {}
    if rule == "separation_read":
        sha = breaker.get("separation_read_sha256")
        return type(sha) is str and bool(_HEX64.fullmatch(sha))
    if rule == "engineer_shortcut_d_zero":
        zero = optimizer.get("d_zero")
        return (
            type(zero) is dict
            and zero.get("kind") == "engineer_shortcut"
            and optimizer.get("d_aggregate") == "balanced_region_mean"
            and optimizer.get("coverage_plan_sha256") is not None
        )
    if rule == "ood_min_accuracy":
        a_rule = entry.get("a_rule")
        return (
            type(a_rule) is dict
            and a_rule.get("kind") == "min"
            and optimizer.get("a_gen_aggregate") == "ood_class_mean"
            and "a_gen_min_class_cases" in optimizer
        )
    if rule == "v_var":
        variant = optimizer.get("variant_rule")
        return type(variant) is dict and variant.get("kind") == "limit_shift"
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


def conformance_failures(versions, constants, pool_versions, decisions):
    """``[(challenge, version, rule, why), ...]`` for every new version and rule that is neither on nor waived.

    ``versions`` are (challenge, version) pairs (the registry's and the constants'), ``constants`` the pool constants
    document, ``pool_versions`` the pairs graded on the pool path, ``decisions`` the owner decision folder.
    """
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
            elif not _rule_on(rule, entry):
                failures.append((challenge, version, rule, "rule_off"))
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
    return {
        "a_rule": {"kind": "min"},
        "optimizer": {
            "budget": "HUMAN_INPUT",
            "d_zero": {"kind": "engineer_shortcut", "budget": "HUMAN_INPUT"},
            "d_aggregate": "balanced_region_mean",
            "coverage_plan_sha256": "ab" * 32,
            "a_gen_aggregate": "ood_class_mean",
            "a_gen_min_class_cases": "HUMAN_INPUT",
            "variant_rule": {"kind": "limit_shift", "limits": ["HUMAN_INPUT"]},
        },
        "fit_breaker": {"separation_read_sha256": "cd" * 32},
    }


def _check(entry, tmp_path, pool=True):
    return conformance_failures(
        {NEW},
        {"versions": {KEY: entry}},
        {NEW} if pool else set(),
        tmp_path,
    )


def test_a_new_version_with_all_four_rules_on_passes(tmp_path):
    assert _check(_all_on(), tmp_path) == []


@pytest.mark.parametrize(
    ("rule", "drop"),
    [
        ("separation_read", lambda e: e["fit_breaker"].pop("separation_read_sha256")),
        ("engineer_shortcut_d_zero", lambda e: e["optimizer"].pop("d_zero")),
        ("engineer_shortcut_d_zero", lambda e: e["optimizer"].pop("d_aggregate")),
        ("engineer_shortcut_d_zero", lambda e: e["optimizer"].pop("coverage_plan_sha256")),
        ("ood_min_accuracy", lambda e: e.update(a_rule={"kind": "mean"})),
        ("ood_min_accuracy", lambda e: e["optimizer"].update(a_gen_aggregate="balanced_region_mean")),
        ("ood_min_accuracy", lambda e: e["optimizer"].pop("a_gen_min_class_cases")),
        ("v_var", lambda e: e["optimizer"].pop("variant_rule")),
        ("v_var", lambda e: e["optimizer"].update(variant_rule=None)),
    ],
)  # fmt: skip
def test_a_new_version_missing_one_rule_fails_on_that_rule(tmp_path, rule, drop):
    entry = _all_on()
    drop(entry)
    assert _check(entry, tmp_path) == [(*NEW, rule, "rule_off")]


def test_a_resolving_owner_waiver_passes_and_any_other_waiver_fails(tmp_path):
    (tmp_path / "2026-11-05-OWNER-MOTOR-17-NO-VVAR-01.md").write_text(
        DECIDED, encoding="utf-8"
    )
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


def test_a_new_version_off_the_pool_path_or_unregistered_fails_every_rule(tmp_path):
    assert _check(_all_on(), tmp_path, pool=False) == [
        (*NEW, rule, "not_graded_on_the_pool_path") for rule in RULES
    ]
    assert conformance_failures({NEW}, {"versions": {}}, {NEW}, tmp_path) == [
        (*NEW, rule, "not_graded_on_the_pool_path") for rule in RULES
    ]


def test_an_exempt_version_is_never_checked(tmp_path):
    exempt = ("f02", "2.5")
    assert conformance_failures({exempt}, {"versions": {}}, set(), tmp_path) == []


def test_the_ood_min_waiver_names_the_versions_own_record_and_its_conditions_report(
    tmp_path,
):
    own = "OWNER-MOTOR-17-OOD-MIN-OFF-01"
    amendment = "OWNER-ACCURACY-OOD-MIN-01-AMENDMENT-2"
    for record in (own, amendment):
        (tmp_path / f"2026-11-05-{record}.md").write_text(DECIDED, encoding="utf-8")
    entry = _all_on()
    entry["a_rule"] = {"kind": "mean"}
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
