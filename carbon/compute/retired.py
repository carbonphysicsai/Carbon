"""The rented-GPU route is retired (OWNER-MINER-COMPUTE-LINK-ONLY-01).

C-MLP-03 slices 4 and 4b rented a GPU per practice trial on the miner's own
RunPod, Lium or Targon account, with the miner's provider key: Carbon created
the pod or VM, read the balance and price, terminated it and read its charge.
The owner retired that on 2026-10-02. Carbon does not rent, stop or bill
compute; a miner starts and stops their own machine, and Carbon only connects
to one the miner already runs.

What a miner may still hold from that route is refused by name, never
translated into something else:
- a runner profile whose runtime declares `rented_gpu` or whose paths name a
  `compute_credential`;
- a setup request choosing `rented-gpu`;
- a frozen campaign whose runtime declares `rented_gpu`, refused before any
  network or SSH call.
"""

from __future__ import annotations

#: The one code every retired rented-GPU input is refused with.
RENTED_GPU_RETIRED = "rented_gpu_retired_connect_your_machine"
#: The setup choice and runtime key the retired route used.
RENTED_CHOICE = "rented-gpu"
RENTED_RUNTIME_KEY = "rented_gpu"
#: What the miner does next. Carbon never contacts the provider to do it.
NEXT_STEP = (
    "Carbon no longer rents, stops or bills compute with your provider key. "
    "Start and stop your machine yourself; check your provider console for "
    "leftover pods, VMs or SSH keys named carbon-... and remove them; revoke "
    "the provider key you gave Carbon."
)


class RentedComputeRetired(ValueError):
    """A retired rented-GPU input, refused by name."""

    def __init__(self):
        super().__init__(RENTED_GPU_RETIRED)
        self.code = RENTED_GPU_RETIRED
        self.next_step = NEXT_STEP


def declares_rented(runtime) -> bool:
    """Whether a runtime (a profile's or a frozen manifest's) names the
    retired rented GPU."""
    return isinstance(runtime, dict) and RENTED_RUNTIME_KEY in runtime


def refuse_rented(runtime) -> None:
    """Refuse a runtime that declares the retired rented GPU."""
    if declares_rented(runtime):
        raise RentedComputeRetired()
