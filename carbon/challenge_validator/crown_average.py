"""The crown's multi-rebuild average (the crown multi-rebuild average ruling (lead-records a322dea4)).

A new crown-rule version, applied going forward only. When a screening grade beats the bar, the
validator rebuilds that model N times on validator-chosen seeds and compares MEANS:

1. **Trigger** (`triggered`): only a screening grade that would change the crown, i.e. beats the king's
   stored MEAN plus the margin (or, with no king, Carbon's baseline floor plus the margin).
2. **N rebuilds** (`derive_seeds`): seed_i = HMAC-SHA256(K_crown, domain | challenge_id | submission_id | i)
   reduced into the registered seed range, never 0 (the official seed), all distinct. K_crown is a
   host-private owner-only file (`read_crown_key`), never in the repository and never in a worker
   container; only the integer seeds cross into the container, at build time. The seeds, the
   per-seed totals and the mean are PRIVATE: `public_view` is all a miner-facing surface may take.
3. **Admissibility before averaging** (constitution 7.3): every rebuild must be scored (every mandatory
   gate and the pack's leg minimums passed). Any gated or minimum-failed rebuild is no takeover,
   reason `unstable_across_seeds`. An infrastructure failure is retried and never counts against
   the miner.
4. **Decision**: the challenger takes the crown iff its mean exceeds the king's mean by MORE than
   margin_N; within it is a tie and the king keeps the crown.
5. **Host-fault check** (replaces the repeat for this path): one of the N seeds, chosen by the same
   secret derivation (`host_fault_index`), is rebuilt a second time and must agree within the
   registered rebuild noise. A mismatch is FAILED_INFRA with a typed alert; the crown does not move.

``margin_N = max(5 sigma_rebuild, 2 * SD_seed / sqrt(N))`` (`margin_n`; recal_stats spread rule
`2sd_mean_n`). N is a REGISTERED CONFIG VALUE (`scripts/validator_host_classes/crown_average.json`),
never a code constant, and the registered margin of a Challenge is valid only for the N it was
measured at: a Challenge with no margin registered at the configured N is UNAVAILABLE, never a guess.
The registry sits outside `carbon/` (like the rebuild-noise registry) so changing it never moves the
worker image id.

This module is pure decision logic: the rebuilds themselves are injected callables, so no worker,
GPU or pool is touched here. DEVELOPMENT / TESTNET only: no qualification, score or LIVE authority.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
from pathlib import Path

from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator.interface import is_digest

SCHEMA = "carbon.crown.average-rule.v1"
REGISTRY = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "validator_host_classes"
    / "crown_average.json"
)
#: The synthetic owner of the validator's averaging-rebuild tasks. Not an ss58 address and never a registered hotkey, so
#: it can never be in a metagraph snapshot or receive weight; a derived task is its alone, never a miner's.
HOST_OWNER = "carbon-crown-average-host"
SEED_DOMAIN = b"carbon.crown.average-seed.v1\x00"
FAULT_DOMAIN = b"carbon.crown.average-host-fault.v1\x00"
#: Outcomes a decision may carry (`bank_promotion`'s own vocabulary, so the caller reads one set).
UNSTABLE = "unstable_across_seeds"
MARGIN_UNREGISTERED = "crown_average_margin_unregistered"
#: A king whose mean was never measured (it was crowned by a single grade): crowns for the Challenge stay paused
#: until it is re-measured at switch-over. A single grade is never compared as if it were a mean.
KING_UNMEASURED = "crown_average_king_unmeasured"
REBUILD_UNAVAILABLE = "crown_average_rebuild_unavailable"
MEAN_EXCEEDS = "mean_exceeds_incumbent_beyond_margin"
MEAN_WITHIN = "mean_within_margin_or_tie"
FIRST_BEATS_BASELINE = "mean_beats_baseline_by_margin"
WITHIN_BASELINE = "mean_within_baseline_floor"
#: An engineering bound, not a scientific value: a rule asking for more rebuilds than this is a typo.
MAX_N = 1000


class CrownAverageInvalid(ValueError):
    """The registry, the key file or an input is not exactly the registered shape."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class Rule:
    """The loaded registry: N (per Challenge), the seed range and each Challenge's registered margin."""

    def __init__(self, document):
        self.version = document["rule_version"]
        self.seed_range = document["seed_range"]
        self._n = document["n"]
        self._override = document["challenge_n"]
        self._margins = document["margins"]

    def n_for(self, challenge_id):
        return self._override.get(challenge_id, self._n)

    def margin_digest_for(self, challenge_id):
        entry = self._margins.get(challenge_id)
        return None if entry is None else entry["measurement_digest"]

    def margin_for(self, challenge_id):
        """The registered margin_N of ``challenge_id`` at the N now configured for it, or None: absent, or
        measured at a different N (a stale margin is never used)."""
        entry = self._margins.get(challenge_id)
        if entry is None or entry["n"] != self.n_for(challenge_id):
            return None
        return entry["value"]


