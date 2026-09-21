# MQ-008 evidence specification — draft for SCI + SRE acceptance

**Status: draft, not accepted.** Written by engineering for the MQ-008 owners to
accept, amend or reject. It decides nothing. It sets **no tolerance**: if the
evidence supports one, that is SCI + SRE's output, not this document's.

`GPU_INITIAL_POLICY.md` P7 makes this the gate on the authorized hardware batch:
no attempt is spent until a written evidence specification exists and the MQ-008
owners have accepted it. This is that specification.

## 1. The question

MQ-008 asks whether a **narrow** backend profile can be qualified under R0/R1/R2
— one exact configuration, qualified first, widened later. Per D3, qualification
attaches to the **backend profile**, never to a provider or a host. Nothing here
prescribes where a validator runs.

## 2. Which quantities are compared

**Compared:**

| Quantity | Why |
| --- | --- |
| `checkpoint/state.npz`, byte-for-byte | The trained weights. This is the scientific output. |
| `checkpoint/manifest.json`, byte-for-byte | Checkpoint structure and recorded shapes; stable across repeats in the baseline. |
| The stable keys of the artifact `manifest.json` | 25 of its 27 keys, listed below. |

**Excluded, deliberately and by name:**

| Key | Why excluded |
| --- | --- |
| `compile_seconds` | Wall-clock measurement. Varies between identical runs. |
| `train_execution_seconds` | Wall-clock measurement. Varies between identical runs. |

**`ReconstructionReceipt.artifact_digest` must not be used as the comparison
quantity.** It is a tree digest over an artifact that contains the two keys
above, so it differs between two runs that computed identical weights. This was
measured: three repeats on one host produced three distinct artifact digests and
one identical weight digest. A specification built on it would report
nondeterminism in every case, including CPU against CPU, and would be measuring a
clock. The exclusion is recorded here so that it is a decision rather than an
omission.

## 3. A precondition the campaign must satisfy

W3 measured that CPU instruction-set level changes the trained weights: AVX2,
AVX and SSE4_2 produce three different results from identical inputs, and every
identity Carbon records is the same across all three.

> **The CPU arm of this campaign must fix and record the CPU feature level.**

If it does not, observed CPU-versus-GPU divergence will include an unknown
contribution from the instruction set, attributed to the device. The attempts
cannot be un-spent, so this is a precondition and not a refinement.

Concretely, each run's record must carry: CPU model and feature level, the exact
`XLA_FLAGS` in force, `jax` and `jaxlib` versions, and the backend profile
identity. Carbon's `observed_environment` does **not** currently capture the
first two; until it does, the campaign must capture them alongside.

## 4. How many repeats

| Arm | Minimum runs | Purpose |
| --- | --- | --- |
| CPU, fixed feature level | 2 | Confirms the baseline still holds in campaign conditions. |
| GPU, identical configuration | **2** | Separates GPU run-to-run variation from device attribution. |

**Two identical GPU repeats are the minimum that can distinguish anything.** With
one GPU run, a difference from CPU cannot be separated into "the device computes
differently" and "this workload is not deterministic on this device". Those have
opposite consequences, and one run cannot tell them apart.

### The sizing problem, stated plainly

The authorized envelope is **four attempts total, including failures, retries and
controls**. The minimum useful design above needs two GPU attempts. That leaves
two for every failure mode: an image that does not start, a driver mismatch, a
run that exceeds its deadline, a cleanup that cannot be confirmed.

> **Engineering's number: four is enough only if nothing fails. A first probe
> that tolerates one failure and still yields a comparable pair needs three GPU
> attempts; a campaign with any margin needs five or six.**

This is the open sizing decision §6 of the policy records. The recommendation is
to scope the batch explicitly as a **first probe** whose success criterion is one
comparable GPU pair, with an agreed follow-on if it fails, rather than to treat
four as a campaign that must produce a qualification.

## 5. What would constitute adequate evidence

Adequate evidence for qualifying **this one narrow profile**:

1. Two GPU runs under identical R0 identities produce **bit-identical**
   `checkpoint/state.npz`; and
2. the CPU arm at a fixed, recorded feature level reproduces the baseline; and
3. the CPU-to-GPU difference is characterised — not necessarily zero, but
   measured and reported, with the comparison procedure named; and
4. every run's environment is recorded to §3's completeness.

(1) is the load-bearing one. If the GPU cannot reproduce itself, nothing about
CPU-versus-GPU is interpretable.

## 6. What would constitute a negative result

A specification that cannot fail is not a specification. Any of these is a
negative result and should be reported as such rather than retried until it goes
away:

- the two GPU runs differ from each other;
- GPU output differs from CPU by more than any registered procedure would accept,
  with no registered procedure that accepts it;
- runs cannot be completed within the envelope, leaving no comparable pair;
- the environment cannot be recorded to §3's completeness, making the comparison
  uninterpretable.

A negative result **does not** authorize choosing a tolerance to convert it into
a positive one. MQ-008 explicitly rejects broadening hardware support by
loosening scientific tolerances.

## 7. What this specification does not establish

Even fully satisfied, it establishes qualification of **one** backend profile:
one device model, one driver version, one toolchain, one environment, one
workload shape, at the step count actually run.

It establishes nothing about: another GPU model or driver; contention effects,
which are a separate empirical question; cross-host CPU reproducibility, which
W3 shows is unresolved; the magnitude of divergence at realistic step counts,
which is unmeasured; or any other workload.

Widening is a further qualification, not an inference.

## 8. Cost

Zero paid spend. The batch is an existing authorization; this specification does
not expand it, and acceptance of this document is not authorization to spend it.
That remains the owner's decision.
