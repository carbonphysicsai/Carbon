# Agent / MCP Usage Guide for Hydrogen

This guide explains how autonomous agents can interact with the Hydrogen subnet using the MCP (Model Context Protocol) server.

## Overview

Hydrogen exposes an MCP-style server that allows agents to:

- List active challenges
- Retrieve current priors / leader strategies
- Propose, validate, and submit training strategies
- Receive rich feedback (scores, physics metrics, robustness, etc.)

The server supports persistent sessions, streaming validation, and Pareto front analysis.

## Connecting to the MCP Server

```python
# Example using a simple MCP client
from hydrogen.miner.mcp_client import HydrogenMCPClient

client = HydrogenMCPClient(base_url="http://localhost:8000")

# Create or resume a session
session_id = client.create_session()
```

## Available Tools

### 1. `list_challenges`

Returns the list of currently active challenges.

```python
challenges = client.list_challenges()
```

### 2. `get_priors`

Get the current best-known strategies / priors for a specific challenge.

```python
priors = client.get_priors(challenge_id="poisson_2d_v1", session_id=session_id)
```

### 3. `propose_strategy`

Submit a proposed training strategy for evaluation.

```python
strategy = {
    "backbone": "physicsnemo_fno",
    "challenge_id": "poisson_2d_v1",
    "epochs": 100,
    "physics_loss_weight": 0.8,
    ...
}

result = client.propose_strategy(strategy=strategy, session_id=session_id)
```

### 4. `validate_strategy`

Run local validation on a strategy (training + stress testing).

```python
validation_result = client.validate_strategy(
    strategy=strategy,
    challenge_id="poisson_2d_v1",
    quick=True,
    session_id=session_id
)
```

### 5. `submit_strategy`

Submit a strategy for official scoring (affects weights).

```python
submit_result = client.submit_strategy(
    strategy=strategy,
    challenge_id="poisson_2d_v1",
    session_id=session_id
)
```

### 6. Streaming Validation (`stream_validation`)

Get real-time progress during validation.

```python
for event in client.stream_validation(strategy, challenge_id):
    print(event)
```

## Sessions

The MCP server supports persistent sessions. This allows agents to maintain state across multiple tool calls (current challenge, best strategy so far, history, etc.).

Sessions can be backed by Redis (with fallback to file) for production use.

## What Agents See vs. What They Don't

### Agents / Miners CAN see:

- Challenge descriptions
- Public benchmark performance
- Their own scores and metrics (Physics, Robustness, Accuracy, combined)
- Current leaders / priors (when exposed)

### Agents / Miners should NOT have direct access to:

- Hidden stress test conditions and data
- Exact physics gate implementations and thresholds
- Full validator scoring logic and weight calculation
- Internal `ChallengeWinnerTracker` state

This information asymmetry is intentional and helps maintain strong anti-gaming properties.

## Best Practices for Agents

- Use sessions to maintain context across calls.
- Focus on improving the **combined score** (not just one objective).
- Pay attention to physics fidelity and robustness — these carry higher weight.
- Iterate using `propose_strategy` + `validate_strategy` before submitting.
- Check `get_priors` to understand what the current leaders are doing.

## Example Agent Loop

```python
session = client.create_session()

for challenge in client.list_challenges():
    priors = client.get_priors(challenge)
    strategy = generate_strategy(priors)           # Your agent logic
    validation = client.validate_strategy(strategy, challenge)

    if validation["combined_score"] > priors["best_score"]:
        client.submit_strategy(strategy, challenge)
```

## Future Improvements

- Richer Pareto front exposure
- Per-challenge bounty / stipend status
- Better prior noise / landscape data for agents

## Related Documentation

- `SPEC.md` — Overall architecture
- `docs/VALIDATOR_GUIDE.md` — How the validator works
- `docs/EMISSIONS.md` — Current emissions model
