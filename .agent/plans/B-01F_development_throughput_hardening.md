# B-01F plan — Development Throughput Hardening

**Ticket:** B-01F
**Status:** final single-ticket candidate; `done` and B-04 runtime selection
remain conditional
**Branch:** `agent/b-01f-development-throughput`
**Exact base commit:** `79293d5b65efef8553c0583ba6cf9bc5d0922ff6`
**Exact base tree:** `62ccbe40d5df0c8c45403609dc14cc7ca892bb25`
**Decision:** `OWNER-DX-01`
**Evidence:** `.agent/evidence/wave_b/b-01f.md`
**Primary Hub map_ref:** `SYSTEM/AGENT-EXECUTION`
**Hub impact:** `HUB_UPDATE_REQUIRED`; `map_structural`; affects
`SYSTEM/GOVERNANCE`, `SYSTEM/DEVELOPMENT-SEQUENCING`, `SYSTEM/CI`,
`SYSTEM/PR-MAINTENANCE`, `SYSTEM/DEVELOPMENT-HUB`,
`SYSTEM/DEVELOPMENT-HUB/VALIDATION`, `SYSTEM/MATURITY`, `WAVE-B`,
`WAVE-B/B-01F`, `WAVE-B/B-01G`, and `WAVE-B/B-04`

## 1. Start gate and bounded authority

1. Preserve all worktrees and local changes; fetch without pull; create the
   dedicated branch from the exact post-PR-#72 `origin/main` above.
2. Verify PR #72's reviewed head/tree, normal merge topology, exact reviewed-
   tree preservation, exact-main canonical/clean-container/Hub checks, and
   ratified-contract maturity.
3. Record `OWNER-DX-01`: B-01F temporarily precedes B-04 runtime while
   preserving the merged B-04 engineering contract.
4. Keep B-01G future `todo` and non-blocking. Do not implement B-04 runtime or
   another scientific ticket.

## 2. Reuse and disposition

- `KEEP` Carbon's canonical Linux/dev-image identity, `uv.lock`, current
  substantive CI acceptance, code-authority boundaries, ticket dependencies,
  human-reserved authority, and normal merge-commit history.
- `WRAP` the canonical environment with one portable launcher so host operating
  systems do not produce competing evidence paths.
- `REPAIR` stale pull-request declarations, path-insensitive CI, avoidable Hub
  fan-out, missing identity hygiene, dynamic-evidence commits, and process-only
  separate-contract requirements.
- `REPLACE` prompt-only merge permission and external-fact closeout commits
  with repository authority, `Merge gate`, and an external receipt.
- `NEW_OWNER_DECISION_REQUIRED` only for live GitHub administration when the
  current credentials lack repository ruleset permission. No scientific,
  security-acceptance, rights, economic, qualification, launch, or production
  value is selected.

## 3. Reviewable vertical slices

1. Governance, tickets, plans, decision, one-PR delivery, evidence classes,
   pull-request template, and launcher.
2. Delivery-hygiene checker, identity/host/path fixtures, and environment
   guidance.
3. Canonical execution wrapper and deterministic command-construction tests.
4. Strict changed-path classifier, path-aware CI, delivery preflight, and
   stable `Merge gate`.
5. Live pull-request body/head validation, relevant PR-state triggers, and
   semantically bounded Hub output fan-out regression.
6. Versioned GitHub main-ruleset definition, dry-run/apply tooling, final
   integration, exact candidate audit, and conditional closeout.

The final reviewed tree contains the working contract, implementation, tests,
and stable evidence together. A separate contract PR is not justified for
B-01F.

## 4. Fixed manifest and final Hub reconciliation

The fixed non-semantic-Hub manifest is:

```text
.agent/DECISIONS.md
.agent/DELEGATED_DECISION_PROTOCOL.md
.agent/DELIVERY_PROTOCOL.md
.agent/WAVE.md
.agent/WAVE_B.md
.agent/WAVE_B_CODEX_HANDOFF.md
.agent/evidence/wave_b/README.md
.agent/evidence/wave_b/b-01f.md
.agent/evidence/wave_b/b-04.md
.agent/plans/B-01F_development_throughput_hardening.md
.agent/plans/B-04_reference_truth_contracts.md
.agent/templates/EXTERNAL_COMPLETION_RECEIPT.md
.agent/tickets/B-01F_development_throughput_hardening.md
.agent/tickets/B-01G_static_schema_codegen_proof.md
.agent/tickets/B-04_reference_truth_contracts.md
.agent/tickets/B-05_measurement_scorepack_authoring.md
.agent/tickets/B-06_dossier_manifest.md
.agent/tickets/B-07F_fixture_official_construction_adapter.md
.devcontainer/Dockerfile
.github/pull_request_template.md
.github/rulesets/main.v1.json
.github/workflows/ci.yml
.github/workflows/development-hub.yml
AGENTS.md
agent_pack/CODEX_TICKET_LAUNCHER.md
agent_pack/EXECUTION_PROTOCOL.md
agent_pack/PLANS.md
agent_pack/README.md
docs/development/ENVIRONMENT.md
docs/development/carbon_hub/data/decisions.json
docs/development/carbon_hub/tools/render_hub.py
docs/development/carbon_hub/tools/test_validator.py
docs/development/carbon_hub/tools/validate_hub.py
scripts/dev/apply_github_ruleset.py
scripts/dev/bootstrap.sh
scripts/dev/canonical.sh
scripts/dev/check_delivery_hygiene.py
scripts/dev/check_diff_hygiene.py
scripts/dev/check_merge_gate.py
scripts/dev/ci.sh
scripts/dev/ci_contract_authority.sh
scripts/dev/ci_derived_documentation.sh
scripts/dev/ci_hub.sh
scripts/dev/ci_preflight.sh
scripts/dev/classify_changes.py
scripts/dev/delivery_hygiene_allowlist.txt
tests/cpu/test_canonical_wrapper.py
tests/cpu/test_change_classifier.py
tests/cpu/test_code_authority.py
tests/cpu/test_delivery_hygiene.py
tests/cpu/test_github_ruleset.py
```

