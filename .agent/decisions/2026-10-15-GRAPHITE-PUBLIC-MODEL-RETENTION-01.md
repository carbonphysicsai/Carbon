# GRAPHITE-PUBLIC-MODEL-RETENTION-01

Working decision: preserve existing CPU/GPU programs and default outputs; wrap
the fixed public battery practice program only for an explicit local Graphite
test campaign, with its descriptor frozen into the campaign manifest. Reuse
safe NPZ state serialization and the carrier's existing bounded snapshot and
retained-byte accounting. Record every trial before compile/run; missing model
bytes are NOT_RETAINED, never inferred from a recipe or synthesized by refitting.

Implementation: carbon/battery/public_model_retention.py, research.py and narrow
campaign.py composition/launch wiring, plus focused tests. No standalone pod
collector change. Packets2/3 confirmed disjoint ownership; ScoreLab confirmed
state.npz reuse and that no dedicated Graphite intake already exists on main.

Rejected: changing old program bytes (historical identity drift), automatic model
upload/default retention (privacy/scope change), pickle/new serializer, winner-only
export (selection bias), or appending these models to the fixed18 cohort.
The sidecar is producer inventory, not scientific admission or security acceptance.
Root owns runtime/image provenance verification and actual extraction. Inference
from retained state must never silently refit. No reserved decision is selected.

Reversible by removing the optional local opt-in/composition binding; existing
campaigns retain their original interpretation. A superseding implementation
must change the opt-in/program version prospectively. Source author runs static
checks and remote CI only, per Root's host/test-dispatch separation.
