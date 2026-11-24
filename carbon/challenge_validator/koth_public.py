"""The public, read-only king document: ``GET /carbon/v1/koth/<challenge_id>``.

What a miner may know about the crown, and nothing else: the king's hotkey and
Ladder-stepped total, the margin a challenger must clear, the score to beat, and
Carbon's baseline while no one is king. The contract is exactly what Launchpad's
reader (``scripts/dev/miner_launchpad/king.py``) enforces:

- closed field set ``schema, challenge_id, challenge_version, exam_version_label, king,
  margin, to_beat, baseline_total``; king ``hotkey, total, since_epoch``;
- ``margin`` is the Challenge's registered rebuild noise, null when none is registered;
  ``to_beat`` is null iff ``margin`` is null, otherwise the displayed king total (or the
  baseline when there is no king) plus the margin;
- ``baseline_total`` is null whenever there is a king;
- every total is in 0..1; the king's total is rounded down to the Ladder step, so it
  never shows a finer value than the Ladder does (``grade_feedback.floor_to_step``).

It reads no per-case, per-leg or per-miner-but-the-king value. A grader that cannot
publish its king yet answers 404; a provider that fails answers 503, never a partial
document. This module is pure: the receiver supplies a ``view`` with ``king()``,
``exam_version_label``, ``baseline_total`` and ``rebuild_noise``.
"""

from __future__ import annotations

import math
import re
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from carbon.scoring import grade_feedback as gf

SCHEMA = "carbon.koth.public.v1"
PATH = "/carbon/v1/koth/"
#: The v2 document (`document_v2`): the v1 fields plus ``to_beat_rule``, with the conservative score to beat. It is served
#: at ``PATH + <challenge_id> + V2_SUFFIX``; v1 stays byte-identical at its own path so current clients keep reading it.
SCHEMA_V2 = "carbon.koth.public.v2"
V2_SUFFIX = "/v2"
TO_BEAT_RULE = "floor_plus_step_plus_margin"
#: The v2 bar on a door with crown averaging on (Lead 5 Nov): a single screening grade must beat the king's N-rebuild
#: MEAN by more than margin_N (the averaging rule's screening step), so the score to beat is
#: ``floor(mean, step) + step + margin_N`` rounded UP (a KING_UNSTABLE king: his single total for the mean; no king: the
#: baseline). Only that rounded-up sum is published: never the mean or margin_N on their own, never a seed. ``margin``
#: stays the registered rebuild noise (the Ladder step's basis) and the king's total stays his graded total.
TO_BEAT_RULE_AVERAGED = "mean_floor_plus_step_plus_margin_n"
TO_BEAT_RULES = (TO_BEAT_RULE, TO_BEAT_RULE_AVERAGED)
#: The v3 document (`document_v3`, owner 16 Nov: "Show scores to 3 decimals, so a lead smaller than the margin is
#: visible. Make the posted bar match the real rule."): v2's field set, served at ``PATH + <challenge_id> + V3_SUFFIX``.
#: The king's total and Carbon's baseline are shown at `TOTAL_DECIMALS` (round half up) from the EXACT value, not
#: floored to the Ladder step, and the single-grade score to beat is the crown rule's own bar (`TO_BEAT_RULE_EXACT`).
#: Display only: crowns are decided on exact totals (`bank_promotion.compare_private_pair`), never on a shown number.
#: A new version at its own path because a v2 reader (the Launchpad kit before 16 Nov) refuses any rule id but v2's
#: own: v1 and v2 stay byte-identical, so every deployed reader keeps reading them.
SCHEMA_V3 = "carbon.koth.public.v3"
V3_SUFFIX = "/v3"
#: The v3 single-grade bar: a challenger is crowned iff his exact total > the king's exact total + the registered
#: margin, so the score to beat is ``king exact total + margin`` (no king: Carbon's exact baseline + margin, the
#: first-crown rule), rounded UP to `TO_BEAT_DECIMALS`, capped at 1 (`to_beat_exact`).
TO_BEAT_RULE_EXACT = "king_plus_margin"
#: The rules a v3 document states: the exact bar, or the averaged one on a door with crown averaging on.
TO_BEAT_RULES_V3 = (TO_BEAT_RULE_EXACT, TO_BEAT_RULE_AVERAGED)
#: The decimals a displayed score to beat carries; it is always rounded UP.
TO_BEAT_DECIMALS = 3
#: The decimals a v3 total carries (the king's, Carbon's baseline, a crown change's): rounded HALF UP from the exact one.
TOTAL_DECIMALS = 3
MAX_BYTES = 16384
FIELDS = frozenset(
    {
        "schema",
        "challenge_id",
        "challenge_version",
        "exam_version_label",
        "king",
        "margin",
        "to_beat",
        "baseline_total",
    }
)
FIELDS_V2 = FIELDS | {"to_beat_rule"}
FIELDS_V3 = FIELDS_V2
KING_FIELDS = frozenset({"hotkey", "total", "since_epoch"})
_VERSION = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._:+-]{0,63}")
_SS58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{47,48}")


class KothPublicRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _unit(value, code, *, nullable=False):
    if value is None and nullable:
        return None
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not 0 <= value <= 1
    ):
        raise KothPublicRefused(code)
    return float(value)


def document(
    *,
    challenge_id,
    challenge_version,
    exam_version_label,
    king,
    rebuild_noise,
    baseline_total,
):
    """The closed public document, or a typed refusal. ``king`` is
    ``{"hotkey", "total", "since_epoch"}`` (total as graded, unrounded) or None;
    ``rebuild_noise`` the registered ``{value, measurement_digest}`` or None."""
    if (
        type(challenge_id) is not str
        or not challenge_id
        or type(challenge_version) is not str
        or not _VERSION.fullmatch(challenge_version)
        or type(exam_version_label) is not str
        or not _LABEL.fullmatch(exam_version_label)
    ):
        raise KothPublicRefused("koth_identity")
    noise = None if rebuild_noise is None else rebuild_noise.get("value")
    margin = _unit(noise, "koth_margin", nullable=True)
    shown = None
    if king is not None:
        if (
            type(king) is not dict
            or type(king.get("hotkey")) is not str
            or not _SS58.fullmatch(king["hotkey"])
            or type(king.get("since_epoch")) is not int
            or king["since_epoch"] < 0
        ):
            raise KothPublicRefused("koth_king")
        total = gf.floor_to_step(_unit(king.get("total"), "koth_king"), noise)
        shown = {
            "hotkey": king["hotkey"],
            "total": total,
            "since_epoch": king["since_epoch"],
        }
        base = total
        baseline = None
    else:
        baseline = _unit(baseline_total, "koth_baseline", nullable=True)
        if baseline is not None:
            baseline = gf.floor_to_step(baseline, noise)
        base = baseline
    to_beat = None
    if margin is not None and base is not None:
        to_beat = min(1.0, base + margin)
    elif margin is not None:
        # a margin with nothing to measure it from: the contract refuses it
        margin = None
    result = {
        "schema": SCHEMA,
        "challenge_id": challenge_id,
        "challenge_version": challenge_version,
        "exam_version_label": exam_version_label,
        "king": shown,
        "margin": margin,
        "to_beat": to_beat,
        "baseline_total": baseline,
    }
    if set(result) != FIELDS or (shown is not None and set(shown) != KING_FIELDS):
        raise KothPublicRefused("koth_fields")
    return result


def to_beat_v2(base, margin):
    """The conservative public score to beat: ``floor(total, step) + step + margin``, rounded UP to
    `TO_BEAT_DECIMALS`, capped at 1. ``base`` is the already step-floored king total (or baseline), so this reads
    public values only; the true bar (exact total + margin) is always below it, by at most one step.
    """
    return _rounded_up(base, gf.step(margin), margin)


