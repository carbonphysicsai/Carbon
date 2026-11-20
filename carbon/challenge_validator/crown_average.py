"""The crown's multi-rebuild average (the crown multi-rebuild average ruling (lead-records a322dea4)).

A new crown-rule version, applied going forward only. When a screening grade beats the bar, the
validator rebuilds that model N times on validator-chosen seeds and compares MEANS:

1. **Trigger** (`triggered`): only a screening grade that would change the crown, i.e. beats the king's
   stored MEAN plus the margin (or, with no king, Carbon's baseline floor plus the margin).
2. **N rebuilds** (`derive_seeds`): seed_i = HMAC-SHA256(K_crown, domain | challenge_id | submission_id | i)
   reduced into the registered seed range, never 0 (the official seed), all distinct. K_crown is a
   host-private owner-only file (read by `crown_average_host`, the validator-host-only module; this one is pure and
   takes the key as bytes), never in the repository and never in a worker
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
from carbon.challenge_validator import host_quiet, registry_version
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
#: A stepwise crown decision ran ONE new rebuild and stopped (`Active.decide` with ``stepwise``): the contender is filed for the
#: sweep, which resumes it on its next tick from the rebuilds kept so far. Not a failure of anything: no attempt is counted,
#: no retry spacing applies and nothing is alerted.
REBUILD_IN_PROGRESS = "crown_average_rebuild_in_progress"
#: Every try of a seed met a busy host (`host_quiet`): Carbon's, never the model's; decided again later.
REBUILD_HOST_CONTENDED = host_quiet.REBUILD_HOST_CONTENDED
MEAN_EXCEEDS = "mean_exceeds_incumbent_beyond_margin"
MEAN_WITHIN = "mean_within_margin_or_tie"
FIRST_BEATS_BASELINE = "mean_beats_baseline_by_margin"
WITHIN_BASELINE = "mean_within_baseline_floor"
#: The incumbent re-measure (`Active.measure_incumbent`): the sitting king's N-rebuild mean is filed; or its rebuilds were
#: not all admissible across the seeds (filed, no mean: the king stays unmeasured, flagged); or the entry is not the king.
KING_MEASURED = "KING_MEASURED"
KING_UNSTABLE = "KING_UNSTABLE"
NOT_THE_KING = "crown_average_remeasure_not_the_sitting_king"
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

    def n_for(self, challenge_id, version=None):
        found = registry_version.find(self._override, challenge_id, version)
        return self._n if found is None else found

    def margin_digest_for(self, challenge_id, version=None):
        entry = registry_version.find(self._margins, challenge_id, version)
        return None if entry is None else entry["measurement_digest"]

    def margin_for(self, challenge_id, version=None):
        """The registered margin_N of ``challenge_id`` (a version's own entry first: `registry_version`) at the N now
        configured for it, or None: absent, or measured at a different N (a stale margin is never used).
        """
        entry = registry_version.find(self._margins, challenge_id, version)
        if entry is None or entry["n"] != self.n_for(challenge_id, version):
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
        if not registry_version.known_key(challenge, known):
            raise CrownAverageInvalid("crown_average_challenge_unknown")
        _count(n, "crown_average_n_invalid")
    for challenge, entry in document["margins"].items():
        if (
            not registry_version.known_key(challenge, known)
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

    def __init__(self, rule, key, *, stepwise=False):
        self.rule, self._key = rule, key
        #: A contender's decision runs at most ONE new rebuild per call and is resumed by the sweep from the rebuilds kept
        #: (`one_new_rebuild_per_call`), so a live grade runs between two rebuilds. Off here (the whole decision in one
        #: call, as before); the receiver turns it on at install (`crown_average_host.install`).
        self.stepwise = stepwise

    def __repr__(self):
        return "Active(<redacted>)"

    def screening(self, store, pair, comparator):
        """``(pair, comparator)`` for the screening comparison under this rule: the incumbent's total is its stored
        MEAN (a scored king with no recorded mean is KING_UNMEASURED: crowns stay paused) and the margin is margin_N. So a
        screening win is exactly the trigger: it beats the king's mean by more than margin_N. A KING_UNSTABLE king (its
        re-measure filed the per-seed statuses and no mean, `store.crown_average_unstable`) keeps its single registered
        total: challengers meet it plus margin_N, and the averaged decision compares their mean with that total.
        """
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
                # only a mean measured on the exam the king's grade in this pair is on (Validator 5 Nov 06:24: NO CARRY;
                # a mean filed on his previous key leaves him KING_UNMEASURED here, so crowns queue until he is re-measured)
                own_key = incumbent.get("evaluation_key")
                mean = store.crown_mean(incumbent["submission_id"], own_key)
                if mean is not None:
                    incumbent = json.loads(json.dumps(incumbent))
                    incumbent["evidence"]["model_p"]["total_score"] = mean
                    pair = {**pair, "incumbent": incumbent}
                elif not store.crown_average_unstable(
                    incumbent["submission_id"], own_key
                ):
                    raise CrownAverageUnavailable(KING_UNMEASURED)
                # else: a KING_UNSTABLE king (its re-measure was seed-fragile, filed with no mean) keeps its crown,
                # flagged by that record, and is met at its single registered total plus margin_N (the owner's
                # unstable-king decision of 2026-11-02): the pair is left as it is.
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
        and grades the model at one seed (the receiver's construction lane); without it nothing moves.
        """
        rebuild = getattr(repeat, "rebuild_at", None)
        if rebuild is None:
            return {**outcome, "outcome": bp.UNAVAILABLE, "reason": REBUILD_UNAVAILABLE}
        incumbent = pair["incumbent"]
        status, king_mean = (None, None) if incumbent is None else bp._scored(incumbent)
        guarded = _guarded

        # The host-fault second build is its OWN build of the same seed (`rebuild_again_at`), not the first one again.
        again = getattr(repeat, "rebuild_again_at", None) or rebuild

        # logged privately so the per-day trigger count is visible (abuse shows as a rate)
        store.record_crown_trigger(submission_id, evaluation_key)
        if self.stepwise and hasattr(store, "crown_rebuild_cached"):
            rebuild, again = one_new_rebuild_per_call(
                store,
                submission_id,
                evaluation_key,
                rebuild,
                again,
                retry_in_call=True,
            )
        try:
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
                keep=_kept_attempts(store, submission_id, evaluation_key),
            )
        except RebuildStep:
            # One new rebuild ran and was kept; the rest wait for the sweep's next tick (the contender stays filed).
            return {
                **outcome,
                "outcome": bp.UNAVAILABLE,
                "reason": REBUILD_IN_PROGRESS,
            }
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

    def measure_incumbent(
        self, store, submission_id, evaluation_key, comparator, repeat
    ):
        """The SITTING king's N-rebuild mean, filed so the averaged rule can compare mean with mean (`screening` reads it
        back through `store.crown_mean`; without it every crown pauses as KING_UNMEASURED). It is the same `run_average` a
        challenger's trigger runs: the same seeds for this submission, the same host-owned uncounted rebuilds
        (``repeat.rebuild_at``, seam B for a graph king), the same host-fault second build. Only the incumbent; it moves
        no crown, logs no trigger and returns no seed, total or mean. A rebuild that cannot run is retried, then
        UNAVAILABLE with nothing filed (run it again); a host-fault mismatch or a record that does not reproduce is
        FAILED_INFRA with nothing new filed."""
        king = store.incumbent()
        if king is None or king.get("model_id") != submission_id:
            raise CrownAverageUnavailable(NOT_THE_KING)
        rebuild = getattr(repeat, "rebuild_at", None)
        if rebuild is None:
            return _result(bp.UNAVAILABLE, REBUILD_UNAVAILABLE)
        again = getattr(repeat, "rebuild_again_at", None) or rebuild
        result = run_average(
            key=self._key,
            challenge_id=comparator["challenge"],
            submission_id=submission_id,
            rule=self.rule,
            rebuild=_guarded(rebuild),
            rebuild_again=_guarded(again),
            king_mean=None,
            baseline_floor=comparator.get("baseline_total"),
            tolerance=(comparator.get("rebuild_noise") or {}).get("value"),
            keep=_kept_attempts(store, submission_id, evaluation_key),
        )
        private = result.get("private")
        host_checked = result["reason"] not in (
            bp.REPEAT_UNAVAILABLE,
            bp.REPEAT_MISMATCH,
        )
        if result["reason"] == UNSTABLE:
            outcome = KING_UNSTABLE
        elif private is not None and "mean" in private and host_checked:
            outcome = KING_MEASURED
        else:
            return _result(result["outcome"], result["reason"])
        try:
            store.record_crown_average(submission_id, evaluation_key, private)
        except Exception as error:
            if getattr(error, "code", None) != "crown_average_changed":
                raise
            return _result(bp.FAILED_INFRA, "crown_average_record_changed")
        return _result(outcome, result["reason"])


