"""The tamper helper's guarantee, checked over every byte rather than one.

The defect this replaces failed for exactly one terminal byte in 256, so an
example-based test would have passed against it. These assert the property over
the whole domain, which is the only check that distinguishes the two.
"""

import pytest
from tamper_support import tampered_bytes


@pytest.mark.parametrize("terminal", range(256))
def test_the_mutation_differs_for_every_possible_terminal_byte(terminal: int) -> None:
    """`data[:-1] + b"x"` is a no-op at 0x78; this must be a no-op at nothing."""
    original = b"\x00\x01payload" + bytes([terminal])
    assert tampered_bytes(original) != original


@pytest.mark.parametrize("terminal", range(256))
def test_length_and_prefix_are_preserved(terminal: int) -> None:
    """Same-length and same-prefix: the change is exactly one byte, the last.

    Length matters because several of these tests feed the result to a decoder
    that would reject a short buffer for the wrong reason, and the test would
    then pass while proving something else.
    """
    original = b"\x00\x01payload" + bytes([terminal])
    mutated = tampered_bytes(original)
    assert len(mutated) == len(original)
    assert mutated[:-1] == original[:-1]


def test_a_single_byte_is_still_tamperable() -> None:
    assert tampered_bytes(b"\x78") != b"\x78"
    assert len(tampered_bytes(b"\x78")) == 1


def test_empty_input_is_refused_rather_than_returned_unchanged() -> None:
    """There is no byte to change, so returning the input would be a silent no-op."""
    with pytest.raises(ValueError):
        tampered_bytes(b"")


def test_the_replaced_expression_really_was_a_no_op_at_0x78() -> None:
    """The diagnosis, asserted rather than taken on trust.

    Kept because it is the reason this helper exists: it shows the old form
    silently returning its input for one byte value in 256, which is what made
    the failure look like a flake.
    """
    no_ops = [t for t in range(256) if (bytes([t])[:-1] + b"x") == bytes([t])]
    assert no_ops == [0x78]
