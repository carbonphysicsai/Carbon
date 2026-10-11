# One-command development evidence pack

EVIDENCE-PIPELINE-ONE-COMMAND-01 wraps the existing Data Collection producer
contract, cheap comparators, optimizer replay, value evaluator and #975's page
renderer. It changes no score, power, readiness, safety or adoption policy.
The customer question stays the packet's registered question: a complete
safe charge map, robot-joint geometry, or supported burst schedule. The
reference remains the referee; the comparison is better decisions at equal
budget, not a model being more accurate than truth.

```text
python -m carbon.development_comparison.evidence_pipeline battery-v3 --manifest return/manifest.json --manifest-sha256 sha256:EXACT_BYTES --output-dir new-battery-pack
python -m carbon.development_comparison.evidence_pipeline f02 --manifest return/manifest.json --manifest-sha256 sha256:EXACT_BYTES --output-dir new-f02-pack
python -m carbon.development_comparison.evidence_pipeline motor --manifest return/manifest.json --manifest-sha256 sha256:EXACT_BYTES --output-dir new-motor-pack
```

Replace the placeholder with the actual manifest byte SHA-256. Outputs are a
new local directory, never overwrite an old pack and never publish a page.
The command does not log into CCX63, AX42, cloud providers or any remote host.
It runs no reference solver, model training or paid dispatch. Public local
exports must first be supplied by Data Collection. Hidden/EVAL/STRESS/quiz,
private customer and protected acquisition material are not eligible.

## Return bundle: inputs, not guesses

The manifest is the closed `carbon.development-evidence-pipeline.v1` shape:

```json
{
  "schema": "carbon.development-evidence-pipeline.v1",
  "scope": "PUBLIC_DEVELOPMENT",
  "family": "f02",
  "method": "impulse-response",
  "files": {
    "export": {"path": "panel.json", "sha256": "sha256:EXACT_BYTES"},
    "comparator": {"path": "materials.json", "sha256": "sha256:EXACT_BYTES"},
    "carbon": {"path": "predictions.json", "sha256": "sha256:EXACT_BYTES"},
    "replay": {"path": "equal-budget-panel.json", "sha256": "sha256:EXACT_BYTES"},
    "bindings": {"path": "bindings.json", "sha256": "sha256:EXACT_BYTES"},
    "context": {"path": "value-context.json", "sha256": "sha256:EXACT_BYTES"},
    "rule": null
  },
  "analysis": {"bootstrap_replicates": 2000, "confidence": 0.95, "seed": 17}
}
```

Analysis settings are explicit, not adopted power/qualification thresholds.
Each descriptor binds the file's **literal bytes**, distinct from its sealed
semantic digest. Duplicate JSON keys, nonfinite JSON, remote paths, symlinks,
traversal and files over 32 MiB are refused. The supplied inventory is bounded
to 256 questions, 4096 physical rows and 512 actions per subtask. These are
tool resource limits, not scientific limits. No directory discovery occurs.

1. **Export:** `carbon.design-search.solved-panel-export.v1` (the actual schema
   constant in `producer_panels.py` controls), sealed by
   `producer_panels.seal_export`, with registered tasks/laws, physical reference
   rows, P/Q/w, exposure and observer identities. Raw Elmer/PyBaMM files or
   aggregate feasibility summaries alone are not this contract. Data Collection
   owns their conversion and registered settlements. A refinement demand needs
   its existing producer settlement; this wrapper performs no new refinement.
2. **Comparator:** plain f02 uses #994's `portfolio_baselines.seal_materials` sidecar
   (waveforms, independent baselines, calibration/response provenance, physical
   observers). Motor uses #917's complete-period signed torque/cogging curves,
   physical geometry coordinates/groups, source pins and matching observer.
   Battery needs no extra sidecar: its public protocol/band inputs come from
   the export. Methods are explicitly selected: battery `protocol` or `band`,
   motor `gaussian` or `multiquadric`, f02 `impulse-response`. Selection must
   precede held-out inspection; the wrapper does not choose a winning method.
   Indexed f02 uses `carbon.development-indexed-f02-materials.v1`, with
   `scope`, the parent `export_digest`, and `indices` rows of
   `{index_value, materials}`. Every registered context appears exactly once.
   Each nested #994 sidecar binds `f02_view(export, index_value)`'s digest,
   retaining the registered subtask, reference and settlement. This is a
   comparator view, not a new question law. Parent and nested scopes must agree.
   All contexts remain mandatory in the final burst schedule.
