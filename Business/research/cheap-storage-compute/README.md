# Cheap public storage and working compute

**Research recommendation, 2026-10-11; no procurement or policy adoption.**

Use **already available local SSD as the working cache**, and **Storage Box for
low-cost remote files/backups** when SFTP/Borg/rsync is sufficient. Consider
**Hippius S3 for public object distribution and frequent downloads**, with B2
as an independent-provider alternative. Rent a Server Auction machine when
its **compute and local disk** will be used together; its sampled current
prices do not justify it as the cheapest storage-only service.

Fresh anonymous vendor observations, fixed low/base/high at retrieval:

| Route | Published point | Main implication |
|---|---|---|
| Storage Box | 1 TB €3.20 / $4 monthly; 5 TB €10.90 / $13; unlimited traffic | Cheap allocated file storage; limited SSH cannot execute uploaded scripts |
| Hippius S3 | $6/TB-month pay-as-you-go, egress included | Useful object API; no full-plan commitment needed for a small corpus |
| Backblaze B2 | $6.95/TB-month; egress up to 3 times average stored data free, then $0.01/GB | Competitive at modest downloads; repeated full remote reads can dominate cost |
| Auction sample | i7-6700, 32 GB, two 512 GB SSDs: $73.90/month including IPv4; 3700X, 64 GB, two 1 TB SSDs: $123.44 | Full root and compute, but mirrored usable disk is roughly one drive, before filesystem overhead |
| Hippius CPU VM | Derived 16 vCPU / 64 GB / 640 GB: $512/month plus IPv4 | Published default account quotas matter; not equivalent throughput to 16 physical cores |
| Existing local SSD | ASSUMPTION incremental rental $0/$0/$0 | Conditional on owned free capacity; power, wear, backup and host compute remain |

Sources and timestamped quote rows are in [PRICE_OBSERVATIONS](PRICE_OBSERVATIONS.md).
Currencies are kept separate; tax and optional services are additional. Offers
can disappear and actual account approval was not checked. Storage capacity,
durability, concurrency and compute are not interchangeable products.

The recommendation changes with access pattern. At an **ASSUMPTION fixed 1 TB
stored**, B2 downloads of **1/3/10 TB per month** cost **$6.95/$6.95/$76.95**,
before the small free-storage allowance. Hippius PAYG is $6 in these tariff
scenarios; a 1 TB Box is $4. This is a bill calculation, not equivalent service
quality or a throughput benchmark. Keep hot data local to avoid repeatedly
paying and waiting for remote reads. [Cost model and sensitivities](COST_MODEL.md).

Hippius's enterprise headline and plan price disagree; use the consistent PAYG
rate until an owner obtains a quote. Its confidential-compute claims are vendor
claims, not Carbon custody acceptance. Every route here is restricted to public,
rights-cleared, non-sensitive data; this proposal does not move sealed work.

Next owner choices: required API and corpus size, monthly download volume,
existing cache capacity, independent-copy requirement and compute utilization.
A public-only restore/throughput check is proposed in [COMPARISON](COMPARISON.md),
not run. No source establishes a provider's actual Carbon throughput today.
