## 2026-10-13 — OWNER-CONSTRUCTION-ANYTHING-01: the construction contract rebuilds anything in scope; the level describes, it does not permit

**Authority.** The owner, 2026-10-13, in the Test Lead's session, in his own
words:

> I just need a construction contract that can rebuild anything at all on our
> 0-4 plan. I need that shipped. And I need that tested on Launchpad with every
> Launchpad capability.

On what "in scope" means:

> The scope is everything level 4 and below that we've tested. Everything. Our
> construction contract just needs to be able to handle everything in level 0-4
> that graphite has used and tested along with the level 5 wins graphite had for
> each challenge built in to construction... We test it. We add it. We end up
> being able to do all of it. And level 5 wins become part of the base.

Revising the entry bar:

> Change it to tested and then we will remove anything we can't protect.

And on the level:

> The level shouldn't matter, a miner should be able to do whatever they want
> that's in scope and our system should rebuild it.

The PR Head put the scope, the entry bar, the level ruling and the supersession
to him directly and he confirmed them in that session before this record was
merged. This changes what a miner may submit and supersedes two existing rules,
and such a decision is not recorded on a relay alone.

**1. Scope is what Graphite has tested, at L0-L4.** Entry is on **tested**.
Items are **removed** when we find we cannot protect them. Attacks subtract from
the scope; they never admit to it.

**2. The level is descriptive, not a permission.** It is derived and reported in
plain words. It never decides what may be submitted.

**3. The rebuild is the only gate.** In scope and rebuildable means admitted. A
failed rebuild is refused, and the refusal **names what could not be rebuilt**.

**4. It supersedes, prospectively, the one-level rules of PLT16-D1 and
DEV-LADDER-KIND-01.** Historical evidence keeps its meaning; nothing recorded is
reinterpreted (invariant 10).

**5. What this does NOT relax. Isolation and bounds stay in full.** The L1 op
set; the L3 menu and memory bound; the L2 pool bounds; L4's G0-G7 with its
allowlist and caps; the compute budget; the import-closure invariants; and the
pinned modules with their v1-v3 digests. **Miner code remains hostile.**
Graph-only and the L3 declarative rule are kept as **containment**, not as level
bookkeeping. Widening what a miner may attempt does not widen what the system
trusts.

**6. L5 wins fold into the base as a mechanism with an empty set.**
`L5_CANDIDATES_2026-10-12.md` holds three candidate ideas from one hunt, all
battery, and states itself that every claimed gain is **unmeasured**. **Nothing
enters the base unmeasured.** The owner has approved measuring the three,
cheapest first.

**Attributed to the Test Lead, not to the owner.** The removal defaults: an
untriaged finding **flags and queues for triage** rather than removing, and a
proposed removal takes effect once triage confirms a real escape. Also theirs:
shipping the L5 promotion path with an empty set.

**Not covered by this record.** Serving it on testnet-sched. That needs the
owner's separate explicit go and he has not given it here.

**Plan it implements.** `shared/operator/CONSTRUCTION_CONTRACT_PLAN_01.md`.

**Maturity.** DEVELOPMENT. This record sets scope and admission policy. It is
not a qualification, a security acceptance, or any authority to serve.
