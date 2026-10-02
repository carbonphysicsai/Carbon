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


PROVIDERS["runpod"] = ("RunPod", _runpod)
PROVIDERS["lium"] = ("Lium (subnet 51)", _lium)


def provider_adapter(name, credential_file):
    """The named provider's adapter on the miner's own key file."""
    if name not in PROVIDERS:
        raise ValueError(f"unknown compute provider {name!r}")
    return PROVIDERS[name][1](FileCredentialProvider(Path(credential_file)))
