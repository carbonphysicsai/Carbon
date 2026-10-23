"""A KOTH king carries across construction versions (OWNER-KOTH-CARRY-ACROSS-VERSIONS-01).

The owner: a king carries to a new construction version (F08 1.4 -> 1.5, ...)
while the sealed evaluation version is unchanged; a new exam resets the king.
Each carry is recorded. A pack-set rotation is not a reset
(OWNER-EXAM-CAP-ROTATION-01, held by VALIDATOR-KOTH-CARRY-SCOPE-01): the king
carries and is regraded on the new set by the existing regrade step; until
that regrade exists every comparison against him is UNAVAILABLE.

The continuity key is `(challenge_id, evaluation_version, pack_set_key)`:
- `evaluation_version` comes from `scoring.sealed_versions.evaluation_version`,
  the table the sealed graders register (F08 1.4 and 1.5 both grade on
  `f08-dual-sealed-batch-8-v1`); a different one refuses the carry;
- `pack_set_key` is each deployment's configured active pack set
  (`evaluation_pack_set.set_key`). Its key leaves the construction version out
  (`sealed_exam_common.pack_set_document`, v2), so the same batches on 1.4 and
  1.5 give one key and no regrade is needed; a different key marks the carry
  `regrade: REQUIRED`.

Either part unknown means no carry: the new deployment starts without a king,
as before (fail closed).

Where: at the cutover, once, into the new deployment's pool store
(`PoolStore.carry_incumbent`). The new store's incumbent is then the king, so
the weights publisher, the winner ledger (which finds the king's existing
record by model id, so his clock is kept) and `score_feed.king_record` (which
shows the deployment's live incumbent) all see him without change. A 1.5
challenger meets him through the unchanged comparator: on an unchanged pack
set the pair reads the king's own carried evaluation of the same measured exam
(`bank_promotion.carry_identity`). The takeover rule, its margin and ties are
untouched.

    python -m carbon.challenge_validator.koth_carry --challenge f08-ribbed-bracket \
        --old-pool OLD.sqlite --old-version 1.4 --old-pack-set-key sha256:... \
        --new-pool NEW.sqlite --new-version 1.5 --new-pack-set-key sha256:... \
        --king-source-pin sha256:...

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from carbon.battery.pool_store import PoolStore, StateError

from .interface import is_digest

CARRY_SCHEMA = "carbon.challenge-validator.koth-carry.v1"


class CarryRefused(ValueError):
    """A typed refusal: no carry, the new deployment keeps no king."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def continuity_key(challenge_id, version, pack_set_key):
    """`(challenge_id, evaluation_version, pack_set_key)` for one deployment,
    or a refusal when either part is unknown."""
    from carbon.scoring.sealed_versions import evaluation_version

    sealed = evaluation_version(challenge_id, version)
    if sealed is None:
        raise CarryRefused("koth_carry_evaluation_version_unknown")
    if not is_digest(pack_set_key):
        raise CarryRefused("koth_carry_pack_set_unknown")
    return (challenge_id, sealed, pack_set_key)


def carry(
    old_store,
    new_store,
    *,
    challenge_id,
    old_version,
    new_version,
    old_pack_set_key,
    new_pack_set_key,
    king_source_receipt_sha256,
):
    """Carry the old deployment's live king into the new one, or refuse.

    `king_source_receipt_sha256` is the old receiver's registered source pin
    (trusted operator configuration, as for every pair lookup). Returns the
    stored carry record; a replay returns the first one."""
    if type(old_store) is not PoolStore or type(new_store) is not PoolStore:
        raise TypeError("pool stores are required")
    if old_version == new_version:
        raise CarryRefused("koth_carry_same_version")
    old = continuity_key(challenge_id, old_version, old_pack_set_key)
    new = continuity_key(challenge_id, new_version, new_pack_set_key)
    if old[1] != new[1]:
        raise CarryRefused("koth_carry_evaluation_version_changed")
    if not is_digest(king_source_receipt_sha256):
        raise CarryRefused("koth_carry_source_pin_missing")
    live = old_store.incumbent()
    if live is None:
        raise CarryRefused("koth_carry_no_king")
    try:
        row = old_store.submission(live["model_id"])
        challenge = row["binding"].get("challenge") or {}
        if (
            row["challenge"] != challenge_id
            or challenge.get("id") != challenge_id
            or challenge.get("version") != old_version
        ):
            raise CarryRefused("koth_carry_king_not_this_version")
        record = {
            "schema": CARRY_SCHEMA,
            "challenge_id": challenge_id,
            "king": {"hotkey": row["hotkey"], "submission_id": live["model_id"]},
            "old_version": old_version,
            "new_version": new_version,
            "evaluation_version": new[1],
            "old_pack_set_key": old[2],
            "new_pack_set_key": new[2],
            # A pack-set change still carries the king
            # (OWNER-EXAM-CAP-ROTATION-01, VALIDATOR-KOTH-CARRY-SCOPE-01): he
            # meets challengers on the new set only once he is regraded on it;
            # until then every comparison is UNAVAILABLE, never a reset.
            "regrade": "NOT_REQUIRED" if old[2] == new[2] else "REQUIRED",
            "king_source_receipt_sha256": king_source_receipt_sha256,
        }
        return new_store.carry_incumbent(old_store, record)
    except StateError as refused:
        raise CarryRefused(refused.code) from None


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m carbon.challenge_validator.koth_carry"
    )
    parser.add_argument("--challenge", required=True)
    parser.add_argument("--old-pool", type=Path, required=True)
    parser.add_argument("--old-version", required=True)
    parser.add_argument("--old-pack-set-key", required=True)
    parser.add_argument("--new-pool", type=Path, required=True)
    parser.add_argument("--new-version", required=True)
    parser.add_argument("--new-pack-set-key", required=True)
    parser.add_argument("--king-source-pin", required=True)
    args = parser.parse_args(argv)
    for path in (args.old_pool, args.new_pool):
        # Existing stores only, opened as the receiver opens them.
        if path.is_symlink() or not path.is_file():
            print(json.dumps({"refused": "koth_carry_pool_unavailable"}))
            return 2
    try:
        record = carry(
            PoolStore(args.old_pool),
            PoolStore(args.new_pool),
            challenge_id=args.challenge,
            old_version=args.old_version,
            new_version=args.new_version,
            old_pack_set_key=args.old_pack_set_key,
            new_pack_set_key=args.new_pack_set_key,
            king_source_receipt_sha256=args.king_source_pin,
        )
    except CarryRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(record, sort_keys=True))
    return 0


if __name__ == "__main__":
    from carbon.challenge_validator.koth_carry import main as _main

    sys.exit(_main())
