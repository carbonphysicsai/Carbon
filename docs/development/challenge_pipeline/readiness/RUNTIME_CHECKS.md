# PLT-09 batch 2: runtime readiness evidence

This batch wraps existing containment, frozen model selection, grant registries,
budget arithmetic and owner caps. It changes no grant, model setting, lane
permission, scientific value or execution authority. Its reviewer is the
Graphite Testing Manager. Batch 1 is merged (#1220); this PR is based on main.

`runtime_by_level` explicitly selects the Challenge, level, roles and grants.
An absent registration is NOT_BUILT; a malformed or conflicting registration
is FAIL. A role without a grant is NO_GRANT_FOR_LEVEL (FAIL). The registry,
HEAD, local origin/main and working file must agree before a grant is used.
The reader uses local Git objects, never fetches or accesses account ledgers.
Grant evidence discloses identities and digests, not accounts or spend.

R2 runs the real fixed containment cell, not pytest or a supplied PASS file.
It binds the manifest bytes before and after the run, the image, every probe,
canary cleanup and actual container-launch evidence. Synthetic reports are
refused. The analysis carrier is the miner research lane used by prelive;
it is distinct from the CPU proposal lane whose registry ends at Level 3.
Pod attribution stays in R3. R8's hostile-model probes stay separate and are
not executed by this batch. Missing Docker or manifest is FAIL.

R4 opens metadata-only sessions with the existing provider, role settings and
grant start rungs, then reads their frozen selection. It never runs a worker,
model request, tool or controller. Each role's block records context, output
maximum, charge-report capability and selection digest. The model's recorded
context is required literally: the current kimi-k3 input cap is smaller, so
R4 reports FAIL rather than silently interpreting full context differently.
The cap is not changed here. A matching committed Test Engineer sizing rule
is also required; absent owner evidence yields REVIEW_REQUIRED only after
the machine properties pass. No numeric sizing rule is invented.

R5 preserves binding and uses the existing budget producer and standing caps.
The complete permitted-run worst case plus cleanup must fit the ceiling;
unused approved ceiling is not treated as an arithmetic error or adequate
headroom. Pod count times the producer's rounded reservation must fit its
allowance. A role that runs no pods must have zero pod allowance; the current
Attacker budget still reserves verify pods, so that discrepancy is FAIL.
A committed Test Lead amounts review must name every role's canonical grant
digest. The reader never judges lost-run headroom or USD adequacy.

Optional reviews are named by `reviews.R4` / `reviews.R5` in the level record.
They use schema `carbon.readiness.runtime-review.v1`, item, challenge, level,
decision PASS/FAIL, reviewer (Test Engineer / Test Lead), ISO date, a nonempty
basis, and `roles` keyed exactly as the run. Each role names `grant_digest`;
R4 additionally names `model`, `max_output_tokens`, and a nonempty
`sizing_rule`. Missing reviews require review; malformed/stale/wrong-scope
reviews fail. Neither a review nor an L0/L1 ruling overrides a machine FAIL.

Validation: focused wrapper and mutation tests, existing containment/model/
grant regression tests, gate runs at L2/L3/L4, formatting, import sorting,
delivery hygiene and canonical CI. Local Windows-managed-worktree wrapper
availability is reported honestly. Maturity: development checks only;
security acceptance, qualification, launch, LIVE and spend remain unearned.
