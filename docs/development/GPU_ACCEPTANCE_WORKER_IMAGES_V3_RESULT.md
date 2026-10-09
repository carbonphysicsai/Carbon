# GPU acceptance on worker-images-v3: RunPod RTX 4090 and A40

Status: DEVELOPMENT evidence, recorded 2026-10-09 by the Graphite Test executor. It is digest-equality evidence only. It is not a scientific qualification, a security acceptance, or a hardware-acceptance record; naming a device class as accepted remains the owner's decision ().

## Question

Does the released worker image, under the pinned determinism configuration, rebuild the same battery recipes to the same weights and predictions within a host and across two separate hosts, for JAX and PyTorch on each device class? Each device class is judged on its own and never compared with another.

## Setup

- Images (worker-images-v3, run 37855550264, main 22d535c94): accelerator , torch-gpu .
- Harness:  from main with #906 (), RunPod SECURE, two pods per backend, two fresh-interpreter repeats per recipe per pod, each pod running the released image directly.
- Recipes (rule in the A40 acceptance brief, section 2b, applied before any rebuild; run record sha256 ):  (20405 parameters),  (195829),  (1089845), and the PyTorch-only  (4204423).
- Pre-checks before any rebuild: the Carbon GPU probe and a driver-build match across the two pods of a backend.

## RTX 4090 ()

| Backend | Recipe | Within each host | Across hosts | Driver build | Weights digest | Predictions digest |
|---|---|---|---|---|---|---|
| jax | deeponet_t1500_w512_d3 | yes | AGREE | 580.159.04 | a505ef92188e | d370e41c829c |
| jax | mlp | yes | AGREE | 580.159.04 | de4a68712520 | 4e654f756f50 |
| jax | mlp_t1500_w64_d2 | yes | AGREE | 580.159.04 | 649c97b1677a | 1e2a0d25855f |
| pytorch | deeponet_t1500_w512_d3 | yes | AGREE | 580.159.04 | 8864b818d07a | 84a2f4b501a0 |
| pytorch | fno_defaults | yes | AGREE | 580.159.04 | 733866dd08a0 | e0ea370ae629 |
| pytorch | mlp | yes | AGREE | 580.159.04 | 1e1224caac60 | b275ee15e427 |
| pytorch | mlp_t1500_w64_d2 | yes | AGREE | 580.159.04 | 45432ee0155c | 2c6835d94cbf |

All seven cells agree within each host and across the two hosts. No replacements, no driver problems.

## A40 ()

| Backend | Recipe | Within each host | Across hosts | Driver build | Weights digest | Predictions digest |
|---|---|---|---|---|---|---|
| jax | deeponet_t1500_w512_d3 | yes | AGREE | 580.178.04 | a505ef92188e | d370e41c829c |
| jax | mlp | yes | AGREE | 580.178.04 | de4a68712520 | 4e654f756f50 |
| jax | mlp_t1500_w64_d2 | yes | AGREE | 580.178.04 | 649c97b1677a | 1e2a0d25855f |
| pytorch | deeponet_t1500_w512_d3 | yes | AGREE | 580.178.04 | 1748f3e2b78f | afaf5c17ab05 |
| pytorch | fno_defaults | yes | AGREE | 580.178.04 | bd836ef74d0a | b96115997122 |
| pytorch | mlp | yes | AGREE | 580.178.04 | a955efbf98de | 2373d2ea8a15 |
| pytorch | mlp_t1500_w64_d2 | yes | AGREE | 580.178.04 | 07573cd93e78 | 465619f7453b |

All seven cells agree within each host and across the two hosts on the second attempt. The first attempt agreed for PyTorch (drivers 580.178.04) but the JAX pair came up on differing driver builds (580.159.03, 580.159.04, 580.178.04) and the harness refused () without running a JAX rebuild; no deviation was recorded.

## Not established

- Datacenter and host location were not exposed by RunPod, so cross-datacenter agreement is not claimed.
- CPU-versus-GPU digests were not compared (the comparison input was empty); GPU digests are not comparable to the capability report's CPU  values.
- Only these four recipes, one seed, and two device classes were run. No tolerance was set or needed.
- H100 and Blackwell classes were not run.
