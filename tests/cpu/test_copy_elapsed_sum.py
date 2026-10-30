"""The reference-rows elapsed time is one float on every interpreter (copy_batch_not_the_pack, Motor 1.5):
the pack writer's float(sum(wall_s)) is left to right on Python <= 3.11 and Neumaier-compensated on >= 3.12, one
ulp apart; the copy check recomputes the 3.12 value everywhere."""

import json
import random

from carbon.challenge_validator import copy_delivery as delivery
from carbon.scoring import physical_dual_pack as physical


def _wall_times():
    rng = random.Random(7)
    return [rng.uniform(0.5, 30.0) for _ in range(90)]


def test_the_sum_is_cpython_3_12s_on_any_interpreter():
    # Computed with Python 3.12.3's builtin sum(); Python 3.11's builtin gives ...956 for the same list.
    assert delivery.reference_wall_seconds(_wall_times()) == 1250.6080673691954


def test_an_empty_or_single_solve_sums_exactly():
    assert delivery.reference_wall_seconds([]) == 0.0
    assert delivery.reference_wall_seconds([0.1]) == 0.1


def _bank(walls):
    return {
        "references": [[1.0] for _ in walls],
        "reference_records": [{"wall_s": w} for w in walls],
    }


def test_only_elapsed_s_is_rewritten_and_the_rest_of_the_document_is_the_producers():
    walls = _wall_times()
    row = {
        "id": "case",
        "status": "RESOLVED",
        "outputs": [1.0] * len(walls),
        "elapsed_s": float(sum(walls)),  # whatever this interpreter's builtin gives
        "source": "MEASURED_ENGINEERING_REFERENCE_RUN",
    }
    produced = physical.canonical([row])
    fixed = delivery._interpreter_independent_elapsed(produced, _bank(walls), physical)
    after = json.loads(fixed)[0]
    assert after["elapsed_s"] == 1250.6080673691954
    assert {k: v for k, v in after.items() if k != "elapsed_s"} == {
        k: v for k, v in row.items() if k != "elapsed_s"
    }
    assert fixed == physical.canonical([{**row, "elapsed_s": 1250.6080673691954}])


def test_a_document_without_an_elapsed_time_is_returned_unchanged():
    raw = physical.canonical([{"id": "case"}])
    assert delivery._interpreter_independent_elapsed(raw, _bank([1.0]), physical) == raw


def test_an_unmeasured_row_adds_no_wall_time():
    walls = [1.0, 2.0, 3.0]
    bank = _bank(walls)
    bank["reference_present"] = [True, False, True]
    bank["references"][1] = [float("nan")]
    raw = physical.canonical([{"id": "c", "elapsed_s": 0.0}])
    after = json.loads(delivery._interpreter_independent_elapsed(raw, bank, physical))
    assert after[0]["elapsed_s"] == 4.0
