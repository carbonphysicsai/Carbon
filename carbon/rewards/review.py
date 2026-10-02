"""Opening-anchored review diagnostic, never retirement or reward reweighting."""

from dataclasses import dataclass

from .core import DAY_MS, tick

HOUR_MS = 3600000


@dataclass(frozen=True)
class Hour:
    start_ms: int
    allocated: int
    earned: int
    evaluator_healthy: bool
    publisher_healthy: bool
    submissions: int
    accepted: int


@dataclass(frozen=True)
class Review:
    status: str
    opens_ms: int
    review_ms: int
    allocated: int
    earned: int
    submissions: int
    accepted: int


def review(opens_ms, review_ms, hours):
    tick(opens_ms)
    tick(review_ms)
    status = "NOT_SCHEDULED"
    if review_ms > opens_ms and (review_ms - opens_ms) % (7 * DAY_MS) == 0:
        status = "INDETERMINATE_COVERAGE"
        expected = set(range(review_ms - 3 * DAY_MS, review_ms, HOUR_MS))
        if (
            type(hours) is tuple
            and len(hours) == 72
            and all(type(h) is Hour and type(h.start_ms) is int for h in hours)
            and {h.start_ms for h in hours} == expected
        ):
            status = "INDETERMINATE_ACCOUNTING"
            valid = all(
                type(v) is int and 0 <= v < 2**63
                for h in hours
                for v in (h.allocated, h.earned, h.submissions, h.accepted)
            ) and all(
                h.earned <= h.allocated and h.accepted <= h.submissions for h in hours
            )
            if valid:
                status = "INDETERMINATE_OPERATIONS"
                if all(
                    h.evaluator_healthy is True and h.publisher_healthy is True
                    for h in hours
                ):
                    allocated, earned = sum(h.allocated for h in hours), sum(
                        h.earned for h in hours
                    )
                    status = (
                        "INDETERMINATE_ZERO"
                        if allocated == 0
                        else "PLATEAU_REVIEW" if 10 * earned < allocated else "CONTINUE"
                    )
                    return Review(
                        status,
                        opens_ms,
                        review_ms,
                        allocated,
                        earned,
                        sum(h.submissions for h in hours),
                        sum(h.accepted for h in hours),
                    )
    return Review(status, opens_ms, review_ms, 0, 0, 0, 0)
