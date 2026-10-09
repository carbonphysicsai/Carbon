# MOTOR-PEAK-FEASIBILITY-01 — peak sizing and acquisition setup audit

Owner request, 2026-10-09; highest priority before BASELINE-AGREEMENT-01 repair.
Starting main: `6aa3e9d10e999afa8982a3dcb9bc90e50de971ab`.
Scope: analysis/documentation and arithmetic checks only, one PR to PR Head.

KEEP the 6/12 N·m, ripple and cogging buyer requirements and existing reference
ownership. Audit the public revised acquisition package at
`66ea509888e4ef0f5ac08750554db744b56b92bf`, not the legacy 8p/24s runtime.
Produce an explicit sizing/saturation screen, envelope-matched manufacturer
comparison, code/config coverage audit and prioritized search/return contract.
No solver execution, spend, hidden/AX42 access, bank construction, runtime
registration, material substitution or qualification. Data Collection owns
the missing-peak and frontier runs; its observations supersede hypotheses,
never the historical records.

Deliverable: `docs/development/challenge_pipeline/round1/motor-peak-feasibility.md`
and its arithmetic sheet. Validate independently recomputed areas, torque,
saturation markers and skew factors, plus existing packet/pipeline tests.
Maturity: SPECIFIED analysis, arithmetic-tested only. Physical feasibility,
thermal duty and reference credibility remain NOT_DEMONSTRATED.

Hub frozen under OWNER-WORKFLOW-SPEED-01; no Hub or WAVE modification. Record a
lesson per execution and hand off the exact head; no pushes after handoff
without ownership returned. Next: #917 CI repair, then miner FAQ, f02 law and
f13 diagnosis. The motor comparator rerun requires a full-coordinate/curve
development re-export, not the current ordinal panel.

Validation: native `py -3.11 -X utf8 -m pytest -q
tests/cpu/test_motor_peak_sizing_document.py
tests/cpu/test_first_three_customer_packets.py
tests/cpu/test_customer_packet_revisions_v2.py
tests/cpu/test_challenge_pipeline.py` — 63 passed (8.26 s).
`python -m carbon.challenge_pipeline validate` — 7 records valid, 475 lessons
valid before the validation lesson was added. Black 26.5.1 and Ruff checks pass.
Native diagnostics are not canonical acceptance; the Windows worktree's Git
metadata prevents the local canonical WSL wrapper resolving its root. Required
exact-head GitHub canonical CI remains the acceptance path, not an inferred pass.
Main moved to `cfb40e0fa74b2304bdd61594916f55b1390b24e1` during validation; its
two A40 acceptance files do not overlap this analysis. PR Head owns base reconciliation.
