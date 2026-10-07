# OPERATOR CPU placement working decision

Ticket: OPERATOR-CPU-PREFLIGHT-01. Recommendation: KEEP.

The existing generic operator adapter sends CPU mode without flavor or vCPU
count, so it cannot represent the approved cpu5c/16-vCPU route. Add an immutable
`CPUPlacement` in operator_compute/model.py; `PodSpec` requires it for CPU and
refuses it for GPU. The Runpod adapter sends exactly one flavor, custom
priority and the pinned vCPU count. No availability fallback is represented.

Absent CPU fields are omitted from GPU canonicalization so existing GPU intent
digests remain unchanged. Earlier ambiguous CPU intents retain their stored
identity/custody and can be reconciled/terminated; new implicit CPU requests
are refused rather than replayed with an invented placement.

Reuse the known pod_control.py payload and current Runpod REST v1 schema:
[Pod creation](https://docs.runpod.io/api-reference/pods/POST/pods) and
[OpenAPI](https://rest.runpod.io/v1/openapi.json), inspected 2026-10-06.
Neither documentation nor fake-provider tests establishes live allocation.

Rejected: assuming CPU mode pins 16 vCPUs, allowing a flavor fallback, putting
family grants into the shared provider model, and changing the active evaluator
or image-release lane. This is reversible additive operator preparation.
To supersede, change CPUPlacement/PodSpec canonicalization, adapter create_body
and their tests prospectively; retain stored intent digests. No scientific,
security, qualification or spend authority is conferred. Coordination:
issue #643 comment 6029142884; routine lead notification is non-blocking.
