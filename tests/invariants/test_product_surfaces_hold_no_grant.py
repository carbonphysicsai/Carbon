"""No product surface can admit work under a development grant (C-MLP-02-D11).

Registration is the only product admission gate, and grants are development
machinery. The rule is checked on what the product surfaces import rather than
on what they happen to call today: a product module that can name `Admission`
can construct one.

The one name a product surface may import from the grant module is
`retained_grant_ledger`, the cleanup-only entry for campaigns launched under a
grant before the decision. It returns a ledger holding a `RetainedGrant`, whose
admission always refuses - so importing it grants nothing.

Both halves carry a specimen: the scanner finds the development CLI's grant
import, and it finds the runner's one permitted import. A scanner that could
find neither would pass on anything.
"""

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
GRANT_MODULE = "carbon.development_session.research_admission"
PRODUCT_SURFACES = (
    ROOT / "scripts" / "dev" / "miner_launchpad",
    ROOT / "carbon" / "miner_mcp",
)
PERMITTED = {("runner.py", "retained_grant_ledger")}


def grant_imports(path: Path) -> set[tuple[str, str]]:
    """Every name imported from the grant module, anywhere in the file."""
    found = set()
    package = path.parent.relative_to(ROOT).as_posix().replace("/", ".")
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == GRANT_MODULE or alias.name.startswith(
                    GRANT_MODULE + "."
                ):
                    found.add((path.name, "<module>"))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                base = package.split(".")[: len(package.split(".")) - node.level + 1]
                module = ".".join([*base, module] if module else base)
            if module == GRANT_MODULE:
                found.update((path.name, alias.name) for alias in node.names)
            elif module == GRANT_MODULE.rpartition(".")[0]:
                found.update(
                    (path.name, "<module>")
                    for alias in node.names
                    if alias.name == GRANT_MODULE.rpartition(".")[2]
                )
    return found


def product_modules():
    for directory in PRODUCT_SURFACES:
        yield from sorted(directory.glob("*.py"))


def test_no_product_surface_imports_grant_admission():
    found = set()
    for path in product_modules():
        found |= grant_imports(path)
    assert found <= PERMITTED, sorted(found - PERMITTED)


def test_the_scanner_finds_the_development_paths_grant_import():
    """Specimen: the development CLI does import the grant, and it is seen."""
    development = ROOT / "carbon" / "development_session" / "research_campaign.py"
    assert ("research_campaign.py", "Admission") in grant_imports(development)


def test_the_scanner_finds_the_one_permitted_import():
    """Specimen: the permitted import is present and detected, so the rule above
    is not passing because the scanner sees nothing in product modules."""
    runner = ROOT / "scripts" / "dev" / "miner_launchpad" / "runner.py"
    assert grant_imports(runner) == PERMITTED


def test_the_permitted_import_admits_nothing(tmp_path):
    """What makes the exception safe: a retained grant refuses every admission."""
    from carbon.development_session.research_admission import RetainedGrant

    retained = RetainedGrant(tmp_path / "grant.json", "sha256:" + "0" * 64, {})
    try:
        retained.verify(root=tmp_path, principal="p", runtime={}, now=0)
    except ValueError as refused:
        assert "admits no new work" in str(refused)
    else:
        raise AssertionError("a retained grant admitted work")
