"""A second grade for tests that drive a crown change through `BankPromotion.consider_private`.

A crown change needs a repeat (OWNER-CROWN-GRADE-REPEAT-01). These tests are about the comparison, not the regrade, so
their second grade is the stored grade again: bit-identical by construction. The real second grade, and its mismatch,
are covered where the gate is (`test_crown_grade_repeat`).
"""


def identical_repeat(store, key, pin):
    """``repeat`` for `consider_private`: each state's stored grade under ``key``, again."""

    def repeat(submission_id):
        return store.private_evaluation_pair(
            submission_id, key, registered_source_receipt_sha256=pin
        )["candidate"]

    return repeat
