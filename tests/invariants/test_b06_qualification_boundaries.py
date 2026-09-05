from __future__ import annotations

import ast
import pickle
from pathlib import Path

import pytest

from carbon import qualification
from carbon.registry import ChallengeKey
from tests.invariants._import_analysis import direct_import_modules

pytestmark = pytest.mark.invariant

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
QUALIFICATION_ROOT = REPOSITORY_ROOT / "carbon" / "qualification"
COMPLETED_UPSTREAM_ROOTS = (
    REPOSITORY_ROOT / "carbon" / "authoring",
    REPOSITORY_ROOT / "carbon" / "evaluation",
    REPOSITORY_ROOT / "carbon" / "generators",
    REPOSITORY_ROOT / "carbon" / "measurement",
    REPOSITORY_ROOT / "carbon" / "registry",
    REPOSITORY_ROOT / "carbon" / "scoring",
)


def imported_modules(path: Path) -> set[str]:
    return {module for module, _ in direct_import_modules(REPOSITORY_ROOT, path)}


@pytest.mark.parametrize(
    ("source", "path"),
    (
        ("from carbon import qualification", REPOSITORY_ROOT / "carbon" / "probe.py"),
        ("from . import qualification", REPOSITORY_ROOT / "carbon" / "probe.py"),
        ("import carbon.qualification", REPOSITORY_ROOT / "carbon" / "probe.py"),
    ),
)
def test_import_scanner_resolves_qualification_namespace(
    source: str, path: Path
) -> None:
    imports = {
        module
        for module, _ in direct_import_modules(
            REPOSITORY_ROOT, path, tree=ast.parse(source)
        )
    }
    assert "carbon.qualification" in imports


def test_completed_upstream_packages_do_not_import_qualification() -> None:
    for root in COMPLETED_UPSTREAM_ROOTS:
        for path in root.rglob("*.py"):
            assert all(
                module != "carbon.qualification"
                and not module.startswith("carbon.qualification.")
                for module in imported_modules(path)
            ), path


def test_qualification_imports_only_exact_upstream_value_type_modules() -> None:
    allowed = {
        "carbon.authoring.primitives",
        "carbon.authoring.refs",
        "carbon.measurement.enums",
        "carbon.measurement.refs",
        "carbon.registry.model",
    }
    for path in QUALIFICATION_ROOT.rglob("*.py"):
        carbon_imports = {
            module
            for module in imported_modules(path)
            if module.startswith("carbon.")
            and not module.startswith("carbon.qualification")
        }
        assert carbon_imports <= allowed, (path, carbon_imports)


def test_public_surface_has_no_qualification_registry_or_live_operation() -> None:
    forbidden_tokens = (
        "activate",
        "active_registry",
        "bittensor",
        "frontier",
        "live",
        "qualify",
        "settlement",
        "treasury",
    )
    public_names = tuple(name.lower() for name in qualification.__all__)
    assert not any(token in name for token in forbidden_tokens for name in public_names)
    assert tuple(state.value for state in qualification.SignerBindingState) == (
        "REQUIRED_MISSING",
        "POPULATED_UNVERIFIED",
    )


def test_refs_are_protected_and_nonpickleable() -> None:
    ref = qualification.ValidationDossierRef(
        ChallengeKey("fixture-burgers", "1.0"),
        "validation-dossier",
        "1.0",
        "sha256:" + "a" * 64,
    )
    assert "fixture-burgers" not in repr(ref)
    assert "fixture-burgers" not in str(ref)
    with pytest.raises(TypeError):
        pickle.dumps(ref)

    manifest_ref = qualification.DossierEvidenceManifestRef(
        ChallengeKey("fixture-burgers", "1.0"),
        qualification.DossierSlot.D10,
        "statistical-manifest",
        "1.0",
        "sha256:" + "b" * 64,
        qualification.StructuralOrigin.DRAFT_OR_UNRESOLVED,
    )
    assert "fixture-burgers" not in repr(manifest_ref)
    with pytest.raises(TypeError):
        pickle.dumps(manifest_ref)
