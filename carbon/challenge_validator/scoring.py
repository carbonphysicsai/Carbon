"""The challenge-neutral scoring port for construction on Carbon's pods (VALIDATOR-01 slice 2).

Graphite constructs on Carbon's pods and Carbon scores each construction on its
own host against the Challenge's frozen rule (OWNER-GRAPHITE-TEST-WAVE-01 §3).
Everything specific to the Challenge comes through one `ChallengeScoring`:
- the construction contract in force, only if its newest expansion record pins
  it (`recorded_contract`);
- what Carbon builds for a strategy, by digest (`built_record`), which the pod
  must reproduce and Carbon's host checks independently;
- the backends its pods serve and the public material shipped to them;
- the job's own allowance, the contract envelope's worker deadline;
- the frozen PRACTICE rule: its score, its paired comparison and its identity;
- the session's baseline strategy and the construction objective text.

What is the same for every Challenge lives here, in `admit` and
`rebuild_differences`. Protected material never enters a pod: `ship_check`
refuses any data path naming a forbidden fragment, whatever the Challenge
declares.

Scores are DEVELOPMENT feedback on adaptively seen public cases, never an exam
result, a weight or a reward.
"""

from __future__ import annotations

import abc
import math

#: Never shipped to a pod, whatever a Challenge declares (lower-case
#: fragments). Kept from Graphite's pods (`FORBIDDEN_DATA`).
FORBIDDEN_DATA = ("ev4", "confirmation", "private", "secret", "credential", "canary")

#: What Carbon compares between what it computed and what the pod built.
REBUILT_FIELDS = (
    "challenge",
    "contract_digest",
    "recipe",
    "recipe_digest",
    "strategy_hash",
    "plan_digest",
    "staged",
    "program",
    "seed",
)


class Unrebuildable(ValueError):
    """Carbon cannot rebuild this construction; it is refused and never scored."""

    def __init__(self, code, issues=()):
        super().__init__(code)
        self.code, self.issues = code, tuple(issues)


class NotServed(ValueError):
    """Carbon rebuilds it, but these pods do not serve its backend."""


class ScoringUnavailable(LookupError):
    """No registered scoring serves this Challenge, or none was named while
    several are registered."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def clean(value):
    """`value` as plain JSON data: numpy scalars to Python, non-finite to None."""
    import numpy as np

    if isinstance(value, (float, np.floating)):
        value = float(value)
        return value if math.isfinite(value) else None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value


class PracticeRule(abc.ABC):
    """A Challenge's frozen rule on its public PRACTICE references.

    `identity` names the rule (its version, authority, status and comparison).
    """

    identity: dict

    @abc.abstractmethod
    def score(self, predictions):
        """`(rows, summary)`: per-case rows (each with `case_id`, `state`,
        `error`, `components`, `important`, `gates` where defined) and the
        aggregate (`eligible`, `score`, `important_score`, `n_scored`,
        `n_gate_failed`, `gate_failures`, `components`)."""

    @abc.abstractmethod
    def compare(self, baseline_rows, rows, eligible):
        """The frozen paired comparison against the baseline's rows."""


