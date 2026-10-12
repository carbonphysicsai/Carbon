# In-house effort-cost scenario

The public sources give compensation, not a measured CAE team's study invoice. This is an **ASSUMPTION transfer model** for US engineering labor; specialist ML, electrochemistry, acoustics and independent-review rates may differ. It cannot determine Carbon's selling price or a customer's willingness to pay.

[BLS mechanical-engineer pay](https://www.bls.gov/ooh/architecture-and-engineering/mechanical-engineers.htm), May 2025, reports median **USD 104,110/year**, with lower/upper-decile boundaries **73,990 / 164,340**. These are separate sourced statistics; choosing them as low/base/high scenario salaries is ASSUMPTION, not an uncertainty interval for a specific team.

[BLS private-industry compensation](https://www.bls.gov/charts/employer-costs-for-employee-compensation/costs-per-hour.htm), June 2026: total **USD 46.89/hour**, wages **32.82**, benefits **14.07**. [ECEC release](https://www.bls.gov/news.release/ecec.htm) reports paid leave **3.54/hour**. These cover private industry broadly, not engineers specifically.

To avoid counting paid leave both as a benefit and lost productive hours, use:

**non-leave compensation multiplier = (46.89 − 3.54) / 32.82 = 1.320841…**

**productive labor cost/hour = annual salary × multiplier / productive annual hours.**

Productive annual hours **ASSUMPTION 2,000 / 1,800 / 1,600** across low/base/high workload scenarios. Derived labor rates: **USD 48.86 / 76.40 / 135.67 per productive hour** (rounded; exact calculations in [evidence.json](evidence.json)). This removes the leave-cost numerator component and incorporates time loss in the denominator; utilization assumptions must be replaced with the team's actual accounting. Broad-industry benefit transfer is a further assumption.

Optional operating overhead multiplier **ASSUMPTION 1.10 / 1.25 / 1.50** produces **USD 53.75 / 95.49 / 203.50 per hour**. This is an unverified facilities/management scenario. Add solver/software/compute/data/testing **only if not already represented in overhead**; record exclusions to prevent double charging. Use labor-only below.

| Scenario study | ASSUMPTION hours L/B/H | Derived ASSUMPTION internal labor USD L/B/H, rounded |
| --- | --- | --- |
| Battery | 80 / 240 / 640 | 3,909 / 18,335 / 86,827 |
| Motor | 64 / 160 / 400 | 3,127 / 12,223 / 54,267 |
| Burst thermal | 48 / 120 / 320 | 2,345 / 9,168 / 43,413 |
| AI-chip cooling | 64 / 200 / 480 | 3,127 / 15,279 / 65,120 |
| Silencer | 80 / 240 / 640 | 3,909 / 18,335 / 86,827 |
| Warpage, usable customer data already supplied | 160 / 400 / 1,200 | 7,818 / 30,558 / 162,800 |

This table uses the same illustrative effort as [job budgets](JOB_OFFERS.md), not independently observed buyer study sizes. Internal labor, external supplier rate and a reusable product fee have different scopes; their difference is not Carbon's gross margin. Salary percentiles also do not measure independent scientific expertise or review independence.

Before using the model in a quote, replace the salary/benefit/utilization transfer with buyer or Carbon receipts, measure each stage, add missing direct costs explicitly, and preserve unknown upper cost/time where reference/data readiness is unresolved. The [existing quote research](../intake-spec-and-quote-model/INTAKE_AND_QUOTE.md) has not earned calibrated price or duration forecasts from the sparse rehearsal records.
