# POD-CREATE-REFUSAL-NAMED-01 — a refused pod create names what the provider said

**Status:** open. **Owner:** Test Engineer (operator layer), with Data Collection (pod jobs). **Reviewer:** Graphite Testing Manager.
**Authority:** Test Lead, 2026-10-13. Same defect class as the three mute refusals fixed in #1290 (miner door, `composition_graphs`, `proposal_arguments_malformed`): a refusal that leaves the reader nothing to act on.

## Why

When an ambiguous create is retried and both attempts fail, `ComputeService._reconcile_then_resend_once` raises `ambiguous create twice; stopped, no third create` built by its local `stop()`, which carries no HTTP status and no provider message; the first attempt's `ComputeError.http_status` is dropped. On 2026-10-13 three pod jobs (16- and 32-vCPU `cpu5m`) ended this way and the cause (capacity, an invalid size, or something else) could not be confirmed from the refusal. `pod_jobs` already appends the HTTP status when the layer provides one (#1250); here it does not.

## Scope

- Every refusal the operator layer raises after a provider call carries the provider's HTTP status and a bounded, sanitised provider message (no key, no account data), for both create attempts, in order.
- The pod-job receipt and Graphite's ledger record them (`pods.bounded_detail`).
- A test per path: first create 5xx then resend 5xx; first create timeout then resend 4xx; reconcile failure.

## Not in scope

Retry policy and the number of creates (unchanged: one reconcile-gated resend, never a third).