def _guarded(build):
    """``build(seed)`` with any failure that is not the model's typed as `RebuildInfra`: a rebuild that cannot run says
    nothing about the model (retried, then UNAVAILABLE, never a loss)."""

    def run(seed):
        try:
            return build(seed)
        except (RebuildInfra, CrownAverageInvalid):
            raise
        except Exception as error:
            raise RebuildInfra("rebuild failed") from error

    return run


class RebuildInfra(Exception):
    """A rebuild failed for a reason that says nothing about the model (infrastructure): retried, never counted
    against the miner."""


class RebuildStep(BaseException):
    """Raised by a stepwise crown decision in place of a second NEW rebuild in one call. A BaseException, so the
    averaging loop's own infrastructure retries (`_guarded`, `_one`) never take it for a failed build.
    """


def one_new_rebuild_per_call(
    store, submission_id, key, first, second, *, retry_in_call=False
):
    """``(rebuild, again)`` wrapping ``first`` / ``second`` (the seeded rebuild and the host-fault second build): a rebuild
    already kept in ``store`` (`PoolStore.crown_rebuild_cached`) is returned from it; the first NEW one runs and is kept;
    any further new one raises `RebuildStep`. A grade that is not a measurement (infrastructure) is not kept. Shared by
    the king's stepwise re-measure and a contender's stepwise decision: the same cache, the same rule.

    ``retry_in_call`` (the contender's decision): the new rebuild counts as run only once it returned a MEASUREMENT (the body
    is kept), so an infrastructure failure, whether raised or returned as a FAILED_INFRA / INDETERMINATE_EVIDENCE body, is
    retried inside the call by the averaging loop's own retries (`_one`) and, if every try fails, ends the decision
    UNAVAILABLE ``rebuild_unavailable`` (an attempt counted, spaced, alerted: a persistent fault never burns the GPU every
    tick). The king's re-measure keeps its earlier rule (a failed new rebuild stops the call).
    """
    ran = []

    def kept(build, again):
        def run(seed, *rest):
            hit = store.crown_rebuild_cached(submission_id, key, seed, again)
            if hit is not None:
                return hit
            if ran:
                raise RebuildStep
            if not retry_in_call:
                ran.append(seed)
            body = build(seed, *rest)
            model = ((body or {}).get("evidence") or {}).get("model_p")
            status = model.get("score_status") if type(model) is dict else None
            measured = type(status) is str and status not in bp.NOT_MEASURED
            if measured:
                store.record_crown_rebuild(submission_id, key, seed, again, body)
            if retry_in_call and measured:
                # the step is counted only for a KEPT measurement: a returned FAILED_INFRA / INDETERMINATE_EVIDENCE body is
                # retried by the averaging loop (`_one`) and, if it never measures, ends the decision UNAVAILABLE
                # rebuild_unavailable (counted, spaced, alerted), never an endless REBUILD_IN_PROGRESS
                ran.append(seed)
            return body

        return run

    return kept(first, False), kept(second, True)


