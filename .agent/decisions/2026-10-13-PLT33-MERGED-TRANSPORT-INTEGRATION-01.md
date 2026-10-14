# PLT33-D2: integrate the registered cap and anchored upload

Authority: Test Lead's bounded PLT-33/#1320 integration assignment after
PLT-29 merged as 8dc35eb30ca090e25c44b9038825dd8fbd32c753, and the existing
OWNER-POD-ENV-LIMIT-RAISE-01 decision. D1 describes the earlier inline recipe
at its original 90,000 cap; it remains historical evidence.

KEEP the runtime's registered ENV_LIMIT_CHARS (currently 108,000), the strict
8,000 CI reserve, the real environment builder and full declared L4 transport
budget. Derive boundary fixtures from the actual registered cap; do not change
the runtime limit or choose a margin from unmeasured provider behavior.

REPAIR frozen-recipe accounting for the actual upload. Report schema v2 adds
manifest_env_chars, counting all manifest environment names and values,
including request-anchor metadata. Legacy manifest_carrier_chars and
manifest_compressed_bytes retain their payload-only meaning; absence of an
inline payload is not zero total transport cost. Include both upload helpers
in the factory fingerprint, and refuse comparisons with different schemas,
runtime/CI limits, reserve, jobs or source recipes.

Use one current recipe at both public source refs, including the existing
#991 comparison. This does not reconstruct deployed environments, remeasure
the provider ceiling or infer a new growth margin. Authentication, owned bytes,
file pins, no-phase-before-anchor, CUDA, accounting and provider dispatch are
untouched. Historical reports are not rewritten. Maturity is offline
DEVELOPMENT tooling/testing only; host/R8/grant/launch acceptance remains
separate. Primary historical map_ref WAVE-C/C-03; Hub retired under OWNER-DX-03.