Exact-head clean-image validation exposed that bootstrap redundantly attempted
to rewrite the image's root-owned managed interpreter. The repaired candidate
therefore adds `scripts/dev/bootstrap.sh` to this fixed list so bootstrap can
reuse an exact trusted interpreter and install only when one is absent. This
bounded recovery does not change the canonical environment identity or the
B-04 exclusion.

The next exact-head canonical run completed bootstrap, doctor, the invariant
lane, and 3,286 CPU tests before the linked-worktree wrapper integration
returned an otherwise silent status of 1. The bounded repair keeps every
mount, identity, isolation, and read-only assertion; it replaces the opaque
global `git status | grep -q` probe under `pipefail` with an exact path-scoped
status capture and gives every remaining shell assertion a distinct
diagnostic. No canonical trust predicate or runtime acceptance is relaxed.

That diagnostic then proved the nested wrapper was rejecting uv's version
string, not Git isolation: the pinned uv binary appends build metadata while
the direct predicate compared the entire output to `uv 0.12.7`. The final
bounded repair parses and compares the exact `0.12.7` semantic-version token,
matching bootstrap and doctor while still rejecting every other version. It
also explicitly normalizes root-owned uv, uvx, and managed Python executables
to non-writable mode and retains opt-in, label-only identity diagnostics. The
exact trust predicate remains fail closed.

After every non-Hub commit settles, perform one coherent semantic Hub
reconciliation. Update `data/hub_data_v2.json` and `data/change_events.json`
for B-01F/B-01G and the conditional B-04 runtime selection (under
`docs/development/carbon_hub/`). Add bounded impact-policy ownership for the
new delivery protocol, external-receipt template, ticket launcher, and main
ruleset artifact so no new authority path remains unmapped. Then run the
renderer once and include only the generated outputs whose bytes truly change.
Do not hand-edit generated files or emit repeated intermediate regenerations.
The final exact manifest is the fixed list above plus that renderer-determined
semantic source/output set; finalize and audit it only after the coherent
render.

No `carbon/**`, runtime fixture, domain contract, dependency, lock, generated
Hub output outside the renderer-determined semantic set, B-04-D1 through
B-04-D10, or
`Design_Specs/Reference_and_TruthAsset_Contract.md` change belongs in the
manifest.

## 5. Validation plan

Run focused checks during each slice, then from the exact final candidate run:

```text
./scripts/dev/canonical.sh ./scripts/dev/check_delivery_hygiene.py --base 79293d5b65efef8553c0583ba6cf9bc5d0922ff6
./scripts/dev/canonical.sh --focused tests/cpu/test_delivery_hygiene.py
./scripts/dev/canonical.sh --focused tests/cpu/test_change_classifier.py
./scripts/dev/canonical.sh --focused tests/cpu/test_canonical_wrapper.py
./scripts/dev/canonical.sh --focused tests/cpu/test_github_ruleset.py
./scripts/dev/canonical.sh python docs/development/carbon_hub/tools/test_validator.py
./scripts/dev/canonical.sh ./scripts/dev/ci_hub.sh
./scripts/dev/canonical.sh ./scripts/dev/ci.sh
```

Also run the clean dev-container acceptance, Hub render `--check`, Hub
validation, route and browser checks, ruleset apply-tool `--dry-run`, and
`git diff --check`. Record exact final commands/results in CI or the external
completion receipt; do not mutate the reviewed tree merely to store them.

## 6. Review, merge, and closeout

1. Open one PR titled `B-01F: harden Carbon development throughput`.
2. Publish the material `OWNER-DX-01` notice to issue #42; route only an
   explicit `DEFER_TO_OWNER` to issue #41.
3. Require exact-head scope checks and `Merge gate`, exact-head Greptile,
   repair of every valid finding, zero unresolved Greptile threads, and no
   applicable blocking direction.
4. Normally merge with the exact expected-head guard; do not squash,
   rebase-merge, or enable auto-merge.
5. Verify ordered parents, reviewed-tree preservation, exact fetched main, and
   exact-main `Merge gate`.
6. Post `.agent/templates/EXTERNAL_COMPLETION_RECEIPT.md` outside the tree.
7. Only after that complete predicate, including the posted receipt, treat
   this candidate's B-01F `done` and B-04 runtime selection as effective.
   Record that exact main and recommend fresh branch
   `agent/b-04-reference-truth`. This owner direction explicitly requires the
   current session to stop before writing B-04 runtime; a later authorized
   session may execute B-04 end to end under the launcher.

## 7. Risks and stop conditions

- Unknown paths classify to full runtime acceptance; do not loosen the
  classifier to make B-01F cheaper.
- A stale or edited PR declaration never substitutes for repository content.
- A legitimate cross-cutting Hub change may rewrite all semantically affected
  outputs; the regression tests semantics, not an arbitrary numeric cap.
- Failed or unauthorized ruleset application remains a truthful manual action,
  not an applied state.
- Any B-04 runtime or later-ticket implementation is out of scope and stops
  this branch.
