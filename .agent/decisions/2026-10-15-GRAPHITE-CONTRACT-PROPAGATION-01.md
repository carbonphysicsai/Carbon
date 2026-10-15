## 2026-10-15 — GRAPHITE-CONTRACT-PROPAGATION-01: reuse contract-bound candidate construction in agent SELECT

Classification: IMPLEMENTATION_LAG. The actual agent SELECT path discards the
campaign's immutable construction binding while the manual freeze and submit
paths enforce it. Repair selection, not the contract registry or submit gate.

KEEP the existing compiler, practice requirement, construction candidate builder,
envelope validation and pre-sign guards. WRAP agent selection with trusted campaign
context so it uses those mechanisms before a candidate is written. Base-only
campaigns retain the existing builder. A plain recipe within a wider contract is
accepted and labelled descriptively; graph use requires its actual staged envelope.

Expose the frozen construction contract in campaign observations. Do not edit
published Graphite role prompts or reinterpret previously frozen candidate records.
Provider/model/runtime/image and test-budget changes are separate Root execution work.
