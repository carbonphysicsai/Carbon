# VALIDATOR-21: Motor hidden batches on the producer, imported by validators

**Status:** design. It is the first of the per-Challenge producer adapters
(Test Lead ruling 2026-10-07: motor, then cooling as VALIDATOR-22, with
VALIDATOR-20 `onboard` built alongside). Security-sensitive (AGENTS.md §13):
it handles hidden cases and references, so it needs a dedicated review.

**Authority:**
- OWNER-VALIDATOR-MAINNET-PARITY-01;
- OWNER-SHARED-ANSWER-KEY-01;
- OWNER-REHEARSAL-AND-RELEASE-01;
- OWNER-DATA-MOTOR-01 (the published, digest-pinned GetDP and Gmsh image);
- OWNER-CHALLENGE-DESIGN-01 (the provisional DEVELOPMENT population and exam);
- MOTOR-VAL-D4 and MOTOR-VAL-D5 (the motor adapter, its fault policy and
  custody).

**Builds on:**
- VALIDATOR-19: the producer, `BatchSource`, the answer key, distribution
  and rotation;
- CHALLENGE-MOTOR-07: `challenge_validator/motor.py`, public PRACTICE only.

**Executor:** the Carbon Validator session.

## Starting state (main at 0e7308fe9)

- `motor/population.py` draws uniformly from the buildable box. Only
  confirmation sets use it with a private generator.
- `scripts/dev/motor/reference/run_batch.py` solves a plan in the pinned
  image, one container per case, with no network. Every case ends as one
  typed record: `OK`, `REFERENCE_INVALID`, `REFERENCE_SOLVER_FAILED`,
  `REFERENCE_TIMEOUT` or `FAILED_INFRA`. It does not resume: an existing case
  directory is refused.
- `MotorAdapter` scores a recipe (compile, rebuild, predict) on its store's
  one public PRACTICE pool with `exam.score_case` and `exam.aggregate`.
- `producer.source_for` refuses motor with `producer_no_source`.

## Design

1. **`MotorBatchSource`** (`challenge_validator/motor_source.py`, used by
   the producer only).
   - **Root.** It has its own 32-byte root, owner-only, outside the
     repository, and separate from battery's root.
   - **Seed pin.** `seed_pin = sha256("carbon.motor.hidden-root.v1" || root)`.
     It is public, as `pool_plan.py` already publishes its root pin.
   - **Draw.** `population.draw(rng, size)`, with
     `rng = Random(HMAC-SHA256(root, "motor-hidden|" + role))`.
     - Uniform only (Q = P): steering is HUMAN_INPUT.
     - A case equal to a public TRAIN or PRACTICE case is refused.
     - The document is
       `{schema, challenge, role, kind, population_version, cases:[{case_id, inputs}]}`.
     - Its canonical sha256 is the fingerprint. It is appended to the
       source's own append-only seed journal (role, kind, fingerprint,
       sequence) before any use. A role is never redrawn differently.
   - **Solve.** `run_batch.py` runs in the image pinned by OWNER-DATA-MOTOR-01
     (`@sha256:` required; a tag is refused). Only unsolved cases are
     planned, into a fresh `solve-<n>/` directory, and its records are
     appended to `records.jsonl`. That makes it resumable without the
     script's overwrite refusal.
   - **Ingest.** Reference failures are kept apart from candidate failures
     (§7.5):
     - `OK`, `REFERENCE_INVALID`, `REFERENCE_SOLVER_FAILED` and
       `REFERENCE_TIMEOUT` are terminal.
     - `FAILED_INFRA` is retried, never stored.
     - The batch is complete when every case has a terminal record. The
       references digest is computed over the sorted `[case_id, record]`
       pairs, as battery computes it.
     - A stored record that changes is refused with
       `producer_references_changed`.
   - **Export** returns `{document, references}`. Motor's rebuild is
     deterministic numpy, so there is no reconstruction salt.
   - **Check** recomputes the fingerprint against the seed journal.
   - **Identities:**
     - `contract_digest` is motor's registered contract;
     - `rule_digest` is the digest of the hidden rule (item 3);
     - `seed_pin` is the pin above.
   - **Cadence** comes from the hidden rule (item 3). It is `None` while that
     rule's values are HUMAN_INPUT, so nothing is scheduled.
   - **No quiz.** Motor's quiz is item 4 below; until then the base class
     refuses with `producer_quiz_unsupported`.
