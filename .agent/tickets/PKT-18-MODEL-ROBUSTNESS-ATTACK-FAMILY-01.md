# PKT-18 Model robustness attack families

Owner-directed queue assignment, 2026-10-13. DEVELOPMENT only.
Starting main: e627c260d326be679d09fddd50540a556f88e790.

## Working contract

Implement two independently callable trained-model input probe families:
geometric deformation and adversarial triangle meshes. Measure deformation,
classify it against an explicitly supplied envelope, and require honest refusal
outside supported scope. Within scope compare predictions with a matched public
reference witness under an explicitly supplied tolerance. No score term, physics
law adoption, reference solve, hostile-code loader or qualification is added.

The trusted operator supplies the model boundary callable and artifact/runtime
identity, envelope/policy and public witness. A callback is not authenticated
model identity; a host runner must establish it. Synthetic controls exercise the
same prediction/verdict path but earn only fixture engineering evidence.

## Reuse and overlap

KEEP attack.engine digest and failure vocabulary. KEEP physics_contract.py and
Product Envelope Guard, which already implement residual/advisory probes.
The queue's blanket zero-matches statement is contradicted by those files.
They do not establish geometric hostile-input coverage of rebuilt models.
Do not edit shared attack adapter.py/verify.py/battery_level4.py owned by #1317.
The new component is callable independently; campaign registration is a named
integration hold, not implicit L4 coverage. Physics gates belong to PKT-19.

## Definition of done

- Bounded deterministic public 2D triangle generators: deformation, irregular
  sampling, density, zero-area and inverted elements, invalid connectivity.
- Explicit displacement/size/area measurements; no selected scientific threshold.
- Per-attempt HELD/BREACHED/NOT_APPLICABLE, plus NOT_RUN/FAILED_INFRA/TIMEOUT/
  CRASHED for missing evidence or execution failure; none imply success.
- Both a correct supported-input control and a known-bad predictor are required
  to discriminate; silent detector and always-refuse model never produce HELD.
- Preserve input identities before callback invocation, failure and incomplete
  coverage, and fixture versus host-declared evidence basis.
- Focused negative/malformed/mutation regressions, canonical CI and one PR.

## Human and host holds

Radical displacement threshold, envelope, reference tolerance/units and supported
mesh resources require Validator/owner values. Real rebuilt-model endpoint,
isolation/time/memory enforcement, authenticated artifact parity, public unseen
panel custody and named scientific/security acceptance remain host-side.
No protected material, solver runs, spend, LIVE or customer claim is authorized.

Hub retired under OWNER-DX-03. No hub mutation or completion-receipt ceremony.