def _count(value, code, minimum=2):
    if type(value) is not int or not minimum <= value <= MAX_N:
        raise CrownAverageInvalid(code)
    return value


def load_rule(path=REGISTRY):
    document = json.loads(Path(path).read_bytes())
    names = {
        "schema",
        "rule_version",
        "n",
        "challenge_n",
        "seed_range",
        "margins",
    }
    if (
        type(document) is not dict
        or set(document) != names
        or document["schema"] != SCHEMA
        or type(document["rule_version"]) is not str
        or not document["rule_version"]
        or type(document["challenge_n"]) is not dict
        or type(document["margins"]) is not dict
    ):
        raise CrownAverageInvalid("crown_average_registry_invalid")
    _count(document["n"], "crown_average_n_invalid")
    # 2 and the top of the 32-bit positive range at least: a range this small has no seed to give.
    if type(document["seed_range"]) is not int or document["seed_range"] < 2**16:
        raise CrownAverageInvalid("crown_average_seed_range_invalid")
    from carbon.challenge_validator.exam_cap import registered_challenges

    known = registered_challenges()
    for challenge, n in document["challenge_n"].items():
        if challenge not in known:
            raise CrownAverageInvalid("crown_average_challenge_unknown")
        _count(n, "crown_average_n_invalid")
    for challenge, entry in document["margins"].items():
        if (
            challenge not in known
            or type(entry) is not dict
            or set(entry) != {"value", "n", "measurement_digest"}
            or type(entry["value"]) not in (int, float)
            or isinstance(entry["value"], bool)
            or not math.isfinite(entry["value"])
            or entry["value"] < 0
            or not is_digest(entry["measurement_digest"])
        ):
            raise CrownAverageInvalid("crown_average_margin_invalid")
        _count(entry["n"], "crown_average_n_invalid")
    return Rule(document)


def read_crown_key(name) -> bytes:
    """K_crown from a configured private file: an exact absolute regular file, owner-private, 32 to 4096
    bytes (like the speed-sample key). It is held by the validator host only and never leaves it.
    """
    selected = Path(name) if type(name) is str else None
    if (
        selected is None
        or not selected.is_absolute()
        or selected.is_symlink()
        or not selected.is_file()
        or selected.resolve() != selected
        or (selected.stat().st_mode & 0o077)
        or not 32 <= selected.stat().st_size <= 4096
    ):
        raise CrownAverageInvalid("crown_key_file_invalid")
    return selected.read_bytes()


def _mac(key, domain, challenge_id, submission_id, *parts):
    if type(key) is not bytes or len(key) < 32:
        raise CrownAverageInvalid("crown_key_invalid")
    if type(challenge_id) is not str or type(submission_id) is not str:
        raise CrownAverageInvalid("crown_identity_invalid")
    message = b"\x1f".join(
        [
            challenge_id.encode(),
            submission_id.encode(),
            *(str(p).encode() for p in parts),
        ]
    )
    return hmac.new(key, domain + message, hashlib.sha256).digest()


