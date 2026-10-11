# Anonymous public tariff observations

Retrieved 2026-10-11. Every row is a **fixed sourced observation: low = base =
high**, not a promise of future stock or invoice. Prices are listed before tax
and optional services; verify checkout treatment and actual stock before an
owner purchase. No login, account inspection, reservation or order occurred.

## Storage Box price feed

Official public product page binds BX11/BX21/BX31/BX41 to product keys
ROBOT_1333/1334/1335/1336. Its price component uses the
[official anonymous price JSON](https://www.hetzner.com/_resources/app/data/app/live_data_prices.json).
The feed was read at **2026-10-11 16:40:18 UTC**; FSN1 and HEL1 rows matched:

| Plan / allocated TB | EUR monthly | USD monthly | EUR hourly | USD hourly |
|---|---:|---:|---:|---:|
| BX11 / 1 | 3.20 | 4.00 | 0.0051 | 0.0064 |
| BX21 / 5 | 10.90 | 13.00 | 0.0175 | 0.0208 |
| BX31 / 10 | 20.80 | 24.00 | 0.0333 | 0.0385 |
| BX41 / 20 | 40.60 | 46.00 | 0.0651 | 0.0737 |

Capacity and included traffic: [product matrix](https://www.hetzner.com/storage/storage-box/).
These are the vendor's separate currency tariffs, not a currency conversion.

## Server Auction examples

[Official anonymous auction JSON](https://www.hetzner.com/_resources/app/data/app/live_data_sb.json)
read on 2026-10-11. A small explicit sample,
selected as the lowest monthly EUR offer for each named processor in that
retrieval; not a market percentile or guaranteed procurement list:

| Public offer ID / CPU | RAM | Disks as advertised | Host EUR monthly / hourly | Host USD monthly / hourly |
|---|---|---|---|---|
| 3086834 / i7-6700 | 32 GB | 2 × 512 GB SATA SSD | 64 / 0.1026 | 72 / 0.1154 |
| 3083608 / Ryzen 7 3700X | 64 GB | 2 × 1 TB SSD (NVMe in feed) | 103 / 0.1651 | 121.54 / 0.1948 |
| 3091086 / Ryzen 9 5950X | 128 GB | 3 × 3.84 TB datacenter NVMe SSD | 226 / 0.3622 | 251 / 0.4022 |

Each sampled row: setup **€0/$0**, IPv4 **€1.70/$1.90 monthly** or
**€0.0027/$0.0030 hourly**. Locations: first FSN1-DC1; second HEL1-DC6;
third HEL1-DC5. Prices are dynamic and offers can vanish. Do not infer 1 Gbit/s
application throughput from the port specification. A mirrored two-drive array
has approximately one drive's capacity before formatting, rather than their sum.
Three-drive capacity depends on the selected redundancy policy: HUMAN_INPUT.

## Object and VM tariffs

| Source | Observation | Decision limitation |
|---|---|---|
| [Hippius pricing](https://hippius.com/pricing) | PAYG $0.0060/GB-month, also $6/TB-month; plans 10 TB $53, 50 TB $245, 100 TB $465/month; egress included | Enterprise headline says $0.0045/GB while the 100 TB plan implies $0.00465. Do not choose the lower inconsistent figure; use consistent PAYG until quote |
| [B2 pricing](https://www.backblaze.com/cloud-storage/pricing) | $6.95/TB-month; free egress up to 3 × average stored bytes, excess $0.01/GB; first 10 GB storage free | Old $6/TB and Hippius's competitor calculator are not controlling current B2 prices |
| [B2 calls](https://www.backblaze.com/cloud-storage/transaction-pricing) | A/B/C free; D first 2,500/day free, then $0.004/10,000 | A request taxonomy remains; not all activity is universally free |
| [Hippius VM billing](https://docs.hippius.com/use/compute/billing) | $18/vCPU-month + $2.50/GB RAM-month + $0.10/GB disk-month; 730-hour monthly estimate; IPv4 $0.005/hour | Published default totals 32 vCPU, 128 GB RAM, 1,024 GB disk; no account entitlement checked; launches need balance for 24 hours |

Hippius per-second billing has a one-minute minimum, including while a VM is
stopped; asking for deletion ends billing. Its public-bandwidth page says free
for now, not a perpetual contract. These are vendor published terms and defaults,
not independently measured service behavior. Largest supported/provisionable VM,
region stock, root permissions for a particular image and uptime guarantee are
HUMAN_INPUT where not established by this read-only evidence.
