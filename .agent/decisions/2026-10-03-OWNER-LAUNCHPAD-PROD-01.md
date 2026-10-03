## 2026-10-03 — OWNER-LAUNCHPAD-PROD-01: the miner front end becomes a zero-friction, production-level application

**Owner, verbatim, in session on 2026-10-03,** relayed to the executors by the
coordinating session:
- "We need to fix that. I want zero friction to use this mining front end.
  This needs to function like a production level application. Reason and
  figure out the fix this is unacceptable"
- "This is our entire workforce facing application. We need a SOTA solution"
- "we need a submission endpoint and a real validation endpoint for us to use
  for real testing and scoring runs that use our validator pinned images"
- "create an optimal workflow for executing this full work list thoroughly
  then test it all"
- On the work list, including its change to the parallel-call rule:
  "approve. you launch this now"

**Decision.**
1. **The miner front end is production work.** Launchpad, its MCP door, its
   supervisor, Carbon's research agent and its tools, the install and update
   path and the Control Center are to work with zero friction, as a
   production-level application. A real submission endpoint and validation
   service run on the validator-pinned images, for real testing and scoring
   runs.
2. **One work list, run as parallel slices.** Each slice (`LP-PROD-A` to
   `LP-PROD-G`) owns a closed set of files and records its own engineering
   decisions in its own file, `.agent/decisions/2026-10-03-LP-PROD-<KEY>.md`,
   citing this record.
3. **The parallel-call rule changes for new campaigns.** A campaign frozen
   from now on runs every tool call of a turn, in the model's order
   (`research_agent_policy.PARALLEL_CALLS_V2`, `LP-PROD-A`). This supersedes,
   for new campaigns:
   - the one-call rule, the owner decision of 28 September 2026
     (`research_agent_policy.PARALLEL_CALLS`, schema
     `carbon.autoresearch.parallel-calls.v1`): the first call runs and every
     other is refused;
   - GRAPHITE-D33's scope, under which only the Graphite Constructor ran
     under that rule. Every Graphite role now runs under v2.

   A campaign frozen earlier keeps the rule it froze (v1, or none) and replays
   byte-identically: its rule, prompt, prompt digest and tool list never
   change. Neither earlier record is rewritten.

**What this authorizes, and what it does not.** It authorizes the engineering
changes in the work list. It does not authorize changing any scientific value,
threshold, gate or tolerance; live economics or a default spend value; chain
writes or weights; exposing any host publicly; security acceptance; or
widening any authority boundary.

**Boundaries kept, with only their reporting changed.**
- The miner's own signer holds the hotkeys; Carbon never holds or reads a key.
  The owner or miner signs registration.
- Miner compute is link-only: Carbon never starts, stops or bills it.
- No exam, protected or hidden-evaluation material reaches a miner.
- One owner-lock holder per campaign.
- A paid model call whose outcome is unknown is never resent blind.
- Evidence is DEVELOPMENT evidence only, and no weights are set.

**Unchanged.** Every scientific, security, economic and delivery rule.
Nothing here is scientific, security or production qualification.
