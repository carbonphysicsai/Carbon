# CHALLENGE-MOTOR-04 — counted motor evidence under study V2

**Status:** implemented. Counted evidence imported and evaluated by adoption.

**Authority:**
- OWNER-DATA-MOTOR-01 (the compute, the image and the operator host);
- OWNER-MOTOR-COUNTED-ADOPT-01 (option A).

**Predecessor:** CHALLENGE-MOTOR-03.

## Scope

- **`carbon/motor/decision_study.py`:**
  - `study_config_path` and a study-id pattern, so V2 has its own config file;
  - `_ok_case_artifacts_valid`, which accepts empty solver logs on a successful case and keeps every other check;
  - `_historical_construction`, `adoption_check` and `adopt_counted_campaign`.
- **`scripts/dev/motor/decision_study.py`:** the default config becomes V2, and an `adopt-counted` command is added.
- **`docs/development/studies/MOTOR_SYNTHETIC_DECISION_V2.json`:** V1 with only `study_id` changed.
- **`docs/development/evidence/motor-decision-construction-fixture-v2/`:** V2's analytical fixture, built on Linux.
- **`docs/development/evidence/motor-decision-counted-v2/`:** the completion manifest, the adoption record, V2's construction, and the counted result and report. Raw artifacts stay on the operator host and in the owner's Drive.
- **Tests** for the V1/V2 identity, the artifact rule (empty logs accepted, unsupported evidence still refused), the historical V1 fixture, adoption equality and refusal, and the committed counted evidence.

Out of scope:
- any change to the exam, the pools, the §6 values, scoring, gates or tolerances;
- a rerun;
- Track B motor replay. That follows in the motor Track B adapter PR.

## Acceptance

- [x] V2 differs from V1 only in `study_id`.
- [x] An OK case with empty solver logs is accepted. Missing logs, short or empty torque files, a bad exit, non-convergence, a mesh mismatch and empty required files are all refused.
- [x] The V1 fixture stays byte-identical and internally consistent.
- [x] V2's construction identity reproduces between the committed fixture and the counted construction: `sha256:959fb6ba…`.
- [x] V2's decisions equal V1's sealed commitments. The counted campaign validates against V1's plan and ledger.
- [x] The counted V2 result is COUNTED_GETDP: complete comparator, 48 executions, 0 retries.

## Maturity ceiling

IMPLEMENTED and TESTED, with counted DEVELOPMENT evidence for one fixed pilot. It is not scientifically qualified, customer accepted or production qualified.