3. **Carbon:** `carbon.development-prediction-input.v1` with `scope`,
   `export_digest`, `model_id`, `source_receipt_digest`, and `rows`. Each row is
   `{band, candidate, condition, values}` for exactly one deduplicated export
   physical row. `band` is null for plain tasks, and its registered scalar for
   indexed tasks. `values` has the full physical observable inventory, or null
   for an **explicit abstention**. Missing, duplicate and foreign rows fail.
   Predictions are judged afresh by the existing decision judge; a supplied
   regret, pass rate or claimed decision is not accepted. Prediction receipts
   must record model/training/environment/selection identity and held-out
   custody outside this file; a hash does not attest those facts.
4. **Replay:** the unchanged sealed #998
   `carbon.design-search.equal-budget-panel.v1`. Its actual reference values,
   objective/units, five-band weights and both screen orders are checked against
   this export and the newly computed predictions. The costs, planning bounds,
   serial complete-panel schedule and solver order come from separately
   registered producer measurements. No new costs or solver ordering are
   inferred. Public-development runs require `cost_basis: MEASURED`; only an
   explicitly labelled synthetic fixture may replay assumption costs.
5. **Bindings:** `carbon.development-replay-bindings.v1`, `export_digest`,
   `jobs`. Each job is `{job_id, case, candidates}`. `candidates` maps replay
   design IDs to `{plain: export_candidate_id}`, or for battery a complete
   `{"5": id, "15": id, "25": id, "35": id, "40": id}` charge map. Plain
   menus cover the exact task action inventory. Battery map menus are the
   explicitly registered replay menu, **not a claim of exhaustive coverage of
   the Cartesian five-band design space**. Duplicate complete actions fail.
   Indexed f02 likewise requires every registered context key, with the
   objective aggregated using the task's already-registered buyer weights.
   It is not flattened into unrelated questions. Each question has one job.
   A job's cluster ID must equal the exported `support_case`, preventing a
   producer from creating bootstrap banks by merely relabelling jobs.
6. **Context:** `carbon.development-value-context.v1`, `export_digest`,
   `selection`, `folds`, `speed`, `item_1`, `item_4`. These are precisely the
   corresponding fields in the [existing value evaluator](../value-bar-evaluator.md).
   Whole-decision speed and two independent held-out fold receipts are separate
   measurements; candidate-condition fit timings are not substituted for them.
   Owner receipts may be null and cannot become PASS. Source/family/model
   identity mismatches fail even when no owner rule has been supplied.
   Fold question identities are checked against the export; known reference
   support cannot be split across purported independent folds. Speed pairs
   refer to actual exported questions and use complete-query units. These
   contradiction checks do not establish independence or accurate timing.
7. **Rule:** the value evaluator's separately registered owner rule, or null.
   Missing reserved rules produce `INSUFFICIENT_EVIDENCE`, not invented values.

## Hops and evidence semantics

Public files and byte pins → producer validation → held-out comparator and
independent Carbon judgement → export-bound reference/ranking cross-check →
three-arm budget replay → registered value bar → evidence page and receipt.

Unsupported interpolation abstains. In replay, missing/abstained predictions
sort last in **registered action order**, never by reference value. Known
infeasible screens preserve objective/secondary ordering; all selected designs
still need solver verification. This is an explicit descriptive replay tie
rule, not permission to choose ranks after seeing truth. The registered replay
order must already agree: disagreement is a typed refusal, not a silent rewrite.
Conservative battery corner envelopes retain #917's abstention policy and are
not qualified uncertainty. Keep both protocol and band diagnostics where the
acquisition comparison needs them; each selected arm has its own manifest.

