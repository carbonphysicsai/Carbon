"""Acceptance for the shared answer key (VALIDATOR-19 slice 4).

These checks back the owner's fairness rule (OWNER-SHARED-ANSWER-KEY-01):
every validator scores every miner on the same cases, with the same solver
results and the same reconstruction seed.

- **`parity`**: whether import-only validators hold the same batches
  (fingerprint, references digest, window, salt digest) and activate the
  same ones at each finalized block.
- **`score_parity`**: whether one submission, received at the same block,
  gets the same active batches, references and aggregate on each.
- **`permit_exposure`**: the leak family's second member. It is what a hotkey
  that acquires a validator permit can fetch while it holds it, counted from
  the Challenge's registered cadence.

The first member (one validator leaks its batch) narrows through the
distribution host's fetch log (`distribution.fetchers`). The key is the same
for every validator, so a leak narrows to the set of hotkeys that fetched
that batch, never to one.

Every result is public: counts, digests and verdicts, never a case, input,
reference or salt. DEVELOPMENT only; deciding whether any measured exposure
is acceptable stays the owner's.
"""

from __future__ import annotations

import hashlib
import math


def held(adapter):
    """`{fingerprint: identity}` for an import-only validator's windowed
    batches. The salt appears only as its digest."""
    store = adapter.target.store
    out = {}
    for batch in store.batches(kind="screening"):
        fingerprint = batch["fingerprint"]
        window = store.window(fingerprint)
        if window is None:
            continue
        salts = store.salts([fingerprint])
        quiz = store.quiz(fingerprint)
        out[fingerprint] = {
            "quiz_digest": None if quiz is None else quiz["quiz_digest"],
            "references_digest": batch["references_digest"],
            "window": window,
            "salt_digest": (
                "sha256:" + hashlib.sha256(salts[0].encode()).hexdigest()
                if salts
                else None
            ),
        }
    return out


def parity(adapters, blocks):
    """Whether every validator holds the same batches and activates the same
    ones at each of `blocks`."""
    holdings = [held(adapter) for adapter in adapters]
    differing = [
        block
        for block in blocks
        if len({tuple(a.target.store.windowed_active(block)) for a in adapters}) != 1
    ]
    return {
        "validators": len(adapters),
        "batches": len(holdings[0]) if holdings else 0,
        "held_identical": all(h == holdings[0] for h in holdings),
        "blocks_checked": len(blocks),
        "active_identical": not differing,
        "differing_blocks": differing,
    }


#: What must agree between validators for one submission's score.
SCORE_FIELDS = ("active_batches", "references", "aggregate")


def score_parity(submitters, strategy):
    """One strategy through each validator's submit door, at the same block.
    Each `submitter(kind, strategy)` returns `(view, operator_record)`, as
    Graphite's hidden-scoring door does. It is injected, so no validator
    surface names Graphite's modules. Returns whether the scored fields agree,
    and each validator's state."""
    records, states = [], []
    for submit in submitters:
        view, record = submit("proposal", strategy)
        states.append(view["state"])
        records.append(
            None if record is None else {k: record.get(k) for k in SCORE_FIELDS}
        )
    scored = [r for r in records if r is not None]
    return {
        "validators": len(submitters),
        "states": states,
        "identical": len(scored) == len(submitters)
        and all(r == scored[0] for r in scored),
    }


def permit_exposure(cadence, held_blocks):
    """What a permit held for `held_blocks` can fetch, under a cadence of one
    batch per `every_blocks` with `active` live at once. It is the worst case
    over where in the rotation the permit starts. Counts only."""
    every, active = cadence["every_blocks"], cadence["active"]
    if type(held_blocks) is not int or held_blocks < 1:
        raise ValueError("a holding of at least one block")
    return {
        "batches_at_once": active,
        "batches_over_holding": active + math.ceil(held_blocks / every),
        "longest_remaining_use_blocks": active * every,
    }
