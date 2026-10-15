"""The registered score on the validator's paid path (VALIDATOR-26).

OWNER-BATTERY-SCORE-RULE-01 adopted a score from the score-tuning registry;
OWNER-BATTERY-V3-FINALS-01 fixed how it is used. A rule naming a registered
score (`exam.REGISTERED_SCORE`) takes its term from the deployment's
configuration: `{registry, registry_sha256, candidate}`, so a different
registered candidate (the score proof's winner) drops in by configuration,
and the rule's digest binds the term.

The score is computed exactly as the tuning study computed it, through
`score_tuning`'s own functions (`member_legs`, `score_member`,
`gate_verdict`) on a submission's stored predictions: never a second
implementation. The `q` leg is the Q3 decision regret on the design
questions of the score's active windows (`design_scoring`), pooled over
them.

This module is value-analysis code. The daemon never imports it: an operator
entry point installs it on a validator (`install`), as the quiz and design
measures are.

DEVELOPMENT only: no qualification, LIVE, reward or mainnet claim.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

TERM_FIELDS = frozenset({"registry", "registry_sha256", "candidate", "decision"})
REGISTRY_DIR = "docs/development/evidence/battery-score-tuning/"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_DECISION = re.compile(r"OWNER-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{2}\Z")


class RegisteredScoreRefused(ValueError):
    """A typed refusal; the code names no private value."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def check_term(term):
    """The deployment's registered-score term, shape only: exactly
    `registry` (a file under the tuning registry directory),
    `registry_sha256` (its hex digest), `candidate` (an id) and `decision`
    (the owner's record adopting the candidate, `OWNER-…-NN`)."""
    if (
        type(term) is not dict
        or set(term) != TERM_FIELDS
        or type(term["registry"]) is not str
        or not term["registry"].startswith(REGISTRY_DIR)
        or not term["registry"].endswith(".json")
        or ".." in term["registry"]
        or type(term["registry_sha256"]) is not str
        or not _SHA.fullmatch(term["registry_sha256"])
        or type(term["candidate"]) is not str
        or not term["candidate"]
        or type(term["decision"]) is not str
        or not _DECISION.match(term["decision"])
    ):
        raise RegisteredScoreRefused("registered_score_term_malformed")
    return dict(term)


