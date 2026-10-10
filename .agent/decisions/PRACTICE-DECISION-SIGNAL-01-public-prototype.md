# PRACTICE-DECISION-SIGNAL-01 public prototype decision

**Decision ID:** PDS-01-D1. **Ticket:** PRACTICE-DECISION-SIGNAL-01.
**Status:** agent-recommended DEVELOPMENT implementation choice; owner
adoption of miner display remains reserved.

**Problem.** Practice accuracy alone did not show Graphite run 5's poor
decision quality. The public practice decision set already supports B4, while
PRACTICE-QUIZ-01 specifies Q3 measures but has not shipped its runtime quiz.

**Recommendation.** Reuse the registered public set and the existing fixed
decision/judging code to measure Q3-style regret and false-feasible rate in a
read-only prototype. Copy only EV4's already registered objective, limits,
bands, costs, baseline and grid into a practice-only rule, with a binding test.
Evaluate the run-5 first-seed distinct recipes, including the default MLP,
using local CPU reconstruction on public TRAIN and public practice inputs.
Pin compilation to run 5's registered battery implementation 1.0; the
in-process JAX code bytes must match that snapshot before rebuilding.
Compare aggregate practice measures to the already committed EV4 development
value. Keep Launchpad and official scoring unchanged.

**Observed public diagnostic.** On the matched eight-member, one-seed run-5
panel, regret's τ-b/ρ against previously published EV4 development value are
+0.308/+0.427, versus −0.473/−0.539 for historical v2 practice accuracy.
The public metric still misranks some recipes and has ties; this is a reason
to consider showing a bounded practice signal, not a decision to do so.

**Alternatives rejected.** Using the run-5 EV4 prediction bundles would not
measure the public practice conditions; those bundles also remain only on the
operator host. Reusing hidden Q3 or tuning references would violate practice
isolation. Inventing a new optimizer, uncertainty band or gate would silently
change the scientific question. Displaying the prototype before owner review
would preempt the reserved product/scientific decision.

**Affected interfaces and invariants.** Only a development script, spec and
tests. The existing static safety-import inventory gains this one
development-only public-data consumer; no runtime provider or exam import
changes. Practice remains intentionally incomplete (invariant 12); no hidden
data enters the computation (invariants 1, 2 and 4), and missing references
are not candidate failures (invariant 20). Historical v2 scores remain
historical (invariant 10). PRACTICE-QUIZ-01 can later consume the evidence but
must use its own approved implementation and disclosure contract.

**Reversibility.** Remove the development script/report without migrating any
runtime schema. To supersede this choice, edit this decision, its ticket and
the prototype specification in the same new PR. No human-reserved value is
filled here; owner choice to show the metric stays open.
