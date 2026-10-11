# Cost and elapsed-time scenarios

This is arithmetic on public tariffs and labelled assumptions, **not measured solver throughput or a quote**. Sources and exact public price observations are in [the comparison](COMPARISON.md) and [JSON](price-observations.json).

Define `J` as useful worker CPU-hours **on the specific advertised machine/thread basis**. Let `c` be allocated worker slots, `u` the useful occupancy fraction, `r` the restart/replay multiplier, `p` the price per billed slot-hour, `S` total setup fees for the fleet, `F` storage/network/idle provisioning charges. Then:

```text
billed fleet slot-hours = J * r / u
compute cost = p * J * r / u + S
job cash cost = compute cost + F
compute wall hours = J * r / (c * u)
elapsed delivery time = account/stock/image delay + compute wall time + output/closeout time
```

All occupancy and replay values are **ASSUMPTION low/base/high scenarios**, not confidence intervals: `u=0.90/0.75/0.50`, `r=1.00/1.10/1.40`. The associated inflation `r/u=1.1111/1.4667/2.8000` is DERIVED. Replay includes job/worker failure; on Spot, it also covers evictions. It is not a measured interruption rate. Add `F=$10/$25/$100` **ASSUMPTION** per job for storage, transfer and billed setup/idle time; unusually large data or long-lived retained snapshots can exceed this. Tax, paid support and engineering labor excluded. A closed run ledger must replace these assumptions later.

## Per-worker tariff inputs

| Route | `p` low/base/high in USD per billed worker-hour | Basis |
|---|---|---|
| Robot AX162 | 0.006212 / 0.012054 / 0.016562 per **thread** | ASSUMPTION short-rental hourly rate = published monthly tariff / **624 billing hours** / 96 threads; 624 is an explicit pricing-model assumption, not a confirmed Robot divisor. Uses limited / regular -1 / regular -2 dollar tariffs. Actual hourly checkout price is HUMAN_INPUT. `S=$39/$359/$494` **per newly acquired host** from those tariff scenarios. |
| Scaleway I520 | 0.017084 / 0.018711 / 0.020339 per thread | Observed €1.562/96, converted with **ASSUMPTION USD/EUR=1.05/1.15/1.25**. No live FX claim. Hourly setup `S=0`; monthly commitment fee excluded from an hourly rental. |
| AWS C7a | 0.010000 / 0.0209375 / 0.051300 per **full core** | Low and high are ASSUMPTION price scenarios; base is observed c7a.48xlarge Spot $4.02/192. High is a budget fallback assumption, **not independently verified On-Demand pricing**. Owner should obtain an actual On-Demand fallback quote. |
| Azure F64as_v6 | 0.010000 / 0.014396984 / 0.068296875 per full core | Low ASSUMPTION; base observed Spot; high observed On-Demand fallback. |
| Azure DC96as_v5 SNP | 0.007000 / 0.009077302 / 0.043000 per thread | Low ASSUMPTION; base observed Spot; high observed On-Demand fallback. Subscription/zone Spot support and stock unverified. |
| GCP C3D | 0.009000 / 0.014000 / 0.060000 per thread | Entire range ASSUMPTION; no exact region/SKU price extracted. This must not be described as a current Spot quote. |
| Vultr VX1 | 0.030000 / 0.030000 / 0.030000 per thread | Observed $5.76/192, before required block storage. Fixed observed tariff, not forecast. |
| Akamai G8 compute | 0.033750 / 0.033750 / 0.033750 per advertised vCPU | Published $2.16/64, before egress. Physical-core throughput equivalence remains HUMAN_INPUT. |

## What two job sizes could cost

Numbers are DERIVED **scenario costs**, rounded to cents for arithmetic reproducibility, not price accuracy. They include compute and specified setup fees, exclude `F`. They are **not equal-work performance rankings**: thread and full-core rows cannot be converted without measured case timings on those machines.

