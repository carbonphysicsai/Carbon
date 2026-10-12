"""PUBLIC-DEV-DECISIONS-01: the public draw is deterministic, inside EV4's
envelope, never on the 0.5 degC grid, and EV4's decision contract."""

from __future__ import annotations

from carbon.battery.value import contract as ev
from scripts.dev.battery import public_dev_questions as pdq
from scripts.dev.battery import score_proof_questions as spq


def _base():
    return ev.load(spq.BASE_CONTRACT)[0]


def test_public_draw_is_deterministic_inside_the_envelope_and_off_the_half_degree_grid():
    base = _base()
    envelope = base["operating_conditions"]["envelope"]
    excluded = spq.public_conditions(base)
    drawn = pdq.draw_conditions(110, envelope, excluded)
    assert drawn == pdq.draw_conditions(110, envelope, excluded)
    assert len(set(drawn)) == 110 and not set(drawn) & excluded
    for t, s in drawn:
        assert envelope["t_amb_c"][0] <= t <= envelope["t_amb_c"][1]
        assert envelope["soc0"][0] <= s <= envelope["soc0"][1]
        assert (t - envelope["t_amb_c"][0]) % 0.5 == 0.25  # never a 0.5 degC grid point


def test_public_contract_keeps_ev4_decision_contract_with_public_scenarios():
    base = _base()
    conditions = pdq.draw_conditions(3, base["operating_conditions"]["envelope"], set())
    contract = pdq.public_contract(base, conditions)
    assert contract["contract_id"] == pdq.CONTRACT_ID
    assert contract["scenarios"]["verification"] == []
    assert [s["conditions"] for s in contract["scenarios"]["development"]] == [
        [list(c)] for c in conditions
    ]
    for key in ("decision", "constraints", "reference", "panel", "design_variables"):
        assert contract[key] == base[key]
    assert len(ev.decision_cases(contract)) == 35 * 3


def test_the_registered_jobs_regenerate_byte_for_byte(tmp_path):
    from scripts.dev.battery import public_dev_pod_phase as phase

    assert pdq.draw(tmp_path / "w", 110)["jobs_sha256"] == phase.JOBS_SHA256


def test_the_pod_sizes_whole_questions_to_its_budget():
    from scripts.dev.battery import public_dev_pod_phase as phase

    per_question = 35 * 77.0 / 30 * phase.TAIL * (1 + phase.REFINE_SHARE)
    assert phase.size(77.0, 30, 110 * per_question + 1) == 110
    assert phase.size(77.0, 30, 64.5 * per_question) == 64
    assert phase.size(77.0, 30, 10.0) == 0