def _result(outcome, reason, **extra):
    return {"outcome": outcome, "reason": reason, **extra}


def _one(rebuild, seed, retries, keep=None):
    """The scored grade of one seed's rebuild, retrying infrastructure failures. Returns ``(status, total)`` or
    raises `RebuildInfra` when every attempt failed. ``keep`` (`_kept_attempts`) keeps each attempt the decision does
    not use as private data; it decides nothing."""
    contended = 0
    for _ in range(retries + 1):
        try:
            body = rebuild(seed)
        except RebuildInfra as failed:
            # a busy host's failure (`host_quiet`) is retried like any infrastructure failure, never the model's
            contended += str(failed) == REBUILD_HOST_CONTENDED
            _keep(keep, seed, False, str(failed), None)
            continue
        model = ((body or {}).get("evidence") or {}).get("model_p")
        status = model.get("score_status") if type(model) is dict else None
        if status in bp.NOT_MEASURED:
            _keep(keep, seed, False, status, body)
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
    if contended == retries + 1:
        raise RebuildInfra(REBUILD_HOST_CONTENDED)
    raise RebuildInfra("every attempt failed")


def _keep(keep, seed, again, reason, body):
    if keep is not None:
        keep(seed, again, reason, body)


#: a kept attempt's body is at most this many canonical JSON bytes (V2 11:26:59Z: a contended host's retries never add
#: MBs per attempt to the pool store); larger, only its sha256, size and model_p status/total are kept
KEPT_BODY_BYTES = 64 * 1024
#: members never kept as values (raw predictions, any base64): their sha256 and size stand in for them
_KEPT_AS_DIGEST = ("predictions", "base64", "_raw")


