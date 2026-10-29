# Complete immutable-image inventory for admitted library children

Status: delegated bounded engineering repair; validation pending.

The owner-directed real public miner install exposed an incomplete readiness
query. On exact prepared M2 `27460f0e47a72ee5a0aab88e3d9146a7fa3915a3`, the new
owned cache had 132 entries passing the existing current-parent, receipt,
context and staged-material validators, while the ordinary image listing
contained none of their child IDs. Direct immutable-ID inspection confirmed
the sampled newly built children and their exact current parent/bundle labels;
the complete all-image listing contained them. A full-set read-only check is
recorded separately and is required before claiming the entire observed set.
No old/global cache or hidden exam material was used.

The shared `present_library_worker_images` query used the default image list,
which omits intermediate and untagged images. Docker documents `--all` as the
complete inventory: <https://docs.docker.com/reference/cli/docker/image/ls/>.
This is `IMPLEMENTATION_LAG` in discovery, not a device/version compatibility
exception or scientific decision.

Repair that existing query with the standard `--all` option. Keep the exact
admitted-ID intersection, strict full-digest parsing, immutable inspection
equality/cardinality, bounded CLI output and at most two metadata calls. Missing
or unknown metadata still cannot establish readiness. The shared miner,
receiver and explicit owner recovery callers use this same observer; none
starts a build merely by reading status. Do not tag images, rewrite receipts,
weaken context/material checks or change setup routing in this repair.

The baseline exact-893 canonical family passed 432 tests in 151.56 seconds,
including both affected cache and receiver modules, before edits. New synthetic
regressions distinguish default-visible images from hidden untagged/intermediate
children, deduplicate exact IDs, exclude a truly missing child and retain the
single-call empty-selection path. Existing unknown/malformed/partial metadata
and owner recovery tests remain intact, with only their list-command fixture
expectations updated. Source/worker package identity changes require honest
new-source artifacts; this grants no scientific, security or launch acceptance.

Hub impact: no Hub edit under the owner's frozen-Hub instruction. Existing
runtime/readiness placement and authority boundaries remain accurate. This
branch touches no scoring producer values, admission, model or protected data.
