# CHAMPIONSHIP-REV5-RULE-01 — pure one-batch selector

**Authority:** OWNER-BATTERY-CHAMPIONSHIP-01, amended by -02; Test Engineer
MARGIN-SIZING-05 and REV5_STRESS_NOTE. Development library only. The Validator
owns the daemon, batch custody, settled G-FEAS/important-region decisions and
the active rule digest. No LIVE rule or payout is changed here.

**Decision:** Add `carbon.championship_stats.rev5.select_rev5_winner` alongside
the older carry-forward primitives. The caller supplies the immutable rev-5
policy fields, one raw shared batch for each contender, settled hard guards and
the Challenge's draw unit. Raw batch size is checked before hidden duplicate
case identities are collapsed. Duplicate entries must have identical values.
All contenders share the same case identities, draw blocks and king errors.

The posted relative improvement is the difference between the mean king and
contender accuracy errors divided by the king's mean accuracy error. The
statistical guard uses the mean paired improvement within each independent
draw block, the sample SD of those block means, and the one-sided Student t
quantile at `1 − alpha_round / K` with `B − 1` degrees of freedom. Both the
posted margin and this guard must pass, as must both settled hard gates.
The denominator for `K` stays the registered maximum even if fewer contenders
enter or some fail a hard gate. Exactly tied top qualifiers keep the king.

Battery's owner-approved **testnet** values are registered as an immutable
mapping: 4,000 raw cases, 10 maximum contenders, 2.25% posted margin, 1%
per-round alpha, and single-case draw blocks. Other Challenges require their
own draw unit and calibrated policy values. The existing carried evidence,
Holm, alpha-investing and confirmation paths remain separate and historical.

**Alternatives rejected:** A case-level SE for all Challenges would understate
uncertainty with correlated draws. Reusing carry-forward evidence would violate
rev 5's fresh single-round rule. An optional SciPy dependency in the pure
library is avoided with a deterministic incomplete-beta Student t quantile.

**Reversibility:** The new module and exports can be removed without migrating
historical results. A later owner score-proof choice that retains a q leg needs
separate question-level resampling and a newly sized posted margin before any
composite round is posted; this accuracy-leg function does not infer one.
