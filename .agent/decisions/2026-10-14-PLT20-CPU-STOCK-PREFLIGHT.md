# PLT-20 CPU stock preflight — working contract

**Status:** selected engineering implementation for PLT-20; no provider query or launch authorized.
**Base:** `origin/main` at `42f875c23f391cf11582b655de85dd487cc2c431`.
**Authority:** `.agent/tickets/POD-JOBS-CPU-FLAVORS-01.md`, amended by the Test Lead in `codex-queue/platform.md` and the owner's 2026-10-14 correction to reuse the historical Data Collection path.
**Primary map:** `SYSTEM/DEVELOPMENT-HUB`; `HUB_IMPACT_NONE` because the Hub is retired/frozen and this implementation changes only the existing pod-jobs adapter contract, not orientation, ownership, placement, status, dependencies, or maturity.

## Contract

Keep the current `RunPodAdapter` and `pod_jobs` flow. Add an opt-in ordered `fallback_flavors` field after a primary CPU flavor. Before any CPU create, query stock for the job's exact vCPU and every explicitly accepted flavor using the historical GraphQL `cpuFlavors.specifics(instanceId)` read. Derive the instance ID from the recorded `<flavor>-<vCPU>-<RAM GB>` pattern and its c/g/m multipliers. Preserve request order when forwarding only known-stock choices to the existing REST create.

Interpret only the historical operator-recorded results: `High` is in stock and `null` is out of stock. Ignore response `id` for joining; the requested instance ID is the subject. Unknown, malformed, missing, contradictory, or unrecognized responses fail closed before create. An empty known-stock set refuses before create. These are implementation rules based on the documented operator history, not a claim of current stock.

`securePrice` is deliberately not read or converted. Historical USD/hour rates are not current quotes and do not establish the raw `securePrice` unit. Retain the existing explicit rate ceiling, deadline, cap, owner switch, and provider-side actual-rate check. A job opting into several flavors is responsible for setting its declared ceiling/deadline to cover the slowest accepted flavor; the implementation invents no performance or price values.

After a successful CPU create, read the actual pod's `cpuFlavorId`, record it in the receipt, and refuse to start the workload if the provider does not report one of the stock-accepted flavors. The bootstrap's authenticated `/go` gate must hold the phase even when the job has no uploads; the launcher releases it only after validating the actual flavor. Partial GraphQL data with a non-empty or malformed `errors` field is UNKNOWN. Existing teardown and reconciliation retain control of any resource already created.

The code pin is immutable. Before any provider create, structurally inspect the selected bootstrap and refuse CPU jobs whose pinned code does not implement the authenticated, deadline-bounded gate before phase execution; do not replace or upgrade that pin. After create, wait within the same job deadline until `/status` reports `waiting_for_operator`. Retry `/go` only for transport-unavailable responses because the authenticated marker write is idempotent. Record status-poll and release-attempt counts in the private receipt. These checks do not claim the provider or arbitrary workloads are secure.

## Validation contract

Tests use only deterministic fixture transport and `InMemoryRunPod`; they prove GraphQL request allow-listing/redaction, identifier construction, `High`/`null` handling, unknown-response refusal, order-preserving filtering, pre-create refusal, actual flavor receipt, and teardown on a mismatch. Run the focused pod-jobs and operator RunPod suites plus the repository's required canonical checks. No test accesses a key, account, provider, pod, hidden evidence, or live ledger.

## Maturity and close predicate

Maximum claim: implemented and tested adapter behavior against deterministic public fixtures. No current provider availability/price, host acceptance, scientific equivalence, security qualification, spend, actual placement, or production maturity is claimed. Close only after focused/regression tests, lint/type/preflight, exact-head CI/Merge gate, independent test lead review, and a PR to `main` ready for the named Graphite Testing Manager reviewer. Hub outputs remain untouched for the stated no-impact reason.
