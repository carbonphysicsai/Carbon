"""The worker image carries only the carbon files its container imports ("Narrow it first").

Host-only code (receiver, door, MCP, host-side scoring ...) must not move the image id; every file the container's own
imports need must be in the image, so a gap fails closed (an absent file), never as a different grade.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from carbon.reconstruction.worker import build_inputs, image_modules

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / ".devcontainer" / "Dockerfile.reconstruction-worker"

# Modules the container really runs (the entrypoint and the subprocess validators it starts by `python -m`) ...
IN_THE_IMAGE = (
    "carbon.reconstruction.worker.entrypoint",
    "carbon.reconstruction.worker.protocol",
    "carbon.reconstruction.worker.artifact_validator",
    "carbon.measurement_runtime.protocol",
    "carbon.measurement_runtime.validator",
    "carbon.reference_runtime.protocol",
)
# ... and host-only code that must not be (a host edit here must not move the image id).
HOST_ONLY = (
    "carbon.challenge_validator.direct_receiver",
    "carbon.challenge_validator.lean_recipe",
    "carbon.challenge_validator.koth_registry",
    "carbon.challenge_registry.published_exam",
    "carbon.miner_mcp.mcp_challenges",
    "carbon.scoring.physical_dual_pack",
    "carbon.scoring.pool_version",
    "carbon.development_session.bundle_construction_worker",
    "carbon.backbone_catalog.listing",
)


def test_the_generated_files_are_what_the_code_gives():
    assert (
        image_modules.stale(ROOT) == []
    ), "run: python carbon/reconstruction/worker/image_modules.py generate"


def test_every_listed_file_exists_and_the_closure_is_inside_the_list():
    listed = image_modules.listed_files(ROOT)
    assert len(listed) == len(set(listed))
    assert [path for path in listed if not (ROOT / path).is_file()] == []
    index = image_modules.module_index(ROOT)
    closure = image_modules.eager_closure(ROOT, index, [image_modules.ENTRYPOINT])
    assert closure <= set(image_modules.listed_modules(ROOT))
    # the committed trace allow-list's modules are in the list too
    assert set(image_modules.trace_modules(ROOT)) <= set(
        image_modules.listed_modules(ROOT)
    )


def test_the_container_modules_are_in_and_host_only_modules_are_out():
    modules = set(image_modules.listed_modules(ROOT))
    for name in IN_THE_IMAGE:
        assert name in modules, name
    for name in HOST_ONLY:
        assert name not in modules, name
    index = image_modules.module_index(ROOT)
    listed = len(image_modules.listed_files(ROOT))
    assert listed < 0.1 * len(index) + 60, (
        listed,
        len(index),
    )  # a narrow set, not the package


def test_the_vendored_lab_directory_is_whole_because_it_is_hashed_whole():
    """carbon_jax_lab.checkpoint hashes `Path(__file__).parent.glob("*.py")`: a partial directory would change the hash."""
    folder = ROOT / "carbon/reconstruction/_vendor/carbon_jax_lab"
    on_disk = {p.relative_to(ROOT).as_posix() for p in folder.glob("*.py")}
    assert on_disk <= set(image_modules.listed_files(ROOT))


def test_the_dockerignore_lets_through_exactly_the_listed_carbon_files():
    ignore = (ROOT / image_modules.DOCKERIGNORE).read_text(encoding="utf-8")
    candidates = [
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "carbon").rglob("*")
        if path.is_file()
        and "node_modules" not in path.parts
        and "__pycache__" not in path.parts
    ]
    survivors = image_modules.docker_survivors(ROOT, ignore, candidates)
    assert survivors == {
        path for path in image_modules.listed_files(ROOT) if path.startswith("carbon/")
    }
    # the repository's usual exclusions are repeated: BuildKit reads this file INSTEAD of the root .dockerignore
    root_lines = [
        line
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert set(root_lines) <= set(ignore.splitlines()) | set(image_modules.BASE_IGNORE)


def test_the_docker_ignore_matcher_follows_docker_semantics():
    ignore = "carbon/**\n!carbon/a/b.py\n!carbon/c.json\n**/__pycache__\n"
    candidates = [
        "carbon/a/b.py",
        "carbon/a/x.py",
        "carbon/c.json",
        "carbon/d/__pycache__/m.pyc",
        "other/file.py",
    ]
    assert image_modules.docker_survivors(ROOT, ignore, candidates) == {
        "carbon/a/b.py",
        "carbon/c.json",
        "other/file.py",
    }


def test_the_dockerfile_copies_carbon_through_its_ignore_file_and_runs_the_smoke():
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "COPY carbon ./carbon" in text
    assert (ROOT / image_modules.DOCKERIGNORE).is_file()
    # a build that ignored the allow-list (a legacy builder) would carry the whole package: the smoke refuses it
    smoke = "/opt/carbon-worker/bin/python -I -m carbon.reconstruction.worker.image_modules smoke"
    assert smoke in text
    assert text.index(smoke) > text.index("COPY --from=builder /opt/carbon ")
    assert "worker_image_files.txt" in (ROOT / "pyproject.toml").read_text(
        encoding="utf-8"
    )


def test_the_build_script_checks_the_generated_files_before_the_digest():
    text = (ROOT / "scripts/dev/c03_worker_image.sh").read_text(encoding="utf-8")
    assert "image_modules.py" in text
    assert text.index("image_modules.py") < text.index(
        '"${build_inputs_program}" digest'
    )


def test_the_build_inputs_file_is_the_generated_one():
    expected = image_modules.render_inputs(ROOT).splitlines()
    expected = [
        line.strip() for line in expected if line.strip() and not line.startswith("#")
    ]
    assert list(build_inputs.paths()) == expected


def test_a_string_literal_naming_a_module_reaches_it(tmp_path):
    """A `python -m carbon.x.y` target is reached by name, not by an import statement."""
    for name, body in (
        ("carbon/__init__.py", ""),
        (
            "carbon/entry.py",
            "import subprocess\nsubprocess.run(['python', '-m', 'carbon.target'])\n",
        ),
        ("carbon/target.py", "import carbon.helper\n"),
        ("carbon/helper.py", ""),
        ("carbon/host_only.py", ""),
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    index = image_modules.module_index(tmp_path)
    lazies: dict = {}
    seen = image_modules.eager_closure(tmp_path, index, ["carbon.entry"], lazies)
    assert seen == {"carbon", "carbon.entry"}
    assert lazies["carbon.entry"] == {"carbon.target"}
    both = image_modules.eager_closure(tmp_path, index, ["carbon.target"])
    assert both == {"carbon", "carbon.target", "carbon.helper"}


def test_a_function_level_import_is_a_lazy_reference_not_an_eager_one(tmp_path):
    for name, body in (
        ("carbon/__init__.py", ""),
        ("carbon/entry.py", "def late():\n    import carbon.later\n"),
        ("carbon/later.py", ""),
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    index = image_modules.module_index(tmp_path)
    eager, lazy = image_modules.split_imports(tmp_path, index, "carbon.entry")
    assert eager == set() and lazy == {"carbon.later"}


def test_the_command_line_checks_the_committed_files():
    program = ROOT / "carbon/reconstruction/worker/image_modules.py"
    done = subprocess.run(
        [sys.executable, "-I", str(program), "check", str(ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0 and done.stdout.strip() == "", done.stdout


def test_trace_check_names_the_traced_carbon_modules_the_list_does_not_carry():
    listed = image_modules.listed_modules(ROOT)
    assert image_modules.trace_check(ROOT, [listed[0], "numpy", "os"]) == []
    extra = image_modules.trace_check(
        ROOT, [listed[0], "carbon.challenge_validator.direct_receiver", "jax", "carbon"]
    )
    assert extra == ["carbon.challenge_validator.direct_receiver"]


# --- `python -m` targets run in the container --------------------------------------------------------------------------


def test_the_scan_finds_the_known_container_run_targets_and_the_list_carries_each():
    """The exporter is run by `docker exec <container> /opt/carbon-worker/bin/python -I -m ...exporter` from four
    controllers; the import closure alone missed it and every Cooling rebuild failed with
    `No module named carbon.reconstruction.worker.exporter`."""
    targets = image_modules.container_run_targets(ROOT)
    assert {
        "carbon.reconstruction.worker.entrypoint",
        "carbon.reconstruction.worker.exporter",
        "carbon.compute.job_server",
    } <= targets
    listed = set(image_modules.listed_modules(ROOT))
    assert targets <= listed, sorted(targets - listed)


def test_the_file_list_names_its_run_targets_for_the_in_image_smoke():
    line = next(
        line
        for line in (ROOT / image_modules.FILES_FILE).read_text().splitlines()
        if line.startswith(image_modules.RUN_TARGETS_PREFIX)
    )
    named = line[len(image_modules.RUN_TARGETS_PREFIX) :].split()
    assert named == sorted(image_modules.container_run_targets(ROOT))


def test_a_run_target_in_an_argv_list_with_flags_is_a_root(tmp_path):
    for name, body in (
        ("carbon/__init__.py", ""),
        (
            "carbon/controller.py",
            (
                "ARGV = ['exec', 'c', '/opt/carbon-worker/bin/python', '-I', '-B', '-m', 'carbon.target', '1']\n"
                "HOST = ['python', '-m', 'carbon.host_only']\n"
            ),
        ),
        ("carbon/target.py", ""),
        ("carbon/host_only.py", ""),
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    assert image_modules.container_run_targets(tmp_path) == {"carbon.target"}
