# Missing reference packages — DC build handoff

`SOLVER-PACKAGE-SPECS-01`; **SPECIFIED, not built or qualified**. These
specifications preserve the buyer tasks in the current packets. They do not
grant build, solver, bank, hidden-data or paid execution authority. No new
solver was installed or run. The [planning sheet](package-specs.json) is
non-executable: accepted image/manifest identities are null and permissions
are false. `HUMAN_INPUT` identifies an unresolved owner/DC selection, with a
recommendation where possible; a recommendation is not an accepted pin.

| Handoff | Buyer decision retained | Principal missing proof |
| --- | --- | --- |
| [f17 OpenFOAM](f17-openfoam.md) | Full 10-mm grooved-channel outlet mixing, pressure and volume/flow | Low-diffusion scalar transport and exact flow-cache reuse |
| [f06 Meep](f06-meep.md) | Finite-width 3D fibre coupling, reflection and robust 45-point summary | Vector mode/fibre observation, independent 3D witness and fine-grid memory |
| [Warpage CalculiX](warpage-calculix.md) | Full 3D underfill/solder choice over complete process/service history | Calibrated material evolution, joint formation and restart state |

No full cold plate, motor comparator, hidden bank, solver build scripts or
runtime adapters are added. This is not a second copy of the buyer packets.
DC owns the eventual implementation and measured return; science/customer
owners own adequacy and applicability. Coordinate new interfaces with Carbon
Validator and PR Head on #643 before implementation. Warpage is a proposed
replacement, not an adopted ninth Challenge.

## 1. Pin before claiming a package

**Shared image-base recommendation:** reuse the inspected f08 acquisition
recipe at `0f12834226f65cdb317e7407e1e83e68c135801b`:
`debian@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f`,
with repository snapshot
`http://snapshot.debian.org/archive/debian/20261001T000000Z trixie main`.
This is a source-recipe observation, **not** independent verification of the
image or a successful f17/f06/warpage build. Recheck registry/platform
resolution and retain the selected linux/amd64 child digest, compiler and
installed-package inventory. A snapshot date alone does not pin every
dependency or prove authenticity. Do not infer a Debian minor version from
an unverified source-lock description.

For each package, DC supplies one versioned `source.lock` and build receipt:

1. Exact upstream release, immutable commit and archive checksum; provenance
   of each checksum and licence/redistribution inventory. A checksum obtained
   by DC establishes content identity, not publisher endorsement. Missing
   archive/dependency hashes are `HUMAN_INPUT: DC`; recommend content-hash
   verification against independently retained upstream release evidence.
2. Exact base/platform digest, package versions, repository snapshot, native
   libraries, Python wheels if used, compiler/linker versions and flags,
   build environment and bounded build concurrency. **HUMAN_INPUT: build
   owner**; recommend serial proof first, then separately bounded concurrency.
   No `latest`, floating install or network download at solve time.
3. Built image digest, solver binary/version hashes, smoke-deck/mesh/observer
   hashes, reproducible build log and licence/SBOM inventory. If compatibility
   forces a base change, record a new prospective recipe; do not overwrite
   the f08 evidence. A native host install is not the canonical container.
4. Per-run case, CAD/mesh, material, BC, source, time/frequency grid, observer,
   normalization/cache and tolerance identities. Also freeze CPU architecture,
   thread/rank counts, environment and resource enforcement. These are future
   manifest obligations, not a newly implemented runtime schema.

Full source and dependency pins precede the build; the final image digest is
necessarily produced by the build. A build can prove compilation and selected
features before scientific material inputs exist, but only with conspicuous
non-production fixtures. **A missing scientific input blocks physical-task
execution, not documentary packaging work.** Security acceptance remains
separate from containerisation. Never prune a shared Docker engine; later
cleanup may target only the owner's explicitly named image tags.

## 2. What a smoke result may say

