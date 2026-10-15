# V8_8-REGISTERED-SCORE-PAYLOAD-01

Root's bounded 2026-10-15 continuation of V8_8-VALIDATOR-SETUP-01 repairs
the actual R5 startup refusal after rollback. The active registry-v5 public
bytes are absent from the verified runtime bundle. No state, score term,
registry values, decision authority, private material or failed receipt changes.

Starting main: 27f74451eacc346e323f1ff2d5f86a8b12407187. Accepted failed
artifact source: 22fc5a8d1b56752faf9541292b8d4b4b1e355142. No open PR
overlaps the selected source/test paths at ticket start. Root alone owns
merge, build, publication, host acceptance and OPERATOR/TEST transitions.

## Contract and working decision

KEEP registered candidate parsing, owner-decision lookup, exact configured
registry SHA and all scoring mathematics. REPAIR the public payload closure
with the exact adopted registry-v5 file, not the surrounding evidence tree.
Its required digest is
70f2943814db0531429613e6ca5e2bd1c0b656673c6ee74de08e98f540758277.
Platform3's disjoint exact-source audit confirms the other construction-time
assets are owner decisions and the EV4 contract, already in the allowlist;
registry parsing has no nested file references. All payload stays manifest-bound.

A materialized release intentionally has no Git history. Its score loader
must verify the complete immutable bundle against an external expected
manifest digest and bind the registry to that manifest's committed source
revision. Never infer trust from a self-hashed manifest or silently disable
the research loader's existing clean-Git registration requirement. Retain
registry/candidate/owner-decision mismatches as typed refusals. The operator
entrypoint passes its already verified bundle identity to child processes.

Read-only service preflight must initialize the configured registered score
metadata using the same loader as daemon startup, without scoring, solving,
reference-case reads, state writes or provider access. No score term means
that check is explicitly not applicable. Fail closed with public reason codes.

## Plan and acceptance

1. Narrow bundle payload and external provenance propagation.
2. Bundle-aware registered score metadata initialization; unchanged Git mode.
3. Preflight check and public materialized-bundle regressions using the real
   adopted registry/candidate and decision, plus absence/tamper/unbound and
   metadata-readiness refusal controls. Verify no solver/scoring invocation.
4. Static source/hygiene checks only locally under OPERATOR; focused and
   subsystem acceptance runs remotely through normal CI. No local baseline
   or tests are authorized in this window. Packets2 reviews the complete diff.
5. One main-based PR; fix concrete review/CI findings on that PR and hand
   Root the exact head and actual check results. No worker merge or image build.

Current authority: CONSTITUTION, INVARIANTS, WAVE and domain scoring/owner
adoption records; OWNER-DX-03 retires Hub/receipt ceremony. Hub impact: none.
Maturity ceiling: DEVELOPMENT packaging and metadata readiness; no scientific,
security, network, LIVE, release or installed-artifact qualification earned.

## Candidate validation

Local static AST parsing of all six Python files passed. Repository-pinned
Black 26.5.1/py310 and Ruff 0.16.3 passed on those files; delivery hygiene
against the starting main and diff whitespace checks passed. No local tests
or runtime were executed under OPERATOR. Canonical test evidence remains
pending the new PR's CI; earlier R5 checks do not validate this repair.

Focused regression scope for canonical CI: test_validator_setup_registered_score,
test_validator_setup_bundle, test_validator_setup_entrypoint,
test_validator_registered_score and test_battery_validator_service. The default
canonical CPU suite also discovers these paths; no workflow/check weakening.

Packets2's complete-diff review of 84b84e411 found one compatibility defect:
host-style generated systemd units lost the transient external bundle pin.
The bounded repair passes the verified digest explicitly to unit generation
and emits it in both units, with malformed-pin refusal before config access.
The fresh-process regression checks both generated pins, exercises the actual
later preflight command using only that binding, and contrasts refusal without
the pin. No systemd installation/start or local test is performed.
