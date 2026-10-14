# PLT-36 controlled environment probe: preparation, not launch approval

The reported baseline (78,076 characters) created; different proposals at
84,501 and 86,408 had ambiguous creates. These are attributed host observations,
not a controlled size bracket or proof of an exact provider ceiling. Capacity,
content and transient causes remain possible. No padded probe ran in this lane.
Current owner-approved `pod_env.ENV_LIMIT_CHARS` remains unchanged at 108,000.

`scripts.dev.graphite_env_probe` prepares a spec through the existing
`RunPodPods.pod_spec` using preflight's fixed sleep command, adds one unused
`CARBON_ENV_PROBE_PADDING` variable, and rechecks the current runtime guard.
The original base cannot be trimmed to hit a target. All other fields remain
unchanged. It exposes Python preparation/measurement functions only; it has
no provisioning CLI, usable credential provider or transport. It does not
wire the old spending preflight directly into a multi-probe campaign.

`request_metrics(spec, ownership_tag)` returns numeric counts only: original
spec environment characters/UTF8 bytes, transport environment characters/UTF8
bytes, environment JSON bytes and full request body bytes. The transport
metrics include the adapter-injected ownership tag, name, image, ports,
resources, CUDA selection and sleep command. They use the current actual
`RunPodAdapter.create_body` and `_send` serializer (`json.dumps(body).encode()`),
including default spacing and ASCII escaping. A compact JSON estimate is
incorrect. The target is in the existing runtime guard's spec units; actual
transport counts are reported separately. No values, tokens, raw body or
hashes of private inputs are written to the report.

The synthetic tests compare those byte counts against bytes passed to the
actual adapter transport, change a non-environment field, vary quote/backslash
and Unicode padding at equal character counts, and lower the guard so padding
fails even though the base still fits. None is a provider-size measurement.

The proposed first host tranche is at most **four sequential creates**,
concurrency one, with no resend or automatic retry. Freeze one pushed source
revision, immutable image, public minimal probe job/record, GPU/count/cloud,
disk/ports/CUDA set and request fields. Use unique equal-length ownership tags
and intent identities and record any unavoidable changing field. Do not
reconstruct private proposal directories, tokens or seeds.

1. Prepare one ASCII-padding control targeting 78,076 characters. If the
   frozen base cannot fit, stop preparation. If the control fails, the expected
   baseline has not reproduced; no size threshold or capacity cause is proved.
2. Prepare the same-content control at 84,501. An opaque or timed-out create
   remains ambiguous; stop the tranche immediately and reconcile ownership.
   If it succeeds, the historical failure has not reproduced.
3. At most two remaining observations may refine a bracket after classified,
   nonambiguous outcomes and explicit operator stop/go. Boundary repeats or
   equal-character encoding contrasts consume this allowance or require a
   separately bounded tranche; they are not free additional probes.
4. Before the next create, require verified cleanup and resolved accounting
   from the previous one. Stop on first ambiguity, uncertain cleanup, missing
   stock/offer, or any preflight/accounting refusal. Never infer noncreation,
   deletion or zero charges from timeout, elapsed grace or an empty listing.

Record source/image/profile/R8 identity, UTC observation time, target and all
measured units, actual create outcome/closed cause/status, answer duration,
resource identity in the private recovery record, running result, teardown
and reconcile evidence, and final accounting state. Public tables carry only
allow-listed numeric sizes/outcomes and public artifact identities. A finite
accepted/rejected bracket is conditional on that fixed configuration and time;
an exact universal platform threshold is not established by one failure.

Execution is **HOST_BOUND / NOT READY** until the authorized operator supplies:

- Exact accepted source/image/public probe manifest and applicable hostile R8
  result. Source changes require the existing lane image acceptance process.
- Finite create, running, reconcile, terminate/list and independent cleanup
  bounds, plus deletion after controller interruption. Existing preflight uses
  a 60-second create timeout, 600-second running/deadline allowance, sleep 900
  and 180-second gone polling. Sleep exit and request deadline are not verified
  independent deletion, and missing reconcile/cleanup maxima remain unresolved.
- A dedicated recorded grant with claim/receipt/settlement integration, finite
  attempts and total billable worst case. The old preflight arithmetic alone
  neither claims a probe allowance nor connects the grant to provider billing.
- Approved rate ceiling, acceptable current stock/offer and actual weekly/account
  reservation headroom, then the concrete worst-case figure through the owner's
  existing spend authority. No figure or grant is created by this preparation.

Reserve each allowed attempt from the full maximum billable duration and
approved rate plus storage, with cleanup reserve at the scope prescribed by
the existing accounting contract. Retain holds for ambiguous/unresolved work.
Do not assume the queue's “USD 0.01 class” prose approves any spend.

After controlled host observations, Root/Validator/owner decide the applicable
unit, ceiling, margin and exact prospective guard amendment. No bound is
automatically derived here. PLT-34 closure trimming and Platform's structural
PLT-29 continue under their own scopes and shared-file serialization. No L4
Constructor/Attacker launch, science, security or deployment acceptance follows
from this tooling or its CPU tests.
