"""Development score variants (VALIDATOR-09; OWNER-GRAPHITE-TEST-WAVE-08 §3).

A development score variant is a score-tuning candidate promoted for Graphite
pressure runs and Attacker Mode X. There is **one definition** of a candidate
(the Test Lead, 2026-10-05): the Challenge's own score-tuning registry entry.
For battery, that is `carbon.battery.value.score_tuning` (#650): weights over
the legs a, r, g, m, n and p, an optional near-limit gate, and seed
stability.

A variant carries that entry **verbatim** and scores only through that
module's functions (`parse_candidate`, `score_member`, `gate_verdict`,
`candidate_scores`). A survivor promoted from the tuning registry therefore
scores byte-identically here. The geometric score is in (0, 1], where 1 is
best (OWNER-TESTNET-WEIGHTS-01 §2a).

**Registration.** A variant is registered before it is served: committed in
`development_score_variant_policies/` and pinned in its registry. It names
the tuning registry it was promoted from (`candidate_registry`: that file's
SHA-256 and commit).

**Never served to miners.** No miner surface, validator, intake or registry
path imports this module (`tests/invariants/test_score_variants_unreachable`).
A Challenge's scoring declares, as data only, the legs a variant may weight
(`ChallengeScoring.declared_score_components`).

The shipped registry starts empty. A fixture document is refused there, and
tests use their own directory. DEVELOPMENT only: no qualification, weight,
reward or LIVE authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

POLICY_DIR = Path(__file__).resolve().parent / "development_score_variant_policies"
SCHEMA = "carbon.development-score-variant.v1"
REGISTRY_SCHEMA = "carbon.development-score-variant-registry.v1"
SCOPE = "DEVELOPMENT_ONLY_NEVER_SERVED_TO_MINERS"
STATUSES = ("CANDIDATE", "SURVIVOR")
_KEYS = frozenset(
    {
        "schema",
        "version",
        "challenge_id",
        "base_rule",
        "candidate",
        "candidate_registry",
        "practice_value_contract",
        "scope",
        "status",
        "authority",
        "fixture",
    }
)
_HEX64 = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")


class ScoreVariantRefused(ValueError):
    """A typed refusal, by code."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def tuning_module(challenge_id):
    """The Challenge's score-tuning module: the one definition of a
    candidate. Refused for a Challenge without one."""
    if challenge_id == "battery-fastcharge-ageing-development-v1":
        from carbon.battery.value import score_tuning

        return score_tuning
    raise ScoreVariantRefused("score_variant_challenge_not_served")


@dataclass(frozen=True)
class ScoreVariant:
    version: str
    digest: str
    challenge_id: str
    base_rule: str
    entry: dict  # the score-tuning registry entry, verbatim
    candidate: object  # that entry, parsed by the Challenge's own module
    candidate_registry: dict
    #: The Challenge's practice value contract (decision data) this variant
    #: was registered against, by digest (the Test Lead's ruling, 2026-10-05).
    practice_value_contract: str
    status: str

    def identity(self):
        """What a result scored under this variant records."""
        return {
            "score_variant": self.version,
            "score_variant_digest": self.digest,
            "base_rule": self.base_rule,
            "candidate": self.entry["id"],
            "candidate_registry": dict(self.candidate_registry),
            "practice_value_contract": self.practice_value_contract,
            "label": "development_score_result:" + self.version,
        }


def _registry(directory):
    try:
        registry = json.loads((Path(directory) / "registry.json").read_text())
    except (OSError, ValueError):
        raise ScoreVariantRefused("score_variant_registry_unreadable") from None
    if (
        type(registry) is not dict
        or registry.get("schema") != REGISTRY_SCHEMA
        or type(registry.get("variants")) is not dict
    ):
        raise ScoreVariantRefused("score_variant_registry_malformed")
    return registry


def registered(directory=None):
    """Every registered version, by name."""
    return dict(_registry(POLICY_DIR if directory is None else directory)["variants"])


def _scoring(challenge_id):
    from carbon.challenge_validator.scoring import ScoringUnavailable, scoring_for

    try:
        return scoring_for(challenge_id)
    except ScoringUnavailable:
        raise ScoreVariantRefused("score_variant_challenge_not_served") from None


