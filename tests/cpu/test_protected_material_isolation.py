"""Protected material never reaches the accelerator path.

This holds today, and it holds structurally rather than by policy: three
independent facts about the code keep hidden cases, seeds and held-out material
away from GPU execution. The risk is not that one of them is wrong now. It is
that all three are currently *accidents of the present design* - nothing fails if
someone adds an import, widens a field set, or relaxes an archive type - and the
protection would disappear without any single change looking like a security
change.

So they are named here and asserted. A failure in this module is not a style
problem: it means the argument that protected material cannot reach a device has
stopped being true.

If GPU-accelerated evaluation against hidden cases is ever wanted, it is a
distinct lane needing its own containment argument, designed then. It must never
arrive as an extension of this one, and relaxing a test here is not that design.

Nothing here initializes a backend, attaches a device or runs a container.
"""

import ast
from pathlib import Path

import pytest

from carbon.reconstruction.model import PublicTrainingArchive, ReconstructionFailure

REPOSITORY = Path(__file__).resolve().parents[2]
PACKAGE = REPOSITORY / "carbon"
ACCELERATORS = "carbon.reconstruction.accelerators"

# The only packages that may know accelerators exist. Each one is on the
# execution side of the boundary: it stages, runs or supervises a worker.
PERMITTED_IMPORTERS = (
    "carbon.reconstruction",
    "carbon.reconstruction.worker",
    "carbon.development_session",
)

# Named individually rather than as "everything else", so that the assertion
# fails loudly for these in particular. These are the packages that hold or
# decide on protected material.
PROTECTED_PACKAGES = (
    "carbon.evaluation",
    "carbon.evaluation_packs",
    "carbon.scoring",
    "carbon.qualification",
    "carbon.gauntlet",
)


def _module_name(path: Path) -> str:
    relative = path.relative_to(REPOSITORY).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _imports(path: Path) -> set[str]:
    """Every module this file imports, read from the syntax rather than the text.

    An AST walk rather than a grep: a string mentioning the module in a comment
    or a docstring is not an import, and an import split across lines still is.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def _accelerator_importers() -> dict[str, set[str]]:
    importers: dict[str, set[str]] = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        referenced = {
            name
            for name in _imports(path)
            if name == ACCELERATORS or name.startswith(f"{ACCELERATORS}.")
        }
        if referenced:
            importers[_module_name(path)] = referenced
    return importers


# --- 1. the import boundary ---------------------------------------------------


def test_only_the_execution_packages_import_the_accelerator_profile():
    """Widening this set is how the boundary would quietly disappear."""
    importers = _accelerator_importers()
    assert importers, "the scan found nothing; it is not actually checking"

    outside = sorted(
        module
        for module in importers
        if not any(
            module == package or module.startswith(f"{package}.")
            for package in PERMITTED_IMPORTERS
        )
    )
    assert not outside, (
        "carbon.reconstruction.accelerators is imported outside the execution "
        f"packages: {outside}. Protected material is kept off the accelerator "
        "path by this boundary; importing it elsewhere removes that argument."
    )


@pytest.mark.parametrize("package", PROTECTED_PACKAGES)
def test_no_protected_package_imports_the_accelerator_profile(package):
    """Stated per package, so a failure names the one that crossed."""
    importers = _accelerator_importers()
    crossed = sorted(
        module
        for module in importers
        if module == package or module.startswith(f"{package}.")
    )
    assert not crossed, f"{package} reached the accelerator path: {crossed}"


# --- 2. the closed staged request ---------------------------------------------


def test_the_staged_worker_request_field_set_is_closed():
    """An open field set is a slot protected material could travel in."""
    from carbon.reconstruction.worker import protocol

    assert type(protocol._REQUEST_FIELDS) is frozenset
    assert protocol._REQUEST_FIELDS, "an empty field set closes nothing"
    # The accelerator block is the single permitted addition, and it is named.
    permitted = protocol._REQUEST_FIELDS | {"accelerator"}
    assert "training" in protocol._REQUEST_FIELDS
    assert not {"evaluation", "exam", "hidden", "held_out", "protected", "final"} & (
        permitted
    )


def test_an_unknown_request_field_is_refused_rather_than_ignored(tmp_path):
    """Closed means refused. A tolerated extra field is an open field set."""
    import json

    from carbon.reconstruction.worker import protocol
    from carbon.reconstruction.worker.model import WorkerFailure

    path = tmp_path / "request.json"
    path.write_bytes(json.dumps({"schema": "x", "hidden_cases": ["secret"]}).encode())
    with pytest.raises(WorkerFailure):
        protocol._closed_json(
            path, protocol._REQUEST_FIELDS, protocol._REQUEST_FIELDS | {"accelerator"}
        )


# --- 3. the single data input is type-enforced public -------------------------


def test_the_only_data_input_refuses_any_role_but_train(tmp_path):
    archive = tmp_path / "train.npz"
    archive.write_bytes(b"fixture")
    digest = "sha256:" + "1" * 64

    for role in ("EVAL", "STRESS", "FINAL", "EXAM", "HIDDEN", "train", ""):
        with pytest.raises(ReconstructionFailure):
            PublicTrainingArchive(archive, digest, "fixture", role)


def test_the_only_data_input_refuses_any_other_format(tmp_path):
    archive = tmp_path / "train.npz"
    archive.write_bytes(b"fixture")
    digest = "sha256:" + "1" * 64

    for fmt in (
        "carbon.protected-trajectories.v1",
        "carbon.public-trajectories.v2",
        "",
    ):
        with pytest.raises(ReconstructionFailure):
            PublicTrainingArchive(archive, digest, "fixture", "TRAIN", fmt)


def test_the_refusal_is_at_construction_not_at_use(tmp_path):
    """So no caller can hold a mislabelled archive and check it later."""
    archive = tmp_path / "train.npz"
    archive.write_bytes(b"fixture")
    with pytest.raises(ReconstructionFailure):
        PublicTrainingArchive(archive, "sha256:" + "1" * 64, "fixture", "EVAL")