class ChallengeScoring(abc.ABC):
    """One Challenge version's construction scoring on Carbon's pods."""

    challenge_id: str
    challenge_version: str
    #: Reconstruction backends these pods serve.
    served_backends: tuple = ("jax",)
    #: Public material shipped to a pod beside the code.
    data_paths: tuple = ()
    #: The refusal code for a strategy naming another Challenge.
    wrong_challenge_code: str = "not_this_challenge"
    #: The Constructor's objective, in the brief.
    construction_objective: str = ""

    def challenge(self):
        return {"id": self.challenge_id, "version": self.challenge_version}

    def check_challenge(self, challenge):
        """Whether `challenge` ({id, version}) is the one this scoring serves."""
        return challenge == self.challenge()

    def contract(self):
        from carbon.reconstruction.capability_registry import contract

        return contract(self.challenge_id)

    def recorded_contract(self):
        """The contract in force, only if its newest expansion record pins it:
        construction stays inside the recorded contract, nothing wider."""
        from carbon.reconstruction import expansion_record

        history = expansion_record.records(self.challenge_id)
        live = self.contract().digest
        if not history or history[-1]["contract_digest"] != live:
            raise Unrebuildable("construction_contract_unrecorded")
        return {
            "challenge": self.challenge_id,
            "contract_digest": live,
            "record_sequence": history[-1]["sequence"],
        }

    def work_seconds(self):
        """The contract envelope's worker deadline: the job's own allowance."""
        seconds = dict(self.contract().envelope).get("worker_deadline_seconds")
        if type(seconds) is not int or seconds <= 0:
            raise ValueError("the construction contract states no worker deadline")
        return seconds

    def ship_check(self):
        """The data paths, refused if any names protected material."""
        for path in self.data_paths:
            if any(fragment in path.lower() for fragment in FORBIDDEN_DATA):
                raise ValueError("forbidden data path " + path)
        return tuple(self.data_paths)

    @abc.abstractmethod
    def built_record(self, strategy, contract_digest, seed, root):
        """`(record, files, program)`: what Carbon builds for `strategy`. The
        record carries every `REBUILT_FIELDS` entry; `files` are the staged
        files; `program` is the fixed program the pod runs."""

    def built_from(self, admitted, seed, root):
        """`(record, files, program)` from a construction already compiled
        (`compile_submission`'s result, or Graphite's development compile).
        `built_record` is compile then this. A Challenge that has no
        development path does not provide it."""
        raise NotImplementedError("this Challenge builds only from built_record")

    @abc.abstractmethod
    def refusal(self, error):
        """`(code, issues)` for a compile refusal `built_record` raised, or
        None when `error` is not a construction refusal."""

    @abc.abstractmethod
    def backend(self, record):
        """The reconstruction backend a built record names."""

    @abc.abstractmethod
    def frozen_rule(self, root):
        """The Challenge's `PracticeRule`."""

    @abc.abstractmethod
    def baseline_strategy(self):
        """The session's declared baseline strategy."""


def admit(scoring, strategy, seed, root, *, contract=None):
    """Compile `strategy` exactly as Carbon would rebuild it; return what Carbon
    would build plus the contract record's sequence. Raises `Unrebuildable`
    (never scored) or `NotServed` (Carbon rebuilds it, these pods do not)."""
    if type(strategy) is not dict:
        raise Unrebuildable("strategy_not_an_object")
    if strategy.get("challenge_id") != scoring.challenge_id:
        raise Unrebuildable(scoring.wrong_challenge_code)
    contract = scoring.recorded_contract() if contract is None else contract
    try:
        built, _files, _program = scoring.built_record(
            strategy, contract["contract_digest"], seed, root
        )
    except Exception as error:
        refused = scoring.refusal(error)
        if refused is None:
            raise
        code, issues = refused
        raise Unrebuildable(code, issues) from None
    backend = scoring.backend(built)
    if backend not in scoring.served_backends:
        raise NotServed("backend_not_served:" + str(backend))
    return {**built, "record_sequence": contract["record_sequence"]}


def rebuild_differences(expected, built):
    """The fields on which the pod's build differs from Carbon's own."""
    if type(built) is not dict:
        return ["built_record_missing"]
    return [name for name in REBUILT_FIELDS if built.get(name) != expected.get(name)]


# -- the registry ------------------------------------------------------------------------------
def _battery():
    from .battery_scoring import BatteryScoring

    return BatteryScoring()


#: Registered scorings by Challenge token. A Challenge joins by record, with
#: its own construction contract registered first.
_FACTORIES = {"battery-fastcharge-ageing-development-v1": _battery}
_CACHE = {}


def registered():
    return sorted(_FACTORIES)


def scoring_for(challenge_id=None):
    """The scoring for `challenge_id`. With None, the only registered one;
    refused once several are registered, so no caller silently defaults."""
    if challenge_id is None:
        if len(_FACTORIES) != 1:
            raise ScoringUnavailable("challenge_scoring_must_be_named")
        (challenge_id,) = _FACTORIES
    factory = _FACTORIES.get(challenge_id) if type(challenge_id) is str else None
    if factory is None:
        raise ScoringUnavailable("challenge_scoring_not_registered")
    if challenge_id not in _CACHE:
        _CACHE[challenge_id] = factory()
    return _CACHE[challenge_id]


def resolve(scoring):
    """`scoring` itself, or the only registered scoring when it is None."""
    if scoring is None:
        return scoring_for(None)
    if not isinstance(scoring, ChallengeScoring):
        raise TypeError("a ChallengeScoring is required")
    return scoring


__all__ = [
    "FORBIDDEN_DATA",
    "REBUILT_FIELDS",
    "ChallengeScoring",
    "NotServed",
    "PracticeRule",
    "ScoringUnavailable",
    "Unrebuildable",
    "admit",
    "clean",
    "rebuild_differences",
    "registered",
    "resolve",
    "scoring_for",
]