def _declared(challenge_id):
    return tuple(_scoring(challenge_id).declared_score_components)


def load_variant(version, *, directory=None, declared=None):
    """A registered variant, verified. `declared` overrides the Challenge's
    declared legs (tests only). The shipped registry refuses a fixture."""
    shipped = directory is None
    directory = POLICY_DIR if shipped else Path(directory)
    variants = _registry(directory)["variants"]
    if type(version) is not str or version not in variants:
        raise ScoreVariantRefused("score_variant_unregistered")
    try:
        document = json.loads((directory / f"{version}.json").read_text())
    except (OSError, ValueError):
        raise ScoreVariantRefused("score_variant_unreadable") from None
    pinned = variants[version]
    if digest(document) != pinned:
        raise ScoreVariantRefused("score_variant_altered")
    if (
        type(document) is not dict
        or set(document) != _KEYS
        or document["schema"] != SCHEMA
        or document["version"] != version
        or type(document["challenge_id"]) is not str
        or type(document["base_rule"]) is not str
        or document["scope"] != SCOPE
        or document["status"] not in STATUSES
        or type(document["fixture"]) is not bool
        or type(document["authority"]) is not dict
        or type(document["candidate"]) is not dict
    ):
        raise ScoreVariantRefused("score_variant_malformed")
    if shipped and document["fixture"]:
        raise ScoreVariantRefused("score_variant_fixture_in_shipped_registry")
    origin = document["candidate_registry"]
    if (
        type(origin) is not dict
        or set(origin) != {"sha256", "commit"}
        or type(origin["sha256"]) is not str
        or not _HEX64.fullmatch(origin["sha256"])
        or type(origin["commit"]) is not str
        or not _COMMIT.fullmatch(origin["commit"])
    ):
        # Promotion is from a committed tuning registry (registration first).
        raise ScoreVariantRefused("score_variant_candidate_registry_malformed")
    contract = document["practice_value_contract"]
    if type(contract) is not str or not (
        contract.startswith("sha256:") and _HEX64.fullmatch(contract[7:])
    ):
        raise ScoreVariantRefused("score_variant_practice_value_contract_malformed")
    pinned_contract = getattr(
        _scoring(document["challenge_id"]), "practice_value_contract", None
    )
    if pinned_contract is not None and contract != pinned_contract:
        # Registered against other decision data than the Challenge pins.
        raise ScoreVariantRefused("score_variant_practice_value_contract_not_pinned")
    module = tuning_module(document["challenge_id"])
    try:
        candidate = module.parse_candidate(document["candidate"])
    except module.TuningError as refused:
        raise ScoreVariantRefused(
            "score_variant_candidate_refused:" + refused.code
        ) from None
    if candidate.kind != "geometric":
        raise ScoreVariantRefused("score_variant_deciding_is_the_base_rule")
    declared = (
        _declared(document["challenge_id"]) if declared is None else tuple(declared)
    )
    if set(candidate.weights) - set(declared):
        raise ScoreVariantRefused("score_variant_component_not_declared")
    return ScoreVariant(
        version=version,
        digest=pinned,
        challenge_id=document["challenge_id"],
        base_rule=document["base_rule"],
        entry=dict(document["candidate"]),
        candidate=candidate,
        candidate_registry=dict(origin),
        practice_value_contract=contract,
        status=document["status"],
    )


def score_member(variant, row):
    """One member's score from its legs row (`member_legs`), through the
    Challenge's own scorer, with its gate verdict."""
    module = tuning_module(variant.challenge_id)
    return {
        **variant.identity(),
        "score": module.score_member(variant.candidate, row),
        "gate": module.gate_verdict(variant.candidate, row),
    }


def panel_scores(variant, legs, recipe_of):
    """Every member's score on a panel, exactly as the tuning loop computes
    it (`candidate_scores`: seed means when stable, gate failures last)."""
    return tuning_module(variant.challenge_id).candidate_scores(
        variant.candidate, legs, recipe_of
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m carbon.scoring.development_score_variants"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    show = sub.add_parser("show")
    show.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            result = registered()
        else:
            result = load_variant(args.version).identity()
    except ScoreVariantRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
