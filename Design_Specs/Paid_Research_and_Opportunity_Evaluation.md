# Paid Research and Opportunity Evaluation Contract

**Version:** 0.1 future implementation contract
**Status:** `SPECIFIED`; no product, price, entitlement, billing, execution, pilot, or commercial validation exists
**Decision:** `OWNER-EVIDENCE-RESEARCH-01`
**Tickets:** `G-PR0` through `G-PR5`; later advanced capabilities remain passive reservations

This companion extends the [Business Canon](../Business/Business_Canon.md) and [Commercial Operating Model](../Business/Commercial_Operating_Model.md) for a bounded research service. Evidence Audit remains Carbon's existing entry product; this design does not declare a new primary revenue source.

## 1. Gate order

```text
G-PR0 freeze pilot scorecard
-> G-PR1 entitlement, rights, quote, authorization
-> G-PR2 tenant campaign memory
-> G-PR3 isolated non-official research
   + G-PR4 retry-safe billing/spend control
-> G-PR5 run pilot and decide stop/iterate/expand
```

Implementation is not activation. Security, rights, deployment, price, and pilot activation remain owner gates. Interest, a declared budget, subscription, model suggestion, or worker availability cannot authorize spending.

## 2. Contract objects

Future quote/campaign records reuse the commercial engagement, rights, privacy, deliverable, and acceptance owners. A quote binds scope, eligible sources, deliverables, expiry, maximum cost, cancellation/refund terms, delegated authorization, and customer rights. A campaign binds tenant goals, requester-authorized context, experiment history, response/deliverable lineage, correction/update state, and cost ledger identities.

Funds use retry-safe reservation, debit, release, cancellation, and refund events bound idempotently to an authorized job. Contribution accounting is separate from official exam fees, frontier, treasury, or settlement.

Hosted research is non-official, tenant-isolated, and resource-isolated. It cannot become official evidence through relabeling. Any later use as reusable evidence needs explicit rights, evidence-use assessment, scientific provenance, and release review.

## 3. Pilot preregistration and measurement

Before paid-workflow implementation, `G-PR0` freezes baseline, sampling and measurement plan, success/stop criteria, and the utility/demand/economics/safety scorecard. Owners supply thresholds; no unsourced market target is invented.

Required measures include matched-total-spend research utility; time/cost to a useful decision; quote issuance, acceptance, and conversion; repeat campaigns/purchases; miner versus external demand; support burden; free-path health; leakage/safety; and contribution after execution, reference/truth, storage, inference, curation, payments, refunds, and support. Self-reported outcomes remain separate from Carbon measurements.

## 4. Opportunity register

| Opportunity | Buyer/user | Measurable value | Costs and rights | Owner/gate | Stop condition |
|---|---|---|---|---|---|
| customer-funded reusable evidence | customer first; later eligible users | useful decision plus rights-approved reuse | execution/reference/storage/curation; contract-specific reuse | G-PR1/3/5 + evidence-release owner | no utility, no reusable rights, unsafe leakage, or negative contribution |
| research-gap study | miners, agents, or customers | closes a preregistered gap | study cost, qualification and release rights | Port C governance; G only if customer-funded | gap not decision-relevant or study cannot be validly designed |
| guidance-effectiveness evaluation | research users and Carbon | prospective improvement versus baseline | measurement, follow-up, privacy | E-RI1 scientific owner | no prospective lift or unacceptable cost/risk |
| failure-demand analysis | researchers, support, product teams | fewer repeated unresolved failures; better resources | triage/curation; purpose-limited demand rights | E-D12 + Ports A/D | signal is manipulated, non-independent, or not actionable |
| later portfolio optimization | governance/research planning | prospective decision value under budget | model/evaluation/rights costs | post-E/G reservation | leakage, unstable calibration, or no prospective benefit |

Ports remain: A approved guidance/resources; B operations without candidate-specific treatment changes; C governed proposals; D independently qualified evidence services/products including failure feedback.

## 5. Isolation and evaluation

Separate logical services are not sufficient isolation. Acceptance saturates shared DB connections/locks, object throughput/quotas, network, KMS, queues, compute, caches, and telemetry. Official evidence capture receives reserved admission and degrades/fails closed according to its approved fault model before commercial workload can starve it.

Research usefulness is evaluated on held-out representative tasks with source grounding, abstention, counterevidence, cost/latency, and downstream decision quality—not answer volume. Advanced transfer, experiment-value, portfolio, and Research Scientist tools remain behind time-forward, lineage-aware prospective evaluation and leakage controls. Existing product/scientific qualification owners retain authority.
