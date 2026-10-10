## 2026-10-09 — OWNER-GPU-DEVICE-CLASSES-01: the A40 and the RTX 4090 are accepted for validator GPU scoring on testnet

**Authority.** The owner, directly in the Carbon Validator session,
2026-10-09: "I accept gpu:rtx4090 for validator GPU scoring on testnet, and
gpu:a40 for PyTorch and JAX". Asked which frameworks the RTX 4090 covers,
they chose "JAX and PyTorch".

**Decided.** `hardware_acceptance.ACCEPTED_DEVICE_CLASSES` (VALIDATOR-27)
admits these two classes. Each is the exact `nvidia-smi` name that the host
device record binds, and each is accepted under both GPU profiles:

| Device class | JAX (`carbon_jax_cuda13_nvidia_development_v1`) | PyTorch (`carbon_torch_cuda13_nvidia_development_v1`) |
|---|---|---|
| `NVIDIA A40` | accepted | accepted |
| `NVIDIA GeForce RTX 4090` | accepted | accepted |

A battery validator deployment with `"device": "gpu"` on such a host
therefore scores on it. Its scores are labelled `gpu:<device kind>` and are
never ranked with CPU scores (`rebuild_identity`). Every other class stays
refused (`evaluation_device_class_not_accepted`).

**Scope:** testnet, enforced. Each entry names its networks (`testnet`), and
`require_accepted` refuses any other network, and an unknown one, at the
deployment and again before each GPU run. Any other network needs a new owner
record.

**Not decided here:**
- the determinism values;
- any other GPU class;
- security qualification of the GPU lane;
- a GPU producer or bank.
