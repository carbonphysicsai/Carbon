# OPERATOR-CPU-PREFLIGHT-01 CPU placement preparation

Status: candidate implemented and focused-tested; handoff pending CI and merge.
No paid execution.

Authority: Ryan's direct 2026-10-06 instruction to complete all work required
before spending; current AGENTS and delivery policy. Base: main ec1f7948.
This independent prerequisite does not depend on the unmerged #718/#722
packets and does not advance a Challenge stage or family queue.

## Scope and definition of done

KEEP the operator-owned compute store, intent identity, credential boundary,
tag reconciliation and verified cleanup. REPAIR the missing CPU placement
contract: a CPU request must contain one explicit flavor and positive integer
vCPU count, represented by an immutable validated value. Bind both to the
request digest and Runpod create body. Reject implicit CPU placement, raw
unvalidated objects, mixed GPU/CPU requests and GPU-specific CUDA constraints
on CPU requests before provider contact. Preserve existing GPU request digests.

Exercise deterministic/fake-provider tests, changed-placement replay refusal,
lost-response reconciliation, GPU compatibility, credential disclosure and
existing lifecycle tests. Run applicable canonical acceptance, record a lesson,
and hand one PR to PR Lead with `Codex is done; PR Lead may take over.`

## Boundaries and next work

No live provider mutations, solver/image build, paid dispatch or grant issue.
Placement in a request does not verify actual allocated hardware or process
RAM. CPU quotes, immutable multi-resource grants, atomic cross-process budget
reservation, finite cost/deadline validation, durable supervision, artifact
retrieval and actual allocation checks remain separately bounded preparation.
No registry, validator, score, protected material, Battery EV5/journal14,
image-release #725 or handed-off branch is changed. Maturity ceiling:
IMPLEMENTED/TESTED request construction only, not paid readiness or qualification.

## Validation and conditional closeout

Canonical focused CPU-placement and pipeline tests on the final executable
inputs: 67 passed, 1 skipped (an existing optional-numpy test in the dev-only
environment). Earlier CPU/GPU/pipeline compatibility acceptance with the
science-jax group passed 135 tests before the final exact-type subclass refusal.
That earlier result is compatibility evidence, not a pass claimed for different
final inputs. Final pinned quality preflight passed after repairing two import-order
diagnostics and restoring tracked file modes only inside its disposable copy.
The Windows mount's executable-mode artifact did not justify ignoring a rule.
Its final result was Ruff 0/776 and Black 0/68, all four changed Python files
clean, and diff hygiene passed against the starting main.

Close this ticket only when the final PR's applicable automated acceptance and
Merge gate pass and PR Lead reports its normal exact-head merge. Retain the
multi-resource admission and real hardware verification limitations above.
