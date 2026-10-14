# PLT-30: PyTorch GPU practice through the shared carrier

Authority: Platform2 queue PLT-30; owner requires the shared JAX mechanism,
Launchpad review and host-owned GPU acceptance. Starting main
270d0b981fecec841994879b096c3d97b815a2ad.

KEEP existing pinned Torch CUDA worker, lock, profile, device/determinism checks,
registered v3 program, CPU implementations and all legacy JAX scope/program bytes.
REPAIR miner local setup/practice/carrier selection to recognize that exact worker,
use the existing Torch pins/runtime program and retain the same miner lane.
A prospective Torch battery scope names only pytorch; JAX-only scopes remain v1.
No change to scoring, hidden data, official admission, device-class comparison,
worker isolation/resources, driver readiness or qualification.

Add discriminating shared-route tests and a same-input cross-framework numerical
fixture. Exact dyadic float32 matrix arithmetic has a bit-exact expected answer;
its zero tolerance is an arithmetic fixture property, not a production tolerance.
Broader PyTorch training/scientific tolerances remain HUMAN_INPUT under
OWNER-PYTORCH-BACKEND-01. Real paired GPU/image installation/trial is HOST_BOUND;
no CPU fixture or skipped CUDA test closes it. Reuse existing fail-on-required-CUDA
Torch worker repeatability tests in the host handoff.

Plan: baseline existing scope/image/carrier controls; pure image/profile selector;
versioned Torch scope and existing program selection; local setup/carrier pin checks;
mock shared-route/refusal/history controls; real CPU JAX/Torch arithmetic parity;
canonical focused/subsystem validation; one main PR and bounded host handoff.
Remote-link GPU serving is not expanded. No provider/spend, actual GPU host check,
production tolerance, install/tag/deploy, keys, sealed material or qualification.

Expected paths: this ticket/decision; gpu_practice.py, battery_gpu.py,
battery/research.py, research_carrier.py, miner_launchpad/environment_setup.py;
new parity/route tests and a host handoff document. Fresh all-open-PR path scan
finds no overlap. Primary map SYSTEM/AGENT-EXECUTION; Hub retired. Root owns merge
after actual applicable exact-head CI/Merge gate, not the builder.
