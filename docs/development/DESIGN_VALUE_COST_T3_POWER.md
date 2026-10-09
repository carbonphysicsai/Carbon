# Solved-panel power diagnostics (VALUE-COST-T3)

This is a DEVELOPMENT producer workflow. Data Collection owns and seals the
solved panel. `design_search` accepts the registered export; it does not infer
objectives, physical limits, population masses, reference outcomes, or exposure
policy from filenames. Test Lead supplies alpha, target power, control
severities, and the eventual interpretation. No report qualifies power or
changes score use.

## Producer export

Use `carbon.design_search.producer_panels.seal_export(body)` to seal a complete
`carbon.design-search.solved-panel-export.v1` JSON object. Its exact fields are
`schema`, `sealed: true`, `family`, `challenge_id`, `exposure_unit`, `exposure`,
`window_sampling`, `questions`, and `laws`. `family` is one of `battery-v3`, `motor`,
`cooling-cell`, `f02`, `f06`, `f08`, `f13`, `f17`. The export digest covers all
fields. Exporting does not itself establish scientific validity.

Each question gives `case`, `support_case`, a registered runnable `task`, its
complete solved `reference` panel, and producer registered `close_call` and
`refinement_demand` booleans. The reference is a list of
`{candidate, condition, values}` for every design and condition. Battery v3
uses an indexed task and a reference list of `{index_value, panel}` in the
registered index order. F02 may use a plain task or an indexed schedule if its
registered buyer decision calls for one. The other six families use plain
tasks. Every question in one export shares the registered objective definition;
the library checks reference completeness and question summaries before
running controls. `support_case` identifies questions that reuse one solved
bank, so they count as one cluster in the separation test.

An optional, digest-bound `refinement_rule` extends the export for settled
near-limit candidates:

```json
{"refinement_rule": {"id": "<PRODUCER_REGISTERED_RULE_ID>", "method": "two-rungs-same-side-change-below-band.v1"}}
```

When this field is present, **every** question has a `settled` field. A plain
question uses `[{"candidate": "...", "feasible": true}]`; an indexed question
uses one `{"index_value": ..., "verdicts": [...]}` row per registered index, in
order. The verdict list may be empty. The producer verifies that both refined
rungs lie on the same side of every relevant limit and change by less than its
registered band, then seals the rule ID and verdicts under `export_digest` (or
`snapshot_digest`). The report checks the digest, the named rule, candidate and
index identities, and contradictions with already resolved panel results. It
does not reconstruct the rungs or declare the producer's refinement adequate.
An unregistered or tampered settlement is refused; the legacy export without
these fields keeps its historical interpretation.

A still-unresolved candidate makes a band UNRESOLVED only if treating it as
feasible could change the registered winner or whether a feasible design
exists. A mandatory NONE_FEASIBLE band fixes the whole indexed map as
NONE_FEASIBLE. If a control picks a still-unresolved candidate, that question
is omitted from that control's common resolved comparison and counted in its
aggregate `unscored_control_mass`; it is never a control failure.

`exposure` is a list of `{case, limit, used}`, one row per question. Its
required unit is `per_question_draws`. This matches the merged
`challenge_validator.design_bank` ledger: a window selects distinct live
questions, increments each selected question's exposure once, and retires each
one at its own E. Thus k=8 and E=5 can produce five windows from eight
questions; E is **not** a global eight-draw cap. Cross-window simulation
uses `window_sampling`, registered through `register_window_sampling`:
one `{case, stratum}` row per question and an explicit
`{questions_per_batch, quotas}` row for every tested k. It follows the
bank ledger's sorted stratum quotas, sampling uniformly from live questions
within each stratum. There is no invented quota allocation when k changes.
The report marks bank-short paths with null detection estimates and a
feasibility probability. It does not model overlapping active windows or
future top-ups.

For a `DesignBank` export, `case` corresponds to `case_id`,
`task` to `inputs.task`, and the solved `reference` to its `OK`
`panel` or indexed `per_index` panel. The producer supplies the
reference-bank cluster `support_case` and the exposure ledger from its
registration. A non-`OK` question is not a solved panel and cannot be
filled in by this adapter. If bank independence is unknown, the producer must
use a shared cluster rather than invent independent evidence.

The CLI also accepts a sealed
`carbon.design-search.design-bank-snapshot.v1` input directly. Its top-level
fields are `schema`, `sealed`, `family`, `challenge_id`, `exposure_unit`,
`exposure`, `window_sampling`, `cases`, `laws`, and `snapshot_digest`. Each `cases` row carries
`case_id`, the DesignBank `inputs` (`task`, `task_digest`, `draw`), its
`reference` (`status: OK` and `panel` or `per_index`), plus `support_case`,
`close_call`, and `refinement_demand`. Exposure rows use `case_id`, `limit`,
and `used`. Use `seal_design_bank_snapshot` to bind the complete snapshot.
The adapter checks the task digest, converts only the required values, and
discards `inputs.draw` before running the report. Producer ownership of
the source ledger and proof verification remains upstream.

Register one grid and/or continuous question law with
`carbon.design_search.diversity.register_law`. If a Challenge has a registered
proposal law Q but no population law P, use `question-law.v2` with
`population_status: UNREGISTERED` and bins containing `case` and `q_mass`.
The report then emits `P: null`; it does not copy Q into P. A registered P
requires separate `p_mass` values. Continuous region masses require the
existing integration evidence. Only solved questions with registered masses
can enter this export. An unsolved or missing reference remains an actionable
producer gap, never a filled-in value.

## Run

Register the behavior-defined controls through
`carbon.design_search.controls.register_controls` with a severity value and
unit for **each** controlled limit quantity. Register accumulation through
`carbon.design_search.power_accumulation.register_accumulation`, choosing the
same exposure unit as the sealed export and an explicit maximum number of
windows. All quantities and units come from the registered task.

```bash
./scripts/dev/canonical.sh python -m carbon.design_search power-report \
  --panel-export /producer/sealed-panel-export.json \
  --controls /producer/registered-controls.json \
  --accumulation /producer/registered-accumulation.json \
  --alpha '<TEST_LEAD_ALPHA>' \
  --power-target '<TEST_LEAD_POWER_TARGET>' \
  --simulation-seed '<PRODUCER_REGISTERED_SEED>' \
  --replicates '<PRODUCER_REGISTERED_REPLICATES>' \
  --max-questions '<PRODUCER_REGISTERED_K_CAP>'
```

The output includes each law's P and Q separately and each control's
false-feasible, missed-opportunity, regret, and abstention aggregates.
`sealed_bank_cross_batch` is a separate curve for every k and window count,
conditional on this finite sealed bank. It is not a P or Q future-batch
probability. The sign test clusters repeated draws by solved reference bank
across all windows. The Monte Carlo standard error describes simulation noise
only; it does not certify the question law, reference, or independence between
banks. The output has no question IDs, winners, per-case reference values, or
bank identities. Keep the input export and controls on the producer.

## Integration status

The eight adapter paths are toy-tested. This branch has no settled Cooling Set A
or Motor Stage 3 producer export to run, and does not claim measured power for
any Challenge. Data Collection must register complete solved panels and their
question laws before a real run. No solver is invoked by the adapter.
