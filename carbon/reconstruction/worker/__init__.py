# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""Pinned CPU-only DEVELOPMENT worker around the C-02 adapter.

The package deliberately has no eager public imports. This keeps ordinary
``carbon.execution`` and ``carbon.reconstruction`` imports free of Docker and
optional numerical runtime side effects.
"""
