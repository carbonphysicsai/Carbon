# PLT30-D1: reuse the existing Torch worker on the miner carrier

TORCH-GPU-01 already supplies the pinned CUDA image, exact lock, device checks
and determinism. TORCH-POD-01 already supplies its v3 battery program. The
missing miner path rejects that image and advertises JAX-only GPU practice.
Reuse those exact artifacts; select the worker backend from its registered
lock and keep image-label/toolkit verification in the shared C-03 carrier.

Legacy generic is_gpu_image remains JAX-only, so Burgers and existing remote
routes do not gain a Torch backend. Battery local practice explicitly serves
the sibling worker through a prospective v2-torch scope advertising pytorch
only. Its JAX scope/program bytes remain v1. The validator's acceptance gate,
device-class separation, isolated miner role and host readiness are unchanged.

The setup checks Challenge scope before host preparation and verifies the
selected worker's actual profile/lock labels. CPU or unknown workers and the
wrong recipe backend refuse before dispatch. Runtime observations remain what
the worker reports; a synthetic CPU observation is not rewritten as GPU proof.

Same-input parity uses dyadic float32 matrix arithmetic whose products and
four-term sums are exactly representable. Bit-exact equality is a bounded
arithmetic fixture property, not an invented training/scientific tolerance.
OWNER-PYTORCH-BACKEND-01 broader tolerances remain HUMAN_INPUT. Each real GPU
worker must execute the required-CUDA version on the host; no skipped or CPU
run establishes that result. No new image installation, host run or qualification.

Primary map SYSTEM/AGENT-EXECUTION; Hub retired under OWNER-DX-03.
