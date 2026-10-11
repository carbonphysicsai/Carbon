# Sources and reproducibility

Repository source pin: `eda5e5f55c1c3fae315e295ea8ed94f91d6d0fce`.
No case bank, journal, protected draw or host telemetry was read. Public
code was inspected only for sampling and custody semantics.

| Source | Git blob | Used for |
| --- | --- | --- |
| .agent/decisions/2026-10-07-OWNER-BANK-ARCHITECTURE-01.md | 4cf98c0baa515b73004cb66c14fcb7c544aa4292 | Historical class B/E and approximate motor cost |
| .agent/decisions/2026-10-07-OWNER-AUTO-PUBLISH-RETIRED-01.md | 2109c6858900f64607005ed223cc68211f556f51 | Retirement, dependency-window reveal and publication |
| .agent/decisions/2026-10-08-OWNER-BANK-EXPOSURE-E2-01.md | a5be32f651660a3ff956ce200074314d874bee81 | Versioned E2 pool revision |
| .agent/decisions/2026-10-10-OWNER-BANK-EXPOSURE-E1-TESTNET-01.md | 48fb8b0c04fae638b5ed8b8f30e6ba3a3a12da7d | Current E1 development choice, cadence, reserve, historical E2 lag correction |
| .agent/tickets/VALIDATOR-23_bank_architecture.md | 02853b3705db0464951d7089a7186983fd2ea703 | Distinct/duplicate counts, question-bank scope, 91 CPU-s and lattice/startup estimates |
| carbon/challenge_validator/bank.py | 984c478248bb0eb7d6028b909859f79c35661236 | Public draw_window active exclusion / random sampling, retirement and reveal |

External primary literature: [Owen (2007)](https://arxiv.org/abs/0712.1111)
on crossed bootstrap; [Stan's official ESS documentation](https://mc-stan.org/docs/reference-manual/analysis.html)
on autocorrelation and effective sample size; [Dwork et al. (2015)](https://arxiv.org/abs/1506.02629)
on adaptive holdout reuse; [Blum and Hardt (2015)](https://proceedings.mlr.press/v37/blum15.html)
on competition leaderboards. These motivate analysis boundaries; none is a
security certificate or a validated Carbon economic setting.

Local formulas are algebraic derivations with declared random-effects and
random-release assumptions. Costs are sourced planning values or ASSUMPTION
ranges, not measured runtime. #1062's 27/48 numeric-resolution result and
owner 0.73 CPU-h planning belong to the public question-resolution research;
numeric resolution is not admissible-bank yield. No hidden-run outcome or
operator data is inferred.

```text
python Business/research/bank-rotation-stats/analyze.py
python -m unittest discover -s Business/research/bank-rotation-stats -p test_analyze.py -v
python -m black --check Business/research/bank-rotation-stats/analyze.py
python -m black --check Business/research/bank-rotation-stats/test_analyze.py
python -m ruff check Business/research/bank-rotation-stats
```

Pinned Black 26.5.1 / Ruff 0.16.3. No runtime or solver imports, no randomized
physical simulation. Offline deterministic arithmetic/tests are DEVELOPMENT
diagnostics, not canonical scientific or security qualification. Final
exact-head repository acceptance and handoff are recorded on the PR.
