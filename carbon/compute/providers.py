# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""The rented-GPU providers a miner can choose, by name (C-MLP-03 slice 4).

Each is a `ComputeProvider` on the miner's own account, built from the
miner's key file. The key file stays on the miner's machine: an adapter reads
it per request through a `FileCredentialProvider` and only into its own
request header.
"""

from __future__ import annotations

from pathlib import Path

from .credentials import FileCredentialProvider

#: Provider name -> (display name, adapter factory).
PROVIDERS = {}


def _runpod(credentials):
    from .runpod import RunPodAdapter, UrllibTransport

    return RunPodAdapter(credentials, UrllibTransport())


def _lium(credentials):
    from .lium import LiumAdapter

    return LiumAdapter(credentials)


def _targon(credentials, *, state_dir, vm_image):
    from .targon import TargonAdapter

    return TargonAdapter(credentials, state_dir=state_dir, vm_image=vm_image)


PROVIDERS["runpod"] = ("RunPod", _runpod)
PROVIDERS["lium"] = ("Lium (subnet 51)", _lium)
PROVIDERS["targon"] = ("Targon (subnet 4), a VM over SSH", _targon)
#: Providers that rent a VM rather than run a container image: the miner
#: names a VM image, and the adapter keeps per-VM SSH keys in `state_dir`.
VM_PROVIDERS = frozenset({"targon"})


def provider_adapter(name, credential_file, *, state_dir=None, vm_image=None):
    """The named provider's adapter on the miner's own key file."""
    if name not in PROVIDERS:
        raise ValueError(f"unknown compute provider {name!r}")
    credentials = FileCredentialProvider(Path(credential_file))
    if name in VM_PROVIDERS:
        if state_dir is None:
            raise ValueError(f"{name} needs a directory for its VM keys")
        return PROVIDERS[name][1](credentials, state_dir=state_dir, vm_image=vm_image)
    return PROVIDERS[name][1](credentials)
