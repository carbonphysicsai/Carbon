# C1 protected-execution review package

**Commissioning decision:** `OWNER-C1-BURGERS-ALPHA-01`
**Package state:** engineering scope prepared; reviewer identity and independent
acceptance are `UNAVAILABLE`
**Admission state:** protected execution disabled

## Exact review target

The eventual review target is one immutable source tree, Carbon wheel, worker
image/config digest, controller and validation-process implementation, exact
`carbon.c03.linux-x86_64-cpu.development.v1` policy, inference/reference
images or processes, archive/custody adapters and deployment manifest on one
named Carbon-controlled single-tenant Linux x86-64 CPU host. A changed target
requires a new package identity and disposition of affected findings.

The accepted PR #149 image
`sha256:dae4717ae00d3174b8644159934eb4edbe94c0ad125549f6ade570a6f4c7e630`
is historical DEVELOPMENT evidence, not automatically the eventual protected
review target.

## Trust model and data flow

Trusted: named Carbon host administrators, kernel, Docker daemon/runtime,
image-build path, Carbon supervisor and external custody/signing owners.
Untrusted at parsing/association: declarative plans, TRAIN archives,
checkpoints, numerical worker behavior, messages and artifact proposals.
Host-root confidentiality, malicious administrators, third-party validator
custody, cross-tenancy, kernel/runtime zero-days, supply-chain compromise,
side channels, physical attack, GPUs and distributed execution are exclusions.

```text
verified plan + public/approved TRAIN + replica DerivedSeed
  -> immutable reconstruction input -> isolated training worker
  -> provisional capped artifact -> isolated bounded validator -> frozen artifact
  -> candidate query only -> bounded inference

separate protected case authority -> reference primary + witness
  -> immutable reference outcomes -> measurement boundary

supervisor only -> receipt/signature/archive journal and public/private projection
```

Training receives no EVAL/STRESS cases, reference values, master entropy,
signing/storage/chain credentials or scoring internals. Inference receives only
the validated frozen artifact and exact candidate query. Reference/measurement
receives no mutable training state or candidate-writable reference assets.
Numerical workers receive no Docker socket or archive/signing credentials.

## Required assessment questions

The independent assessment must inspect and exercise:

1. exact data flows, positive permitted-input schemas and absence of protected
   values from reconstruction/inference;
2. effective Docker/cgroup/namespaces/capabilities/seccomp/LSM/filesystem/
   network controls and their downgrade behavior;
3. every untrusted JSON/ZIP/NPZ/checkpoint/artifact parser, including streaming
   caps, expansion/member limits and native parser process limits;
4. supervisor CPU/memory/PID/scratch/output/log/deadline enforcement and honest
   OOM/resource cause attribution;
5. caller/supervisor/host restart, cancellation, descendant termination,
   create-response loss, deadline preservation, cleanup uncertainty and slot
   quarantine;
6. exact replay, cross-attempt/policy/environment rejection and prevention of
   retry/repeat/budget laundering;
7. reconstruction, frozen inference, reference, measurement, receipt, signing,
   archive and public projection authority separation;
8. errors, logs, timings, artifacts and public/private disclosure surfaces;
9. single-tenant trusted-host limitations, especially the inability of this
   profile alone to protect hidden exams on independently administered hosts;
10. dependency/image provenance, build credentials, final notices and the
    deployment/custody manifest.

Every finding must identify origin, severity, exact affected target, evidence,
recommended repair, repair revision and retest result. Automated findings are
labeled automated. Only a real authorized independent reviewer/domain owner may
provide the separately required independent acceptance.

## Existing DEVELOPMENT evidence offered to the reviewer

- PR #149 exact tested head/run/merge and image manifest;
- C-03 service traces for lab FNO, Foundax 512, create-loss continuation,
  resource denial, network canary, blocked operation and descendants;
- controller/staging/protocol/store tests for identity, replay, malformed input,
  bounded export, late writes, cleanup and quarantine;
- this continuation's bounded Docker response capture, non-retryable terminal
  cause retention, same-boot monotonic deadline and resource-bounded native
  artifact validation evidence; and
- the source-use manifest and exact open boundaries above.

## Missing independent-review inputs

| Missing item | Owner | Effect while absent |
|---|---|---|
| Authorized independent reviewer identity and engagement authority | Security/domain owner | No independent assessment starts; package remains ready |
| Exact final protected image/controller/inference/reference/archive deployment manifest | Engineering + operations | Review target cannot be frozen |
| Reviewer findings and confirmed-fix retest record | Independent reviewer + engineering | Protected admission remains disabled |
| Security-owner acceptance for the exact target and trust assumptions | Security owner | `SECURITY_QUALIFIED` remains false |

No purchase, outbound reviewer message, credential request or claimed approval
is made by this package.
