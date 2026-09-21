"""Is this the declared execution environment? Answered without guessing.

A run that executes in the wrong environment produces numbers from a different
stack and looks correct in every respect except the numbers. Under `docker run`
that could not happen quietly: the image was named by digest in the command and
the daemon enforced it. On a rented pod there is no daemon - the image is
whatever was selected at provisioning, and a tag instead of a digest resolves to
something else silently.

So the check has to happen in-process, and it has two hard limits worth stating
before the code rather than after.

**It cannot compare the image digest.** A container cannot read its own: labels
and digests are registry and daemon metadata, not filesystem. What it compares
are the *properties the digest was pinning* - interpreter, `jax` and `jaxlib`
versions, the CUDA line. That catches the realistic failure and establishes
nothing about byte identity with a published image, and every record it produces
says so in those words.

**Some properties cannot be read at all.** The CUDA version readers are optional
and vary by plugin build. An absent one is `None`.

`None` is not a mismatch, and the distinction is the whole point of this module.
Refusing on it would convert *"could not check"* into *"is wrong"* - the same
error, mirrored, as converting *"could not observe"* into *"nothing was there"*,
which is why the numerics record separates `OBSERVED` from `UNAVAILABLE`. The
rule underneath both is that **unknown must not become a definite claim**, and it
breaks in opposite directions depending on which way you face:

    observing   "can't see"  must not become  "nothing there"
    verifying   "can't check" must not become  "mismatched"

Each looks correct in isolation, which is how a codebase ends up holding one and
violating the other. So an unreadable property is reported as unverifiable, the
run proceeds, and the record carries what was checked and what was not.

**And one case the mirrored rule does not cover.** If *nothing* is verifiable,
the guard is inert exactly where it is most needed: an unfamiliar image whose
readers all return `None` produces no mismatch, and the run proceeds behind a
record that honestly says nothing was checked. "Four of five verified" and "none
verified" are different states, so `nothing_was_verified` reports the second as
its own condition rather than letting it pass as an ordinary incomplete check.
"""

from __future__ import annotations

#: Properties compared directly against the profile's declared values.
DECLARED_PROPERTIES = ("python", "jax", "jaxlib")

NOT_A_DIGEST_CHECK = "declared properties only, NOT the image digest"


def environment_problems(
    *,
    declared: dict,
    found: dict,
    cuda_version: object,
) -> tuple[list[str], list[str], list[str]]:
    """Compare a running environment against a declared profile.

    `declared` is a profile document; `found` maps each name in
    `DECLARED_PROPERTIES` to the running value; `cuda_version` is the numerics
    record's reading, which may be `None`.

    Returns `(mismatched, unverifiable, verified)`. A caller refuses on the
    first, records the second, and must check that the third is non-empty -
    never collapsing them, because they mean different things to whoever reads
    the evidence afterwards.

    `verified` is reported rather than asserted. A property counts as verified
    only when both sides were present and agreed; an earlier version listed all
    three unconditionally and so claimed verification even while refusing.
    """
    mismatched: list[str] = []
    unverifiable: list[str] = []
    verified: list[str] = []
    for name in DECLARED_PROPERTIES:
        want, got = declared.get(name), found.get(name)
        if want is None or got is None:
            # An absent value on either side is not a match. Comparing them with
            # `!=` would let `None == None` pass, so an unreadable property and a
            # profile that fails to declare it would agree - and report a
            # verification that never happened.
            unverifiable.append(
                f"{name} could not be compared: "
                f"profile declares {want!r}, running {got!r}"
            )
        elif want != got:
            mismatched.append(f"{name}: running {got!r}, profile declares {want!r}")
        else:
            verified.append(name)

    # The profile id names the CUDA line the image is built against. The runtime
    # reports its own version as an integer like 13000 for 13.0 - when it can.
    if "cuda13" in str(declared.get("profile_id", "")):
        if type(cuda_version) is int:
            if cuda_version // 1000 != 13:
                mismatched.append(
                    f"CUDA runtime major is {cuda_version // 1000}, "
                    "profile declares cuda13"
                )
        else:
            unverifiable.append(
                "CUDA runtime version is unreadable on this build; "
                "the cuda13 line was not verified"
            )
    return mismatched, unverifiable, verified


def environment_check_record(verified: list[str], unverifiable: list[str]) -> dict:
    """What the evidence carries about this check, including its limits."""
    return {
        "verified": list(verified),
        "unverifiable": list(unverifiable),
        "note": NOT_A_DIGEST_CHECK,
        "any_verification_performed": bool(verified),
    }


def nothing_was_verified(verified: list[str], unverifiable: list[str]) -> bool:
    """Did the check establish anything at all?

    Its own condition, distinct from a mismatch, and the mirrored rule does not
    cover it. That rule says *could not check this* must not become *this is
    wrong*. It is silent on *could not check anything*, which is a different
    claim: "four of five verified" and "none verified" are not the same state,
    and only the second means no verification occurred.

    The failure it catches is the guard going inert exactly where it is most
    needed. In an unfamiliar image every reader can return `None`, so nothing
    mismatches, everything is unverifiable, and the run proceeds behind an
    honest-looking record saying nothing was checked - quietly, because one
    unverifiable property among four reads as normal.

    A caller decides what to do. For a rented pod, where the image is the least
    certain thing in the run, refusing is the only setting that buys anything.
    """
    return not verified and bool(unverifiable)


__all__ = [
    "DECLARED_PROPERTIES",
    "NOT_A_DIGEST_CHECK",
    "environment_check_record",
    "environment_problems",
    "nothing_was_verified",
]
