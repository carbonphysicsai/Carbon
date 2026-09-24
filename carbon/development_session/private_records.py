"""Private, bounded, canonical operator records.

Shared by the development grant path and the product surfaces, which is why it
lives here rather than in `research_admission`: reading an operator file is not
grant machinery, and a product surface must not need the grant module to read
its own configuration.
"""

from __future__ import annotations

import json

from .profile import canonical


def private_json(path):
    if (
        not path.is_absolute()
        or path.resolve() != path
        or not path.is_file()
        or path.stat().st_size > 65536
        or path.stat().st_mode & 0o077
        or path.parent.stat().st_mode & 0o077
    ):
        raise ValueError("private bounded operator record required")
    raw = path.read_bytes()
    value = json.loads(raw)
    if canonical(value) != raw:
        raise ValueError("canonical operator record required")
    return value
