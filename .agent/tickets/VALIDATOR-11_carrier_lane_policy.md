# VALIDATOR-11 — The CPU carrier lane's registered policy and environment probe

**Status:** implemented in bounded DEVELOPMENT scope, awaiting review.
**Authority:** the Graphite readiness gate's item R3 (the Graphite Testing
Manager, at the Test Lead's instruction, 2026-10-05) needs a registered
policy id and registry for the CPU carrier lane. VALIDATOR-06 (#608) built
the lane, and the Test Lead approved its design.

**Executor:** the Carbon Validator session. Branch
`claude/carrier-lane-policy`, from main `506979c4d`.

## Outcome

The CPU carrier lane's declared properties now have one registered,
digest-pinned source: `carrier-lane-v1` in
`carbon/agent_campaign/graphite/compute_lanes/`. Its environment can be
probed read-only.

## Working decisions

- **VAL11-D1 — the registered document** declares:
  - lane `c03-carrier`, host `operator`, levels 0-3;
  - a program deadline margin of 45 s, at hourly USD 0;
  - attribution: the registered pod-attribution policy in force, with no
    environment claim ever on this lane, so pod-attribution-v2's GPU probe
    does not apply;
  - the environment probe.

  A change is a new version plus a registry entry.
- **VAL11-D2 — one source.**
  - `lane_policy()` verifies the pin, the closed key set, and that the
    document equals the lane's code (`CARRIER_LEVELS`, `SETUP_MARGIN_S`,
    price and host). It refuses `lane_policy_altered`,
    `lane_policy_malformed` or `lane_policy_disagrees_with_the_lane`.
  - `CarrierPods` will not start without it, and `describe()`, which is
    logged on every run, records the version and digest.
- **VAL11-D3 — the probe** (R3), read-only, runs nothing:
  - `environment_check(manifest)` loads the pinned C-03 worker image
    manifest, then asks `docker_runtime.doctor` with that image id and
    identity. That covers image presence, its binding labels and entrypoint,
    and the host's capacity, cgroup v2 and engine mode.
  - Image presence is `True` (found, even if ineligible), `False` (absent)
    or `None` (the doctor stopped before inspecting it), never assumed.
  - Each run's effective controls are still verified inside the carrier's
    trusted lane after start.
  - CLI: `python -m carbon.agent_campaign.graphite.carrier_pods check
    --image-manifest PATH` exits 0 when eligible, 1 when not, and 2 on a
    refused policy.

## Validation

- `tests/cpu/test_graphite_carrier_lane_policy.py` covers:
  - the policy and its match with the lane;
  - altered and disagreeing documents refused;
  - the lane refusing to run without its policy, and recording it;
  - the probe's presence and eligibility outcomes;
  - an unreadable manifest;
  - the CLI's exit codes.
- With `tests/cpu/test_graphite_carrier_lane.py`: 26 passed.
- `scripts/check_quality.py --base origin/main`: passed.
- Canonical: recorded in the PR.

## Maturity

TESTED (DEVELOPMENT). The lane stays flagged for the dedicated security
review (AGENTS.md §13). No real C-03 run is part of this ticket.
