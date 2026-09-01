# Carbon Delivery Protocol

**Status:** repository delivery authority for bounded development tickets
**Applies to:** agents, human executors, reviewers, pull requests, and ticket
closeout records
**Decision authority:** `CONSTITUTION.md`, `AGENTS.md`, the active Wave and
ticket, and `.agent/DELEGATED_DECISION_PROTOCOL.md` remain controlling

## 1. Purpose

Carbon finishes a selected ticket through one reviewable delivery lifecycle:

```text
working contract and durable decisions
→ coherent vertical implementation slices
→ canonical validation
→ exact-head required checks
→ exact-head Greptile Review
→ repair every valid finding
→ zero unresolved Greptile threads
→ normal expected-head merge
→ reviewed-tree and exact-main verification
→ bounded ticket closeout
→ next ready ticket
```

Greptile is Carbon's routine independent correctness review. Human and domain-
lead review remains asynchronous oversight unless current authority explicitly
reserves a value or acceptance decision to a human. Human silence is not a
delivery gate. A human-reserved science, security-acceptance, rights,
economics, qualification, `LIVE`, launch, deployment, or production decision
stays unavailable and fail closed.

Unless current owner direction explicitly says to stop before merge, a session
authorized to execute a ticket end to end continues through the normal merge,
exact-main verification, closeout, and selection of the next ready ticket.
Another owner prompt is not required solely to merge an unchanged, green,
reviewed ticket.

## 2. One pull request per ticket by default

The default ticket history is:

```text
commit 1: working contract, decisions, plan, and ticket-start state
later commits: coherent vertical implementation slices and their tests
final candidate: contract, implementation, tests, and stable tracked evidence
                 reviewed together
```

The working contract may evolve during implementation. Record material changes
prospectively, notify the applicable lead, and bind final review to the whole
candidate tree.

A separate contract pull request is permitted only when:

- the selected ticket is contract-only;
- a concurrent downstream ticket truly requires a merged immutable contract;
- an established cross-domain public-interface freeze requires it; or
- current authoritative sequencing records another concrete reason.

Ticket size alone is not a reason. A retained exception separates merge
topology, not substantive gates: all applicable scientific, statistical,
security, protocol, rights, operational, review, and maturity boundaries still
apply.

Use one ticket branch/worktree and one ticket pull request unless an exception
above is recorded. Use normal merge commits only. Do not squash, rebase-merge,
enable auto-merge, or create an empty commit merely to provoke validation.

## 3. Canonical validation

On macOS, Windows, or noncanonical Linux, run ticket commands through:

```text
./scripts/dev/canonical.sh <command> [args...]
```

Inside the exact canonical environment, the wrapper executes directly. A
native-host result is never canonical merely because it passed. Follow the
active ticket and detected change scope for focused and full commands.

Every final candidate must pass delivery preflight and the stable `Merge gate`
required by `.github/workflows/ci.yml`. Runtime-bearing or unknown changes
remain fail closed to the full runtime acceptance scope. A lighter classified
scope does not weaken any ticket-specific substantive validation requirement.

The versioned main-ruleset definition lives at
`.github/rulesets/main.v1.json`; `scripts/dev/apply_github_ruleset.py --dry-run`
prepares/verifies its application. Apply it only with repository-
administration permission and verify live state afterward. Insufficient
credentials require the exact unapplied artifact and smallest manual owner
action, never a claim that the ruleset is active.

## 4. Exact-head merge predicate

Normal merge is authorized only when all of the following are simultaneously
true:

1. the pull-request head SHA is exact, unchanged, and equals the expected head;
2. the pull-request tree is the final candidate tree;
3. every check required by the detected scope succeeded on that exact head,
   including `Merge gate`;
4. `Greptile Review` succeeded on the same exact head;
5. every valid finding was repaired and any repaired tree was reviewed again;
6. the unresolved Greptile thread count is zero;
7. no observed applicable `CHANGE`, `BLOCKED`, or `REQUEST_CHANGES` direction
   remains;
