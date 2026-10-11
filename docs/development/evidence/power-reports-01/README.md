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

## Aggregate results on the supplied exports

Both commands above ran against the producer's October 9 development exports.
The source files and the full JSON outputs remain in the producer workspace;
this record contains only aggregates and digests. Neither export includes a
digest-bound refinement rule or a `settled` verdict. The neutral reference
resolver therefore reports every question UNRESOLVED. It would be incorrect
to show the resulting null detection estimates as zero power or as a control
failure.

| Export | Export digest | Questions | Shared solved-bank clusters | Unresolved Q mass | Common resolved mass, all 16 controls | P |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Motor | `sha256:720e93a2d6bf4540119fa46c3d47478811a7f412dc80f6627ef228a6c5758569` | 20 | 1 | 1.0 | 0.0 | unregistered |
| Battery v3 | `sha256:2ec4da3ccfc358d412bd38648f4ca9fb6a010e838964a1e4e3f65a4a2b5f041d` | 25 | 1 | 1.0, in each of five bands | 0.0 | unregistered |

The complete requested curve domain is **questions per batch k = 1 through
8** by **windows within exposure E = 1 through 5**. Every one of its 40 cells
has `exposure_feasible = true` and `run_feasible_probability = 1.0` under the
registered per-question quotas and 2,000 simulation replicates. For every
control, severity, metric, and battery band, each cell's
`estimated_detection_probability` and Monte Carlo standard error is **null
(unestimable)**. The first k or window meeting target is also null. This is a
conditional result for these sealed development panels, not a future-batch
population probability. It supplies no pass/fail verdict.

The full aggregate CLI outputs had SHA-256 digests
`2edb8f4d5f3ea8b522f33d3174739541f02735d095f54946836983dfa0ee8bc1`
(motor) and
`2db600b9b73c401f7f0ef8b83b122ed9e723cffe6d748eaaead2f652dee4adc2`
(battery v3). A leakage scan found zero occurrences of the exports' question
or solved-bank IDs in either output. The outputs are not committed because
they repeat the same null result in approximately 4 MB of JSON.

Data Collection needs to re-seal the exports with per-candidate verdicts
settled under a named, digest-bound refinement rule before a separation
curve can be estimated. Each export currently names one shared solved-bank
cluster. Under the registered one-sided exact sign test, one cluster has a
minimum possible p-value of 0.5, even if all questions are settled and a
control is worse. A panel intended to measure detection at alpha 0.05 also
needs genuinely independent solved-bank clusters; relabeling one bank would
not supply them. Any later export must be reported separately under its own
digest rather than silently replacing these results.
