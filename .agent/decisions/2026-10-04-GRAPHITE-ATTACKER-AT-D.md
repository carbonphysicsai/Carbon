## 2026-10-04 — GRAPHITE-ATTACKER-AT-D: the attack-knowledge store and its isolation invariant

**Authority.** OWNER-GRAPHITE-ATTACKER-01 (owner, 2026-10-04) §2 and §3: a
durable, content-addressed, append-only attack-knowledge store that learns
only from Carbon's own attack runs and public material; each frozen admission
run pins a store snapshot by digest in its suite version, and specimens added
later belong to the next suite version (invariant 10); the store and attack
modules are unreachable from anything miners receive, enforced by an
import-closure invariant test; they never read, derive from or record sealed
or confirmation material; the engine never tunes against held-out controls;
a timeout is never a pass; findings use only the CONDITIONS vocabulary. The
choices below are engineering choices within that decision. No scientific
value, threshold, gate or tolerance, no spend and no authority boundary
changes. DEVELOPMENT only: no weights, no chain writes, nothing live.

**Decision.**
1. **The store** (`carbon/agent_campaign/attack/knowledge.py`,
   `AttackStore(root)`, schemas `carbon.graphite.attack-knowledge.*.v1`).
   - Every record is a canonical JSON object written once under its sha256
     (`objects/<hex>.json`); `journal.jsonl` lists each record once, in the
     order added (`seq`, `kind`, `digest`). The same record added twice is
     stored once. Records carry no timestamp, so the same knowledge gives the
     same digests on any host. A torn final journal line (a crash
     mid-append) is never read and is cut before the next append.
   - Owner-only like the miner's library: an absolute, non-symlink root the
     user owns, directories 0700, files 0600, an exclusive lock per write.
   - Record kinds: `attempt` (an attack the oracle judged, outcome one of
     HELD, REFUSED, BREACHED, TIMEOUT, CRASH, UNREBUILDABLE, NOT_RUN),
     `near_miss` (with the oracle's own margin when it reports one),
     `finding` (verified: `rebuilt` must be True, the source must be the
     attack oracle, the condition must be in CONDITIONS, with evidence
     digests and its regression specimen), and `regression` (a specimen's
     re-run under a new contract version). Every record names its Challenge,
     construction level, contract digest, one of the eight Track A checks,
     family, boundary, strategy and attempt identity.
   - Sources: `carbon_attack_oracle` and `public_material` only; a finding
     only from the oracle. Anything else is refused `attack_source_refused`.
2. **Priors** (`priors(challenge_id)`; `priors(None)` across Challenges):
   counts only, by check, by family (with its levels and boundaries) and by
   strategy, with the findings each strategy found. HELD and REFUSED count
   as held; TIMEOUT, CRASH, UNREBUILDABLE and NOT_RUN count as inconclusive,
   never held. Across Challenges, families are keyed `<challenge>/<family>`;
   checks are shared. No score, rank or threshold is derived here.
3. **Specimens and regression.** One specimen per verified finding, per
   Challenge and level (`specimens`). `regression_due(challenge, level,
   contract)` lists the specimens found under another contract version and
   not yet re-run under this one; `replay_specimens(adapter)` re-runs them
   through `adapter.oracle(family, SpecimenAttempt(name, value))` (the
   `attack.adapter.AttackInput` shape: the finding's attempt identity and
   the stored specimen) and records each state from the oracle's `verdict`
   (`attack.adapter.OracleResult`): HELD or REFUSED is HELD, BREACHED is
   BREACHED; FAILED_INFRA, TIMEOUT, CRASHED, NOT_RUN, an unknown or missing
   verdict, a result for another family, or an oracle that raises one of
   the listed run failures, is INCONCLUSIVE, never a hold.
4. **Snapshots and frozen replay.** `snapshot()` freezes the records the
   store serves at that moment, in journal order; its sha256 is the store
   digest. `pin(digest)` returns a `ReadOnlyView` of exactly that
   snapshot's records, each re-verified against its digest; a missing or
   altered snapshot or record is refused typed. The view refuses every
   write, `suite_pin()` gives what a frozen run records in its suite
   version, and `replay(digest)` refuses any digest but the pinned one
   (`replay_under_another_digest`). A pinned view serves all its frozen
   records or none: if any is no longer admissible on read (the protected,
   sealed or held-out rules grew since the freeze), the pin, every read and
   `replay` are refused `attack_snapshot_withheld`, so a frozen run is never
   silently served a subset (invariant 10). Review repair, 2026-10-04: the
   first version withheld such records from a pinned view and still let
   `replay` succeed.
5. **Protected, sealed and confirmation material.** Every write and every
   read applies Graphite's protected rule (`graphite.tools.protected`) and
   the store's own markers: sealed material (`sealed`, a private pool,
   final conditions) and held-out control material. A record that fails on
   read (the markers grew since it was written) is withheld by the live
   store from records, priors and specimens, listed by `withheld()`, and
   left out of later snapshots; a pinned view holding one is refused whole
   (decision 4). The one
   exempt field is `check`, which must be one of the eight Track A check
   names (`fresh_attack_confirmation` is the check's name, not material).
   A store root whose path names EV4/EV5, confirmation, seal, secret,
   credential, canary or held-out material is refused, and the store opens
   files only under its root (tested behaviourally with an audit hook).
   The protected rule over-refuses by design: a boundary written as a
   repository path under `carbon/agent_campaign/` or `tests/` is refused, so
   adapters name boundaries neutrally (for example `experiment.admit`).
6. **A finding that names a protected, sealed or held-out case** is
   recorded as an `OTHER_SIGNAL` exposure (`exposure_finding`): the reported
   condition is kept, the named content is withheld and only its digest
   kept, and each identifying field that names the material is dropped. The
   specimen is kept when neither it nor the family names the material, so
   the exposure can still be re-run; otherwise it has none. The exposure is
   checked once more before it is stored: if what it must keep (its
   Challenge identity) still names the material it is refused typed, never
   stored to be withheld on read. Review repair, 2026-10-04: the first
   version refused a finding that named held-out material outright (losing
   it), dropped the specimen whenever any field named material, and stored
   an exposure without a final check.
7. **Held-out controls.** An attempt, near-miss or finding whose `control`
   field is a held-out control, and an attempt or near-miss whose content
   names held-out material, is refused `held_out_control_refused`; only
   trained controls are stored. `training_view(adapter)` is the engine's
   way to an adapter and is an allow-list: it exposes only `challenge_id`,
   `level`, `contract_digest`, `families`, `oracle`, `rebuild`,
   `level_families` (forwarded through closures, with no instance
   dictionary and no attribute holding the adapter) and
   `controls('trained')`, which refuses any other split and any answer
   carrying another split. `trained_controls` reads the trained split. The
   store's specimen re-run reads no control at all. The held-out split is
   read only by the report, for wrongful rejection. This guards Carbon's
   own engine against a mistaken read; it is not a sandbox for hostile code
   (closure introspection can still reach the adapter). Review repair,
   2026-10-04: the first version was a deny-list proxy that forwarded every
   other attribute, so a declared adapter's `control_set` reached the
   held-out split.
8. **The isolation invariant**
   (`tests/invariants/test_attack_store_unreachable.py`). The import walk of
   the product key invariant, run from the miner edition (which holds the
   shared pack's loader and the Library), the method cards, the Launchpad
   and the MCP door, reaches no file of `carbon/agent_campaign/attack/`, no
   reached file has an import statement naming the attack package (whether
   or not the name resolves to a file, so an implicit namespace package is
   caught), and no reached file holds a string naming the attack package,
   the store's schema prefix or its directory. The shared pack (decompressed) and every
   file the Launchpad and the door ship name none of them either. A fresh
   interpreter importing every importable miner-surface module holds no
   attack module. Specimens: a planted lazy import of the store from a miner
   path, a Launchpad entry two lazy imports from it, and an MCP door string
   import are each found and fail the same assertion.
9. **Mutations, each turning a named check red:** a replay that accepts a
   changed store digest and a pin that reads the live journal
   (`frozen_replay_is_pinned`); an engine whose training split is the
   held-out one and an unguarded training view
   (`engine_reads_only_trained_controls`); a deny-list training view
   (`view_exposes_only_the_allow_list`); a pinned view that withholds like
   the live store (`frozen_view_is_all_or_nothing`); a raw-dict specimen
   attempt and an oracle reading that ignores `verdict`
   (`regression_detects_a_reintroduced_breach`); a planted import of the
   store from a miner path, and a lazy import of the attack package as a
   namespace package (the invariant's planted-violation tests).

**Interfaces for the other slices.** AT-C's `verify.record` stores a verified
finding with `add_finding(..., rebuilt=True)` and routes the returned
record's condition (OTHER_SIGNAL when protected, sealed or held-out material
was named) through `controller.record_finding`, and calls
`controller.record_finding` even when the store refuses the finding (a
store refusal must never stop a finding from blocking expansion); AT-A's suite records `ReadOnlyView.suite_pin()`
in each frozen suite version and replays through `pin(d).replay(d)`; the
engine reaches adapter controls only through `training_view`.

**Not changed.** EV5 and its sealed batch, every sealed or confirmation
material, the live construction contract, the expansion records, the miner
edition, the Launchpad, the MCP door and every existing plan, prompt, digest
and replay.
