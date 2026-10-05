# AI accelerator cooling — Level-0 Launchpad construction

**Challenge:** `chip-cold-plate` version `1.0`

**Tickets:** `CHALLENGE-AI-COOLING-06` (construction),
`CHALLENGE-AI-COOLING-07` (Graphite public-practice scoring),
`CHALLENGE-AI-COOLING-08` (Interface-v1 validator) and
`CHALLENGE-AI-COOLING-09` (PB-ADV / Mode X)
**State:** DEVELOPMENT construction integration; not scientifically,
security, customer, production or LIVE qualified

## What is now reachable

Carbon can resolve the periodic-cell cooling Challenge through the same
Challenge registry and Launchpad campaign seam used by other Challenges. A
miner or Graphite construction may submit one declarative Level-0 recipe:

```json
{
  "schema_version": "1.0",
  "challenge_id": "chip-cold-plate",
  "backbone": "kernel_ridge",
  "parameters": {
    "length": "length_8",
    "ridge": "ridge_1e_6"
  }
}
```

The tokens are exact finite choices. Their public numeric values are exposed
in Challenge discovery. The registered choices are the published calibration
grid: kernel lengths `0.25, 0.5, 1, 2, 4, 8, 16` and ridge values
`1e-8, 1e-6, 1e-4, 1e-2, 1e-1, 1`. Carbon converts a token to its value only
after contract validation.

Construction rebuilds the existing deterministic Gaussian kernel-ridge model
from the digest-pinned 400-case public TRAIN pool. Public practice rebuilds the
same recipe in the registered Linux CPU isolated carrier and predicts the
fixed 100-case public PRACTICE pool. Practice labels remain on the trusted host;
the worker receives only practice inputs. Counted decision-study CFD, private
pool records and future confirmation material have no construction loader.

## Scope and worker

The model predicts the existing periodic straight-channel cell’s peak
heated-face temperature, 30-segment axial temperature profile and pressure
drop from the nine registered inputs. It does not represent manifolds,
transient loads, two-dimensional chiplet maps or hardware.

The worker is the existing verified C-03 Linux x86-64 CPU isolated carrier:
two CPUs, 4 GiB memory, no swap, float64 numerical work and a 600-second worker
deadline. The cooling
recipe uses NumPy from that pinned environment and offers no GPU practice
lane. This ticket builds or authorizes no new image.

## Fail-closed boundaries

- Unknown families, fields and choice tokens are rejected before worker
  dispatch.
- Cross-Challenge recipes never fall back to battery, Burgers or another
  compiler.
- Graphite can construct and score a candidate on the fixed public PRACTICE
  cases through Cooling's named `ChallengeScoring`. Its paired baseline result
  is descriptive only, carries no confidence interval and is never
  promotable.
- Launchpad's product-campaign `evaluate_frozen` path still returns the typed
  refusal `cooling_validator_not_served`; it has not been wired to a private or
  official evaluator. The separate Interface-v1 `ChallengeAdapter` now serves
  only the exact digest-pinned public PRACTICE batch through an owner-only
  DEVELOPMENT store. It creates no private or official exam.
- A candidate-triggered reconstruction exception, prediction exception or
  non-finite aggregate score is classified by the digest-pinned
  `cooling-candidate-fault-v1` policy as `FAILED_INFRA / adapter_failure`.
  The result carries the policy version, digest and fault kind but never the
  exception text. The validator does not retry, charge or refund; the policy
  records the existing surrounding A7 lifecycle interpretation so Track A can
  test selective-crash/retry behavior against an inspectable rule.
- The admission sheet remains `DRAFT_NOT_FROZEN`: attack budget and the fresh
  evaluator-held confirmation population are `HUMAN_INPUT`.
- PB-ADV/Mode X is served by the existing Challenge-neutral design-search
  methods with an explicit request-bound K and write-once point commitments.
  No default K, attack grid, acceptance threshold or reference campaign is
  supplied. Constructed Track-B decision-value controls and the fresh sealed
  confirmation set remain separate tickets.

## Inspect and reproduce the engineering path

From the repository root:

```text
python -m carbon.agent_campaign study \
  --out docs/development/cold_plate/level0 \
  --challenge chip-cold-plate

python -m carbon.agent_campaign study \
  --check docs/development/cold_plate/level0
```

The generated files are:

- `docs/development/cold_plate/level0/study-sheet.json`;
- `docs/development/cold_plate/level0/permission-inventory.json`.

Challenge discovery is available through the existing open-tier Challenge
catalog (`list` then `describe` for `chip-cold-plate`, version `1.0`). Product
campaign launch continues through the existing Launchpad runner with that exact
Challenge id and version; there is no cooling-specific shared-workflow branch.

The Graphite path now requires an explicit Challenge. Its no-network,
no-provider, no-spend fixture run is:

```text
python -m carbon.agent_campaign.graphite.phase3 run \
  --root <PRIVATE_DIR_OUTSIDE_REPOSITORY> \
  --challenge chip-cold-plate \
  --dry-run
```

That run uses scripted inference, synthetic predictions and an in-memory
RunPod transport, while exercising Carbon's real admission, rebuild, public
practice scoring, comparison, bundle and clean-rebuild paths. It is fixture
evidence, not a scientific result. A paid Graphite run additionally needs the
existing exact grant, credentials, pushed code ref, miner campaign and frozen
literature snapshot; naming this Challenge does not authorize spend.

## What comes next

Level-0 construction, public Graphite scoring, the public-practice
Interface-v1 validator, the Graphite attack adapter, its constructed Track-B
controls and PB-ADV/Mode X are now implemented in bounded DEVELOPMENT scope.
The remaining cooling preparation is:

1. owner/operator creation and sealing of a fresh confirmation set;
2. completion and owner freeze of the attack budget and confirmation-population
   pins, followed by dry run, smoke test, pod scoring and rebuild/refusal entry
   checks.

The frozen 8-design × 6-condition decision study and its counted 48-case CFD
evidence remain unchanged. This integration does not turn that single
development problem into a population-reliability or learned-model-advantage
claim.
