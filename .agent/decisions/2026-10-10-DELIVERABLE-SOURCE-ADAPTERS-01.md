# DELIVERABLE-SOURCE-ADAPTERS-01

Ticket DELIVERABLE-ADAPTERS-01, reversible working engineering decision.

Add policy aliases motor, cooling-cell and f02, not runtime IDs. Reuse #966;
extend its extraction with explicitly allow-listed scalar JSON pointers for
schema/family-matched public aggregate reports/laws. Missing/wrong-schema,
ambiguous/nonfinite/wrong-type sources become extraction gaps, never zero
measurements. Do not add arbitrary JSON paths from a caller or copy source
objects into a dossier. The old battery adapter and NASA factor fact mapping
stay unchanged; missing battery-named facts are GAP for the new families.

Keep historical counted motor/cooling results clearly separate from current
robot-joint/case-plane packets, and proposed f02 registration separate from
measured adequacy. Point reproductions are SOURCED, not uncertainty estimates.
Manual acceptance, D01–D07/D09/D10 completion, IP and scientific credibility
remain HUMAN_INPUT. No dossier completeness promotes qualification.

Alternatives rejected: broad artifact scanning, a parallel renderer, copying
battery evidence into other families, and inferred physical performance from
packet requirements. Supersede this file, source policy and scalar extractor
if a lead changes the mapping. Notify #643; no scientific interface changes.
