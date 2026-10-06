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

from carbon.challenge_validator import scoring as challenge_scoring

BATTERY = "battery-fastcharge-ageing-development-v1"
LEVEL0_ONLY = "score_variant_runs_at_level_0_only"


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
    """The registered variant `version`, verified by #654's `load_variant`:
    among its refusals, a document recording no practice value contract
    (`score_variant_malformed`) or another than the Challenge pins
    (`score_variant_practice_value_contract_not_pinned`)."""
    return _module().load_variant(version, directory=_directory())


def resolve(version, scoring, *, level=0):
    """The registered development score variant `version` for the session's
    Challenge, verified; None without one. Refused, typed, before anything is
    read or spent: #654's refusals (unregistered, altered, malformed, another
    practice value contract than the Challenge pins and the rest), another
    Challenge's variant, and a Challenge that pins no practice value contract
    or whose pinned file no longer has its digest."""
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
        variant = _load(version)
    except dsv.ScoreVariantRefused as refused:
        raise ScoreVariantRefused(refused.code) from None
    if variant.challenge_id != scoring.challenge_id:
        raise ScoreVariantRefused("score_variant_is_another_challenges")
    # #654 checks the variant's record against the pin only when the
    # Challenge pins one; a Challenge that pins none serves no variant here.
    practice_contract(scoring)
    return variant


def practice_contract(scoring):
    """The Challenge's pinned practice value contract, `(file, digest)`,
    checked against the committed file. Refused when the Challenge pins none
    (`score_variant_practice_contract_unpinned`) or the file no longer has
    the pinned digest (`score_variant_practice_contract_altered`)."""
    scoring = challenge_scoring.resolve(scoring)
    pinned = scoring.practice_value_contract
    file = scoring.practice_value_contract_file
    if pinned is None or file is None or scoring.challenge_id not in _LEGS:
        raise ScoreVariantRefused("score_variant_practice_contract_unpinned")
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


def hidden_result(variant, target, full):
    """The variant's result on one hidden-pool score record, operator-side
    only (the hidden-pool variant gate the Test Lead approved).

    The legs are the practice variant's (`member_legs` under the pinned
    practice value contract), over the hidden pool's own case store and
    every active case, with a missing case asked empty (`cover`). `full` is
    the adapter's operator score record (`BatteryAdapter.score_record`). The
    result never reaches the agent, a miner, weights, the allow-list,
    settlement or rule v2's own record."""
    if variant.challenge_id != BATTERY:
        raise ScoreVariantRefused("score_variant_hidden_unserved")
    file, _pinned = practice_contract(
        challenge_scoring.scoring_for(variant.challenge_id)
    )
    document, _digest = _battery_contract(file)
    batches = list(full["active_batches"])
    case_ids = [
        case["case_id"]
        for fingerprint in batches
        for case in target.store.batch(fingerprint)["document"]["cases"]
    ]
    asked, _missing = challenge_scoring.cover(full["predictions"], case_ids)
    row = (
        _module()
        .tuning_module(BATTERY)
        .member_legs(document, asked, target._case_store(batches), case_ids)
    )
    return challenge_scoring.clean(_module().score_member(variant, row))


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
            # The variant identity already carries the pinned digest (#654).
            file, _pinned = practice_contract(scoring)
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
    "LEVEL0_ONLY",
    "ScoreVariantRefused",
    "VariantRule",
    "identity_of",
    "practice_contract",
    "resolve",
    "rule_for",
]
