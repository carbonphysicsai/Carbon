"""A second grade for tests that drive a crown change through `BankPromotion.consider_private`.

A crown change needs a repeat (OWNER-CROWN-GRADE-REPEAT-01). These tests are about the comparison, not the regrade, so
their second grade is the stored grade again: bit-identical by construction. The real second grade, and its mismatch,
are covered where the gate is (`test_crown_grade_repeat`).
"""


def stored_grade_repeat(store):
    """``repeat`` for a flow test that files its own evaluation: the one evaluation the store holds for the state, again."""
    import json

    def repeat(submission_id):
        with store.db() as db:
            rows = db.execute(
                "SELECT body FROM operations WHERE kind='private_evaluation.v1'"
            ).fetchall()
        mine = [
            json.loads(raw)
            for (raw,) in rows
            if json.loads(raw)["submission_id"] == submission_id
        ]
        if len(mine) != 1:
            raise LookupError("one stored grade per state in these tests")
        return {"submission_id": submission_id, "evidence": mine[0]["evidence"]}

    return repeat


def identical_repeat(store, key, pin):
    """``repeat`` for `consider_private`: each state's stored grade under ``key``, again."""

    def repeat(submission_id):
        return store.private_evaluation_pair(
            submission_id, key, registered_source_receipt_sha256=pin
        )["candidate"]

    return repeat