`baseline.json`, `carbon.json`, `screening.json`, `equal-budget.json`,
`value-evidence.json`, `value-report.json`, `ledger.json`, `evidence.md` and
`receipt.json` are retained. Raw analysis JSON includes public-development
per-decision detail; the page presents aggregate results. The receipt pins
inputs, executed code and output bytes, records analysis CPU/wall time and
its exclusions, and states that it launches zero solves and publishes nothing.
Fit/calibration/acquisition, query, retained verification, money and original
training costs are not all measured by this local invocation. Missing costs
remain NOT_MEASURED/UNMEASURED; the page does not certify C2/C3 affordability.

A complete negative result is a valid finished pack. An insufficient value
bar can also be displayed honestly when reserved receipts/rules are null.
Missing required transport evidence or a bad hop is different: exit 2,
`{"status":"REFUSED","stage":...,"reason":...}` and **no new page**.
The completion receipt is written last; an I/O interruption can leave a partial
directory without a receipt. It must never be reported as completed.

**Limit of current routes:** #998 only owns battery-v3, motor and f02. Cooling,
f06, f08, f13 and f17 return `FAMILY_ROUTE_NOT_IMPLEMENTED_BY_OPTIMIZER`.
The stronger #1011 f08/f13 comparators are retained; they are not replaced with
weaker methods just to force a complete pipeline. Indexed f02 is wrapped as
identity-bound per-context #994 comparator views and a complete schedule for
#998's existing f02 aggregate objective. Optimizer owners must extend the
other five family routes prospectively before those paths can complete.

## Data Collection return checklist

Return the public solved-panel export **and** the family comparator material
above; retain native raw results, environment/observer identities and timing
ledgers outside the analysis bundle. Missing peak curves or settlements are a
refusal, not zero-valued torque or an assumed feasible answer. The 24-context
f02 schedule needs a complete set of context sidecars and bindings.

The selected Carbon arm must separately supply its pinned predictions and
pre-held-out selection/rebuild receipt; this command cannot create that arm.
Optimizer supplies the registered candidate-map menu, solver-alone ordering,
cost plan and measured full screening/verification costs. Registration must
pre-date held-out results. Do not pick the winning menu or ordering afterwards.

Return the independently held-out fold, complete-query speed and owner-rule
receipts where earned. Otherwise leave the reserved fields null; expect an
honest insufficient page. Cross-check all seven manifest roles and compute
their literal byte pins only after the files are final. Start the command in
an empty output location. A finished page requires `receipt.json`; review it
before any owner-approved investor/public use. Panels finishing alone do not
prove Carbon adds value.

Byte identity does not establish rights, source independence, calibration
adequacy, pre-heldout registration, trustworthy timings or the strongest cheap
baseline. Producer custody and owner review retain those responsibilities.
Fixture packs are prominently **SYNTHETIC FIXTURE**, confer no reference or
Challenge qualification, and cannot be silently relabelled public evidence.
Pages are draft evidence artifacts for owner review, not automatic investor
publication, traction or LIVE claims. Battery EV5/journal14 remains untouched.

## The Carbon arm

`python -m carbon.development_comparison.carbon_arm battery-v3 --export ... --export-sha256 ... --train ... --train-sha256 ... --scope ... --output-dir ...`
produces the `carbon` role (`predictions.json`) and its receipt
(`receipt.json`), whose digest the predictions carry.

The arm trains the kit's registered default recipe on a pinned TRAIN set only.
A row outside TRAIN's support abstains, and a fixture TRAIN set can never
produce public predictions. The receipt records the fit cost and the
inference cost, cold and warm. See MODEL-PREDICTIONS-FOR-EVIDENCE-01.

Kits:
- **`battery-v3`** waits for its registered TRAIN set.
- **`motor`** is the 10p/12s machine. It needs `--material` set to the curve
  sidecar, for the panel designs' grammar. Its DEVELOPMENT TRAIN comes from
  the sidecar's study designs
  (`python -m carbon.development_comparison.motor_10p12s_kit`) until the
  registered TRAIN set lands.
- **`f02`** has 24 plain context questions. Its support is the registered
  960-case TRAIN plan's domain, and `carbon_arm.domain_gaps` must find no
  panel row outside it.
