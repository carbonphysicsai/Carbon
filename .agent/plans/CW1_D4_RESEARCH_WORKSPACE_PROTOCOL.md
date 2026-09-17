# C-W1-D4 public workspace protocol amendment v1

Owner: OWNER-C-W1-D4-AUTORESEARCH-01. Scope: authenticated public/synthetic
DEVELOPMENT only. This is an additive registered task, not a second research API.

The twelve `carbon_research_v2` operations remain. `start_research_task` gains
`DevelopmentWorkspaceTaskSpecV1`, version `carbon.autoresearch.workspace.v1`,
with the closed actions public_material, inventory, read_file, write_file,
notebook, capability_request and run_python. Each uses canonical bounded JSON
arguments; exact schemas are enforced by the D4 provider. Existing task records
and canonical bytes remain unchanged. The legacy provider rejects the new kind;
only the explicit public-development composition executes it.

Transport: B-07 canonical binary is standard canonical base64 in a single
`call_base64` field, under the `carbon_research_v2` authenticated tool namespace.
The trusted supervisor maps twelve model function names to those operations.
Submission remains separately authenticated under `carbon_protocol_v1`.

Workspace task bindings contain zero strategies and the exact new practice
scope. File/script output is self-reported; it is not a reconstruction recipe,
reference-service result, accepted comparison or signed final evidence. Practice
uses the existing PracticeTaskSpec and the separately fixed trusted real JAX
provider. Novel unrepresentable constructions become capability requests.

The D4 supervisor may append `carbon.autoresearch.public-result.v1` to an owned
successful task result: exact task id, B-07 receipt digest, result digest and
bounded public/self-owned payload. The B-07 receipt remains unchanged. The
projection cannot retrieve another requester's files, arbitrary controller paths
or protected/final material. Reads are byte-ranged at 4096 bytes; writes fit the
12288-byte canonical argument cap. Nested checkpoint exports remain task-owned.

Research/practice inputs are public, adaptively seen and ineligible as final
confirmation. Provider keys, signing keys, wallet, repository and final case roots
remain outside worker mounts. Budgets cannot be changed by any action. B-07
durable state is saved before execution, with one supervisor lease. Restart of a
running task requires reconciliation and never automatically retries.


## Public material and supervised reply extension

The optional local `carbon.autoresearch.supervised-reply.v1` envelope contains
the original canonical v2 reply, a canonical terminal task observation, and the
owned `carbon.autoresearch.public-result.v1` projection. The authenticated
requester selects neither a provider nor a projection callback. The original
`call` interface and twelve nominal operations remain available unchanged.
A started queued task is awaited by the supervisor without model status calls;
running/ambiguous replay is never dispatched twice.

Public reference access allows only `research-train` and
`research-validation`. Primary C-04 calls are individually admitted and counted;
failed/ambiguous calls retain reservations and cannot trigger case replacement.
Primary-only practice does not claim measured reference uncertainty. Final
reference refinement remains a separate evaluator-owned operation.

Every arbitrary Python workspace task conservatively consumes one of the 16
research trial slots, including analysis-only scripts and failures. A task may
explore one declared construction hypothesis; it cannot grant additional
training authority by running an inner search loop. CPU/time caps remain
independently enforced; no claim is made that arbitrary source code permits
perfect semantic counting of hidden internal optimization operations.
