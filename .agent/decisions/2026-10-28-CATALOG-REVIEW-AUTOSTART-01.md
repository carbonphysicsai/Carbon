# CATALOG-REVIEW-AUTOSTART-01

Status: delegated implementation; canonical validation and actual fresh-stdio
auto-start proof pending. Classification: IMPLEMENTATION_LAG.
Base `f3ce2c172e7b458da0b6f8f6770180439221387b`, tree
`953f1bb80c50f0aa8dd84f45b739396926573a71`.
Branch `codex/catalog-review-autostart`; frozen proof source, failed tasks,
candidate and held PhysicsNeMo source remain unchanged.

## Existing promise and actual defect

`docs/MINING.md:119` promises that saving setup settings starts the model
catalog in the background. The installer also states that a new install has
no profile yet and Review starts the catalog after writing one. Its
`--no-start` option controls the Control Center, not catalog installation.
The existing page fulfilled the promise with a wrapper after shared Review;
the MCP door used the same setup dispatcher without that wrapper.

The operator's actual fresh f3ce install and six real stdio MCP setup calls
persisted a valid practice-only own-agent profile and attached the tools,
but the next status still reported INCOMPLETE, 0/241, started_at null and a
manual action. The later operator-started job is not automatic-start proof.
Evidence archive SHA256:
`a4c9e396337a7d8b11e09c8f8226db5ab37d4d0d725da54231f0f20bd66ff662`,
with 16 inner hashes verified by Codex-INT.

The Lead explicitly authorized this bounded repair under the owner's
agent-first and actual-environment readiness instructions. Current
CONSTITUTION, INVARIANTS, WAVE direct-assignment direction, delivery/delegated
protocols, lean build target and current launch handoff remain controlling.
The earlier page-only scheduling text was engineering implementation, not
a reserved scientific or security acceptance decision. This repair confers
no scientific, security, economic, LIVE, launch or mainnet qualification.

## Choice and boundaries

KEEP `catalog_build.start`, its persisted-profile/running/complete checks,
exclusive child lock, pinned owner-run installer, logs and actual status.
REPAIR the existing shared `setup_operations.perform` boundary: only after
a successful confirmed Review or recheck reports profile_written, attempt
the maintained background start for that setup's state directory. Both
doors use this path. Remove the page's duplicate post-Review wrapper and
retain its explicit manual retry through the same start-or-status helper.
Expected operating-system or malformed-launch failures leave the successful
profile save intact; actual status still offers manual retry. Unexpected
programming errors are not converted into successful starts.

No status/read/reconnect/compute call starts a catalog job. No new MCP tool,
request field, setup flag, job-state framework or GPU-build consent is added.
No speculative RUNNING or installed marker is written by Review. Existing
source/profile/image checks, user values, own spending cap, private paths,
mock/official isolation and typed refusals remain unchanged. The background
child may fetch pinned wheels and build missing entries only through the
already maintained installer. Catalog completeness does not qualify a worker,
Challenge, official image or host.

Source/wheel/context identities change and any fresh target install/image
must bind the new source honestly. No scoring producer FILES, dependency lock,
worker image-admission rule, scientific value, score or historical artifact
is changed. The frozen Development Hub remains untouched under the current
delivery protocol.

## Baseline and validation plan

Reused actual canonical frozen77 full-shard outcomes: catalog_after_update
10 PASS, miner_setup_agent_first 30 PASS, practice_only 47 PASS; no failures,
errors or skips in those modules. The recheck module miner_setup_after_install
adds 46 PASS. Relevant setup source and all four tests are byte-identical from
77 to f3ce (empty Git diff). This is source-equivalent measured evidence,
not a claimed f3ce full-suite rerun. Verified completed-manifest log hashes:

- cpu0 `f89d0cfed231683db184f1aed71a7b0eed64c150ff8323347a4ada4dd9a83900`;
- cpu1 `718bc6dbb26620a79aa11a6af3eecb1c8d1e24315490b39ddfa3e259c19d3fae`.

Focused canonical command for Codex-INT, with OPENBLAS/OMP/MKL threads set
to one, one test process and no local execution:

```bash
./scripts/dev/canonical.sh .venv/bin/python -m pytest -q \
  tests/cpu/test_catalog_after_update.py \
  tests/cpu/test_miner_setup_agent_first.py \
  tests/cpu/test_practice_only.py \
  tests/cpu/test_miner_setup_after_install.py
```

Run changed Python through pinned Black 26.5.1 and Ruff 0.16.3, applicable
import/isolation and launchpad checks. Preserve original assertions while
testing both doors, real MCP practice/own-agent profile save, no-profile
recheck, refused confirmation, read-only/compute calls, existing job-lock
idempotence and start failure with truthful retry. The actual target proof
is a new fresh-install stdio MCP Review followed by observed background
job start/progress without a separate manual start. Fixture subprocess
spies and class tests do not establish that real proof or full installation.