def derive_seeds(key, challenge_id, submission_id, n, seed_range):
    """The N averaging seeds: ``HMAC-SHA256(K_crown, domain | challenge_id | submission_id | i)`` reduced
    into ``1 .. seed_range - 1``. Never 0 (the official seed) and all distinct: a collision or a zero
    takes the next candidate (``attempt``), so the result is a pure function of the inputs.
    """
    _count(n, "crown_average_n_invalid")
    if type(seed_range) is not int or seed_range < 2**16:
        raise CrownAverageInvalid("crown_average_seed_range_invalid")
    seeds = []
    for index in range(n):
        attempt = 0
        while True:
            digest = _mac(key, SEED_DOMAIN, challenge_id, submission_id, index, attempt)
            seed = 1 + int.from_bytes(digest[:8], "big") % (seed_range - 1)
            if seed not in seeds:
                break
            attempt += 1
        seeds.append(seed)
    return seeds


def host_fault_index(key, challenge_id, submission_id, n):
    """Which of the N seeds is rebuilt a second time, chosen by the same secret derivation."""
    _count(n, "crown_average_n_invalid")
    digest = _mac(key, FAULT_DOMAIN, challenge_id, submission_id)
    return int.from_bytes(digest[:8], "big") % n


def margin_n(seed_sd, n, sigma=0.0):
    """margin_N = max(5 sigma_rebuild, 2 * SD_seed / sqrt(N)) (recal_stats spread rule `2sd_mean_n`)."""
    _count(n, "crown_average_n_invalid")
    for value in (seed_sd, sigma):
        if (
            type(value) not in (int, float)
            or isinstance(value, bool)
            or not math.isfinite(value)
            or value < 0
        ):
            raise CrownAverageInvalid("crown_average_margin_input_invalid")
    return max(5 * sigma, 2 * seed_sd / math.sqrt(n))


def triggered(screening_total, king_mean, baseline_floor, margin):
    """Whether a screening grade would change the crown, so the N rebuilds are worth their GPU time: its total
    beats the king's MEAN plus the margin, or the baseline floor plus the margin when there is no king.
    Anything else is a plain grade with no extra cost."""
    for value in (screening_total, margin):
        if type(value) not in (int, float) or not math.isfinite(value):
            return False
    bar = king_mean if king_mean is not None else baseline_floor
    if bar is None or not math.isfinite(bar):
        return False
    return screening_total > bar + margin


