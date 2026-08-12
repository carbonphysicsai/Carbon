# Hydrogen Validator Guide

## Overview

The Hydrogen validator evaluates miner-submitted training strategies across multiple physics challenges using a multi-objective scorer and a challenge winner tracker.

It produces weights using a **winner-heavy + participation dust** distribution and submits them via standard Yuma Consensus.

## Quick Start

```bash
# Clone and install
cd Hydrogen
pip install -r requirements.txt

# Run the validator
python neurons/validator.py --netuid 63
```

## Key Configuration

| Flag / Env Var              | Description                                      | Default |
|-----------------------------|--------------------------------------------------|---------|
| `--dry_run`                 | Compute scores but do not submit weights         | False   |
| `--active_challenges`       | List of challenges to track                      | See code |
| `strategy_storage_dir`      | Directory for local strategy storage             | `./strategies` |

## How It Works

1. **Strategy Retrieval** — Pulls strategies via `StrategyStore` (currently local file based).
2. **Scoring** — Uses `HydrogenScorer` to compute Physics, Robustness, and Accuracy scores.
3. **Tracking** — `ChallengeWinnerTracker` updates per-challenge leaders with exponential decay.
4. **Weighting** — Produces winner-heavy + dust weights.
5. **Submission** — Calls `set_weights()` (unless in dry-run mode).

## ChallengeWinnerTracker Behavior

- Only miners who beat the current best **combined score** on a challenge get strong weight.
- Old performance decays exponentially (`decay_factor=0.85`).
- Participation dust gives small rewards to recent non-winners.
- Call `reset_round()` at the end of each round/day for heavy discounting.

## Dry Run Mode

Useful for testing:

```bash
python neurons/validator.py --dry_run true
```

Scores and tracker state are updated, but no weights are submitted to the chain.

## Monitoring

The validator logs basic stats every cycle:

- Number of challenges tracked
- Current leaders per challenge
- Number of miners tracked

## Strategy Storage

Currently uses `LocalFileStrategyStore`. Strategies are stored as JSON in `./strategies/`.

To add a new strategy manually (for testing):

```json
{
  "backbone": "physicsnemo_fno",
  "challenge_id": "poisson_2d_v1",
  "epochs": 50
}
```

Save it as `{hotkey}_default.json` in the strategies directory.

## Future Improvements

- Platform-backed strategy store
- Hybrid emissions layer (bounties + stipends)
- Stronger anti-capture protections

## Support

For issues or questions, open an issue on the Hydrogen GitHub repository.
