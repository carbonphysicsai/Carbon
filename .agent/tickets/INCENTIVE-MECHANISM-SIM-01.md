# INCENTIVE-MECHANISM-SIM-01 — prospective incentive sensitivity

**Status:** development analysis candidate prepared; awaits exact-head CI and PR Lead review/merge. No LIVE or scientific/economic qualification.
**Base:** `origin/main` at `b58bc2d54205d063264173f7b5969ac5e11d42b2`.
**Authority:** owner task of 2026-10-10; `carbon/battery/exam.py` development comparison; `carbon/rewards/winner_decay.py` and `winner_eligibility.py` testnet transport; AGENTS.md §14 and scientific canon §11–13. All simulated miner qualities, correlations, strategies, challenger-margin alternatives, decay alternatives, window timing and allocation are assumptions. The owner retains economic settings and emission policy.

## Working contract

- Use the committed public Graphite run-5 practice summaries to estimate a *proxy* score-noise scale. The summaries are seed-to-seed public practice results, **not** hidden-window or exam noise. Pin their digest, show the sample size and do not silently promote the proxy to a measured official variance.
- Keep score comparison, promotion, weight target and observed payment distinct. The simulation ends at theoretical weight targets; it predicts neither chain settlement nor miner receipts.
- Preserve the current development rule's comparison margin, sample minimums and alpha as labelled inputs. A fast normal-interval surrogate approximates the registered bootstrap final; mark the approximation in every report. Paired same-case evidence is the current path; unpaired is an explicit counterfactual.
- Simulate one Challenge at a time. Initial incumbent, true qualities and synthetic case errors are declared in a manifest. Distinct hotkeys cannot exceed one scored submission per window; extra hotkeys may add attempts. A repeated coldkey does not reset reward age.
- Output aggregate scenario curves only. Never write case samples, seeds, recipes, hidden IDs or per-run winner traces. Include a separate canary comparison schema for the Validator's eventual testnet observations.
- Tests use synthetic fixtures. No solver, hidden/AX42 data, spend, production weights or LIVE changes.

## Plan and completion predicate

1. Pin and audit the public noise source and current protocol seams.
2. Add a deterministic simulation, explicit assumption manifest, aggregate curves, and bounded recommendations.
3. Test deterministic replay, comparison/promotion separation, sybil and timing accounting, noise provenance, and output disclosure.
4. Run focused and canonical validation, open one PR, then hand its exact tested head to PR Lead. No merge by this ticket's author.

## Scope/Hub

Primary historical map reference: `WAVE-C/INCENTIVE-MECHANISM-SIM-01`. The Development Hub is retired under current `.agent/DELIVERY_PROTOCOL.md`; no Hub source or generated output is changed. This analysis changes no runtime maturity or authority boundary.
