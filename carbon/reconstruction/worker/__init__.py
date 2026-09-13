"""Pinned CPU-only DEVELOPMENT worker around the C-02 adapter.

The package deliberately has no eager public imports. This keeps ordinary
``carbon.execution`` and ``carbon.reconstruction`` imports free of Docker and
optional numerical runtime side effects.
"""
