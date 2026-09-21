# Host resource allocation and workload scale (N1, N2, N3)

Ticket: C-CORE-19. Branch `agent/core-platform-19-gpu-lane-split`.
Authority: `GPU_VALIDATOR_DEPLOYMENT_PACKAGE.md` on
`agent/gpu-execution-lane-design` (PR #248).

Three pieces of work that share one question: **what may a validator's host
configuration be changed to without changing the result?** N2 answers it by
measurement, N1 removes the constraint the answer licenses removing, and N3
removes the fixture limit that stopped every previous result from being measured
at more than two training steps.

Nothing here is QUALIFIED. N2 is CHARACTERIZED on one host; N1 and N3 are
IMPLEMENTED and TESTED.

---

## 1. Result, stated first

**Resource sizing is a cost and throughput decision, not a reproducibility
decision.** Across nine container configurations - usable core count 1, 2, 4 and
8; memory ceiling 2, 4 and 8 GiB; and two simultaneous runs on disjoint cpusets -
eighteen runs produced **one** weight digest:

```text
41b15c91a82214a629fa11b9d05dee4b748fff4c200c6b3e6854cf9939a7ccbc
```

| Label | cpus | cpuset | memory | Runs | Distinct digests |
| --- | --- | --- | --- | --- | --- |
| cores1 | 1 | `0` | 4g | 2 | 1 |
| cores2 | 2 | `0,1` | 4g | 2 | 1 |
| cores4 | 4 | `0-3` | 4g | 2 | 1 |
| cores8 | 8 | `0-7` | 4g | 2 | 1 |
| mem2g | 4 | `0-3` | 2g | 2 | 1 |
| mem4g | 4 | `0-3` | 4g | 2 | 1 |
| mem8g | 4 | `0-3` | 8g | 2 | 1 |
| conc_a | 4 | `0-3` | 4g | 2 | 1 |
| conc_b | 4 | `4-7` | 4g | 2 | 1 |

`conc_a` and `conc_b` ran **simultaneously** on disjoint core sets. They agree
with each other and with every serial configuration.

This is the opposite of the W3 instruction-set finding, and the contrast is the
point. Changing *which instructions* the host may use changes the weights.
Changing *how many cores and how much memory* the process is given does not.

### Why this is not a contradiction

The measured `sched_getaffinity` count tracked the cpuset exactly (1, 2, 4, 8), so
the pool genuinely saw different core counts - this is not a case of the setting
failing to take effect. Intended, effective and observed values were recorded
separately, as D1 does, precisely so that distinction could be made:

| Label | Intended cpuset | Observed `cpuset.effective` | Observed `cpu.max` | Affinity |
| --- | --- | --- | --- | --- |
| cores1 | `0` | `0` | `100000 100000` | 1 |
| cores2 | `0,1` | `0-1` | `200000 100000` | 2 |
| cores4 | `0-3` | `0-3` | `400000 100000` | 4 |
| cores8 | `0-7` | `0-7` | `800000 100000` | 8 |

`jax_device_count` stayed 1 and `OMP_NUM_THREADS` stayed unset throughout. The
operations in this workload are not partitioned across the thread pool in a way
that changes reduction order, so pool size does not reach the arithmetic. The
instruction set does, because it changes the width of the reductions themselves.

**Scope.** One host, one backbone, one workload, two steps. It establishes that
core count and memory ceiling are not *automatically* part of the execution
class. It does not establish that no larger workload could make them so - N5
experiment 2 is where that gets tested.

**This did not change the declared envelope.** `CPU_COUNT` is still 2 and
`MEMORY_BYTES` still 4 GiB, and a worker launch still allocates exactly that.
N2 varied the allocation *outside* the worker's fixed envelope, deliberately, to
answer whether the envelope could be widened without changing results. It says
the answer is yes on this evidence; it does not itself widen anything. Publishing
a different envelope is a separate decision with its own acceptance.

---

## 2. N1: the cpuset is no longer a string literal

`docker_runtime.py` rejected any allocation that was not exactly cores 0 and 1:

```python
if (cpuset != "0,1" or ...):
    raise WorkerFailure(WorkerCode.INVALID)
```

The consequence mattered more than the constant: **two concurrent reconstructions
were impossible**, because both demanded the same two cores. A validator scoring
a queue was serialised by a string comparison.

This is the defect class the portability work already removed for device identity,
and the repair follows that pattern rather than substituting a different constant.
New module `carbon/reconstruction/host_execution.py`:

- `parse_cpuset()` reads both notations Docker and cgroup v2 use (`0,1` and
  `0-1`), which is why the old equality test could not simply be widened - the
  kernel reports back a different string than the one requested.
- `derive_cpuset()` resolves an allocation from the host's actual logical CPUs.
- `resolve_cpuset()` reports what this host can offer, and is surfaced through
  `doctor`.

Both enforcement paths were reconciled, not just the create path. The observed
check at the far end of the module compared a cpuset string against an eligible
set; it now compares parsed sets and checks the quota against the cardinality of
that set:

```python
eligible = set(parse_cpuset(cpuset))
... int(cpu_quota[0]) != len(eligible) * int(cpu_quota[1])
```

N2 is what licenses this: unpinning the cpuset would have been unsafe if core
count changed the weights.

Tests: `tests/cpu/test_host_execution_allocation.py`, 31 cases.

---

## 3. N3: the fixture can express a step count other than two

Every determinism result to date - W3, W5, and the GPU characterization - was
measured on two training steps and 4,696 parameters, because the C-02 compile
fixture could express nothing else. It pinned the count in three independent
places: the sampling parameter's domain, the compatibility rows, and the training
support contract's resource lookup. Missing any one of them fails the compile
rather than silently training a different number of steps.

Widening is **opt-in**, via `sampling_levels` on `make_compile_fixture()` and
`steps` on `compile_c02_plan()`. The levels live in the training support contract,
so changing them changes its digest and therefore every plan digest derived from
it. Widening unconditionally would have rewritten identities for callers that
never asked for more steps. The default plan digest is asserted unchanged:

```text
sha256:cf927795afab440a864bd9137cb5368659ec673167b0b17f990a70f98962b4b8
```

Two is the floor, and it is the **training contract's** floor: `warmup_steps` is 1
by default and the profile requires `0 <= warmup_steps < steps`, so a one-step run
would be entirely warmup. The fixture compiles it and the profile refuses it,
which is the correct division of responsibility - widening the fixture did not
widen what training accepts.

Verified end to end at 8 steps (`completed 8`) and 32 steps (`completed 32`).

Tests: `tests/cpu/test_c02_step_count_fixture.py`, 22 cases.

---

## 4. What N3 immediately produced: a correction, not a confirmation

N3 is a fixture change, not a measurement. But it unblocked one measurement worth
recording here because it **overturned a claim the W3 and W5 packets were
carrying**: that the two-step figure was a floor because divergence "compounds
with step count".

AVX2 vs SSE4_2, `fno` backbone, at 2, 8 and 32 steps:

| Steps | Quantity | Differing | Max absolute | Max relative |
| --- | --- | --- | --- | --- |
| 2 | Parameters | 2660 / 4696 (56.6%) | `2.086e-07` | `6.105e-04` |
| 2 | Predictions | 9 / 64 (14.1%) | `1.746e-10` | `1.264e-06` |
| 8 | Parameters | 3109 / 4696 (66.2%) | `2.384e-07` | `8.929e-05` |
| 8 | Predictions | 9 / 64 (14.1%) | `2.328e-10` | `1.151e-05` |
| 32 | Parameters | 3529 / 4696 (75.1%) | `1.132e-06` | `3.072e-04` |
| 32 | Predictions | 12 / 64 (18.8%) | `9.313e-10` | `4.474e-06` |

The assumption was half right:

- **Absolute divergence grows** monotonically, about 5x over a 16x increase in
  length.
- **The share of affected values grows** monotonically, 56.6% -> 75.1%.
- **Relative divergence does not.** At 32 steps the parameter figure
  (`3.072e-04`) is *below* its 2-step value (`6.105e-04`); the prediction figure
  peaks at 8 steps and falls again by 32.

These are consistent: the magnitudes of the parameters and predictions themselves
change as training proceeds, so a growing absolute difference need not be a
growing relative one. The margin rule was stated in relative terms, so the
"floor" framing was wrong for the rule it was supporting.

The two-step prediction figure was nonetheless an **under**statement, by about
9x, just not for the reason given. `c-core-19-gate-margin-analysis.md` now carries
`1e-5` rather than `1e-6`, described as the largest value observed over 2-32
steps rather than as a floor.

`c-core-19-cpu-determinism-across-configurations.md` §4 and
`c-core-19-gate-robustness-options.md` §2 were corrected in the same pass. A
secondary error was fixed there too: the original prediction row reported
`11 / 64` differing beside a max relative of `1.264e-06`, but those came from two
different comparisons - the count from AVX2-vs-AVX, the magnitude from
AVX2-vs-SSE4_2.

**32 steps is the authorized envelope's per-invocation maximum**, so the envelope
is now covered end to end. Real training runs are far longer, the trend is not
monotone in the relative figure, and nothing here licenses extrapolating past 32.

---

## 5. Maturity

| Item | State |
| --- | --- |
| N1 cpuset resolution | IMPLEMENTED, TESTED |
| N2 allocation invariance | CHARACTERIZED on one host, one workload |
| N3 step-count fixture | IMPLEMENTED, TESTED |
| Scale correction to W3/W5 | Measured; supersedes an assumption |

None of these is SCIENTIFICALLY_QUALIFIED, SECURITY_QUALIFIED or
PRODUCTION_QUALIFIED. N2 in particular is a one-host characterization and is not
a licence to publish an execution class.

## 6. What the owner should decide

Nothing is blocked on a decision. The one item worth surfacing: N2 says a
validator may be sized freely on this evidence, which makes **throughput** a
tuning question rather than a correctness question. Whether to publish a
recommended size is a policy choice that should wait for N5 experiment 2, which
tests the same question at a realistic workload.
