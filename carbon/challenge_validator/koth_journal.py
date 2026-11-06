"""One journal line per crown event on the receiver (Lead 5 Nov: the KOTH outcome was not logged, so 381 uncontended
challengers looked like a silent door).

Each line is the receiver's structured journal line (`carbon.battery.intake.log`: UTC time, service, event, closed
fields): task ids, evaluation keys, outcome and reason codes only; never a hotkey, path, score, seed or mean. Writing a
line never raises and never changes an outcome.
"""

from __future__ import annotations


def note(event, **fields):
    """Write one journal line; any failure is swallowed (a log line is never a decision)."""
    try:
        from carbon.battery.intake import log

        log(event, **fields)
    except Exception:  # noqa: BLE001, S110 - a log line never changes the outcome
        pass


def contention(path, candidate, outcome, incumbent=None, store=None):
    """The line of one crown comparison: ``path`` is live (a fresh grade) or sweep (a queued decision);
    ``incumbent`` is the king it met (read before the decision). With ``store`` (the pool store), the outcome and reason
    codes are also filed for the public launch board's queue (`PoolStore.record_crown_decision`); that write is swallowed
    on failure like the line, so it never changes an outcome."""
    if type(outcome) is not dict:
        return
    if store is not None and type(outcome.get("outcome")) is str:
        try:
            store.record_crown_decision(
                candidate,
                outcome.get("evaluation_key"),
                outcome["outcome"],
                outcome.get("reason"),
            )
        except Exception:  # noqa: BLE001, S110
            pass  # a record of the decision is never the decision
    note(
        "koth_contention",
        path=path,
        candidate=candidate,
        incumbent=outcome.get("incumbent", incumbent),
        evaluation_key=outcome.get("evaluation_key"),
        outcome=outcome.get("outcome"),
        reason=outcome.get("reason"),
        **({"error": outcome["error"]} if "error" in outcome else {}),
    )