def to_beat_exact(total, margin):
    """The v3 single-grade score to beat (`TO_BEAT_RULE_EXACT`): the king's EXACT total (or Carbon's exact baseline)
    plus the registered margin, the crown rule's own bar, rounded UP to `TO_BEAT_DECIMALS`, capped at 1. A challenger
    is crowned iff his exact total exceeds ``total + margin``; the shown bar is never below that.
    """
    return _rounded_up(total, 0.0, margin)


def shown_total(value):
    """A total as a v3 document shows it: ``value`` rounded HALF UP to `TOTAL_DECIMALS`, exactly (decimal arithmetic
    on the float's shortest form), so 0.7795 shows 0.780 and 0.77949 shows 0.779."""
    exact = Decimal(repr(float(value)))
    grid = Decimal(1).scaleb(-TOTAL_DECIMALS)
    return float(exact.quantize(grid, rounding=ROUND_HALF_UP))


def _rounded_up(base, step, margin):
    raw = (
        Decimal(repr(float(base)))
        + Decimal(repr(float(step)))
        + Decimal(repr(float(margin)))
    )
    shown = raw.quantize(Decimal(1).scaleb(-TO_BEAT_DECIMALS), rounding=ROUND_CEILING)
    return min(1.0, float(shown))


def to_beat_averaged(bar, noise):
    """The conservative averaged score to beat (`TO_BEAT_RULE_AVERAGED`): ``bar`` is ``{"base", "margin"}`` (the king's
    exact mean, or the total that stands for it, and the registered margin_N), ``noise`` the rebuild noise that sets the
    Ladder step. The true bar (base + margin_N) is always below it, by at most one step plus the rounding.
    """
    if type(bar) is not dict or set(bar) != {"base", "margin"}:
        raise KothPublicRefused("koth_crown_bar")
    base = gf.floor_to_step(_unit(bar["base"], "koth_crown_bar"), noise)
    return _rounded_up(base, gf.step(noise), _unit(bar["margin"], "koth_crown_bar"))


def document_v2(*, crown_bar=None, **kwargs):
    """The v2 public document: `document` (same arguments, same checks) with the conservative ``to_beat`` and
    ``to_beat_rule``. Every other field is exactly v1's. ``crown_bar`` (`PoolKingView.crown_bar`) is the averaged bar of
    a door with crown averaging on; the score to beat is then `to_beat_averaged` under `TO_BEAT_RULE_AVERAGED`.
    """
    base = document(**kwargs)
    result = {**base, "schema": SCHEMA_V2, "to_beat_rule": TO_BEAT_RULE}
    margin = base["margin"]
    if margin is not None and crown_bar is not None:
        result["to_beat"] = to_beat_averaged(crown_bar, margin)
        result["to_beat_rule"] = TO_BEAT_RULE_AVERAGED
    elif margin is not None:
        held = (
            base["king"]["total"]
            if base["king"] is not None
            else base["baseline_total"]
        )
        result["to_beat"] = to_beat_v2(held, margin)
    if set(result) != FIELDS_V2:
        raise KothPublicRefused("koth_fields")
    return result


