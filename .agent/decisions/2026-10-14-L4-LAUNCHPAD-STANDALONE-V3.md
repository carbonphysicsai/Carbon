# L4-LAUNCHPAD-STANDALONE-V3-01: exact Development subject selector

Date: 2026-10-14. Executor: Platform3. Status: working engineering decision; no scientific, security, serving or spend acceptance.

The ticket's requested Launchpad graph-v3 test cannot be selected by a fresh request today: a numeric `construction_level` hint still binds the combined composition, while the existing Graphite phase-3 `--level 4` route is separate from Launchpad and needs its own host/grant. An old version-0 launch record cannot be fabricated for new work.

Decision: add one optional `construction_variant_digest` field on Launchpad launch. Accept only the already registered battery standalone graph-v3 digest under `agent=graphite` and the existing DEVELOPMENT construction-level capability. A numeric hint does not grant access. Preserve the combined default and version-0/1 replay, and give newly selected launches a version-2 writer capture that binds selector, resolved registered variant, target and canonical digest. Refuse wrong subject, Challenge, agent, arm, conflicting hint, stale registration or changed capture before dispatch. Reuse the existing variant compiler, target-service gate and downstream G0-G5, resource, grant and security controls. No new registry version or active service is introduced.

Rejected alternatives: relabel `construction_level:4` to select standalone (would reinterpret existing requests and violate the descriptive-level rule); fake a historical version-0 capture (would evade writer authority); relax combined required-check health to make the default route appear runnable (would fabricate PASS evidence). Existing direct phase-3 remains a separate possible test and is not modified.

Conflict classification: NO_CONFLICT within a bounded DEVELOPMENT selector. Opening this subject on a production miner/validator route or declaring its checks healthy would require a new owner decision and is excluded. Historical map_ref SYSTEM/DEVELOPMENT-HUB is unchanged; the current OWNER-DX-03 protocol retires Hub maintenance. Notify Test Lead and the combined Validator/Launchpad reviewer through the PR; Root owns CI/merge.
