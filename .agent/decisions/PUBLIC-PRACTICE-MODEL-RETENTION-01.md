# PUBLIC-PRACTICE-MODEL-RETENTION-01 working decision

Status: prospective engineering candidate; no runtime adoption or qualification.

The normal battery campaign already freezes an optional public model retention
descriptor, and its practice runner already has an accounted snapshot and
private producer inventory. Reuse those seams for `agent=autonomous` with an
explicit v2 descriptor (`PUBLIC_AUTONOMOUS_TEST`). The accepted campaign
implementation revision must equal its declared source commit. The default
remains no retention; existing Graphite v1 descriptors, programs, inventory,
and artifacts retain their schemas and bytes.

The retained program only wraps the pinned public battery practice stage, stores
bounded `state.npz` from `recipes.state_bytes`, and binds recipe, image, public
input, fit, prediction, runtime, and source provenance in a sidecar. The
existing `recipes.model_from_bytes` reads NPZ with `allow_pickle=False` and
supports the compiler's MLP/DeepONet JAX/PyTorch and FNO/PyTorch state families.
ScoreLab ingestion remains a separate receiver action. Historical campaigns
and the frozen 18-fit ScoreLab cohort are not migrated.

Canonical tests and normal release/adoption remain required before Product
uses this path for new model-producing GPU trials. No host run is performed by
this source candidate.
