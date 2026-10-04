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
   through `adapter.oracle(family, specimen)` and records each state. A
   result is BREACHED or HELD only from an explicit state or Boolean
   `breached`; a timeout, crash, unrebuildable or missing result, or an
   oracle that raises one of the listed run failures, is INCONCLUSIVE.
4. **Snapshots and frozen replay.** `snapshot()` freezes the journal; its
   sha256 is the store digest. `pin(digest)` returns a `ReadOnlyView` of
   exactly that snapshot's records, each re-verified against its digest; a
   missing or altered snapshot or record is refused typed. The view refuses
   every write, `suite_pin()` gives what a frozen run records in its suite
   version, and `replay(digest)` refuses any digest but the pinned one
   (`replay_under_another_digest`).
5. **Protected, sealed and confirmation material.** Every write and every
   read applies Graphite's protected rule (`graphite.tools.protected`) and
   the store's own markers: sealed material (`sealed`, a private pool,
   final conditions) and held-out control material. A record that fails on
   read (the markers grew since it was written) is withheld from records,
   priors, specimens and pinned views and listed by `withheld()`. The one
   exempt field is `check`, which must be one of the eight Track A check
   names (`fresh_attack_confirmation` is the check's name, not material).
   A store root whose path names EV4/EV5, confirmation, seal, secret,
   credential, canary or held-out material is refused, and the store opens
   files only under its root (tested behaviourally with an audit hook).
   The protected rule over-refuses by design: a boundary written as a
   repository path under `carbon/agent_campaign/` or `tests/` is refused, so
   adapters name boundaries neutrally (for example `experiment.admit`).
6. **A finding that names a protected case** is recorded as an
   `OTHER_SIGNAL` exposure (`exposure_finding`): the reported condition is
   kept, the protected content is withheld and only its digest kept, each
   identifying field that names protected material is dropped, and it has
   no specimen.
7. **Held-out controls.** A record with a held-out control is refused
   `held_out_control_refused`; only trained controls are stored.
   `training_view(adapter)` is the engine's way to an adapter: it forwards
   everything but refuses `controls('held_out')`; `trained_controls` reads
   the trained split. The store's specimen re-run reads no control at all.
   The held-out split is read only by the report, for wrongful rejection.
8. **The isolation invariant**
   (`tests/invariants/test_attack_store_unreachable.py`). The import walk of
   the product key invariant, run from the miner edition (which holds the
   shared pack's loader and the Library), the method cards, the Launchpad
   and the MCP door, reaches no file of `carbon/agent_campaign/attack/`, and
   no reached file holds a string naming the attack package, the store's
   schema prefix or its directory. The shared pack (decompressed) and every
   file the Launchpad and the door ship name none of them either. A fresh
   interpreter importing every importable miner-surface module holds no
   attack module. Specimens: a planted lazy import of the store from a miner
   path, a Launchpad entry two lazy imports from it, and an MCP door string
   import are each found and fail the same assertion.
9. **Mutations, each turning a named check red:** a replay that accepts a
   changed store digest and a pin that reads the live journal
   (`frozen_replay_is_pinned`); an engine whose training split is the
   held-out one and an unguarded training view
   (`engine_reads_only_trained_controls`); a planted import of the store from
   a miner path (the invariant's planted-violation test).

**Interfaces for the other slices.** AT-C's `verify.record` stores a verified
finding with `add_finding(..., rebuilt=True)` and routes the returned
record's condition (OTHER_SIGNAL when protected material was named) through
`controller.record_finding`; AT-A's suite records `ReadOnlyView.suite_pin()`
in each frozen suite version and replays through `pin(d).replay(d)`; the
engine reaches adapter controls only through `training_view`.

**Not changed.** EV5 and its sealed batch, every sealed or confirmation
material, the live construction contract, the expansion records, the miner
edition, the Launchpad, the MCP door and every existing plan, prompt, digest
and replay.
