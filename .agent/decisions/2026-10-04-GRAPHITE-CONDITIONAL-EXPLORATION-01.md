## 2026-10-04 — GRAPHITE-CONDITIONAL-EXPLORATION-01: a finding stops locking, not exploration, and results recorded while it is open are tagged

**Authority.** OWNER-GRAPHITE-TEST-WAVE-03
(`.agent/decisions/2026-10-04-OWNER-GRAPHITE-TEST-WAVE-03.md`, carbonphysicsai/Carbon#574),
item 2. The owner's direction for the wave is "Max freedom, Max scoring
alignment with value, and Minimum attack surfaces". Item 2 states that the
controller's `admission_expansion_after_finding` refusal "is kept for
miner-facing and LOCK paths", and that "For development-variant expansions it
is replaced by the conditional tag". It also states that every result produced
while a finding is open is tagged with the open findings' ids and digests, and
that such a result cannot be cited as unconditional evidence until those
findings are repaired and the affected attacks re-run. Its "Rules as
hypotheses" paragraph makes test-side classification rules registered,
versioned policies with their raw evidence kept, so the Attacker can test them.

Everything below is an engineering choice within that delegated authority.
No scientific value, threshold, gate or score changes. There are no weights,
no chain writes, no live run and no spend. No public MCP tool and no
miner-facing schema changes. This is W2 of the test wave. W1 (the
development-only contract variants) is separate work.

**Decisions.**

1. **The rule is a registered policy, `conditional-evidence.v1`.**
   - **Where.** `carbon/challenge_readiness/conditional_evidence.py`, stdlib
     only, because the contract lane has no numpy.
   - **Shape.** The rules are data (`POLICIES`), in the pattern of
     `carbon.battery.exam.RULES` and Graphite's `FrozenRule` identity. The
     identity (`policy`, `status` `PROVISIONAL_INTERNAL_DEVELOPMENT`,
     `authority`, and the digest of the rules) goes on every tag.
   - **Change control.** A change to the rule is a new version. Results keep
     the identity they were tagged under, and a tag naming an unknown or
     altered identity is refused.

2. **The tag.** A result carries two keys.
   - `conditional_on`: every open finding as `{id, digest}`, sorted by id. The
     digest is the sha256 of the finding body's canonical JSON (sorted keys,
     compact separators), which is the body the controller's `findings` table
     stores.
   - `conditional_policy`: the policy identity.

   An empty `conditional_on` is an unconditional result under the policy. A
   tag never leaves its result. After a repair, unconditional evidence is a
   result produced after the repair.

