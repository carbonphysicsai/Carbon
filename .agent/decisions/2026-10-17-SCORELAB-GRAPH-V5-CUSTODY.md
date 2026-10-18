# ScoreLab graph custody variant (DEVELOPMENT)

The existing `public-model-custody-receipt.v5` and `public-model-entry.v5`
remain the common create-only, unscored bank records. Historical bundle role
manifests (`public-model-artifact-roles.v2`) keep their exact bytes and reader.
The graph path uses the distinct `public-model-artifact-roles.v3` manifest and
`graph-source-state.v1` header. Graph-only receipt and entry fields name the
source kind, role schema, and submission digest. The graph producer has no
original runtime-environment artifact: the graph role manifest excludes that
role and the environment and bundle-reference digests are null. Original
source, image, and worker evidence bytes retain their own hashes; construction
limits are not relabelled as runtime-environment evidence.

The graph writer checks the canonical Level 4 staging envelope, original
construction kit and recipe, inert state header, graph build receipt, measured
inference-v2 input/output and timing receipt, and the retained private attempt's
image/operation/control lineage. The private attempt remains in the producer
bank; no miner projection is added. An optional original terminal task receipt
is byte-retained but has no authority without a typed receiver check. The
writer never executes graph or model source, never runs a solver, and creates
no score, replay, qualification, or LIVE claim. A trusted Challenge and the
separate ScoreLab receiver remain required to interpret a benchmark result.
