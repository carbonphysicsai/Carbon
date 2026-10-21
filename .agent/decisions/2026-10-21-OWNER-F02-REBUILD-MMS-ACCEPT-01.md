# OWNER-F02-REBUILD-MMS-ACCEPT-01: code verification accepted for the rebuilt F02 Elmer image

Date: 2026-10-21
**Status: ACCEPTED by the owner.** The owner said "accepted" directly in the Data Collection session on 2026-10-21. They were answering the question of whether to accept the rebuilt image's MMS result. Code verification is a science acceptance reserved to the owner. This record takes effect when the PR Head merges it, confirming it with the owner as for OWNER-CODE-VERIFICATION-ACCEPT-01.

**Why it is needed.** OWNER-CODE-VERIFICATION-ACCEPT-01: "A rebuild or re-pin needs a new run and a new acceptance." RR-04's F02 image (`sha256:61be1cb77c51fcdd822250e372754a9ce728a5bb42f39b7ba03cdf5e70901add`) is lost on every host.

## Accepted

The image is the 2026-10-21 rebuild of the locked Elmer package, `sha256:fe8a5b1abebf56bbd9cd1aae2ee08f1825b2991abc0bb14b5be3fae26e6512ec`. The test is OWNER-CODE-VERIFICATION-ACCEPT-01's manufactured transient-heat test: hex808, BDF2, T = 1 + sin(pi x) sin(pi y) sin(pi z) cos(2 pi t), registered end time t_end = 0.375. The expected order is 2, and the band is [1.7, 2.3].

| Direction | Pair | Max | RMS |
|---|---|---|---|
| Space | 8 → 16 | 1.991 | 1.867 |
| Space | 16 → 32 | 1.977 | 1.913 |
| Time | 1/8 → 1/16 | 1.787 | 1.787 |
| Time | 1/16 → 1/32 | 2.118 | 2.118 |

The finest pairs are inside the band. Evidence: `docs/development/evidence/f02-rebuild-20261021/mms-evidence.json`, cited by digest in `rebuild-record.json`.

**Related, not decided here:** the Validator's A5 lineage ruling and the re-pin, both 2026-10-21. Every one of the 48 cases' solved outputs equals RR-04's (difference 0.0), recorded in the same `rebuild-record.json`.

## Scope

This record accepts code verification of the discretisation only. It is not reference adequacy, physical validity or qualification.