def check_decision(term, repository):
    """The owner's record adopting the term's candidate (the owner's #1101
    security conditions: a candidate change is owner-only, each with a
    decision record naming the candidate and the registry digest). The
    record is the `.agent/decisions/*.md` file whose heading names
    `term["decision"]`; its text must name both the candidate id and the
    registry sha256, or the scorer is refused."""
    decision = term["decision"]
    heading = re.compile(rf"\A## .*\b{re.escape(decision)}\b")
    for path in sorted((Path(repository) / ".agent" / "decisions").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if not heading.match(text):
            continue
        if term["candidate"] in text and term["registry_sha256"] in text:
            return path
        raise RegisteredScoreRefused("registered_score_decision_mismatch")
    raise RegisteredScoreRefused("registered_score_decision_unrecorded")


def _registry(term, repository, tuning):
    """Keep Git registration, or consume an externally pinned public bundle."""
    from carbon.validator_setup.bundle import (
        MANIFEST,
        RUNTIME_DIGEST_ENV,
        SetupRefused,
        verify,
    )

    expected = os.environ.get(RUNTIME_DIGEST_ENV)
    manifest = repository / MANIFEST
    bundle = None
    if expected is not None or manifest.exists() or manifest.is_symlink():
        if expected is None:
            raise RegisteredScoreRefused("registered_score_bundle_unbound")
        try:
            bundle = verify(repository.absolute(), expected)
        except SetupRefused:
            raise RegisteredScoreRefused("registered_score_bundle_refused") from None
        rows = {row["path"]: row for row in bundle.manifest["files"]}
        if term["registry"] not in rows:
            raise RegisteredScoreRefused("registered_score_registry_unavailable")
        if rows[term["registry"]]["digest"] != "sha256:" + term["registry_sha256"]:
            raise RegisteredScoreRefused("registered_score_registry_changed")
    try:
        candidates, identity = tuning.load_registry(
            repository / term["registry"],
            repository=None if bundle is not None else repository,
        )
    except (OSError, ValueError, tuning.TuningError, subprocess.SubprocessError):
        raise RegisteredScoreRefused("registered_score_registry_unavailable") from None
    if bundle is not None:
        # materialize takes only committed blobs; verify binds those exact
        # bytes to the external manifest pin and its immutable source revision.
        identity["commit"] = bundle.manifest["source_revision"]
    return candidates, identity


class RegisteredScore:
    """One registered candidate from clean Git or a verified committed bundle,
    checked against the configured digest and owner decision."""

    def __init__(self, term, repository):
        from carbon.battery import quiz_stratum as qs
        from carbon.challenge_validator.design_scoring import BatteryQ3Measures

        from . import score_tuning as st

        term = check_term(term)
        repository = Path(repository)
        candidates, identity = _registry(term, repository, st)
        if identity["sha256"] != term["registry_sha256"]:
            raise RegisteredScoreRefused("registered_score_registry_changed")
        candidate = candidates.get(term["candidate"])
        if candidate is None:
            raise RegisteredScoreRefused("registered_score_candidate_unknown")
        check_decision(term, repository)
        self.term = term
        self.registry_identity = identity
        self.candidate = candidate
        self.contract = qs.contract(repository)
        self.design = BatteryQ3Measures(repository)
        self._st = st

    def measure(self, predictions, case_ids, store, decision_regret):
        """The candidate on one model's stored predictions: its legs, raw
        score (higher is better) and gate verdict, from `score_tuning`."""
        st = self._st
        row = st.member_legs(
            self.contract, predictions, store, case_ids, decision_regret=decision_regret
        )
        return {
            "candidate": self.candidate.id,
            "score": st.score_member(self.candidate, row),
            "gate": st.gate_verdict(self.candidate, row),
            "eligible": bool(row["eligible"]),
            "legs": dict(row["legs"]),
            "gates": dict(row["gates"]),
        }

    @staticmethod
    def pooled(batches):
        """`pooled_regret`, on the installed scorer, so the daemon never
        imports this module."""
        return pooled_regret(batches)

    def gate(self, predictions, case_ids, store):
        """The candidate's gate verdict alone (finals:
        OWNER-BATTERY-V3-FINALS-01)."""
        st = self._st
        row = st.member_legs(self.contract, predictions, store, case_ids)
        return st.gate_verdict(self.candidate, row)


def pooled_regret(batches):
    """The Q3 decision regret pooled over the active windows' design
    results: each window's mean regret weighted by its questions. Returns
    `(regret, cause)`: cause `q_candidate_failed` when any window is the
    candidate's failure (INELIGIBLE), `q_unavailable` when any is not
    measured otherwise (VOID, a reference failure); else regret."""
    total, weight = 0.0, 0
    for result in batches.values():
        status = result.get("status")
        if status == "INELIGIBLE":
            return None, "q_candidate_failed"
        if status != "OK" or result.get("mean_regret") is None:
            return None, "q_unavailable"
        n = len(result.get("per_question") or []) or 1
        total += float(result["mean_regret"]) * n
        weight += n
    if not weight:
        return None, "q_unavailable"
    return total / weight, None


def install(target, repository=None):
    """Give a battery validator its registered score, when its rule names
    one. Returns the target."""
    rule = getattr(target, "rule", {}) or {}
    term = rule.get("score")
    if term is None:
        return target
    target.registered_score = RegisteredScore(
        term, repository if repository is not None else target.repository
    )
    return target


__all__ = [
    "RegisteredScore",
    "RegisteredScoreRefused",
    "check_term",
    "install",
    "pooled_regret",
]
