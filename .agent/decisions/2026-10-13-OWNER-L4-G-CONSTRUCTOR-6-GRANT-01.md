# OWNER-L4-G-CONSTRUCTOR-6-GRANT-01 — grant -6 at USD 14.94, in the owner's own word

Date: 2026-10-13
Status: APPROVED by the owner, confirmed directly in the PR Head session.
Authority: the owner. `OWNER-POD-LAUNCH-DELEGATION-01` reserves **every new
grant figure** to him, so this was not delegable.
Scope: `GRAPHITE-GRANT-L4-G-CONSTRUCTOR-6` only.
Maturity: DEVELOPMENT spend authority. No scientific authority is created.

## What he approved

| field | value |
| --- | --- |
| ceiling | **USD 14.94** |
| worst case | USD 14.91 |
| runs | one |
| start model | kimi-k3 |
| replaces | `GRAPHITE-GRANT-L4-G-CONSTRUCTOR-5` (`replaced_by`) |
| pool | the standing weekly test grant (`OWNER-TEST-GRANT-01`) |

## Why it needed his word

He had said only **"I approve new grant"**, with no figure, and the figure
USD 14.94 was **inferred from `-5`**. An inference from a prior grant is not an
approved figure: it is the mechanism by which a figure confirmed for one scope
quietly becomes general, which is the same defect that sent
`GRAPHITE-GRANT-MODEL-QWEN-CONSTRUCTOR-1` back to him earlier today. A figure
relayed through a third session would not have cured it either; it had to be his
word in the session that records it.

Asked directly, he approved **USD 14.94**.

## Conditions carried from -5

`-5`'s record established that a replaced grant must be **unlaunchable, not
merely unused**: `check_phase3_grant` refuses any grant carrying `replaced_by`
with `grant_is_replaced_by_a_later_grant`, before any key, pod, claim or file
read. `-6` replacing `-5` puts `-5` in that state, and the same predicate that
drops it from `standing_open()`'s weekly sum is the one that refuses launching
it — so the basis counts the pair once because the first genuinely cannot be
spent.

## Not covered

- Any further grant in this series. `-7` would need its own figure confirmed.
- The run's launch, which waits on the pod-environment PR merging
  (`OWNER-POD-ENV-LIMIT-RAISE-01`). The executor has said they will launch
  nothing until then, which is the correct order: the run would otherwise be
  spent under a limit that is about to change.
- Any scientific conclusion from the run.