def document_v3(*, crown_bar=None, **kwargs):
    """The v3 public document (owner 16 Nov): `document` (same arguments, same checks) with ``to_beat_rule``; the
    king's total and Carbon's baseline shown at `TOTAL_DECIMALS`, half up, from their EXACT values; the score to beat
    `to_beat_exact` (exact total + margin, rounded up) under `TO_BEAT_RULE_EXACT`. ``margin`` and every other field are
    exactly v1's. ``crown_bar`` (`PoolKingView.crown_bar`) is the averaged bar of a door with crown averaging on; the
    score to beat is then `to_beat_averaged` under `TO_BEAT_RULE_AVERAGED`, as on v2.
    """
    base = document(**kwargs)
    result = {**base, "schema": SCHEMA_V3, "to_beat_rule": TO_BEAT_RULE_EXACT}
    # `document` checked both values and shows them floored to the step; v3 shows them from the exact value
    exact = None
    if base["king"] is not None:
        exact = float(kwargs["king"]["total"])
        result["king"] = {**base["king"], "total": shown_total(exact)}
    elif base["baseline_total"] is not None:
        exact = float(kwargs["baseline_total"])
        result["baseline_total"] = shown_total(exact)
    margin = base["margin"]
    if margin is not None and crown_bar is not None:
        result["to_beat"] = to_beat_averaged(crown_bar, margin)
        result["to_beat_rule"] = TO_BEAT_RULE_AVERAGED
    elif margin is not None:
        result["to_beat"] = to_beat_exact(exact, margin)
    if set(result) != FIELDS_V3:
        raise KothPublicRefused("koth_fields")
    return result


class PoolKingView:
    """The receiver's king view over its pool store: the incumbent, its owner hotkey
    and latest scored total, and the epoch its signed submission arrived in. It reads
    only; ``open_store`` returns the pool store, ``epoch_of`` maps a submission id to
    an epoch (or None), and ``baseline`` is Carbon's baseline total or None."""

    def __init__(
        self,
        *,
        open_store,
        epoch_of,
        exam_version_label,
        rebuild_noise_of,
        baseline=lambda: None,
        crown_bar_of=None,
        value=None,
    ):
        # ``value(model)``: the number this version is ranked by when it is not its total (`crown_official`)
        self._standing = {} if value is None else {"value": value}
        self._open, self._epoch_of = open_store, epoch_of
        self._crown_bar_of = crown_bar_of
        self.exam_version_label = exam_version_label
        self._noise_of, self._baseline = rebuild_noise_of, baseline

    @property
    def rebuild_noise(self):
        return self._noise_of()

    @property
    def baseline_total(self):
        return self._baseline()

    def crown_changes(self, limit=5, *, v3=False):
        """The last ``limit`` changes of incumbent, newest first, from the pool's incumbent events only:
        ``[{"from_hotkey", "to_hotkey", "since_epoch", "total"}]``, each exactly what the king page shows for that king
        (its hotkey, the epoch its signed submission arrived in, its step-floored total; with ``v3``, the total as the
        v3 page shows it, `shown_total`, for the v6 board only). ``from_hotkey`` is None for a
        first incumbent. A change whose king cannot be shown on the king page (no scored total, no epoch, a host-owned
        derived row) is left out, never partly shown. Nothing but incumbent events is read: no undecided crown, averaging
        record, derived rebuild, regrade, repeat or private evaluation."""
        store = self._open()
        noise = self.rebuild_noise
        noise = None if noise is None else noise.get("value")

        # A change decided on the total keeps showing its total when the version is ranked by another number now: only the
        # newest change of a king whose crown record names that number shows it.
        events = store.events("incumbent")
        newest = {}
        for place, event in enumerate(events):
            newest[event["body"].get("model_id")] = place

        def shown(model_id, place=None):
            ranked = (
                self._standing
                if self._standing
                and place is not None
                and newest.get(model_id) == place
                and store.crown_decided_by(model_id)
                else {}
            )
            standing = store.incumbent_standing(model_id, **ranked)
            epoch = self._epoch_of(model_id)
            if standing is None or epoch is None:
                return None
            hotkey = _owner_hotkey(standing["owner"])
            if not _SS58.fullmatch(hotkey):
                return None
            exact = _unit(standing["total"], "koth_king")
            total = shown_total(exact) if v3 else gf.floor_to_step(exact, noise)
            return hotkey, total, epoch

        changes = []
        for place, event in enumerate(events):
            body = event["body"]
            if type(body.get("model_id")) is not str:
                continue  # the crown was vacated: not a change of king
            new = shown(body["model_id"], place)
            previous = body.get("previous")
            old = None if previous is None else shown(previous)
            if new is None or (previous is not None and old is None):
                continue
            changes.append(
                {
                    "from_hotkey": None if old is None else old[0],
                    "to_hotkey": new[0],
                    "since_epoch": new[2],
                    "total": new[1],
                }
            )
        return changes[::-1][:limit]

    def crown_bar(self, challenge_id):
        """The averaged bar a screening grade must clear on a door with crown averaging on, or None: the receiver's
        ``crown_bar_of(challenge_id)`` (`direct_receiver._crown_bar`), which knows the averaging rule; this module does
        not. ``{"base", "margin"}`` is private: `document_v2` publishes only their rounded-up sum.
        """
        return None if self._crown_bar_of is None else self._crown_bar_of(challenge_id)

    def king(self):
        store = self._open()
        incumbent = store.incumbent()
        if incumbent is None:
            return None
        standing = store.incumbent_standing(incumbent["model_id"], **self._standing)
        epoch = self._epoch_of(incumbent["model_id"])
        if standing is None or epoch is None:
            return None
        return {
            "hotkey": _owner_hotkey(standing["owner"]),
            "total": standing["total"],
            "since_epoch": epoch,
        }