def _kept_body(body):
    """``body`` for a kept attempt: every member whose name holds `_KEPT_AS_DIGEST` replaced by its sha256 and size;
    then, if still over `KEPT_BODY_BYTES`, only the body's sha256, size and its model_p score status and total.
    """

    def canonical(value):
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str
        ).encode()

    def stand_in(value):
        raw = value.encode() if type(value) is str else canonical(value)
        return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}

    def strip(value):
        if type(value) is dict:
            return {
                k: (
                    stand_in(v)
                    if any(part in str(k) for part in _KEPT_AS_DIGEST)
                    else strip(v)
                )
                for k, v in value.items()
            }
        if type(value) is list:
            return [strip(v) for v in value]
        return value

    if body is None:
        return None
    kept = strip(body)
    raw = canonical(kept)
    if len(raw) <= KEPT_BODY_BYTES:
        return kept
    model = ((body if type(body) is dict else {}).get("evidence") or {}).get("model_p")
    model = model if type(model) is dict else {}
    return {
        "over_bound": True,
        **stand_in(body),
        "model_p": {
            "score_status": model.get("score_status"),
            "total_score": model.get("total_score"),
        },
    }


def _kept_attempts(store, submission_id, key):
    """A ``keep(seed, again, reason, body)`` for `run_average`: each crown rebuild attempt the decision did not use (a
    busy host's, an infrastructure failure, a grade that is not a measurement, a host-fault repeat that disagreed) is
    kept as private data, ``contended`` set for a busy host's (`PoolStore.record_crown_rebuild_attempt`; data harvest
    plan G6, Lead 20 Nov 2026). No decision reads it; the decision rule is unchanged. Never raises.
    """
    record = getattr(store, "record_crown_rebuild_attempt", None)
    if record is None or not is_digest(key):
        return None

    def keep(seed, again, reason, body):
        try:
            record(
                submission_id,
                key,
                seed,
                again,
                reason=str(reason),
                contended=reason == REBUILD_HOST_CONTENDED,
                body=_kept_body(body),
            )
        # kept data never changes or stops a decision
        except Exception:  # noqa: BLE001, S110
            pass

    return keep


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
    keep=None,
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
            grades.append((seed, *_one(rebuild, seed, retries, keep)))
        except RebuildInfra as failed:
            # every try met a busy host: said as such (never UNSTABLE, never a loss); otherwise as before
            reason = (
                REBUILD_HOST_CONTENDED
                if str(failed) == REBUILD_HOST_CONTENDED
                else REBUILD_UNAVAILABLE
            )
            return _result(bp.UNAVAILABLE, reason)
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
    # a repeat that cannot run is not a grade
    except Exception as failed:  # noqa: BLE001
        _keep(keep, first_seed, True, str(failed) or type(failed).__name__, None)
        return _result(bp.UNAVAILABLE, bp.REPEAT_UNAVAILABLE, private=private)
    if not same:
        _keep(keep, first_seed, True, bp.REPEAT_MISMATCH, second_body)
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
    "REBUILD_IN_PROGRESS",
    "Active",
    "CrownAverageInvalid",
    "CrownAverageUnavailable",
    "RebuildStep",
    "Rule",
    "derive_seeds",
    "host_fault_index",
    "load_rule",
    "margin_n",
    "one_new_rebuild_per_call",
    "public_view",
    "run_average",
    "triggered",
]
