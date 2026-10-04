## 2026-10-03 — OWNER-GRAPHITE-MINER-01: Graphite becomes the Carbon agent miners run

**Owner, verbatim, in session on 2026-10-03:**
- Asked whether Graphite should be the Carbon agent people can run, then:
  "Work the Graphite-Miner now."
- On literature cards, after a no-cards default was proposed: "why do you
  think it shouldn't have cards. We will already know the behavior they
  drive. We should maybe give them the option to hunt for more?"
- Asked "So should we have a 'research' option when using graphite-miner?",
  then, on the proposed Research / Build / Full modes with a Library and paper
  import: "Yes I like this capability a lot"
- "We have a way to keep the research hunts focused on the best content for
  the challenge?" The focus layer below was proposed in reply and not
  objected to.
- On per-epoch call and trial caps: "Yes generous and tunable limits. I don't
  like that internal graphite has limits like that honestly"

**Decision.**
1. **One engine, two editions.**
   - The miner edition of Graphite replaces the `autonomous` Carbon agent for
     new Launchpad campaigns. A new launch with `agent=autonomous` is refused
     with `autonomous_agent_replaced`. Campaigns and launch keys recorded
     earlier still run and replay unchanged.
   - Internal Graphite stays Carbon's testing agent, on the same engine.
2. **What the miner edition runs on and leaves out.**
   - It runs on the miner's own model, key, budget and compute. It uses no
     Carbon spending grant, Carbon model account or pods.
   - Roles: Reader, Planner and Constructor. The Attacker, Writer and
     Optimizer researcher stay internal.
   - Next-level ideas become ordinary `capability_request` actions.
   - There is no model escalation unless the miner configures one.
3. **Literature.**
   - The shared card pack ships with the product. It is the frozen phase-2
     snapshot: 1,773 cards, served UNCHECKED, with its `withheld_protected`
     cards left out.
   - Rights: each card holds an arXiv title and abstract, which arXiv releases
     as CC0 descriptive metadata, plus Carbon's own extracted fields.
   - The miner's agent can hunt arXiv for more cards. Hunts run on the miner's
     model and budget, at no more than one request every 3 s, with
     deduplication. Hunted cards go to the miner's private library, layered
     over the shared pack.
   - Miners can import their own text. PDF import is a follow-up.
   - Contributing cards back to the shared pack is deferred.
4. **Modes, frozen at launch.**
   - RESEARCH: hunt and read, then write a ranked plan. No practice
     submission.
   - BUILD: take a plan, then construct, practise, select and submit.
   - FULL, the default: research, then build, under a research share the
     miner sets.
   - A Library (Control Center tab and MCP tools) shows shared and private
     cards, search and the plan, and lets the miner pin, ban and import.
5. **Focused hunts.**
   - Queries are derived from the Challenge's public discovery document.
   - Each card gets a graded, per-Challenge ranking, including whether it can
     be built under the Challenge's contract.
   - Each miner's library learns from the miner's own practice results.
   - A cheap first-pass triage runs before full extraction.
   - Pins and bans steer the ranking.
   - Ranking uses only public material and the miner's own practice results,
     never hidden-test conditions or results.
6. **Limits are money and time, not call counts.**
   - For the miner edition, the miner's own campaign ceilings bind. Per-epoch
     call and trial counts are optional, with generous defaults the miner can
     tune.
   - Internal Graphite drops its session-turn and per-role call caps. The
     spending grant's money limit still binds every run. Stall detection stays.
   - Long runs use explicit, recorded context compaction as a versioned rule
     for new runs. History is never dropped silently, and replays stay exact.

**Unchanged.**
- The boundaries OWNER-LAUNCHPAD-PROD-01 lists.
- Every scientific value, threshold and gate.
- No hidden-test access, no chain writes, no weights.
- Frozen historical plans replay byte-identically.
