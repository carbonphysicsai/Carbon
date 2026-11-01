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
from decimal import ROUND_CEILING, Decimal

from carbon.scoring import grade_feedback as gf

SCHEMA = "carbon.koth.public.v1"
PATH = "/carbon/v1/koth/"
#: The v2 document (`document_v2`): the v1 fields plus ``to_beat_rule``, with the conservative score to beat. It is served
#: at ``PATH + <challenge_id> + V2_SUFFIX``; v1 stays byte-identical at its own path so current clients keep reading it.
SCHEMA_V2 = "carbon.koth.public.v2"
V2_SUFFIX = "/v2"
TO_BEAT_RULE = "floor_plus_step_plus_margin"
#: The decimals a displayed score to beat carries; it is always rounded UP.
TO_BEAT_DECIMALS = 3
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
    step = gf.step(margin)
    raw = (
        Decimal(repr(float(base)))
        + Decimal(repr(float(step)))
        + Decimal(repr(float(margin)))
    )
    shown = raw.quantize(Decimal(1).scaleb(-TO_BEAT_DECIMALS), rounding=ROUND_CEILING)
    return min(1.0, float(shown))


def document_v2(**kwargs):
    """The v2 public document: `document` (same arguments, same checks) with the conservative ``to_beat`` and
    ``to_beat_rule``. Every other field is exactly v1's."""
    base = document(**kwargs)
    result = {**base, "schema": SCHEMA_V2, "to_beat_rule": TO_BEAT_RULE}
    margin = base["margin"]
    if margin is not None:
        held = (
            base["king"]["total"]
            if base["king"] is not None
            else base["baseline_total"]
        )
        result["to_beat"] = to_beat_v2(held, margin)
    if set(result) != FIELDS_V2:
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
    ):
        self._open, self._epoch_of = open_store, epoch_of
        self.exam_version_label = exam_version_label
        self._noise_of, self._baseline = rebuild_noise_of, baseline

    @property
    def rebuild_noise(self):
        return self._noise_of()

    @property
    def baseline_total(self):
        return self._baseline()

    def crown_changes(self, limit=5):
        """The last ``limit`` changes of incumbent, newest first, from the pool's incumbent events only:
        ``[{"from_hotkey", "to_hotkey", "since_epoch", "total"}]``, each exactly what the king page shows for that king
        (its hotkey, the epoch its signed submission arrived in, its step-floored total). ``from_hotkey`` is None for a
        first incumbent. A change whose king cannot be shown on the king page (no scored total, no epoch, a host-owned
        derived row) is left out, never partly shown. Nothing but incumbent events is read: no undecided crown, averaging
        record, derived rebuild, regrade, repeat or private evaluation."""
        store = self._open()
        noise = self.rebuild_noise
        noise = None if noise is None else noise.get("value")

        def shown(model_id):
            standing = store.incumbent_standing(model_id)
            epoch = self._epoch_of(model_id)
            if standing is None or epoch is None:
                return None
            hotkey = _owner_hotkey(standing["owner"])
            if not _SS58.fullmatch(hotkey):
                return None
            total = gf.floor_to_step(_unit(standing["total"], "koth_king"), noise)
            return hotkey, total, epoch

        changes = []
        for event in store.events("incumbent"):
            body = event["body"]
            if type(body.get("model_id")) is not str:
                continue  # the crown was vacated: not a change of king
            new = shown(body["model_id"])
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

    def king(self):
        store = self._open()
        incumbent = store.incumbent()
        if incumbent is None:
            return None
        standing = store.incumbent_standing(incumbent["model_id"])
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


def serve(view, challenge, build=None):
    """``(status, document-or-refusal)`` for ``GET PATH<challenge_id>`` on a receiver
    serving ``challenge`` (a ``ChallengeKey``). ``view`` is None when this grader does
    not publish its king yet."""
    if view is None:
        return 404, {"refused": "koth_unpublished"}
    try:
        return 200, (build or document)(
            challenge_id=challenge.challenge_id,
            challenge_version=challenge.version,
            exam_version_label=view.exam_version_label,
            king=view.king(),
            rebuild_noise=view.rebuild_noise,
            baseline_total=view.baseline_total,
        )
    except KothPublicRefused as refused:
        return 503, {"refused": refused.code}
    except (AttributeError, OSError, ValueError, KeyError, TypeError):
        return 503, {"refused": "koth_unavailable"}


__all__ = [
    "PATH",
    "SCHEMA",
    "SCHEMA_V2",
    "V2_SUFFIX",
    "KothPublicRefused",
    "PoolKingView",
    "document",
    "document_v2",
    "serve",
    "serve_v2",
]
