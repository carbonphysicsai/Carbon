# POWER-REPORTS-01: registered development-panel diagnostic

**DEVELOPMENT only.** These registrations implement the requested diagnostic
at alpha 0.05 and target power 0.8. They do not adopt a score threshold,
qualify a question population or change an optimizer. Inputs are Data
Collection's `solved-panel-export.v1` development files; no solver, hidden
bank or AX42 material is involved.

The controls are registered before their outcomes are calculated. Each of
the four behavior classes has four severities: half, one, two and four times
the export's refinement band, in each controlled limit's own unit. Motor
controls use holding mean torque (0.05/0.1/0.2/0.4 N m), energized torque
peak-to-peak (0.01/0.02/0.04/0.08 N m) and cogging peak-to-peak
(0.01/0.02/0.04/0.08 N m). Battery v3 controls use charging peak
temperature (0.25/0.5/1/2 C) and plating minimum
(0.001/0.002/0.004/0.008 V). The sign-error region is predeclared as
motor skew 2–4 degrees or battery first-stage C rate 1.5–2.0; other
registered strata are included. The path-aware control is accurate on the
primary registered search path. These severity choices are diagnostic
proposals, not Test Lead acceptance values.

`accumulation.json` registers five windows, the exposure limit in both
exports. Run `python -m carbon.design_search power-report` with the matching
controls file, `--accumulation accumulation.json`, `--alpha 0.05`,
`--power-target 0.8`, `--simulation-seed 20261009`, `--replicates 2000`
and `--max-questions 8`. The export supplies the registered grid law and
bank-sharing labels. There is no continuous law in either export. The
panel's `population_status` is `UNREGISTERED`, so P remains unmeasured and
the curves are conditional on the sealed development panel.

The aggregate results and exact input digests are added after the run. No
per-question IDs, winners, margins or reference values belong in this
directory.
