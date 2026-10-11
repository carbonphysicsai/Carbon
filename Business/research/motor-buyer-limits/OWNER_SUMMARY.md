# Motor buyer limits: owner summary

**Keep the precision-joint requirements while the pending skew study is assessed. Public evidence does not justify loosening them simply because the reported panel has no joint passes.** This is a research recommendation; Test Lead and owner decide.

First reconcile units. The latest owner report says **0.30 pp fraction**. The [committed precision-joint packet](https://github.com/carbonphysicsai/Carbon/blob/59fc17a74134afd5628771e462ac567bf79e9120/docs/development/challenge_pipeline/round1/motor-precision-joint-v2.md) says **5% of mean AND 0.30 N·m holding pp**, with **0.60 N·m peak pp and 0.05 N·m zero-current cogging pp**. Those are mock requirements, not OEM receipts. A fraction of 0.30 is 30%. The active manifest and reported panel's cogging cutoff remain HUMAN_INPUT. No panel or hidden material was accessed.

The strongest comparisons are:

- [Tecnotion](https://www.tecnotion.com/wp-content/uploads/2022/12/WhitePaper_Cogging_2023.pdf): unpowered cogging pp guidelines **1% of continuous torque for QTL, 3% for QTR**. These are family-specific guidelines. Continuous rated torque cannot be replaced by a static holding mean.
- [STXI PRHD2](https://stxim.com/product/prhd2-highly-dynamic-servo-motors/): advertised cogging **<2% of nominal torque**, but the public page lacks the pp/amplitude test definition.
- [Published 10p/12s pump study](https://www.mdpi.com/1996-1073/17/21/5379): **≤5% loaded-ripple study constraint**; a different rotating-load job and larger envelope.
- E-bike and aerial studies provide useful achieved/design figures, but not a universal buyer ceiling. Commutation and waveform definitions differ.

Three defensible paths are documented: preserve the precision joint; compare against a selected direct-drive supplier family once continuous rating and buyer tolerance are established; or define a separate rotating application with its own requirements. The latter two change what the product can claim. None automatically makes the existing panel feasible.

All fixed numbers above are sourced observations/constraints, with low/base/high equal to the listed value, not confidence intervals. [Limit options](LIMIT_OPTIONS.md) includes labelled illustrative ranges and conversion arithmetic. Physical error bands and exact buyer acceptance values remain HUMAN_INPUT.

The next useful evidence is one immutable contract, joint pass/fail per geometry, refined numerical margins and measured torque lost to skew. Static magnetics alone cannot prove continuous thermal duty, controller position accuracy, acoustic noise or physical cogging. No existing Challenge files or limits were changed; no solver runs or spend occurred.
