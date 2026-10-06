"""Graphite phase 3 under a development score variant (VALIDATOR-09 slice 2).

`phase3 run --score-variant VERSION` scores a Constructor session's practice
results under a registered development score variant
(`carbon.scoring.development_score_variants`, #654) beside the Challenge's
frozen practice rule. The variant is:

1. **resolved before spend** (`resolve`): an unregistered, altered, unknown
   or other Challenge's variant is refused, typed, before any grant, pod or
   model call, as is one registered against another practice value contract
   than the one the Challenge declares (`practice_value_contract`, battery:
   EV4's development decision contract, the Test Lead on #668);
2. **pinned** in the session brief (`initial_observation.score_variant`) and
   in the Level-0 permission profile, whose digest the campaign controller
   records;
3. **frozen**: the provider's frozen rule is `VariantRule`, the base rule
   with the variant's result beside it, and every result, the session
   summary and the delivery carry the variant's label;
4. **checked on resume**: a session resumes only under the variant its brief
   pinned.

The base rule still scores, compares and decides promotion, exactly as
without a variant. The variant's result is development evidence beside it: an
order against the baseline under the variant's own score (closest to 1 is
best; a gate FAIL ranks last, the EV5 ruling), with no margin and never
promotable. The agent's practice feedback shows the VARIANT's score as its
score (the Test Lead, #668), so Graphite optimises the variant, never the
base rule. A variant runs at Level 0 only in this slice.

**Never a miner door.** Only this development runner imports the variant
module. Every miner door refuses a registered variant by name
(`capability_registry.is_development_variant`).

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import json
from pathlib import Path

from carbon.challenge_validator import scoring as challenge_scoring

BATTERY = "battery-fastcharge-ageing-development-v1"
LEVEL0_ONLY = "score_variant_runs_at_level_0_only"
#: The variant document's record of the practice value contract digest it was
#: registered against. #654's schema has no such field yet, so it is read from
#: the document's `authority` until it does; absent, the variant is refused.
CONTRACT_FIELD = "practice_value_contract"


class ScoreVariantRefused(ValueError):
    """A typed refusal, by code."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _module():
    from carbon.scoring import development_score_variants

    return development_score_variants


def _directory():
    """The variant registry read: None is the shipped one (tests point
    elsewhere)."""
    return


def _load(version):
    """The registered variant `version` and its verified document."""
    dsv = _module()
    directory = _directory()
    variant = dsv.load_variant(version, directory=directory)
    folder = dsv.POLICY_DIR if directory is None else Path(directory)
    try:
        document = json.loads((folder / f"{version}.json").read_text())
    except (OSError, ValueError):
        raise dsv.ScoreVariantRefused("score_variant_unreadable") from None
    if dsv.digest(document) != variant.digest:
        raise dsv.ScoreVariantRefused("score_variant_altered")
    return variant, document


def recorded_contract(document):
    """The practice value contract digest a variant document was registered
    against: #654's top-level field once it has one, until then its
    `authority` entry; None when absent."""
    if CONTRACT_FIELD in document:
        return document[CONTRACT_FIELD]
    authority = document.get("authority")
    return authority.get(CONTRACT_FIELD) if type(authority) is dict else None


def resolve(version, scoring, *, level=0):
    """The registered development score variant `version` for the session's
    Challenge, verified; None without one. Refused, typed, before anything is
    read or spent: an unregistered or altered variant, another Challenge's, a
    Challenge that declares no practice value contract, and a variant
    registered against another contract than the one the Challenge declares
    (or recording none)."""
    if version is None:
        return None
    if level != 0:
        raise ScoreVariantRefused(LEVEL0_ONLY)
    dsv = _module()
    try:
        scoring = challenge_scoring.resolve(scoring)
    except (challenge_scoring.ScoringUnavailable, TypeError):
        raise ScoreVariantRefused("challenge_scoring_must_be_named") from None
    try:
        variant, document = _load(version)
    except dsv.ScoreVariantRefused as refused:
        raise ScoreVariantRefused(refused.code) from None
    if variant.challenge_id != scoring.challenge_id:
        raise ScoreVariantRefused("score_variant_is_another_challenges")
    _file, declared = practice_contract(scoring)
    recorded = recorded_contract(document)
    if recorded is None:
        raise ScoreVariantRefused("score_variant_practice_contract_unrecorded")
    if recorded != declared:
        raise ScoreVariantRefused("score_variant_practice_contract_mismatch")
    return variant


def practice_contract(scoring):
    """The Challenge's declared practice value contract, `(file, digest)`,
    checked against the committed file. Refused when the Challenge declares
    none (`score_variant_practice_contract_unpinned`) or the file no longer
    has the declared digest."""
    declared = challenge_scoring.resolve(scoring).practice_value_contract
    if declared is None or scoring.challenge_id not in _LEGS:
        raise ScoreVariantRefused("score_variant_practice_contract_unpinned")
    file, pinned = declared
    if _LEGS[scoring.challenge_id][1](file) != pinned:
        raise ScoreVariantRefused("score_variant_practice_contract_altered")
    return file, pinned


