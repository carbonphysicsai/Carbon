## 2026-10-10 — MODEL-PREDICTIONS-FOR-EVIDENCE-01: the Carbon arm of an evidence pack, and the battery v3 kit

**Authority.**
- **The direction.** The Test Lead, under OWNER-DEV-AUTONOMY-01: the evidence
  pipeline (#1016) needs, per Challenge, the selected Carbon model's
  predictions on the panel's physical rows, with its measured inference cost.
- **Battery.** The Test Lead chose option (a): a battery v3 kit, built now on
  fixtures. Data Collection solves a registered v3 TRAIN set, disjoint from the
  panel.
- **The scope.** DEVELOPMENT only. There is no threshold, qualification or
  value claim, and no spend.

**Decision.**
- **`carbon.development_comparison.carbon_arm`** trains one registered default
  recipe on a pinned TRAIN set and predicts every physical row of a
  solved-panel export:
  - **the recipe:** a dense network on Carbon's shared trainers
    (`carbon.battery.training` and `torch_training`), at the battery defaults,
    full batch, float64, with Carbon's seed;
  - **the outputs:** `carbon.development-prediction-input.v1`, whose
    `source_receipt_digest` is the digest of a
    `carbon.development-carbon-arm-receipt.v1`. The receipt names the model,
    TRAIN (its sha256, records, exclusions and support), the recipe, the code
    (commit and file digests), the environment, and the measured fit and
    inference cost. Inference has a cold call, which includes compilation,
    and a warm call, which is the query cost.
- **What it never does:**
  - **reads the panel's reference values.** A row's inputs come from its
    action and band only.
  - **selects a recipe on panel results.**
  - **extrapolates.** A row outside TRAIN's observed support abstains
    explicitly.
  - **lets a fixture pass as public.** Fixture TRAIN produces only
    `SYNTHETIC_FIXTURE` predictions.
- **`battery_v3_kit`:**
  - **inputs:** `c1`, `c2`, `switch_v`, `cooling` (categorical), `ambient_c`
    (the band) and `soc0`. The v3 TRAIN set varies SOC0 over 0.10, 0.20 and
    0.30. The panel's SOC0 is not in the export: it is 0.10, from battery's
    registered requirement (`timing.initial_soc`), confirmed by Data
    Collection. Unregistered, the kit refuses to predict;
  - **outputs:** the panel's five observables, directly;
  - **TRAIN record:** `carbon.battery-v3.train-record.v1`, specified in the
    module docstring for Data Collection.

  Carbon's battery Challenge kit cannot cover v3: it has no switch voltage or
  cooling input, and its `c1` starts at 0.5.
- **`motor_10p12s_kit`** (amendment, same day). The panel's machine is
  MOTOR-FEASIBILITY-02's 10-pole, 12-slot, double-layer machine. Carbon's
  motor Challenge kit is another machine (the GRUCAD 8-pole, 24-slot frame),
  so it cannot serve. This kit is the panel machine's:
  - **the model:** the 48-sample signed torque curve of one 2D slice, from
    the six grammar coordinates, the current density and the current angle;
  - **the observables:** Data Collection's registered three-slice step skew
    (d in {-s/2, 0, +s/2}, current angle gamma - 5d, read at theta + d, the
    mean, and cogging from shifted J = 0 curves), then
    `curve_observables`. Applied to the sidecar's own curves, this reduction
    reproduces the panel's observables exactly (worst relative error
    6e-16). That checks the observer only, not any model.
  - **the arm** gained multi-query kits (`outputs`, `queries`, `reduce`). A
    row abstains when any of its queries is unsupported.
- **The motor TRAIN.** The Test Lead's decision is (i): a registered TRAIN
  set of new designs. Until it lands, Data Collection cleared the sidecar's
  19 study designs, which are disjoint from the panel, as a DEVELOPMENT
  stand-in (`train_from_sidecar`); every record names that source.
  Leave-one-design-out over the panel is never used for value-bar claims.
- **f02** has no kit and no export; it is a typed gap.

**Evidence (fixture, not a claim).** On the real battery-v3 export, a toy
fixture TRAIN of 162 records and a quick recipe gave:
- 493 of 493 rows predicted, all accepted by the pipeline's Carbon hop;
- a warm query of about 4 ms for all rows.

**Motor evidence (the stand-in, not a claim).** On the real motor export,
with the 19 study designs as TRAIN (170 cases):
- 9 of 44 rows are predicted and 35 abstain, because the panel's
  coordinates (slot bottom down to 34 mm) lie beyond the study designs'
  range;
- the pipeline's Carbon hop accepts all 44;
- a warm query takes about 4 ms for 176 model queries.

**Next.** Run each arm on its registered TRAIN set when it lands, with
`--scope PUBLIC_DEVELOPMENT`: battery v3's 4,000 cases, and motor's 128
geometries × 11 solves.