def _owner_hotkey(owner):
    """The king's hotkey from a stored evaluation's ``owner``. The pool store keeps it as
    ``{"hotkey", "request_digest"}`` (`PoolStore._private_model`); a bare hotkey string is
    taken as it is. Anything else is a typed refusal, never a partial king."""
    if type(owner) is dict:
        if set(owner) != {"hotkey", "request_digest"}:
            raise KothPublicRefused("koth_king")
        owner = owner["hotkey"]
    if type(owner) is not str:
        raise KothPublicRefused("koth_king")
    return owner


def serve_v2(view, challenge):
    """``(status, document-or-refusal)`` for ``GET PATH<challenge_id>V2_SUFFIX``: `serve`, v2 document."""
    return serve(view, challenge, build=document_v2)


def serve_v3(view, challenge):
    """``(status, document-or-refusal)`` for ``GET PATH<challenge_id>V3_SUFFIX``: `serve`, v3 document."""
    return serve(view, challenge, build=document_v3)


def serve(view, challenge, build=None):
    """``(status, document-or-refusal)`` for ``GET PATH<challenge_id>`` on a receiver
    serving ``challenge`` (a ``ChallengeKey``). ``view`` is None when this grader does
    not publish its king yet."""
    if view is None:
        return 404, {"refused": "koth_unpublished"}
    try:
        averaged = {}
        if build in (document_v2, document_v3) and hasattr(view, "crown_bar"):
            # only the v2 and v3 documents name their rule; v1 keeps the single-grade bar it has always stated
            averaged = {"crown_bar": view.crown_bar(challenge.challenge_id)}
        return 200, (build or document)(
            challenge_id=challenge.challenge_id,
            challenge_version=challenge.version,
            exam_version_label=view.exam_version_label,
            king=view.king(),
            rebuild_noise=view.rebuild_noise,
            baseline_total=view.baseline_total,
            **averaged,
        )
    except KothPublicRefused as refused:
        return 503, {"refused": refused.code}
    except (AttributeError, OSError, ValueError, KeyError, TypeError):
        return 503, {"refused": "koth_unavailable"}


__all__ = [
    "PATH",
    "SCHEMA",
    "SCHEMA_V2",
    "SCHEMA_V3",
    "TOTAL_DECIMALS",
    "TO_BEAT_RULE_AVERAGED",
    "TO_BEAT_RULE_EXACT",
    "V2_SUFFIX",
    "V3_SUFFIX",
    "KothPublicRefused",
    "PoolKingView",
    "document",
    "document_v2",
    "document_v3",
    "serve",
    "serve_v2",
    "serve_v3",
    "shown_total",
    "to_beat_exact",
]
