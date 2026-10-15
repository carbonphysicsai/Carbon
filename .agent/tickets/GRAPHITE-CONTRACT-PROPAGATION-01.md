# GRAPHITE-CONTRACT-PROPAGATION-01: preserve the advertised contract through agent selection

Status: IN_PROGRESS; executor Packets3; runtime/merge owner Root.
Starting base: 90d7fd25e5b2cc797b006276e3c43998eb194cb7.
Primary map_ref: SYSTEM/AGENT-EXECUTION; Hub retired under OWNER-WORKFLOW-SPEED-01.

## Problem and bounded behavior

The actual M281 Graphite campaign 2eaf2898d78ee415c8f0aecc3abef703 completed two
isolated practice trials, selected a base DeepONet recipe, then refused submit
with level_not_registered. Its immutable contract was ad15, but agent SELECT
used the base-contract candidate builder and lost the construction binding.

Repair the shared agent selection path and its direct campaign/Graphite plumbing.
Compile and freeze under the campaign's immutable advertised construction contract;
retain that binding through existing commitment and submission checks. Plain base
recipes remain legitimate within a wider contract. Levels describe actual recipe
changes; they are not permissions. Require graph documents only when graph fields
are used. Preserve the original recipe, validated envelope, and historical records.

## Plan and acceptance

1. Reuse the existing construction compile/freeze/candidate mechanisms for agent SELECT.
2. Expose frozen contract context in the initial observation without changing published prompts.
3. Test actual scripted agent SELECT, accepted plain recipes, missing/mismatched bindings,
   graph staging requirements, and unchanged base/historical behavior.
4. Run focused canonical acceptance remotely or in Root's assigned local TEST slot.
5. Deliver one PR, exact head, tests and bounded limitations to Root and Product.

Root separately owns PyTorch worker adoption, more practice trials, explicit
capability-exploration guidance, runtime rerun through verdict, and cleanup.
No provider/model/solver execution, runtime deployment, new contract registration,
route substitution, threshold changes or qualification is part of this code ticket.

## Validation and maturity

Open PR overlap checked: no overlap on the assigned implementation paths.
Native runtime baseline is deferred to Root's TEST slot; no native result is canonical.
Completion requires the focused regression suite and applicable exact-head CI;
this ticket earns engineering implementation/testing only, never qualification.
