# Transparent public-work cost model

Prices observed 2026-10-11; USD and EUR are separate tariff currencies, not an
exchange-rate conversion. Tax, options and operations are excluded unless named.
Source points have low = base = high. Workloads/utilization below are explicit
ASSUMPTION low/base/high scenarios, not Carbon measurements or confidence bands.
No provider has been rented or benchmarked here.

## Storage and downloads

Let S be average **billable** logical TB, including retained versions, and E be
monthly outbound TB. For decimal units used in the calculation:

`Hippius_PAYG_USD = 6*S` at its current included-egress tariff.

`B2_USD = 6.95*S + 10*max(0,E-3*S) + chargeable_calls`.

This conservatively omits B2's first 10 GB free storage; Class A/B/C requests
are now free, while specified Class D activity can charge. The average storage
allowance is byte-hour based, so a newly uploaded-and-immediately-downloaded
corpus need not receive three times its end-of-month size free. Read the actual
billing period. [B2 pricing](https://www.backblaze.com/cloud-storage/pricing),
[transaction schedule](https://www.backblaze.com/cloud-storage/transaction-pricing),
[Hippius tariff](https://hippius.com/pricing).

For Box, choose an allocated capacity tier containing S **and required free
space/snapshot headroom**; the monthly cap is payable even when partly empty.
Full-month tariffs below omit extra headroom deliberately. Each workload value
is a fixed scenario; the column sequence is low/base/high size, not cost CI.

| ASSUMPTION S (TB) | 0.25 | 1 | 5 |
|---|---:|---:|---:|
| Hippius PAYG, E/S 1 or 3, USD/month | 1.50 | 6.00 | 30.00 |
| Hippius PAYG, E/S 10, USD/month | 1.50 | 6.00 | 30.00 |
| B2, E/S 1 or 3, USD/month | 1.7375 | 6.95 | 34.75 |
| B2, E/S 10, USD/month | 19.2375 | 76.95 | 384.75 |
| Box tier before headroom, USD/month | 4.00 | 4.00 | 13.00 |
| Box tier before headroom, EUR/month | 3.20 | 3.20 | 10.90 |

ASSUMPTION capacity multiplier for versions/headroom low/base/high
**1.10/1.25/1.50**. At fixed 1 TB primary data all three need a larger-than-1-TB
Box, so the next 5 TB tier is $13/€10.90. At fixed 5 TB primary they need the
10 TB tier, $24/€20.80. If versions actually occupy extra bytes, S also grows
for PAYG: allocated free space and stored versions are different cost features.

Storage-only crossover, DERIVED and conditional on fitting the tier: a $4 Box
costs less than Hippius PAYG above **0.6667 TB** billable data, and less than
B2's storage line above **0.5755 TB**. The $13 Box crosses at **2.1667 TB** and
**1.8705 TB**, respectively. These fixed points ignore headroom, request costs,
support, transfer speed, redundancy and API requirements; they are not overall
value rankings.

## Compute, disk and utilization

Hippius VM published resource formula:

`monthly_USD = 18*vCPU + 2.50*memory_GB + 0.10*disk_GB`.

At fixed illustrative **16 vCPU / 64 GB / 640 GB**, DERIVED $512/month,
`512/730 = $0.701370/hour`; attached IPv4 adds $0.005/hour, yielding
**$0.706370/hour** and **$0.044148 per provisioned vCPU-hour**. This size fits
the published aggregate defaults if the rest of the account is empty; it is
not a confirmed available instance. There is no claim that these vCPUs equal
physical cores or another machine's solver throughput. Default quota and
24-hour balance requirement can block provisioning. [Billing and quotas](https://docs.hippius.com/use/compute/billing).

For a sampled auction offer, including its IPv4:

`rental = min(hourly_price * ceil(rented_hours), monthly_cap)` within the
applicable calendar-month billing period; crossing periods needs separate caps.
Setup is zero in the observed rows. Partial hours and powered-off rental still
count. [Robot billing](https://docs.hetzner.com/general/billing-and-account-management/cancellation/cancellations-robot/).

The sampled i7-6700 is four physical cores/eight threads and costs $0.1184 per
host-hour including IPv4: **$0.0296 per provisioned physical-core-hour** before
utilization. Its full-month $73.90 spread across an ASSUMPTION 730-hour month
is **$0.02531/core-hour**. That normalization is not its short-rental tariff.
[Intel specification](https://www.intel.com/content/www/us/en/products/compare.html?productIds=97123%2C88196),
[dated offers](PRICE_OBSERVATIONS.md).

At ASSUMPTION busy fraction low/base/high **0.25/0.50/0.80**, hourly i7 cost
per busy core-hour is **$0.1184/$0.0592/$0.0370**. Increasing utilization lowers
unit cost, so numerical cost low/base/high is **$0.0370/$0.0592/$0.1184**.
This omits time spent provisioning/administering it and compares neither speed
nor numerical adequacy. The 5950X sample has 16 physical cores/32 threads, but
its much larger RAM/SSD configuration has a different price. Its raw feed's
`CoreCount=1` is not a usable physical-core count; verify the named processor.
[AMD specification](https://www.amd.com/en/products/processors/desktops/ryzen/5000-series/amd-ryzen-9-5950x.html).

Use `total_cost / completed_admissible_public_cases` for a future measured
comparison. Required RAM/disk per worker, solver speed, concurrency, setup time
and useful utilization are HUMAN_INPUT. SMT is not assumed to double throughput.
Auction compute and disks share one bill: do not count the whole bill as both
storage savings and cheap compute.

## Owned/new local SSD

Existing free capacity: ASSUMPTION incremental rental **$0/$0/$0**, conditional
on available owned capacity; power, wear, host opportunity cost and backup remain.
No source or inspection establishes Carbon's free disk space.

New-device planning only, **not a current retail quote**: fixed illustrative
2 TB device, purchase low/base/high **€100/€200/€400**, amortization horizon
**24/36/48 months**, incremental power **2/5/10 W**, electricity
**€0.10/€0.20/€0.40 per kWh**, and monthly hours fixed **730/730/730**.
Do not combine all independent low inputs as a warranty. Joint low-cost scenario
uses €100/48 months and 2 W at €0.10; base €200/36, 5 W at €0.20; high €400/24,
10 W at €0.40. DERIVED device/power costs are **€2.23/€6.29/€19.59 per month**,
before host, replacement, backup and labor. Two mirrored devices roughly double
device capital and require a changed power estimate; that is not a second-site
backup. Owner should replace assumptions with a permitted machine inventory and
current quote before choosing a purchase.
