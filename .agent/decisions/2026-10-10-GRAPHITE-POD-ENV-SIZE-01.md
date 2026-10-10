## 2026-10-10 — GRAPHITE-POD-ENV-SIZE-01: a Graphite pod ships its import closure, its environment is measured before any create, and the probe uses the real spec

**Authority.**
- **The direction.** The Test Lead, under OWNER-DEV-AUTONOMY-01, as the top
  priority: stage A is blocked.
- **The cause.** Every stage-A pod create was recorded as
  `pod_launch_ambiguous`. RunPod answers a create request whose environment
  is over about 118,000 characters with an opaque HTTP 500. The whole-tree
  code manifest put a Graphite pod's environment near 131,000 characters.
  The launch preflight's probe passed because it created a pod with an
  empty environment.
- **The precedent.** #906 fixed the same failure for the A40 harness.
- **The scope.** Engineering only. No grant, spend, threshold or scoring
  change.

**Decision.**
- **The ship.** `pods.ship_list` ships the static import closure of
  `ENTRY_MODULES` (the bootstrap's runner and Graphite's pod phase) and of
  every module under `DYNAMIC_PACKAGES` (the packages reached by
  `importlib` at run time), the non-code files in the closure's
  directories, and the scoring's public data. It never ships the lessons
  register, a `private` directory, or any path the guard names
  (`FORBIDDEN_DATA`), code included, as the A40 ship does. A protected data
  path is still refused. Every shipped file is still sha-pinned in the
  manifest and checked on the pod.
- **The measurement.** Battery's ship falls from 1,603 files to about 800,
  and the environment from about 131,000 to under 82,000 characters.
- **The guard.** `RunPodPods.pod_spec` builds the create request's
  `PodSpec` and refuses an environment over 90,000 characters
  (`pod_env.ENV_LIMIT_CHARS`) with `pod_env_too_large`, naming the largest
  variable. `launch` calls it before the balance read, the offer read and
  any create.
- **The probe.** `preflight.probe_pod` builds its pod with the same
  `pod_spec`, changing only the start command to a sleep
  (`PROBE_COMMAND`). An oversized environment fails the probe before any
  create.
- **Shared code.** The closure walk, blob reader and size count move to
  `scripts/dev/exam_design/runpod/pod_env.py`; the A40 harness imports them
  unchanged.

**Tests.** `tests/cpu/test_graphite_pod_env_size.py`:
- the ship is the closure, with no lessons, `private` or guard-named path,
  and its environment fits with room to spare;
- the real entry (`runner graphite_practice`) runs in a directory holding
  only the shipped files, rebuilds what Carbon pinned and predicts
  PRACTICE; each registered battery development variant builds there as in
  the repository;
- an oversized environment is refused before any provider call;
- a real launch and the probe differ only in the start command.

`test_graphite_launch_preflight.py` gains the probe's use of `pod_spec` and
its refusal. `test_challenge_validator_hardening.py` now checks that a code
module whose file name says "private" no longer ships.

**Not decided.** The provider's exact limit is unmeasured; 90,000 is a
conservative bound.
