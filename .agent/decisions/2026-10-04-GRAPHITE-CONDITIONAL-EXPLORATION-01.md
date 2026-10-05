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
`conditional-evidence.v2`. v1 does not decide it. (Decided for v2 by the
amendment below: `repair-attestation.v1`, with the verified re-run as its v2
target.)

### Amendment 2026-10-05: conditional-evidence.v2 and repair-attestation.v1

**Authority.** The Test Lead's review of carbonphysicsai/Carbon#577 set
follow-up items for W2, and the owner approved the wave. Items 2 and 6 of
that review were built in GRAPHITE-DEV-VARIANTS-01. This amendment builds the
remaining items, numbered 1-5 below as the wave brief numbers them. They are
engineering choices within that delegated authority. No scientific value,
threshold, gate or score changes. There are no weights, chain writes, live
runs or spend, and no public MCP tool or miner-facing schema changes.

**Versioning.** The rule text changed, so this is a new version,
`conditional-evidence.v2`, which is now the current one.
`conditional-evidence.v1` stays registered and unchanged, so a result tagged
under it keeps a valid identity. `repair-attestation.v1` is a separate
registered policy. v2 records its name and digest (`repair_attestation`), so
a change to either one is also a new version of v2.

1. **A finding's own evidence is not conditional on itself.**
   - **Choice.** The citation check applies only to claims that rely on the
     result: `RELIANCE` = PASS, ACCEPTED, TESTED, FROZEN, LOCK
     (`conditional_evidence.relies`). Admission report evidence is checked
     only for a PASS check. FAIL, INCONCLUSIVE and NOT_RUN checks may cite a
     conditional result. A finding's own evidence was already never checked.
   - **Why not exclude a result's own findings from its tag.** That would
     let the report that found F back a PASS as if F did not exist, although
     everything else in it was produced while F was open. It would still
     leave a report that is conditional on other open findings unable to back
     its FAIL. It would also contradict the phase 3 choice of tagging a
     session with its own findings. The direction of the claim is what
     matters: a FAIL that cites conditional evidence can only block, never
     advance.
   - **Changed W2 test.** W2's test asserted that a FAILED report whose checks
     all FAIL could not cite a tagged result. Item 1 removes exactly that
     behaviour. The test now asserts the refusal for a FAILED report with a
     PASS check, and the new tests assert that the FAIL case passes.

2. **Tag detection consults the controller's ledger.**
   - **The ledger.** `ConditionalLedger` holds every evidence and artifact
     digest that a controller attempt-ledger entry recorded while that entry
     carried a non-empty `conditional_on` (or `repaired_by_attestation`),
     with those findings. A digest recorded both ways is conditional (the
     union is kept). `CampaignController.conditional_ledger()` builds it, and
     `ConditionalLedger.load(store)` reads a controller store read-only.
   - **Where it is consulted.** Every citation check takes `ledgers=`:
     `admission.validate`, `ladder.validate`, `state.validate_record` and
     `load_state`. `CampaignController.check_lock` passes its own ledger.
     `python -m carbon.challenge_pipeline validate --conditional-ledger STORE`
     passes any controller store the operator names. Without a ledger, the
     repository validators still check bytes only.
   - **Bytes.** The byte check also reads gzip, bzip2, xz and zip copies.
     Reading is bounded and nested at most three deep, and an unreadable copy
     is refused. It also reads YAML- or TOML-style keys and Python-style
     dicts in text.
   - **Limit.** A copy made outside the controller, which its ledger never
     recorded, and whose bytes drop the tag cannot be detected by digest.
     Only its bytes speak for it.

3. **No result is written untagged while a finding is open.**
   - **Phase 3.** The experiment calls `on_finding` once a finding is
     durable, and `Phase3Provider.bind_findings(control)` records it on the
     controller at that point, so a next-level proposal written after it
     carries it. `run_session` now records the session's findings
     (`sync_findings`) before `poll` ingests its events and artifacts, which
     covers a run that another process ran.
   - **Next-level proposals.** A proposal written with a controller bound is
     `carbon.graphite.next-level-proposal.v2`: v1 plus the controller's tag
     as of when it was first written. A writer with no controller bound
     writes v1 as before. A level proposal transcribed from a v2 proposal
     carries the tag, and it cannot be ACCEPTED while the tag lists a finding.
   - **Controller.** A canary finding is recorded before the event or
     artifact entry that exposed it (`_result_entry`), so that entry carries
     it. The stored evidence bytes cannot carry a tag without changing their
     digest. Their ledger entry is their tag of record (item 2).
   - **Phase 4.** The family report is re-tagged (`retag`) after the findings
     it raises and the baseline's findings are recorded, as the coverage
     report already was.

4. **Repair attestation, `repair-attestation.v1`, with the v1 conditions.**
   1. It is registered as a versioned policy and recorded in
      `conditional-evidence.v2` (`repair_attestation`: name and digest).
   2. `record_repair` requires `rerun` (at least one re-run attempt id or
      report digest, each once), `code_ref` (the 40-hex commit the re-run ran
      at) and the operator, besides the note and the evidence bytes. An empty
      or malformed field is refused (`repair_rerun_identities_required`,
      `repair_code_ref_required`, `operator_required`). The code checks their
      form only.
   3. A repaired finding never unblocks LOCK, miner-opening or frozen runs.
      It stays in the findings ledger and still refuses every LOCK-path
      expansion. A result carrying `repaired_by_attestation` is refused
      (`conditional_evidence_attested_repair_at_lock`) at the LOCK, at FROZEN
      level evidence (the level miners get) and at a pipeline record's frozen
      run, whether its bytes or the ledger say so. TESTED evidence, a Track B
      review and an ACCEPTED level proposal may cite it.
   4. Results recorded while a finding's latest state is an attested repair
      carry `repaired_by_attestation`, the sorted repair ids. A repair id is
      `repair-<16 hex>`, from the digest of the repair record without its id.
      The key appears only when the list is non-empty, so a result with no
      attested repair has v1's tag shape. A recurrence reopens the finding
      and drops its repair from the list.
   5. **The v2 target.** Verify the re-run from the ledger instead of
      attesting it: for each family the finding affects, an attempt recorded
      after the repair time, at a code ref that contains the fix.

5. **Attempt-ledger schema by kind.** Control entries keep
   `carbon.agent-campaign.attempt.v1` with their keys unchanged. Result
   entries (`event`, `artifact`, `terminal`) are v2: v1 plus the tag, whose
   keys the named policy defines. This is the safer choice for replay. A
   replay of a v1 store's control entries reads the same bytes and schema as
   before, and each entry's schema names exactly the keys it has. A store
   mixes v1 and v2 entries by kind. Stores written by #577's branch, where
   every entry was v2, are development-only and are not migrated.

**Tests.**
- `tests/cpu/test_conditional_evidence_followup.py` covers items 1-5, with one
  mutation per guard shown to fail its test.
- `tests/cpu/test_conditional_evidence_graphite.py` covers the phase 3 and
  phase 4 ordering, with their mutations.
- W2's tests are updated for v2: the policy identity, `record_repair`'s new
  required identities, and item 1's changed FAIL behaviour.

**Maturity.** Implemented and tested against fixtures. Not scientifically or
security qualified. The ledger check covers what a controller recorded. The
repair attestation is unverified by design until `repair-attestation.v2`.
