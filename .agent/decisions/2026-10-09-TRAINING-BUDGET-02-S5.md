## 2026-10-09 — TRAINING-BUDGET-02-S5: a Level 4 graph is priced from its G5 compile

**Authority.**
- **The ticket.** TRAINING-BUDGET-02, slice 5.
- **The measurement.** The Level 4 session's G5 measurement (#909): G5's
  `compile.json` carries `train_step_flops`, one gradient step at the
  declared batch with the loss graph included and the optimizer update
  excluded, plus `train_step_loss`.

**Decision.**
- **The calculator takes G5's result rather than running G5,** because G5
  runs in its own isolated lane.
  - `cost(..., level=4, graph_compile=<compile.json>)`, or the CLI's
    `--graph-compile`, prices F4 as the recipe's `steps` × `train_step_flops`.
    The batch is the recipe's `batch_size`.
  - F1 is HUMAN_INPUT, because G5 records no parameter count.
  - A result without a positive `train_step_flops` is refused
    `cost_level4_graph_unmeasured`.
  - With no result, Level 4 is still `cost_level4_graph_pending`.
- **Where the budget check runs.** An admission that checks a Level 4
  recipe's budget does so after G5, with G5's result. That call sits in the
  Level 4 pipeline, the Level 4 session's.

**Not claimed.**
- **The optimizer's update** is not in `train_step_flops`, so a Level 4 F4
  leaves it out.
- **Calibration.** F4's conversion to seconds is still R5's on each
  Challenge's study.
