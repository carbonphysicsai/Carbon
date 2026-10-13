# PLT-29: pinned code manifest outside the environment

Platform queue structural prerequisite, reviewer Carbon Validator. Starting
main `29fa548c45ad7fe7cf71d871c0c1bddc400497e8`. One PR to main; no builder
merge, release, deployment, provider request, host acceptance or spend.
Initial open-PR scan: no overlap on proposed code paths. After #1321 merged as
704f0fc1880e131e499aa96ce7ffd1e1b1fa4d4f, its size-test fixture was free to
repair. Late open #1334 overlaps pods.py and #1324 overlaps phase3's test;
those publication seams remain held for Test Lead serialization.

Authority: current constitution/invariants/WAVE, delivery/delegated protocol,
Build Out/overlay, Code Authority, Graphite grant/transport and shared bootstrap
contracts; queue PLT-29's delegated structural decision. Hub retired; primary
historical map_ref WAVE-C/C-03. Never change the environment bound or reserve.
The owner override in #1321 is that PR's work, not inferred authority here.

KEEP the shipped file set, every SHA-256, image/overlay pins, frozen request
identity, source-only bootstrap, deadline/cancellation, ownership, authentication
and typed infrastructure failures. REPAIR only delivery. New creates bind the
exact public manifest bytes by SHA-256 and byte count in fixed-size environment
fields. Deliver the bytes through the existing pod's token-authenticated HTTP
server, before the bootstrap fetches or executes code. Verify the request's
anchor first, then retain each file's existing SHA-256 check. No external
artifact host, credential or new spend is needed by this software mechanism.

Prospective transport identity: new private job records select anchored upload;
old records retain their legacy environment encoding without rewrite. Legacy
operator/A40 bootstrap callers remain supported. Missing, wrong, oversized or
altered manifests stay fail closed, with a named anchor/field refusal. Model
inputs, overlays, phase config and receipt identity are not relaxed.

Plan: canonical baseline; helpers and authenticated receiver/wait/upload;
100-path environment-growth control (<200 characters), post-create tamper and
no-code-before-anchor controls; source-only/A40/transport regressions, pinned
formatting, canonical hygiene, exact-head CI and ready handoff. Report actual
before/after fixture size and distinguish local tests from host acceptance.
Manifest: this ticket; carbon/agent_campaign/graphite/pods.py;
scripts/dev/exam_design/runpod/{pod_control.py,bootstrap.py};
tests/cpu/test_graphite_manifest_upload.py;
tests/cpu/test_graphite_phase3.py (exact create-anchor migration assertion);
tests/cpu/test_graphite_pod_env_size.py (oversized-phase fixture only);
docs/development/graphite/PINNED_MANIFEST_TRANSPORT.md.
Maturity ceiling: implemented/tested DEVELOPMENT transport. No isolation,
security, physical validity, deployment or LIVE qualification is earned.
