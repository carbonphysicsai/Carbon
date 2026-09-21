"""One source of truth for the subnet Carbon runs on.

The value was asserted independently in six places across `development_session`
and `miner_mcp`. Each guard was correct; having six of them was the problem,
because a mainnet subnet will exist eventually and the failure mode of a
scattered constant is that one copy moves and the rest keep guarding the old
network - silently, since each guard still passes on its own terms.

These tests pin the value and assert the duplication does not come back. They
deliberately do **not** test a network switch: there is no mainnet netuid yet,
and a test for a shape nobody has chosen would fix that shape in place.
"""

import pathlib
import re

from carbon.chain import CARBON_NETUID, CARBON_NETWORK

REPOSITORY = pathlib.Path(__file__).resolve().parents[2]
SOURCE = REPOSITORY / "carbon" / "chain" / "models.py"


def test_the_value_is_pinned():
    """Changing the subnet should be a deliberate edit to this test as well."""
    assert CARBON_NETWORK == "testnet"
    assert CARBON_NETUID == 567


def test_the_constant_is_exported_from_the_chain_package():
    from carbon import chain

    assert "CARBON_NETUID" in chain.__all__
    assert "CARBON_NETWORK" in chain.__all__


def test_no_module_carries_its_own_copy_of_the_subnet_literal():
    """The duplication must not creep back in.

    Scoped to the packages that held the six copies. A bare `567` elsewhere in
    the tree is almost always an unrelated number, so this asserts where the
    problem actually was rather than pattern-matching the whole repository.
    """
    offenders = []
    for package in ("development_session", "miner_mcp", "chain"):
        for path in (REPOSITORY / "carbon" / package).rglob("*.py"):
            if path == SOURCE:
                continue
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if re.search(r"(?<![\w.])567(?![\w.])", line):
                    offenders.append(
                        f"{path.relative_to(REPOSITORY)}:{number}: {line.strip()}"
                    )
    assert (
        offenders == []
    ), "import CARBON_NETUID from carbon.chain instead of restating it:\n" + "\n".join(
        offenders
    )


def test_the_declaring_module_stays_dependency_free():
    """It is imported by modules that should not pull in the chain SDK.

    `profile.py` imported only the standard library and `carbon.registry` before
    this. Keeping the declaring module on standard-library imports is what makes
    consolidating here cheap rather than a new dependency edge.
    """
    imports = [
        line
        for line in SOURCE.read_text(encoding="utf-8").splitlines()
        if line.startswith(("import ", "from "))
    ]
    assert imports, "expected the module to import something"
    assert not [line for line in imports if "carbon" in line], imports


def test_every_former_holder_still_imports_cleanly():
    """The five modules that held a copy still load with the shared constant.

    Imported statically rather than through importlib: `test_code_authority`
    keeps a pinned allow-list of every dynamic-import site so that each one is
    deliberate, and a convenience test is not a good reason to lengthen it.
    """
    from carbon.development_session import __main__, profile, research_campaign, service
    from carbon.miner_mcp import standard_cli

    for module in (research_campaign, profile, service, __main__, standard_cli):
        assert module is not None
