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

from carbon.scoring import grade_feedback as gf

SCHEMA = "carbon.koth.public.v1"
PATH = "/carbon/v1/koth/"
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
            "hotkey": standing["owner"],
            "total": standing["total"],
            "since_epoch": epoch,
        }


def serve(view, challenge):
    """``(status, document-or-refusal)`` for ``GET PATH<challenge_id>`` on a receiver
    serving ``challenge`` (a ``ChallengeKey``). ``view`` is None when this grader does
    not publish its king yet."""
    if view is None:
        return 404, {"refused": "koth_unpublished"}
    try:
        return 200, document(
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


__all__ = ["PATH", "SCHEMA", "KothPublicRefused", "PoolKingView", "document", "serve"]
