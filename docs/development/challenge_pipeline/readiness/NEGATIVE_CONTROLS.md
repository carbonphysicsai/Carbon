# Executable negative controls: PKT-14

DEVELOPMENT engineering evidence only. Validator owns comprehensiveness and
scientific use; Test Lead reviews framing. No physical, security, host, launch
or qualification acceptance follows. The initial delivery/Hub hold was resolved
by the owner's direct 2026-10-13 instruction; current DELIVERY_PROTOCOL applies.

## First slice and scope

The 42-item readiness roster is unchanged. P1, P2 and A4 have public code and
registration inputs. Whenever one runs, the live CHECKS function is invoked
on BOTH the current positive context and a known-bad context:

| Item | Deliberate bad input | Required FAIL reason |
| --- | --- | --- |
| P1 | An unregistered Challenge identity | Challenge not in the registry |
| P2 | Same Challenge with validator adapter removed | No Interface v1 adapter recorded |
| A4 | An identity with no controller designation | No admission controller designated |

This proves those particular properties, not gate comprehensiveness. P1 does
not prove Launchpad reachability. P2 does not qualify physics or prove a real
rebuild. A4 reads a public designation, never a signer, secret or LOCK ledger.

The checker source, control implementation, spec and bad specimen have hashes
in the digest-bound report. There is no cached control receipt. The controls
call the current registry function, so changing it to accept everything must
produce CONTROL_FAILED. Returning FAIL for an unrelated missing dependency
or raising an exception is not detection. Rejecting both signs reports
NO_POSITIVE_WITNESS and earns no controlled pass.

The other 39 items remain UNCONTROLLED in this slice. Missing controls do not
acquire coverage from another family, a review, waiver or successful pytest
process. Host/private checks are NOT run to manufacture coverage.

Native public-code observation on the PKT-14 candidate (2026-10-13, level 0):

| Challenge | Controlled PASS in the three-item subset | Outstanding sampled gap |
| --- | --- | --- |
| battery-fastcharge-ageing-development-v1 | 3/3 | None in this subset |
| electric-motor-magnetics | 2/3 | A4 operator identity still pending |
| chip-cold-plate | 2/3 | A4 operator identity still pending |

These are **not** full readiness counts or canonical acceptance. All three
partial runs return exit 1 and controlled_ready=false. The 39 uninstrumented
items and every physical/noise/host prerequisite remain unearned. No operator
identity is invented or changed to obtain a passing count.

## Prospective report and CLI

Readiness report v2 preserves original `status`, `counts`, `green` and
`launch_ready` as **legacy results**, not proof of controlled readiness. Every
row also carries `controlled_status` and `control` (checked count, both signs,
spec/code/specimen identities and margin/noise metadata). The report's
`control_summary` records checked items, controlled PASS count, uncontrolled
items, failed controls and specimen invocations.

`controlled_ready` requires a full roster, every original item PASS and every
item controlled PASS. A partial report, review-only pass or waiver cannot
make it true. The readiness CLI now exits 0 only for `controlled_ready`;
absent or false is exit 1. Legacy JSON/history is not rewritten or rescored.
The subset count is **not** "Ready Challenge": print its denominator and the
42-item overall requirement beside it.

Public, no-host first-slice check (writes no history):

```sh
python -m carbon.challenge_pipeline readiness --challenge CHALLENGE --only P1,P2,A4 --no-history
```

It deliberately returns exit 1 even if all three pass: 3/3 checked is not
42/42. Operator launch permission remains a separate decision.

## Margin beside noise

Structural registration checks have no scalar physical margin or calibrated
noise unit. They report min/p01/noise as null, explicitly
NONSCALAR_STRUCTURAL_CHECK, with definition owner Carbon Validator. Null is
not zero noise, and these controls do not qualify a physical measurement.

The Python `run_gate(public_measurements={ITEM: ...})` seam accepts aggregate
diagnostics only, with scope PUBLIC_DEVELOPMENT or SYNTHETIC_FIXTURE, finite
`margins`, `unit`, source binding, and optional same-unit `noise_estimate`,
`noise_unit`, `noise_source_digest`. It reads no measurement file or producer
path. Real returned measurements require authorized public provenance and
the domain owner's definition; a declared scope/hash is not such approval.
Source digests must have the canonical SHA-256 shape. A synthetic numerical
measurement cannot make the full controlled_ready flag true. Control kinds
are explicit: future NUMERICAL controls with no measurement stay HUMAN_INPUT,
never inherit the structural no-scalar exemption.

Minimum and linearly interpolated empirical p01 are reported together with
the supplied noise estimate. Missing noise is HUMAN_INPUT, not a noise-free
pass. Minimum at or below supplied noise reports WITHIN_NOISE and contributes
zero controlled passes. ABOVE_NOISE describes arithmetic, not adequacy or
qualification. No alpha, confidence rule, scientific tolerance, sample-size
floor or production threshold is selected by this ticket.

All retained numerical examples are synthetic; no hidden/tuning/plating
panel or Score Lab holdout is opened. Numerical controls for S3/H4 and the
remaining roster are missing work, not implied by this engineering slice.

## Acceptance

Tests deliberately replace the checker with always-pass, always-fail,
wrong-reason and raising versions and demand refusal of controlled readiness.
Tests also run the real P1/P2/A4 checker code, explicitly naming any metadata
substitution as a fixture. Margin/noise tests change noise so the controlled
count changes, and assert missing/invalid metadata stays closed.
Native diagnostics are not canonical acceptance. Use the canonical wrapper
or pinned GitHub CI; no paid/reference/host execution is authorized here.