| Route / fleet | J=200 low/base/high USD | J=5,000 low/base/high USD |
|---|---|---|
| Robot AX162, newly acquired **one host** | 40.38 / 362.54 / 503.27 | 73.51 / 447.40 / 725.86 |
| Robot AX162, newly acquired **two hosts** | 79.38 / 721.54 / 997.27 | 112.51 / 806.40 / 1,219.86 |
| Scaleway I520 hourly | 3.80 / 5.49 / 11.39 | 94.91 / 137.22 / 284.74 |
| AWS C7a | 2.22 / 6.14 / 28.73 | 55.56 / 153.54 / 718.20 |
| Azure Fasv6 | 2.22 / 4.22 / 38.25 | 55.56 / 105.58 / 956.16 |
| Azure SNP | 1.56 / 2.66 / 24.08 | 38.89 / 66.57 / 602.00 |
| GCP C3D | 2.00 / 4.11 / 33.60 | 50.00 / 102.67 / 840.00 |
| Vultr VX1 | 6.67 / 8.80 / 16.80 | 166.67 / 220.00 / 420.00 |
| Akamai G8 | 7.50 / 9.90 / 18.90 | 187.50 / 247.50 / 472.50 |

The two-host Robot row includes **two setup fees**. Holding an already acquired server makes setup sunk rather than charging it to every job; do not subtract it from a new acquisition decision. Billed-hour rounding and monthly caps need the actual invoice rule. At these particular job durations the hypothetical hourly compute amounts are below the published monthly caps, so no cap reduction was applied. Robot's unconfirmed hourly divisor is a material cost-model gap.

OVH is a different model: the published SCALE-A8 monthly tariff is €1,199.99, normalized at **ASSUMPTION 730 hours/month** to DERIVED €0.008562 per physical-core-hour at full occupancy (192 cores). At **ASSUMPTION USD/EUR=1.05/1.15/1.25** that is $0.008990/$0.009846/$0.010702. These are utilization economics, **not purchasable hourly rates**. A short newly rented job may owe the full monthly bill, plus unknown setup/options. Monthly cash low/base/high = DERIVED $1,259.99/$1,379.99/$1,499.99 for this same euro tariff and FX range, **plus HUMAN_INPUT setup/options**. [OVH official tariff update](https://blog.ovhcloud.com/en/posts/dedicated-servers-pricing-update-h2-2026/).

For GCP SNP/TDX use `p = ordinary_VM_p + confidential_vCPU_surcharge + GiB_per_vCPU * confidential_memory_surcharge`. A **4 GiB/vCPU example** adds On-Demand $0.0042246 (SNP) or $0.0052202 (TDX) per slot-hour, and Spot $0.0006696 or $0.0017746, respectively. These are DERIVED from the [CVM price table](https://cloud.google.com/confidential-computing/confidential-vm/pricing), **not total CVM prices**. Native VM shape memory units and rates must match the actual configuration; no single SNP/TDX fleet price is quoted without a base-SKU quote.

## Time and capacity sensitivity

| Useful CPU-hours on matched worker basis | 192 workers, low/base/high compute hours | 48 workers, low/base/high compute hours |
|---|---|---|
| 200 | 1.16 / 1.53 / 2.92 | 4.63 / 6.11 / 11.67 |
| 5,000 | 28.94 / 38.19 / 72.92 | 115.74 / 152.78 / 291.67 |

These are DERIVED from the assumptions above, excluding first-run delays. The expensive endpoint cannot honestly promise a few hours at the requested concurrency. For an owner deadline **ASSUMPTION example 24 hours**, 5,000 hours needs DERIVED `ceil(5000*r/(24*u)) = 232/306/584` comparable workers. That exceeds the owner's 200-vCPU envelope even in the low scenario.

**Physical-core ledger:** two AX162 hosts have 96 physical cores even though they expose 192 SMT threads. If the job's 5,000 CPU-hours means independent full-core-hours, use `c=96`, not 192: ideal 52.08 hours; scenario 57.87/76.39/145.83 hours. One C7a.48xlarge has 192 full cores, so the earlier 192-worker table applies on that full-core basis. SMT speedup, generation effects, memory bandwidth and solver license/thread behavior remain **HUMAN_INPUT measured throughput**; no doubling of scientific throughput is assumed.

**RAM test:** `concurrent_cases <= floor((usable_RAM - host_reserve)/peak_RAM_per_case)`, and `workers <= concurrent_cases * threads_per_case`. Both reserve and peak case RAM are HUMAN_INPUT. A 192-core bare-metal base with 128 GB is not automatically able to run 192 reference cases simultaneously. Measure on a public-only case under the infrastructure owner's authorization; research did not run it.
