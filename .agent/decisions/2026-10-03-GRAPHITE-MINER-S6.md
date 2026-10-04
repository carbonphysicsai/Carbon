## 2026-10-03 — GRAPHITE-MINER-S6: internal Graphite sessions drop their call caps; money and time bind

**Authority.** OWNER-GRAPHITE-MINER-01 §6
(`.agent/decisions/2026-10-03-OWNER-GRAPHITE-MINER-01.md`). The owner, asked
about per-epoch call and trial caps, said: "Yes generous and tunable limits. I
don't like that internal graphite has limits like that honestly". The decision
reads: "Internal Graphite drops its session-turn and per-role call caps. The
spending grant's money limit still binds every run. Stall detection stays",
and "Long runs use explicit, recorded context compaction as a versioned rule
for new runs. History is never dropped silently, and replays stay exact."

The boundaries OWNER-LAUNCHPAD-PROD-01 lists are unchanged. OWNER-LAUNCHPAD-PROD-02
decision 1 ("why would we limit an agents output tokens? ... It's their
economics, compute, and choice!") is the same direction for miner agents: a
Carbon-imposed count gives way to money. Its decision 4 is the precedent
followed here for changing a rule: the new rule applies from the next run,
and runs already recorded keep the rule they were recorded under.

Everything below is an engineering choice within the slice's delegated
authority (Graphite miner edition, slice S6). No grant value, scientific value,
threshold or gate changes.

**Decision.**
1. **A versioned session-limits rule.** `carbon/agent_campaign/graphite/provider.py`
   defines two rules:
   - `SESSION_LIMITS_V1`, the historical rule. A session record with no
     `session_limits` block is under it.
   - `SESSION_LIMITS_V2` (`carbon.graphite.session-limits.v2`). A session
     opened from 2026-10-03 is under it. Its record carries the block.

   A provider opens new sessions under v2 by default. The constructor
   argument `session_limits=SESSION_LIMITS_V1` exists only so tests can
   reproduce the historical rule; the phase-3 runner never passes it. A
   resume always follows the rule the record carries, whatever the provider
   was built with.
2. **What v2 freezes.** The session record's `session_limits` block states:
   - the bounds: `money_cap_nanodollars` (the grant's `worst_case_run_cost`,
     the controller's per-run reservation), `model_spend_cap_nanodollars` (the
     run ledger's money ceiling; the token share for phase 3) and
     `elapsed_seconds` (the task's `max_runtime_s`);
   - the caps it does not have: `session_turns` and `role_call_cap`, both
     null. `operator_call_cap` is null unless an operator sets one;
   - the loop's rules: `loop_limits` and `compaction`.

   Phase 3 adds:
   - that the cap covers model calls and pods;
   - the pod limit;
   - the stall rule (5 attempts, one rung);
   - what a capped session does (decision 6).
3. **Loop arguments.**
   - A v2 session passes `limits=LOOP_LIMITS` and `compaction=COMPACTION_V1`
     to `research_loop.run_epoch`, and never `max_provider_calls`.
     `LOOP_LIMITS` is `{**research_agent_policy.LIMITS_V2, "calls_per_epoch":
     None, "trials_per_epoch": None}`, so only the run ledger's ceilings bind.
   - A v1 session passes exactly what it passed before: `max_provider_calls=150`
     for the Constructor (`Phase3Provider.HISTORICAL_SESSION_TURNS`, from
     `roles.CONSTRUCTOR_SESSION_TURNS`), and nothing for a harness role, which
     keeps the loop's shared 48.
4. **Ledger caps.**
   - Under v2, `provider_attempts` is the operator's own cap, None by default.
   - Under v1 it is the operator's cap, or else the historical session cap,
     as before.
   - `Phase3Provider` no longer defaults `max_calls_per_run` to 150. `caps()`
     takes the rule.
5. **Resume checks.** Before any call:
   - A v2 record whose block differs from what the code would freeze for the
     same task is refused with `session_limits_changed`.
   - A block with an unknown schema is refused with `session_limits_unknown`.
   - Removing the block from a v2 Constructor record is refused with
     `grant_or_caps_changed`, because the frozen caps (no call cap) do not
     match v1's 150.
6. **A capped v2 session still closes its work.** Phase 3 only.
   - Without a call cap, the common end of a session the agent does not end
     is a limit: the run's money cap, or its elapsed limit.
   - Before this change a capped run neither bundled nor escalated. Under v2:
     on a money stop, or an operator's call cap, the session's best
     improvement is bundled. The ablation pods are admitted against the same
     run cap, so nothing is spent past it.
   - On any limit stop the stall rule's one-rung escalation applies.
   - On an elapsed stop no new pod launches, so nothing is bundled.
   - The final state is unchanged: `failed`, `run_cap_reached` and the
     dimension.
   - A v1 session behaves exactly as before.
7. **Every Graphite role.** The rule is at the provider, so a new harness
   session (Reader, Planner and the rest) is no longer capped by the loop's
   shared 48 either.
8. **Unchanged.**
   - Role prompts, tool manifests and their digests.
   - The phase-3 brief, so a session resumed by a newer runner keeps its
     registered brief.
   - Grant files and values. `max_runtime_s` (39,600 s) keeps its value as the
     time bound; it was derived from 150 calls and 12 pods.
   - The stall limit and the ladder.
9. **The dry run.** `phase3 run --dry-run` still opens with the three-call
   turn and reports `parallel_calls_run`. It now also reports
   `session_limits_rule`, `model_call_cap` (null), `money_cap_usd` (4.91) and
   `elapsed_limit_s`. `run_session` and `status` report each session's
   `session_limits`.

**Replay evidence.** `tests/cpu/test_graphite_internal_limits.py` pins the
digests of the epoch plans the code at `9bfd9add` wrote for a v1 Constructor
session and a v1 Reader session. A v1 session still writes those bytes. A v1
record crashed at every checkpoint resumes, on a provider that opens v2
sessions, with no reply resent and the same session record digest. Mutation
checks are in `tests/cpu/test_graphite_internal_limits_mutations.py`.

**Dependency.** The v2 rule runs on the engine interface built in slice S1:
`research_agent_policy.LIMITS_V2`, `COMPACTION_V1` and `run_epoch(...,
limits=, compaction=)`. `provider.py` imports them at module level, so this
slice needs S1 merged to import. On the S6 branch alone the tests were run
with a scratch-only stand-in for that interface, which was never committed.

**Not changed, follow-up.** These closed, single-purpose callers keep their
grant-derived call caps. They are outside this slice's files and are not agent
sessions:
- `level_planner.MAX_CALLS`;
- `optimizer_research.MAX_CALLS`;
- `triage.MAX_CALLS_PER_RUN`;
- `closed_task`'s `max_calls`.

Each is derived from its own grant's money, as the grants README shows.
Whether to restate them as money-only is a separate change.

**Maturity.** Implemented and tested, with scripted models and pods only. Not
security, scientific or production qualified. No live session has run under
v2.
