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
- **Motor and f02 are not here:**
  - motor needs a 10p/12s kit, its own job;
  - f02 has no kit and no export; it is a typed gap.

**Evidence (fixture, not a claim).** On the real battery-v3 export, a toy
fixture TRAIN of 162 records and a quick recipe gave:
- 493 of 493 rows predicted, all accepted by the pipeline's Carbon hop;
- a warm query of about 4 ms for all rows.

**Next.** Run the arm on the registered v3 TRAIN set when it lands, with
`--scope PUBLIC_DEVELOPMENT`.
