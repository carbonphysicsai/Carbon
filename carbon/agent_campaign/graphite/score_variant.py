"""Graphite phase 3 under a development score variant (VALIDATOR-09 slice 2).

`phase3 run --score-variant VERSION` scores a Constructor session's practice
results under a registered development score variant
(`carbon.scoring.development_score_variants`, #654) beside the Challenge's
frozen practice rule. The variant is:

1. **resolved before spend** (`resolve`): an unregistered, altered, unknown
   or other Challenge's variant is refused, typed, before any grant, pod or
   model call;
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
promotable. A variant runs at Level 0 only in this slice.

**Never a miner door.** Only this development runner imports the variant
module. Every miner door refuses a registered variant by name
(`capability_registry.is_development_variant`).

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

from carbon.challenge_validator import scoring as challenge_scoring

BATTERY = "battery-fastcharge-ageing-development-v1"
#: How a variant reads a member's legs on the practice predictions, per
#: Challenge. `value_contract` names the value contract the legs are computed
#: under. HUMAN_INPUT: no owner has pinned one, so None refuses before any
#: spend (`score_variant_practice_contract_unpinned`).
PRACTICE_LEGS = {BATTERY: {"value_contract": None}}
LEVEL0_ONLY = "score_variant_runs_at_level_0_only"


class ScoreVariantRefused(ValueError):
    """A typed refusal, by code."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _module():
    from carbon.scoring import development_score_variants

    return development_score_variants


def _load(version):
    """The shipped registry's variant `version` (tests read their own)."""
    return _module().load_variant(version)


def resolve(version, scoring, *, level=0):
    """The registered development score variant `version` for the session's
    Challenge, verified; None without one. Refused, typed, before anything is
    read or spent."""
    if version is None:
        return None
    if level != 0:
        raise ScoreVariantRefused(LEVEL0_ONLY)
    dsv = _module()
    try:
        challenge = challenge_scoring.resolve(scoring).challenge_id
    except (challenge_scoring.ScoringUnavailable, TypeError):
        raise ScoreVariantRefused("challenge_scoring_must_be_named") from None
    try:
        variant = _load(version)
    except dsv.ScoreVariantRefused as refused:
        raise ScoreVariantRefused(refused.code) from None
    if variant.challenge_id != challenge:
        raise ScoreVariantRefused("score_variant_is_another_challenges")
    practice_legs(variant.challenge_id)
    return variant


def practice_legs(challenge):
    """The Challenge's practice-legs entry; refused when none is served or its
    value contract is not pinned."""
    entry = PRACTICE_LEGS.get(challenge)
    if entry is None:
        raise ScoreVariantRefused("score_variant_practice_legs_not_served")
    if entry["value_contract"] is None:
        raise ScoreVariantRefused("score_variant_practice_contract_unpinned")
    return entry


def identity_of(variant):
    """What a session pins and every result records; None without a variant."""
    return None if variant is None else variant.identity()


def _battery_legs(base, value_contract):
    """A member's `member_legs` row on battery's public PRACTICE references:
    the practice store `score_practice` scores on, every practice case, a
    missing case asked empty exactly as the base rule asks it (`cover`)."""
    from carbon.battery.practice import practice_store
    from carbon.battery.value import contract

    store = practice_store(base.practice, base.material, base.root)
    document, _digest = contract.load(contract.CONTRACTS / value_contract)
    case_ids = list(base.practice.case_ids)
    tuning = _module().tuning_module(BATTERY)

    def legs(predictions):
        asked, _missing = challenge_scoring.cover(predictions, case_ids)
        return tuning.member_legs(document, asked, store, case_ids)

    return legs


_LEGS = {BATTERY: _battery_legs}


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
            entry = practice_legs(variant.challenge_id)
            legs = _LEGS[variant.challenge_id](base, entry["value_contract"])
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
    "LEVEL0_ONLY",
    "PRACTICE_LEGS",
    "ScoreVariantRefused",
    "VariantRule",
    "identity_of",
    "practice_legs",
    "resolve",
    "rule_for",
]
