## 2026-10-12 — MINER-STATUS-AND-SCREENING-LADDER-01-D1: bounded public counts and registered geometric display

Owner-directed PLT-08, one independent PR to main. Carbon Validator reviews
the disclosure boundary. This is engineering authority, not deployment or
scientific/security qualification. The owner explicitly supplied the relative
grid/update convention and directed the loader to #1205's committed value file.

Use the existing attempt ledger through a read-only aggregate query: no receipt,
timestamp, submission hash, strategy or contract/window/case content enters the
count projection. Counts are scoped to the served contract and chain-known
non-canary hotkeys. Unknown refusal strings are counted under the single closed
code unclassified_refusal; their text is never emitted. A missing/unreadable
ledger gives null status rows, not invented zero activity.

The ladder uses stored pooled screening records only, with exact current rule,
eligibility and device checks. Chain ownership supplies the coldkey. It does not
infer ownership from a submission. Replay the immutable records in stable order
rather than creating another scientific store or changing scoring. Missing chain
ownership omits that row. Canary/development/final/fresh evidence is excluded.

Use the Test Engineer's screening_grain.load/entry_for/coldkey_own_se/update
functions from #1205, reading the highest-numbered file. Missing module, file,
matching identity, noise evidence or minimum evidence remains fail closed.
No measured values, minimum sizes or update thresholds are copied into code.
The noise estimate is for the current submission only, never pooled across
coldkeys or previous submissions. Keep existing scoring outputs prospectively
as operator-only screening_noise (case errors and question regrets), without
identities. Historical records are not rewritten and cannot fake this evidence.
Use immutable score insertion order, so late completion cannot reorder history.
Grid values come from the reference; the projection rejects a numerical edge
that overstates the score. Dashboard checks admit only integer powers within
binary64 representation error across Python/JavaScript, not a score tolerance.
Additive v1 ladder metadata names the geometric grid and sense. Existing readers'
released precision continues to govern existing sections and older ladder shapes.
Python and Worker readers explicitly verify the new grid and reject off-grid raw
values. Public counts are an allow-list, separate from score-bearing records.

Rejected: a hard-coded 3.5% grain, a 0.005 absolute score step, hotkey-based ladders,
raw latest scores, arbitrary refusal strings, another score calculation and a
hidden-score history. A later grain/policy revision has its own public identity;
historical records are not overwritten. Changes are reversible by removing the
new projection/helper and its additive feed fields. The smallest superseding
change is the registered grain contract plus the loader/grid convention, or the
explicit allow-list in score_feed/ledger and their disclosure tests.

Human-owned: the measurement/entry registration and release/cutover authority.
No such missing input is guessed; missing registration remains sealed. No Hub
update is made under the current retirement policy. Decisions travel with the
implementation PR, under the queue's no-decision-only-PR instruction.

After synchronizing main, OWNER-BATTERY-CHAMPIONSHIP-04 is the merged direct
owner confirmation. Its Testnet DEVELOPMENT boundary is enforced at build:
mainnet emits null for both additions and never calls the new disclosure path.
The status source must be the current deployment's existing attempt ledger
(intake.attempt_ledger_path, normally beside that deployment's inbox). The
ledger predates this feature and records contract identity, not rule identity;
there is no safe retrospective split of a mixed historical ledger across rules
sharing a contract. Do not supply a shared historical ledger or infer a split.
The optional source remains null until the operator supplies the correct ledger.
Activity counts include current-rule scored submissions across device classes;
only the score-bearing ladder is filtered/ranked within a device class.