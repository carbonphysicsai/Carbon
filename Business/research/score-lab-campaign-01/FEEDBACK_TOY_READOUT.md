# Disclosed-score feedback gamer: toy-only diagnostic

Input: `physics-example.json`, `feedback-search-example.json`,
`feedback-disclosure-example.json`, and the read-only ten-rule candidate file
`sha256:157b1db5f091910f5602b15c9f5029f0171e6da7e8b6dbc5ffb5aa5c775bd235`.
Aggregate output: `FEEDBACK_TOY_ALL10.json.gz`
(`sha256:cb78bbf246c63748dca48f0743bc6451cd4ab2098ff347f33701d8a838b105ce`).
This is an analytic toy with assumed score grains (`aggregate`, first three
score questions), decimal rounding (2, 4), probes per epoch (2, 6), and four
epochs. Each setting is replayable. The gamer sees only its rounded score;
buyer value is evaluated after the search on disjoint toy questions.

Seven rules scored all eight settings. A positive score gain accompanied by
lower buyer value occurred in 4/8 settings for N2, 2/8 for V2r2 k1, 4/8 for
V2r2 k3, and 2/8 for V2r2 k5. The largest observed loss change was 0.04583
toy units for V2r2 k5. N1, N3 and N4 gained score without a negative value
change in this small run. The in-force, V9 and V10 candidates had an
unscored/gated probe, so their feedback outcome is `INSUFFICIENT_EVIDENCE`.

This is a search-path counterexample, not a rule ranking or evidence about
Launchpad's actual disclosure. The toy candidate functions are proxies, the
trait space is narrow, and the value side is a small synthetic sample.