class CrownAverageUnavailable(Exception):
    """The averaged crown decision cannot be made (no registered margin, no rebuild noise): nothing moves."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


#: The installed rule, or None (off). Set once at receiver start from its configuration (`install`), like the
#: official receipt store; `BankPromotion.consider_private` reads it.
ACTIVE = None


class Active:
    """The rule in force on one receiver: the registered rule and K_crown (never printed, never logged)."""

    def __init__(self, rule, key):
        self.rule, self._key = rule, key

    def __repr__(self):
        return "Active(<redacted>)"

    def screening(self, store, pair, comparator):
        """``(pair, comparator)`` for the screening comparison under this rule: the incumbent's total is its stored
        MEAN (a scored king with no recorded mean is KING_UNMEASURED: crowns stay paused) and the margin is margin_N. So a
        screening win is exactly the trigger: it beats the king's mean by more than margin_N."""
        margin = self.rule.margin_for(comparator["challenge"])
        if margin is None:
            raise CrownAverageUnavailable(MARGIN_UNREGISTERED)
        noise = comparator.get("rebuild_noise")
        if noise is None:
            raise CrownAverageUnavailable("rebuild_noise_unregistered")
        incumbent = pair["incumbent"]
        if incumbent is not None:
            model = (incumbent.get("evidence") or {}).get("model_p")
            if (
                type(model) is dict
                and model.get("score_status") == bp.SCORED
                and model.get("total_score") is not None
            ):
                mean = store.crown_mean(incumbent["submission_id"])
                if mean is None:
                    raise CrownAverageUnavailable(KING_UNMEASURED)
                incumbent = json.loads(json.dumps(incumbent))
                incumbent["evidence"]["model_p"]["total_score"] = mean
                pair = {**pair, "incumbent": incumbent}
        screened = {
            **comparator,
            "rebuild_noise": {
                "value": margin,
                "measurement_digest": self.rule.margin_digest_for(
                    comparator["challenge"]
                ),
            },
        }
        return pair, screened

    def decide(
        self, store, submission_id, evaluation_key, pair, outcome, comparator, repeat
    ):
        """The averaged decision for a screening win, in place of the repeat. ``repeat.rebuild_at(seed)`` rebuilds
        and grades the model at one seed (the receiver's construction lane); without it nothing moves."""
        rebuild = getattr(repeat, "rebuild_at", None)
        if rebuild is None:
            return {**outcome, "outcome": bp.UNAVAILABLE, "reason": REBUILD_UNAVAILABLE}
        incumbent = pair["incumbent"]
        status, king_mean = (None, None) if incumbent is None else bp._scored(incumbent)

        def guarded(build):
            def run(seed):
                # a rebuild that cannot run says nothing about the model: retried, then UNAVAILABLE, never a loss
                try:
                    return build(seed)
                except (RebuildInfra, CrownAverageInvalid):
                    raise
                except Exception as error:
                    raise RebuildInfra("rebuild failed") from error

            return run

        # The host-fault second build is its OWN build of the same seed (`rebuild_again_at`), not the first one again.
        again = getattr(repeat, "rebuild_again_at", None) or rebuild

        # logged privately so the per-day trigger count is visible (abuse shows as a rate)
        store.record_crown_trigger(submission_id, evaluation_key)
        result = run_average(
            key=self._key,
            challenge_id=comparator["challenge"],
            submission_id=submission_id,
            rule=self.rule,
            rebuild=guarded(rebuild),
            rebuild_again=guarded(again),
            king_mean=king_mean if status == bp.SCORED else None,
            baseline_floor=comparator.get("baseline_total"),
            tolerance=(comparator.get("rebuild_noise") or {}).get("value"),
        )
        private = result.get("private")
        if private is not None:
            try:
                store.record_crown_average(submission_id, evaluation_key, private)
            except Exception as error:
                if getattr(error, "code", None) != "crown_average_changed":
                    raise
                # the same decision rebuilt differently: a host that does not reproduce is not a grade
                return {
                    **outcome,
                    "outcome": bp.FAILED_INFRA,
                    "reason": "crown_average_record_changed",
                }
        held = {**outcome, "outcome": result["outcome"], "reason": result["reason"]}
        if "alert" in result:
            held["alert"] = result["alert"]
        return held


def install(cfg):
    """Turn the rule on (or off) from a receiver's configuration: ``cfg["crown_average"] = {"key_file": ...}``."""
    global ACTIVE
    section = cfg.get("crown_average")
    if section is None:
        ACTIVE = None
        return
    if type(section) is not dict or set(section) != {"key_file"}:
        raise CrownAverageInvalid("crown_average_selection_invalid")
    ACTIVE = Active(load_rule(), read_crown_key(section["key_file"]))


class RebuildInfra(Exception):
    """A rebuild failed for a reason that says nothing about the model (infrastructure): retried, never counted
    against the miner."""


def _result(outcome, reason, **extra):
    return {"outcome": outcome, "reason": reason, **extra}


def _one(rebuild, seed, retries):
    """The scored grade of one seed's rebuild, retrying infrastructure failures. Returns ``(status, total)`` or
    raises `RebuildInfra` when every attempt failed."""
    for _ in range(retries + 1):
        try:
            body = rebuild(seed)
        except RebuildInfra:
            continue
        model = ((body or {}).get("evidence") or {}).get("model_p")
        status = model.get("score_status") if type(model) is dict else None
        if status in bp.NOT_MEASURED:
            continue
        if type(status) is not str:
            raise CrownAverageInvalid("crown_average_grade_invalid")
        total = model.get("total_score")
        if status == bp.SCORED and (
            type(total) not in (int, float)
            or isinstance(total, bool)
            or not math.isfinite(total)
        ):
            raise CrownAverageInvalid("crown_average_grade_invalid")
        return status, (float(total) if status == bp.SCORED else None), body
    raise RebuildInfra("every attempt failed")


