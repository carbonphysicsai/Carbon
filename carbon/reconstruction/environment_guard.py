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
) -> tuple[list[str], list[str]]:
    """Compare a running environment against a declared profile.

    `declared` is a profile document; `found` maps each name in
    `DECLARED_PROPERTIES` to the running value; `cuda_version` is the numerics
    record's reading, which may be `None`.

    Returns `(mismatched, unverifiable)`. A caller refuses on the first and
    records the second - never the other way round, and never both collapsed
    into one list, because they mean different things to whoever reads the
    evidence afterwards.
    """
    mismatched = [
        f"{name}: running {found.get(name)!r}, profile declares {declared.get(name)!r}"
        for name in DECLARED_PROPERTIES
        if found.get(name) != declared.get(name)
    ]
    unverifiable: list[str] = []

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
    return mismatched, unverifiable


def environment_check_record(unverifiable: list[str]) -> dict:
    """What the evidence carries about this check, including its limits."""
    return {
        "verified": list(DECLARED_PROPERTIES),
        "unverifiable": list(unverifiable),
        "note": NOT_A_DIGEST_CHECK,
    }


__all__ = [
    "DECLARED_PROPERTIES",
    "NOT_A_DIGEST_CHECK",
    "environment_check_record",
    "environment_problems",
]