Separate four results: **BUILD_OK**, **FEATURE_PROOF**, **TASK_OBSERVER_PROOF**,
and **REFERENCE_ADEQUACY_NOT_DEMONSTRATED**. These are report labels here, not
new runtime enums. A version banner is only BUILD_OK; a tiny fixture cannot
qualify the task. Each family specifies the smallest ladder that exercises
its risky features. Stop at an unsupported feature rather than substitute a
different buyer task. Numerical thresholds not already selected in a packet
remain `HUMAN_INPUT: science/reference owner` with explicit recommendations.

Record deterministic input/deck identity separately from numerical
reproducibility. Repeat the same frozen case in clean work directories at the
same resource shape; compare raw fields/integrals and exported observables,
not just a rounded score. **HUMAN_INPUT recommendation:** two clean repeats
for smoke, followed by a cross-build/platform witness before claiming broader
reproducibility. Byte-stable metadata excludes clocks/paths; numerical fields
use approved unit-bearing tolerances, not an invented universal epsilon.
Serial evidence does not qualify an MPI/parallel build or altered partition.

The [f13 finding](../round1/f13-power-balance-diagnosis.md) motivates independent
accounting: pin sign, plane/region, units and normalization; retain raw
integrals; never force closure by defining one physical term as the residual.
Compare independently measured contributions. Check conservation, mesh/time
convergence, observer convergence and independent buyer-tool agreement
separately. A small residual cannot prove the right solution or the right
decision.

## 3. Retained return, including failures

DC returns the frozen manifest and ledger plus:

- Raw logs, fields/state and independently extracted integrals, dimensions,
  masks/orientations, mesh statistics, solver iterations and convergence.
- Complete-case wall seconds, **summed process CPU seconds** (solver and
  helpers), allocated node/core-hours, process-tree peak memory and enforced
  memory limit. RSS and container/cgroup memory have different meanings;
  retain both where available. Report meshing/build/normalization/extraction,
  successful and failed/refined attempts separately; no parallel-speedup
  assumption converts CPU time to wall time. Retain hardware/thread details.
- Hypothesis versus actual timing/memory and the counted launches. Small
  smoke results cannot furnish a statistical p95 or full-bank C2. Cost is
  **UNMEASURED** until the appropriate complete-task study returns.
- A typed failure cause: invalid input, missing/unconverged reference,
  observer unsupported, numerical unresolved, infrastructure failure, or
  resolved physical infeasibility. These categories must map to the existing
  runtime policy later. Missing truth is never candidate failure or
  `NONE_FEASIBLE`; failed attempts remain in the resource ledger.
- Repeat/convergence/conservation results and remaining HOLDs, not a single
  green smoke flag. No automatic retries or implied permission to exceed caps.

Before a feasibility panel, freeze its exact designs/conditions, controls,
refinement selections, resource/attempt cap and stage authority. Existing
first-round ceilings are not an enforced runner or a fresh campaign grant.
This ticket proposes no new cap or spend. Exact CPU/memory sizing is measured
on the eventual authorised hardware, not inferred from supplier core count.

## 4. Credibility and decisions

Apply the [credibility contract](../round1/reference-credibility.md): matched
decks and observables, pointwise agreement **and** feasibility/pick agreement
or regret in buyer units. Thresholds remain HUMAN_INPUT where not adopted.
Buyer-tool witnesses come from separate non-hidden draws or provenance-checked
retired published cases, **never hidden EVAL/STRESS/quiz/tuning**; run outside
the producer's custody. Self-convergence does not earn Tier 2. Systematic
disagreement is a reference finding, with a prospective versioned revision,
not a candidate penalty or silent historical rescore. Claims remain “matches
the reference simulator”; no reality claim without the required Tier 3.

DC should build the least-cost feature ladder first, then return whether the
original task fits the resources and whether the credible route exists. If
f06's supported fine grid or warpage's full history cannot be delivered, stop
that route and report the smallest science/owner choice. No safety relaxation,
unapproved dimensional reduction or counterfeit adequate reference.