def run_average(
    *,
    key,
    challenge_id,
    submission_id,
    rule,
    rebuild,
    rebuild_again,
    king_mean,
    baseline_floor,
    tolerance,
    retries=2,
):
    """The N-rebuild decision for one triggered challenger.

    ``rebuild(seed)`` and ``rebuild_again(seed)`` (the host-fault second build) each return a grade body shaped like
    `PoolStore.private_evaluation_pair` rows and may raise `RebuildInfra`. ``king_mean`` is the king's stored
    mean (None with no king, then ``baseline_floor`` is the bar). ``tolerance`` is the Challenge's registered
    rebuild noise: the host-fault pair must agree within it.

    Returns ``{"outcome", "reason", ...}`` in `bank_promotion`'s vocabulary. The ``private`` entry (seeds, per-seed
    totals, mean) goes to the private evaluation only (`public_view` is the miner-facing remainder).
    """
    n = rule.n_for(challenge_id)
    margin = rule.margin_for(challenge_id)
    if margin is None:
        return _result(bp.UNAVAILABLE, MARGIN_UNREGISTERED)
    if tolerance is None:
        return _result(bp.UNAVAILABLE, bp.REPEAT_TOLERANCE_UNREGISTERED)
    seeds = derive_seeds(key, challenge_id, submission_id, n, rule.seed_range)
    grades = []
    for seed in seeds:
        try:
            grades.append((seed, *_one(rebuild, seed, retries)))
        except RebuildInfra:
            return _result(bp.UNAVAILABLE, REBUILD_UNAVAILABLE)
    private = {"seeds": seeds, "n": n, "margin": margin}
    if any(status != bp.SCORED for _seed, status, _t, _b in grades):
        # admissibility before averaging: a seed-fragile model cannot win on its good seeds
        return _result(
            bp.NO_WINNER if king_mean is None else bp.INCUMBENT_KEEPS,
            UNSTABLE,
            private={
                **private,
                "statuses": [status for _s, status, _t, _b in grades],
            },
        )
    totals = [total for _seed, _status, total, _body in grades]
    mean = math.fsum(totals) / n
    private.update({"totals": totals, "mean": mean})
    # host-fault check: one secretly chosen seed is rebuilt again and must reproduce
    chosen = host_fault_index(key, challenge_id, submission_id, n)
    first_seed, _status, _total, first_body = grades[chosen]
    try:
        second_body = rebuild_again(first_seed)
        same = bp.repeat_agrees(first_body, second_body, tolerance)
    except Exception:  # noqa: BLE001 - a repeat that cannot run is not a grade
        return _result(bp.UNAVAILABLE, bp.REPEAT_UNAVAILABLE, private=private)
    if not same:
        return _result(
            bp.FAILED_INFRA,
            bp.REPEAT_MISMATCH,
            private=private,
            alert={
                "schema": bp.ALERT_SCHEMA,
                "code": bp.REPEAT_MISMATCH,
                "states": [submission_id],
                "action": "recheck_validator_host",
            },
        )
    if king_mean is None:
        if baseline_floor is None:
            return _result(
                bp.UNAVAILABLE, "baseline_floor_unregistered", private=private
            )
        if mean > baseline_floor + margin:
            return _result(bp.FIRST_INCUMBENT, FIRST_BEATS_BASELINE, private=private)
        return _result(bp.NO_WINNER, WITHIN_BASELINE, private=private)
    if mean > king_mean + margin:
        return _result(bp.CHALLENGER, MEAN_EXCEEDS, private=private)
    return _result(bp.INCUMBENT_KEEPS, MEAN_WITHIN, private=private)


def public_view(result):
    """What a miner-facing surface (ladder, koth, board feed, status) may take from a decision: the outcome and
    reason only. Never the seeds, the per-seed totals, the mean or the margin."""
    return {"outcome": result["outcome"], "reason": result["reason"]}


__all__ = [
    "ACTIVE",
    "Active",
    "CrownAverageInvalid",
    "CrownAverageUnavailable",
    "Rule",
    "derive_seeds",
    "host_fault_index",
    "install",
    "load_rule",
    "margin_n",
    "public_view",
    "read_crown_key",
    "run_average",
    "triggered",
]
