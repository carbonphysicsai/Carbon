# Electric motor magnetics — Level-0 Launchpad construction

**Challenge:** `electric-motor-magnetics` version `1.0`

**Ticket:** `CHALLENGE-MOTOR-02`

**State:** DEVELOPMENT construction integration; not scientifically,
security, customer, production or LIVE qualified

## What is reachable

Carbon can resolve the Motor Challenge through the same Challenge registry and
Launchpad campaign seam used by other Challenges. A miner or Graphite
construction may submit one declarative Level-0 recipe:

```json
{
  "schema_version": "1.0",
  "challenge_id": "electric-motor-magnetics",
  "backbone": "kernel_ridge",
  "parameters": {
    "length": "length_4",
    "ridge": "ridge_1e_4"
  }
}
```

The tokens are exact finite choices. Challenge discovery publishes their
numeric values. The registered choices are the existing public calibration
grid: kernel lengths `0.25, 0.5, 1, 2, 4, 8, 16` and ridge values
`1e-8, 1e-6, 1e-4, 1e-2, 1e-1, 1`. Carbon converts a token only after strict
contract validation.

Construction rebuilds the existing deterministic Gaussian kernel-ridge model
from the digest-pinned 150-case public TRAIN pool. Public practice rebuilds
the same recipe in the registered Linux CPU isolated carrier and predicts the
fixed 30-case public PRACTICE pool. Practice labels remain on the trusted host;
the worker receives only inputs. The private 60-case pool, frozen decision-
study references and future confirmation material have no construction loader.

## Scope and worker

The model predicts the 60-angle electromagnetic torque curve over one
15-degree rotor period for the existing two-dimensional, surface-PM periodic
cross-section from eight registered inputs. It does not represent
three-dimensional end effects, thermal behavior, drive transients or hardware.

The worker is the existing verified C-03 Linux x86-64 CPU isolated carrier:
two CPUs, 4 GiB memory, no swap, float64 numerical work and a 600-second worker
deadline. The Motor recipe uses NumPy from that pinned environment and offers
no GPU practice lane. This ticket builds or authorizes no new image.

## Fail-closed boundaries

- Unknown families, fields and choice tokens are rejected before worker
  dispatch.
- Cross-Challenge recipes never fall back to battery, cooling, Burgers or
  another compiler.
- The campaign may construct, practice and freeze a candidate, but submission
  evaluation returns the typed refusal `motor_validator_not_served` until a
  separate validator/scoring ticket registers Motor.
- The admission sheet remains `DRAFT_NOT_FROZEN`: attack budget and the fresh
  evaluator-held confirmation population are `HUMAN_INPUT`.
- Constructed Track-B controls and the fresh sealed confirmation set remain
  separate tickets.

## Inspect and reproduce the engineering path

From the repository root:

```text
python -m carbon.agent_campaign study \
  --out docs/development/motor/level0 \
  --challenge electric-motor-magnetics

python -m carbon.agent_campaign study \
  --check docs/development/motor/level0
```

The generated files are:

- `docs/development/motor/level0/study-sheet.json`;
- `docs/development/motor/level0/permission-inventory.json`.

Challenge discovery is available through the open-tier Challenge catalog
(`list`, then `describe` for `electric-motor-magnetics`, version `1.0`). Product
campaign launch continues through the existing Launchpad runner with that
exact Challenge id and version; there is no Motor-specific branch in the
shared workflow.

## What comes next

This PR is the construction/admission adapter only. The remaining Motor work
is deliberately separate:

1. the Motor adapter for the Challenge-neutral validator/scoring seam;
2. the five constructed Track-B Motor controls;
3. owner/operator creation and sealing of a fresh confirmation set;
4. completion and owner freeze of the attack budget and confirmation-
   population pins;
5. dry run, smoke test, pod scoring and rebuild/refusal entry checks;
6. the separately owner-approved counted 8-design × 6-condition decision-
   reference campaign.

The frozen decision study, delegated 4.0 N m / 0.30 limits, six conditions,
eight-design rule and method settings remain unchanged. This integration
does not create a scientific-qualification or model-advantage claim.
