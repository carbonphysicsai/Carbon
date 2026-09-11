# Direct reference versus surrogate deployment baseline v0.1

**Status:** development diagnostic. No product fitness, deployment hardware, production latency, or Challenge reference configuration is qualified.

A surrogate only creates client acceleration value if it improves a declared requirement against a credible deployable baseline. The baseline should use the **cheapest reference/direct configuration that remains scientifically adequate for the client claim**, not an unnecessarily expensive qualification anchor.

In the smooth Burgers fixture, the same-method reference convergence study found that the 128-point Cole–Hopf configuration agreed with the 8,192-point anchor at roughly machine precision while running about 130x faster in the primary repeated timing run.

For 256 cases on the same CPU fixture:

| Reconstructed candidate | Surrogate prediction time | Candidate / 128-point direct-reference time | 8192-point anchor / candidate time |
|---|---:|---:|---:|
| I | 53.1 ms | 43.6x slower | anchor 3.0x slower than candidate |
| C1 | 21.2 ms | 17.4x slower | anchor 7.5x slower than candidate |
| C2 | 40.0 ms | 32.8x slower | anchor 4.0x slower than candidate |
| C3 | 15.7 ms | 12.9x slower | anchor 10.1x slower than candidate |

The direct 128-point reference took about 1.22 ms for the same 256-case batch. Under this CPU development fixture, every tested surrogate was therefore slower than the apparently converged direct method. A speedup claim measured only against the 8,192-point anchor would have been misleading for client deployment because that anchor was far more expensive than the routine computation needed on this easy population.

This is not evidence that learned surrogates lack value in other regimes. GPU inference, expensive industrial references, repeated-query workloads, geometry complexity, deployment constraints and different physical jobs can reverse the result.

## Carbon Fit rule

Before funding a surrogate-acceleration program:

1. map the reference/direct-method accuracy-cost frontier;
2. identify the cheapest configuration that remains scientifically plausible for the intended client claim;
3. benchmark that configuration as a deployable baseline on relevant hardware and workload;
4. compare full surrogate lifecycle and query cost against that baseline;
5. proceed on acceleration grounds only when the proposed construction can plausibly improve a declared client requirement.

A stronger/slower reference may still be required for qualification or audit. Its cost belongs to qualification/live evidence according to its role; it should not automatically become the deployment baseline used to advertise surrogate speedup.