def identity_of(variant):
    """What a session pins and every result records; None without a variant."""
    return None if variant is None else variant.identity()


def _battery_contract(file):
    from carbon.battery.value import contract

    return contract.load(contract.CONTRACTS / file)


def _battery_digest(file):
    try:
        return _battery_contract(file)[1]
    except (OSError, ValueError):
        return None


def _battery_legs(base, file):
    """A member's `member_legs` row on battery's public PRACTICE references:
    the practice store `score_practice` scores on, every practice case, a
    missing case asked empty exactly as the base rule asks it (`cover`),
    under the declared practice value contract."""
    from carbon.battery.practice import practice_store

    store = practice_store(base.practice, base.material, base.root)
    document, _digest = _battery_contract(file)
    case_ids = list(base.practice.case_ids)
    tuning = _module().tuning_module(BATTERY)

    def legs(predictions):
        asked, _missing = challenge_scoring.cover(predictions, case_ids)
        return tuning.member_legs(document, asked, store, case_ids)

    return legs


#: Per Challenge: (its legs reader, its value contract digest reader).
_LEGS = {BATTERY: (_battery_legs, _battery_digest)}


class VariantRule:
    """The base frozen rule with the variant's result beside it. `score`
    returns the base rows and summary plus `score_variant` (`score_member`:
    the variant identity, its score and its gate verdict); `compare` is the
    base rule's. `legs` overrides the Challenge's legs reader (tests only)."""

    def __init__(self, base, variant, legs=None):
        self.base, self.variant = base, variant
        self.variant_identity = variant.identity()
        self.identity = {**base.identity, "score_variant": self.variant_identity}
        if legs is None:
            scoring = challenge_scoring.scoring_for(variant.challenge_id)
            file, pinned = practice_contract(scoring)
            self.identity["practice_value_contract"] = pinned
            legs = _LEGS[variant.challenge_id][0](base, file)
        self._legs = legs

    def __getattr__(self, name):
        if name == "base":
            raise AttributeError(name)
        return getattr(self.base, name)

    def score(self, predictions):
        rows, summary = self.base.score(predictions)
        result = _module().score_member(self.variant, self._legs(predictions))
        return rows, {**summary, "score_variant": challenge_scoring.clean(result)}

    def compare(self, baseline_rows, rows, eligible):
        return self.base.compare(baseline_rows, rows, eligible)

    def fail_verdict(self):
        tuning = _module().tuning_module(self.variant.challenge_id)
        return tuning.admissibility.FAIL

    def compare_variant(self, baseline, result):
        """`result` against the baseline's, both `score_member` results under
        this variant. Development evidence only: an order, no margin, never
        promotable. A gate FAIL ranks last (the EV5 ruling)."""
        out = {
            "label": self.variant_identity["label"],
            "score_variant": self.variant_identity["score_variant"],
            "promotable": False,
        }
        mine = self.variant_identity["score_variant_digest"]
        if (
            type(baseline) is not dict
            or baseline.get("score_variant_digest") != mine
            or result.get("score_variant_digest") != mine
        ):
            return {**out, "outcome": "NO_BASELINE_UNDER_THIS_VARIANT"}
        fail = self.fail_verdict()
        base_failed, failed = baseline["gate"] == fail, result["gate"] == fail
        out.update(
            baseline_score=baseline["score"],
            score=result["score"],
            baseline_gate=baseline["gate"],
            gate=result["gate"],
        )
        if failed or base_failed:
            outcome = "BELOW_BASELINE" if failed else "ABOVE_BASELINE"
            if failed and base_failed:
                outcome = "BOTH_GATE_FAILED"
            return {**out, "outcome": outcome, "reason": "a gate FAIL ranks last"}
        if result["score"] is None or baseline["score"] is None:
            return {**out, "outcome": "NOT_SCORABLE"}
        delta = result["score"] - baseline["score"]
        outcome = "ABOVE_BASELINE" if delta > 0 else "BELOW_BASELINE"
        if delta == 0:
            outcome = "EQUAL"
        return {**out, "outcome": outcome, "delta": delta}


def rule_for(base, variant):
    """The session's frozen rule: the base rule, or `VariantRule` over it."""
    return base if variant is None else VariantRule(base, variant)


__all__ = [
    "CONTRACT_FIELD",
    "LEVEL0_ONLY",
    "ScoreVariantRefused",
    "VariantRule",
    "identity_of",
    "practice_contract",
    "recorded_contract",
    "resolve",
    "rule_for",
]
