## 2026-10-05 — GRAPHITE-ADMISSION-CONTROLLER-01: an admission-conditions CLI and one designated admission controller per (Challenge, level)

**Authority.**
- OWNER-GRAPHITE-TEST-WAVE-03 (`.agent/decisions/2026-10-04-OWNER-GRAPHITE-TEST-WAVE-03.md`)
  §2, the test wave's W2 rule: a finding "blocks `LOCK` of the affected
  level". The owner approved the Graphite test wave.
- The Test Lead's decision of 2026-10-05, in the Test Lead session, approving
  both parts of this work as part of that wave: the conditions CLI and a
  designated admission controller per (Challenge, construction level).
- It builds on W1 (GRAPHITE-DEV-VARIANTS-01, `check_lock`) and the W2
  follow-up (GRAPHITE-CONDITIONAL-EXPLORATION-01's amendment, the ledgers
  `admission.validate` consults).

Everything below is an engineering choice within that delegated authority.
No scientific value, threshold, gate, score or tolerance changes. Nothing
widens for miners. There is no chain write, no live run and no spend.

**The gap.** Each phase-3 root has its own campaign controller, and
`check_lock` cross-checked whichever controller it was handed. A LOCK checked
against a fresh controller would have bound an empty findings ledger, so the
W2 rule held per controller rather than per level. The battery Level 0
findings from Data Collection's divergence report (#609) also had no command
to reach the R2 root's controller.

**Decisions.**

1. **`phase3 conditions`.**
   - **Usage.**
     `python -m carbon.agent_campaign.graphite.phase3 conditions --root ROOT --grant GRANT --challenge TOKEN (--report PATH [--record-also] | --identity)`.
   - **Offline.** It opens the root's own controller (`controller_for`) with a
     `Phase3Provider` built from a scripted model with no script and `NoPods`,
     a pod backend that refuses every call before anything is created. No
     RunPod key is needed or read, and no model call can be made.
   - **Grant.** The provider's capabilities must match the grant's provider,
     and the grant must be the one the store is bound to.
   - **Report checks.** The report is checked before the store is opened:
     - its schema must be `carbon.admission-conditions.v1`;
     - every condition must name an admission condition;
     - an optional `challenge` must be `--challenge`;
     - an optional `level` must be a ladder level.
   - **Exact bytes.** The bytes checked are the bytes consumed, through a
     private copy.
   - **No new store.** A root without a controller store is refused; the
     command never creates one.
   - **Output.** It prints, as JSON, the finding ids, each id's result, the
     controller's identity, the designation and any warnings. Warnings also
     go to stderr.
   - **Idempotent.** The same bytes give the same ids
     (`<report sha12>-<index>-<condition>`). A repeat records nothing new and
     reports `ALREADY_RECORDED`. A finding repaired since the first run is
     reopened (`REOPENED_AFTER_REPAIR`). That is the controller's existing
     rule: a repaired finding recorded again is open again.
   - **`--identity`.** It prints only the controller's identity and its
     designation status. Nothing is consumed.
   - **Refusals.** Each refusal is typed, with a plain message. A held lock
     is `controller_already_active`; another process holds the root.

2. **Controller identity.**
   - **The id.** Each store gets a write-once random id, `ROOT/controller/store-id`:
     32 hex characters, mode 0600.
   - **When it is written.** It is created on the first open, under the
     supervisor lease, and linked into place whole, so a crash never leaves a
     partial id. A store opened before ids existed gets one on its next open.
     Its database and ledger are not touched.
   - **Damage.** A damaged id is refused (`controller_store_id_invalid`), and
     the lease is released.
   - **`CampaignController.identity()`.** It returns the bound grant's digest,
     the store id and `identity`, the sha256 of those under
     `carbon.campaign-controller-identity.v1`. It never contains a host path.
   - **Why the store id.** The grant digest alone is shared by every root
     under one grant, so it cannot name a single controller.

3. **The designation, `carbon/challenge_pipeline/admission_controllers.json`.**
   - **Schema.** `carbon.admission-controllers.v1`, one entry per (Challenge,
     level): `{challenge, level, name, identity, status}`.
   - **Status.** `status` is `DESIGNATED` with a digest, or
     `PENDING_OPERATOR_IDENTITY` with `identity: null`.
   - **Checks.** A name is a label, never a host path. A malformed or missing
     file refuses every LOCK (`admission_controllers_malformed`).
     `challenge_pipeline validate` checks the file.
   - **Battery Level 0.** The designated controller is the R2 phase-3 root's,
     whose run produced #609. Its identity exists only on the operator's
     host, so the entry is committed pending. The executor runs
     `conditions --identity` on that root, and a one-line follow-up PR fills
     it in.

4. **`check_lock` binds the designated controller.**
   - **Order.** `check_lock(block, challenge_id, *, repository, level=0)`
     first requires this controller's identity to be the designated one for
     (challenge, level), before the block is read.
   - **Refusals.**
     - `admission_controller_not_designated`: there is no entry;
     - `admission_controller_identity_pending`: the entry's identity is null;
     - `admission_controller_mismatch`: another controller is designated.
   - **Battery Level 0.** Until the follow-up lands, every battery Level 0
     LOCK is refused `admission_controller_identity_pending`.

5. **The CLI follows the designation.**
   - **Which level.** The level is 0, or the level the report names.
   - **Refused.** Consumption into a controller that is not designated for
     that level, or that is another controller, is refused with the same
     codes.
   - **`--record-also`.** It records anyway, and warns that the root is not
     the LOCK authority, so the findings must also reach the designated
     controller.
   - **While pending.** Consumption is allowed, with an explicit warning.
     - The R2 root is the intended authority. Refusing would leave its
       findings unrecorded until the identity lands, and that identity is
       read from the same root.
     - Recording a finding only ever closes LOCK, never opens one. An extra
       root that consumes a report while the designation is pending blocks
       nothing that should pass.
     - `check_lock` refuses every LOCK while the entry is pending, so no LOCK
       can rely on the choice.

6. **Follow-up (recorded only, not built).** Give admission its own
   controller, bound to a dedicated zero-spend grant rather than a run's
   grant. Admission state should not live inside an exhausted run root, whose
   grant expires and whose store also carries run state. When it exists, the
   designation moves to it as a new entry.

**Tests.**
- `tests/cpu/test_graphite_admission_controller.py` covers:
  - consume, an idempotent repeat, and a repeat after a repair;
  - a held lock;
  - a wrong schema and malformed reports;
  - a root without a store;
  - a grant mismatch;
  - no RunPod key read, watching file reads and environment reads, and
    `NoPods` refusing every call;
  - identity stable across opens, never a path, and a pre-existing store
    getting an id with nothing else changed;
  - a damaged id;
  - `--identity`;
  - `check_lock` refusing not designated, mismatch and pending;
  - the committed pending entry;
  - designation-file checks;
  - `--record-also`, pending consumption and a report-named level.
- **Mutations.** Each guard is switched off once and its test shown to fail
  (13 mutations).
- **Existing tests.** The W1/W2 `check_lock` tests now designate their
  fixture controller.

**Maturity.** Implemented and tested against synthetic grant copies and the
retained EV2 report. Not scientifically or security qualified. The battery
Level 0 designation is pending its operator-reported identity.
