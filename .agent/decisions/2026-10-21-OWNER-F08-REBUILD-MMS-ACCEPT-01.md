# OWNER-F08-REBUILD-MMS-ACCEPT-01: code verification accepted for the rebuilt F08 CalculiX build

Date: 2026-10-21
**Status: ACCEPTED by the owner.** The owner said "accept F08 rebuild" directly in the Test Lead's session on 2026-10-21. The Carbon Validator relayed it to Data Collection, who records it here. Code verification is a science acceptance reserved to the owner. This record takes effect when the PR Head merges it, confirming it with the owner as for OWNER-CODE-VERIFICATION-ACCEPT-01.

**Why it is needed.** Under OWNER-CODE-VERIFICATION-ACCEPT-01, a rebuild or re-pin needs a new run and a new acceptance. RR-PACKS-07's native build (solvers_id `sha256:6098f39d40d642ab7aaa3fc300a44ff866e330db52b8d8b1bd9ee9709b0098c3`) is lost on every host.

## Accepted

The accepted build is the 2026-10-21 AX42 rebuild of RR-PACKS-07b's recorded setup: ccx 2.23 with SPOOLES and gmsh 4.15.2, in the pinned Debian trixie snapshot.

| Item | Value |
|---|---|
| Image | `sha256:22a7902fcd32a3bc454e7617e775b1be39e77e4826f6fc1ddd43ad534378539d` |
| solvers_id | `sha256:adcdd02bcb9a906046d8276f797f2c7f2c79bcc8745546cd35407a70bebd86a2` |
| ccx | `cdd00603c70dae940e6c48ab64c4776daa429c360ca515f257cc173bcfa0c9cd` |
| gmsh | `aebfb5b25decf2260acbce3c3de592a7e1231ee2089b8432f13e2fa10e05a9e5` |
| Rebuild record | `docs/development/evidence/f08-rebuild-20261021/rebuild-record.json`, sha256 `3619445b67a6985cd82bf2f75fa31e3d2343cc04ffe04773db96d348ebf9133a` |

RR-07's `f08_verify` was run in that build behind the repository's docker shim, as RR-07 ran it:
- **MMS:** PASS, observed order H1 2.056, L2 3.133.
- **Closed-form axial rod:** PASS, frequencies within 2.4e-7 relative, static within 1.6e-7.

**Related, not decided here.** The Validator's re-pin criteria, 2026-10-21, are met. The lineage is complete: all 8 ladder geometries were solved at h = 3, 2.25 and 1.7 mm. Every compared output (worst dynamic, static, and the three damping peaks) is bit-identical to RR-PACKS-07's committed `ladder-observed.json`, with max |diff| 0.0 and no label changes.

## Scope

This record accepts code verification of the discretisation only. It is not reference adequacy, physical validity or qualification.