8. the pull-request base has been reconciled under current repository policy;
9. every human-reserved value needed for the affected behavior is available,
   or the behavior remains explicit and fail closed; and
10. the expected-head guard is supplied to the merge operation.

PR-body or issue-comment changes do not alter the Git tree. A declaration edit
cannot substitute for a required repository change. A corrected declaration
must be validated from the current live pull-request body and current head
without an empty commit. Do not change the final reviewed tree merely to record
successful external facts. When a real repository defect requires a tree
repair, the repaired head requires fresh checks and review.

## 5. Post-merge predicate

After a normal merge:

1. verify the merge commit has the expected ordered parents;
2. require the second parent to equal the exact reviewed head;
3. require the merge tree to equal the exact reviewed tree;
4. require the reviewed head to be ancestral to current `main`;
5. require fetched `origin/main` to equal the merge commit;
6. require the exact-main `Merge gate` and any other push-only required checks
   to succeed on that merge;
7. post the external completion receipt;
8. make any prepared conditional ticket closeout effective only now; and
9. select and continue the next ready ticket when the session authorizes
   continued work.

If any post-merge predicate fails, do not call the ticket `done` and do not
start its dependent. Diagnose or repair through a new bounded change without
rewriting the reviewed or merged history.

## 6. Two evidence classes

### 6.1 Tracked stable evidence

Repository-tracked ticket, plan, decision, contract, and evidence files record
facts that are meaningful before the final commit exists:

- ticket scope and authority set;
- starting base commit and tree;
- durable decisions and working contracts;
- expected manifest;
- validation commands and acceptance invariants;
- maturity ceiling; and
- a conditional completion predicate.

Tracked evidence must not guess the final head/tree or create a recursive
identity problem. A final candidate may state that `done` and the next-ticket
selection become effective only after the exact external predicate passes.

### 6.2 External dynamic completion receipt

Facts that exist only after the candidate or merge exists belong outside the
reviewed tree:

- final reviewed head and tree;
- CI run and required job/check identities;
- Greptile check and summary identities;
- unresolved thread count and disposition of findings;
- merge commit, ordered parents, and merge tree;
- exact-main check identities;
- lead/issue notification identity;
- final bounded maturity; and
- next selected ticket and exact starting base.

Use the normalized template at
`.agent/templates/EXTERNAL_COMPLETION_RECEIPT.md`. Put the completed receipt in
the pull-request body, one normalized pull-request completion comment, issue
#42, or a retained GitHub Actions artifact. The tracked evidence file points to
the chosen location without inventing its future identity.

Do not create commits named or serving only as:

- `record successful CI`;
- `record final review evidence`;
- `evidence seal`;
- `record merge evidence`;
- `retrigger validation`; or
- any equivalent external-fact-only update.

## 7. Conditional closeout

A final ticket candidate may coordinate its own bounded `done` state and the
next ticket's selection in the same reviewed tree. That transition is inert on
the branch and on an unchecked merge commit. It becomes authoritative only
after:

```text
exact final head/tree
+ scope-required exact-head checks and Merge gate
+ exact-head Greptile Review
+ all valid findings repaired
+ zero unresolved Greptile threads
+ no applicable block
+ normal expected-head merge
+ ordered-parent and reviewed-tree equality
+ exact-main Merge gate
+ completed normalized external receipt posted
```

This avoids a recursive closeout pull request while preserving every
substantive gate. If the predicate does not pass exactly, the prior merged
selection remains controlling.

## 8. Maturity and reserved authority

Close a ticket only in its bounded maturity. `SPECIFIED`, `IMPLEMENTED`, and
`TESTED` are separate claims. None implies scientific qualification, security
acceptance, network qualification, commercial validation, production
qualification, `LIVE`, launch, frontier, settlement, weight, emission, legal
rights, or deployment authority.

Routine engineering merge authority cannot override a human-reserved
decision. Missing reserved authority remains explicit and fail closed even
when `Merge gate` and Greptile are green.