3. **A separate method and a separate ledger for development expansions.**
   - **The methods.** `CampaignController.record_expansion` is unchanged. It
     is the LOCK path (Track A's `expansions`), and it is still refused after
     any finding. The new `record_development_expansion` takes the same
     arguments and binds the challenge's newest construction record the same
     way. It proceeds while findings are open.
   - **The ledger.** It records into a new `development_expansions` table, as
     `{sequence, recorded_at, kind: "development", profile, version, widened,
     permissions, conditional_on, conditional_policy}`.
   - **Why a separate method.** The LOCK method's signature and behaviour stay
     exactly as they were, and no keyword can turn a LOCK expansion into a
     development one.
   - **Why a separate ledger.** `admission._expansions` keeps its exact
     six-key validation for the LOCK ledger, and `admission._findings` and
     `_lock` are unchanged. `_expansions` now also names the refusal
     `admission_development_expansion_refused` for any entry carrying `kind`
     or a tag. Such an entry was already refused by the exact-key check.
   - **What never sees a development entry.** `admission_ledgers()`,
     `current_profile()` and any LOCK. A LOCK of a development permissions
     digest is `admission_lock_unrecorded_state`.
   - **Running under it.** `launch` accepts a spec under the newest
     development profile (`development_profile()`) as well as under the
     profile in force, so exploration can run there. The controller only
     dispatches Carbon's own campaigns and never a miner.
   - **The miner path.** An invariant
     (`tests/invariants/test_development_ledger_unreachable.py`) shows that
     no file a miner receives, and not the validator, imports the controller
     or names the ledger.

4. **"Open" needs a repair record, which is new.**
   - **Why.** Under the existing semantics nothing ever resolves a finding:
     it is never removed, and `clear_halt` leaves it in place. The owner's
     condition is "repaired and the affected attacks re-run".
   - **The record.** `record_repair(finding_id, operator, note, evidence)` is
     operator-only, like `clear_halt`. It needs a note of at least 20
     characters and the re-run's evidence bytes, which are stored by digest
     and bound to the finding's digest. It is appended to a new append-only
     `finding_states` table and to the hash-chained ledger.
   - **What it changes.** A repaired finding stops tagging later results. It
     stays in the findings ledger, and it still blocks every LOCK-path
     expansion.
   - **Recurrence.** A repaired finding that is recorded again, under the
     same id because its evidence recurred, is open again
     (`finding_recurred`). Without this, the idempotent `_finding` would keep
     a recurred defect silently repaired.
   - **Limit.** The code cannot verify that the attacks were re-run. The
     record is the operator's attestation with its evidence, and this is
     stated in the policy so it can be tested.

5. **Where results get the tag.**
   - **Controller attempt ledger** (`ATTEMPT_SCHEMA` v2).
     - **Tagged automatically** in `_append`: `event`, `artifact` and
       `terminal` entries, which are what an agent run returns. Doing it in
       `_append` means a new caller cannot forget the tag.
     - **Not tagged:** control entries such as launch, usage, cancel and
       findings.
     - **Old stores** keep their v1 entries.
   - **Development expansions** carry the tag in the entry itself.
   - **Climb reports** (`climb.climb(..., open_findings=())`, report v2) and
     **attack family reports** (`report.family_report(..., open_findings=())`,
     report v3).
     - **Always tagged.** Both always carry the keys. These are pure report
       builders, so the caller passes the controller's `open_findings()`.
   - **Graphite phase 3 session result** (`run_session`): tagged with the
     findings open after `sync_findings`, the session's own included, which
     is the conservative choice.
   - **Graphite phase 4 records.** Tagged with the findings open after
     Carbon's side recorded every finding: the coverage report (v5), its
     family report and the iteration-log entry (v3).
   - **Not tagged: permission profiles.** They are inputs, not results. Phase
     4's B2 benchmark is nested in the tagged coverage report, and the
     citation check reads nested values.

6. **One citation check, wired at every site that cites evidence as
   established.**
   - **The check.** `require_unconditional` refuses a value with a non-empty
     `conditional_on` at any depth, with the typed code
     `conditional_evidence_cited_unconditionally`. `require_unconditional_path`
     reads a cited file or every file under a cited directory as JSON, as
     JSON Lines, or (failing both) by searching the bytes for an embedded
     non-empty `conditional_on` list. That catches a tagged record pasted
     into a Markdown status file.
   - **Where it is wired:**
     - the ladder's TESTED and FROZEN level evidence (`ladder.validate`);
     - an ACCEPTED level proposal (`proposals.validate`; `conditional_on` and
       `conditional_policy` are new optional keys, both or neither, so a
       conditional proposal can be filed as PROPOSED but not accepted);
     - every admission report's check evidence, for both tracks and any state
       with a report (`admission._study`; readiness records reach it through
       `admission.validate`);
     - the LOCK itself, which re-checks every piece of evidence it binds
       (`admission._lock`);
     - a pipeline record's frozen run (`state.validate_record`).
   - **Not wired:**
     - the climb harness's own internal stop rule ("a finding stops the
       climb"), which is unchanged;
     - the design-search freeze (`carbon/design_search`) and EV4/EV5
       material, which cite no Graphite result today.

**Tests.**
- `tests/cpu/test_conditional_evidence.py`.
- `tests/cpu/test_conditional_evidence_graphite.py` (phase 3 and phase 4).
- `tests/cpu/test_conditional_evidence_mutations.py`. It has one mutation
  per guard, each shown to fail its guarding test. The citation check is
  disabled once against each of the six sites.
- `tests/invariants/test_development_ledger_unreachable.py`, with a planted
  specimen.
- Existing tests are unchanged except one strengthening:
  `test_graphite_phase3_literature._forbid_widening` also refuses
  `record_development_expansion`.

**Maturity.** Implemented and tested against fixtures. Not scientifically or
security qualified. The tag records attribution; it is not an analysis of
whether a later result actually depends on an earlier defect.

**Open for the Test Lead.** Whether an operator attestation with the re-run's
evidence is enough to release a finding for tagging, or whether a repair
should require a specific re-run record (for example a fresh phase 4 coverage
report naming the finding's family), is a policy question for
`conditional-evidence.v2`. v1 does not decide it.
