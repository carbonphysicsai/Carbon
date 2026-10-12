## 2026-10-12 — BATTERY-V4-OUTPUTS-PROPOSAL-01-D2: guarded v3 compatibility and deliberate helper re-pin

Owner direction, 2026-10-12: apply Carbon Validator's review in PR #1190,
including the golden test, two refusal-only guards, an exact producer helper
re-pin and lessons row N4. Source: #1190 comment 6128934517.

The prospective explicit solve-v4 route remains in truth_env.py. Existing
v3 callers retain their exact default command and serialized records; the
new guards refuse only jobs declaring the v4 jobs schema or records declaring
the v4 record schema (also when the sidecar is missing). The existing sidecar
refusal is retained. Refusal precedes record creation, append or service start.

The regression predicate is the same literal golden test passing canonically
against main's pre-v4 helper and the candidate helper, plus both refusal tests.
The golden uses the actual truth service with a fake solver, fixed provenance
and deterministic fixture worker/time/resource measurements. It compares the
complete command list and literal success/failure record bytes, with no new
top-level schema. Exact record-byte equality also preserves record digests.

Only after that predicate passes, update the producer's exact truth_env.py
digest. The old digest is
84f10dce1bf14e2cab2b1f7012342e6e84ce8a4c12de45ba76a1a689d8cf8862.
The new exact digest is
5673d992c7b3095f56343c28836560e19a1f5d17776664ac07b90ee9e25e52e2.
The HELPER_PIN_MISMATCH check, other helper pins, registered entrypoints,
solver image/overlay and pinned domain/recipe/training modules stay intact.
The release note in the output-contract proposal lists the re-pinned helper;
the PR body carries the golden comparison evidence and new exact digest.

The Validator's merge-timing condition goes to PR Head: if CONFIRM-02's solve
uses a checkout of main rather than a pinned tag/commit, merge after that solve
starts. This Platform session neither merges nor releases. The output proposal
still grants no scientific adoption, qualification, production or LIVE authority.
