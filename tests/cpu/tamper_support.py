"""A same-length mutation that cannot be a no-op.

`data[:-1] + b"x"` looks like a tamper and is one only when the final byte is
not already `0x78`. Where the mutated bytes are randomized - an encrypted
ciphertext, for instance - that is about one run in 256, and the failure is
silent in the worst direction: an integrity test that should report REJECTED
reports VERIFIED, and the assurance the test exists to provide is quietly gone.
A retry passes, so it reads as a flake.

That defect was diagnosed and repaired at one call site and survived at three
others, which is the argument for a named function rather than a fourth careful
expression. A constant cannot be passed to this; the replacement byte is derived
from the byte it replaces, so there is no way to call it and get the input back.
"""

from __future__ import annotations


def tampered_bytes(data: bytes) -> bytes:
    """`data` with its final byte flipped: same length, guaranteed different.

    Guaranteed because the new byte is `x ^ 1`, which differs from `x` for every
    possible byte. The property is established by construction rather than
    checked afterwards, so a caller cannot get it wrong by supplying a constant
    that happens to match.
    """
    if not data:
        raise ValueError("cannot tamper with empty bytes: there is no byte to change")
    return data[:-1] + bytes([data[-1] ^ 1])