2. **A Challenge-neutral `HiddenBatchStore`**
   (`challenge_validator/hidden_batch_store.py`). It is the validator's
   custody of imported producer batches, shared by motor now and cooling
   next (D5's reasoning).
   - It is owner-only SQLite and stores batch, references and window.
   - It knows no Challenge rule. Each adapter validates a package before it
     reaches the store.
   - `active(block)` mirrors battery's `windowed_active`.
3. **The hidden rule** (`carbon/motor/hidden_rule.py`, a document pinned by
   digest).
   - It references, without changing them:
     - the existing exam (gates, components, aggregate, TRAIN scales);
     - the population version;
     - the reference outcomes that exclude a case from scoring.
   - **HUMAN_INPUT, null until the owner sets them:**
     - `every_blocks` and `active_batches` (the cadence);
     - `batch_cases` (the size);
     - `scored_per_window` (the per-hotkey cap).
   - **Proposed** to the owner, mirroring battery rule v2: 1080 blocks, 3
     active, 30 cases (the PRACTICE size, about 9 core-hours per batch), one
     scored submission per hotkey per 360 blocks.
4. **Validator import and scoring** (`MotorAdapter`, with a hidden mode
   selected by its deployment).
   - **`import_answer_key` and `holds_answer_key`**, as battery's:
     - identities, window and fingerprint are verified;
     - the references are exactly the batch's cases, against the committed
       digest;
     - a public case is refused.
   - **`evaluate`** scores the recipe on the union of hidden screening
     batches active at the request's finalized block.
     - Cases with a terminal reference failure are excluded. They are never
       charged to the candidate.
     - It never stalls: with nothing newly active, the current batches keep
       scoring.
     - With no batch ever imported, it returns `Unavailable` (typed
       `FAILED_INFRA`, never a score).
   - **The miner outcome** stays the allow-listed
     `{score, eligible, n_cases, n_scored, n_gate_failed}`. Case ids,
     inputs, references and per-case rows stay operator-only.
5. **Producer wiring.** `source_for` registers motor under its approval
   record. This ticket drafts OWNER-MOTOR-HIDDEN-POOL-01 for the owner; the
   approval itself is the owner's.

## Slices (one PR, final-tree review)

1. Contract and decisions (this file).
2. `MotorBatchSource` and its seed journal, with fixture solves.
3. `HiddenBatchStore` and motor's hidden rule document.
4. Motor import and hidden-mode `evaluate`.
5. Producer registration, the deployment config and the `onboard` adapter
   entry (VALIDATOR-20).

## Tests

- Draws are deterministic per role, the journal is committed before jobs,
  and a public-case collision is refused.
- Solve resumes: only unsolved cases are re-planned, the image must be
  pinned, and `FAILED_INFRA` is never stored.
- Seal and export round-trip through `answer_key.package` and verify.
- The import refuses each tamper: identity, window, fingerprint, references,
  public case.
- Windows activate and rotate, never stall, and score the union of active
  batches; a reference failure is excluded from scoring.
- No case id, input or reference appears in any miner outcome or public
  commitment.
- An unset HUMAN_INPUT cadence schedules nothing, and a draw without a
  registered size is refused.

## Out of scope

- Motor's quiz and tuning-set definitions. Data Collection proposes them;
  the owner approves.
- Cooling (VALIDATOR-22).
- Any change to motor's exam, gates, scales or population.
- Releasing retired batches (HUMAN_INPUT).

## Maturity ceiling

IMPLEMENTED and TESTED, with fixture solves and the real image on a small
smoke batch. It is not SECURITY_QUALIFIED or SCIENTIFICALLY_QUALIFIED, and
it carries no LIVE authority.

## Human input required

1. **Approval** of OWNER-MOTOR-HIDDEN-POOL-01: hidden motor batches on the
   producer for testnet.
2. **The four hidden-rule values** (proposed in item 3).
