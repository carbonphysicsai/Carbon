from __future__ import annotations

import ast
import pickle
from pathlib import Path

import pytest

from carbon import measurement
from carbon.registry import ChallengeKey
from tests.invariants._import_analysis import direct_import_modules

pytestmark = pytest.mark.invariant

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MEASUREMENT_ROOT = REPOSITORY_ROOT / "carbon" / "measurement"
UPSTREAM_ROOTS = (
    REPOSITORY_ROOT / "carbon" / "authoring",
    REPOSITORY_ROOT / "carbon" / "evaluation",
    REPOSITORY_ROOT / "carbon" / "resource_policy",
    REPOSITORY_ROOT / "carbon" / "scoring",
)


def imported_modules(path: Path) -> set[str]:
    return {module for module, _ in direct_import_modules(REPOSITORY_ROOT, path)}


@pytest.mark.parametrize(
    ("source", "path"),
    (
        ("from carbon import measurement", REPOSITORY_ROOT / "carbon" / "probe.py"),
        ("from . import measurement", REPOSITORY_ROOT / "carbon" / "probe.py"),
        ("import carbon.measurement", REPOSITORY_ROOT / "carbon" / "probe.py"),
    ),
)
def test_import_scanner_resolves_measurement_namespaces(
    source: str, path: Path
) -> None:
    imports = {
        module
        for module, _ in direct_import_modules(
            REPOSITORY_ROOT, path, tree=ast.parse(source)
        )
    }
    assert "carbon.measurement" in imports


def test_completed_upstream_packages_do_not_import_measurement() -> None:
    for root in UPSTREAM_ROOTS:
        for path in root.rglob("*.py"):
            assert all(
                module != "carbon.measurement"
                and not module.startswith("carbon.measurement.")
                for module in imported_modules(path)
            ), path


def test_measurement_has_only_authorized_upstream_type_and_pack_imports() -> None:
    forbidden = (
        "carbon.qualification",
        "carbon.mcp",
    )
    for path in MEASUREMENT_ROOT.rglob("*.py"):
        for module in imported_modules(path):
            assert not any(
                module == prefix or module.startswith(f"{prefix}.")
                for prefix in forbidden
            ), (path, module)

    allowed_resource_imports = {
        "carbon.resource_policy.model",
        "carbon.resource_policy.refs",
    }
    for path in MEASUREMENT_ROOT.rglob("*.py"):
        resource_imports = {
            module
            for module in imported_modules(path)
            if module == "carbon.resource_policy"
            or module.startswith("carbon.resource_policy.")
        }
        assert resource_imports <= allowed_resource_imports, (path, resource_imports)

    allowed_scoring_imports = {
        "carbon.scoring.model",
        "carbon.scoring.pack",
    }
    for path in MEASUREMENT_ROOT.rglob("*.py"):
        scoring_imports = {
            module
            for module in imported_modules(path)
            if module == "carbon.scoring" or module.startswith("carbon.scoring.")
        }
        assert scoring_imports <= allowed_scoring_imports, (path, scoring_imports)

    source = "\n".join(
        path.read_text(encoding="utf-8") for path in MEASUREMENT_ROOT.rglob("*.py")
    )
    assert "ScoreEngine" not in source
    assert "ScoreInput(" not in source


def test_public_surface_exposes_no_a5_constructor_or_engine() -> None:
    assert "ScoreInput" not in measurement.__all__
    assert "ScoreEngine" not in measurement.__all__
    assert "LoadedScorePack" not in measurement.__all__
    assert not hasattr(measurement, "ScoreInput")
    assert not hasattr(measurement, "ScoreEngine")


def test_reconstruction_policy_exposes_no_later_ticket_authority() -> None:
    forbidden = {
        "CoverageHarness",
        "DossierQualification",
        "FrontierPromotionEvent",
        "ScoreInput",
        "TreasurySettlement",
    }
    assert forbidden.isdisjoint(measurement.__all__)
    for field in measurement.ReconstructionEvidencePolicy.__dataclass_fields__:
        assert not any(
            token in field
            for token in ("bittensor", "commercial", "frontier", "network", "treasury")
        )
    for public_type in (
        measurement.ScorePackAuthoringContract,
        measurement.ScorePackInputBinding,
        measurement.ScorePackProjection,
    ):
        for field in public_type.__dataclass_fields__:
            assert not any(
                token in field
                for token in (
                    "bittensor",
                    "commercial",
                    "frontier",
                    "network",
                    "settlement",
                    "treasury",
                )
            )


def test_measurement_refs_are_protected_and_nonpickleable() -> None:
    challenge = ChallengeKey("fixture-burgers", "1.0")
    digest = "sha256:" + "a" * 64
    refs = (
        measurement.MeasurementDefinitionRef(
            challenge,
            measurement.MeasurementDefinitionKind.UNIT,
            "synthetic-unit",
            "1.0",
            digest,
        ),
        measurement.MeasurementContractRef(challenge, digest),
    )
    for ref in refs:
        assert "fixture-burgers" not in repr(ref)
        assert "fixture-burgers" not in str(ref)
        with pytest.raises(TypeError):
            pickle.dumps(ref)
