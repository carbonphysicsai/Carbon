"""Carbon's own images and containers from earlier installs, and nothing
else (M1 E2E R6-1, R11-2).

Docker is a stand-in: no engine is reached. The rules held here:
- only Carbon's own repositories, catalog images (by the catalog install's
  label) and exited practice-job containers (by the job label) are listed,
  never another program's image or container, a running one, or an
  untagged image of another repository;
- no image a record of the current install names is listed, and no catalog
  image built over a parent the install still names;
- what each kind frees is said;
- each is removed without force, containers first, and a refusal is
  reported, not overridden.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.dev.miner_launchpad import installed, superseded_images

CURRENT = "sha256:" + "a" * 64
ANALYSIS = "sha256:" + "b" * 64
PARENT = "sha256:" + "c" * 64
OLD = "sha256:" + "d" * 64
OTHER = "sha256:" + "e" * 64
OLD_PARENT = "sha256:" + "f" * 64
CATALOG_OLD = "sha256:" + "1" * 64
CATALOG_NEW = "sha256:" + "2" * 64
LIBRARY = superseded_images.LIBRARY_LABEL
PARENT_LABEL = superseded_images.PARENT_LABEL


def image(repository, tag, image_id, size="1.2GB"):
    return json.dumps(
        {"Repository": repository, "Tag": tag, "ID": image_id, "Size": size}
    )


class Docker:
    def __init__(self, refuse=()):
        self.refuse, self.calls = set(refuse), []
        self.images = [
            image("carbon-c03-worker", "new", CURRENT),
            image("carbon-analysis", "new", ANALYSIS),
            image("carbon-cw1d4-parent", "x", PARENT),
            image("carbon-c03-worker", "old", OLD),
            image("carbon-analysis", "old", OLD),
            image("carbon-torch-gpu-worker", "hand", OLD_PARENT, "6.0GB"),
            image("carbon-c03-worker", "<none>", OLD),
            image("postgres", "16", OTHER),
            image("someone/carbon-c03-worker", "old", OLD),
        ]
        self.catalog = [
            image("<none>", "<none>", CATALOG_OLD, "2.0GB"),
            image("<none>", "<none>", CATALOG_NEW, "2.0GB"),
        ]
        self.labels = {
            CATALOG_OLD: {LIBRARY: "sha256:" + "9" * 64, PARENT_LABEL: OLD_PARENT},
            CATALOG_NEW: {LIBRARY: "sha256:" + "8" * 64, PARENT_LABEL: CURRENT},
        }
        self.containers = [
            json.dumps({"ID": "c" * 64, "Names": "carbon-d4-old", "Size": "12MB"})
        ]

    def __call__(self, *argv):
        self.calls.append(argv)

        def ok(out=""):
            return subprocess.CompletedProcess(argv, 0, out, "")

        if argv[0] == "ps":
            # Docker applies the filters: only exited, labelled Carbon jobs.
            assert "label=" + superseded_images.JOB_LABEL in argv
            assert "status=exited" in argv
            return ok("\n".join(self.containers))
        if argv[:2] == ("image", "ls"):
            if "label=" + LIBRARY in argv:
                return ok("\n".join(self.catalog))
            return ok("\n".join(self.images))
        if argv[:2] == ("image", "inspect"):
            return ok(json.dumps(self.labels.get(argv[-1], {})))
        if argv[0] == "rm" or argv[:2] == ("image", "rm"):
            target = argv[-1]
            if target in self.refuse:
                return subprocess.CompletedProcess(
                    argv, 1, "", "conflict: image is being used by a container"
                )
            return ok()
        raise AssertionError(argv)


def install(tmp_path):
    """A recorded install: worker and analysis manifests, the analysis one
    naming its parent, as the installer writes them."""
    state, repo = tmp_path / "state", tmp_path / "repo"
    state.mkdir(mode=0o700)
    artifacts = repo / ".carbon-artifacts" / "research-images"
    artifacts.mkdir(parents=True)
    worker = repo / ".carbon-artifacts" / "c03-worker-image.json"
    worker.write_text(json.dumps({"image_id": CURRENT}))
    analysis = artifacts / "analysis.json"
    analysis.write_text(json.dumps({"image_id": ANALYSIS, "parent": PARENT}))
    installed.write(state, image_manifest=worker, analysis_image_manifest=analysis)
    return state, repo


def test_only_carbons_superseded_images_catalog_and_job_containers_are_listed(
    tmp_path,
):
    state, repo = install(tmp_path)
    found = superseded_images.superseded(state, repo, Docker())
    assert [(item["kind"], item["ref"]) for item in found] == [
        ("container", "carbon-d4-old"),
        ("catalog", CATALOG_OLD),
        ("image", "carbon-c03-worker:old"),
        ("image", "carbon-analysis:old"),
        ("image", "carbon-torch-gpu-worker:hand"),
    ]
    assert superseded_images.kept(state, repo) >= {CURRENT, ANALYSIS, PARENT}


def test_the_dry_run_says_what_each_kind_frees(tmp_path, capsys):
    """M1 E2E R11-2: one "y" should free enough, and say how much each kind
    frees; a non-Carbon image is never in the listing."""
    state, repo = install(tmp_path)
    assert (
        superseded_images.main(
            ["list", "--state-dir", str(state), "--repo", str(repo)], Docker()
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "postgres" not in out and OTHER not in out
    assert "  practice job containers that finished: 1, frees about 12.0MB" in out
    assert "  catalog images built over an earlier worker: 1, frees about 2.0GB" in out
    assert "  Carbon images from earlier installs: 3, frees about 8.4GB" in out


def test_removal_is_without_force_containers_first_and_reports_a_refusal(
    tmp_path, capsys
):
    state, repo = install(tmp_path)
    docker = Docker(refuse={"carbon-analysis:old"})
    code = superseded_images.main(
        ["remove", "--state-dir", str(state), "--repo", str(repo)], docker
    )
    assert code == 1
    removals = [c for c in docker.calls if c[0] == "rm" or c[:2] == ("image", "rm")]
    assert removals == [
        ("rm", "c" * 64),
        ("image", "rm", CATALOG_OLD),
        ("image", "rm", "carbon-c03-worker:old"),
        ("image", "rm", "carbon-analysis:old"),
        ("image", "rm", "carbon-torch-gpu-worker:hand"),
    ]
    assert not [c for c in removals if "-f" in c or "--force" in c]
    out = capsys.readouterr().out
    assert "removed carbon-d4-old" in out
    assert "kept carbon-analysis:old: conflict" in out


def test_docker_failure_lists_nothing(tmp_path):
    state, repo = install(tmp_path)

    def broken(*argv):
        return subprocess.CompletedProcess(argv, 1, "", "no daemon")

    assert superseded_images.superseded(state, repo, broken) == []


def test_sizes_read_as_docker_prints_them():
    assert superseded_images.size_bytes("1.2GB") == 1_200_000_000
    assert superseded_images.size_bytes("0B (virtual 1.2GB)") == 0
    assert superseded_images.size_bytes("12MB (virtual 3GB)") == 12_000_000
    assert superseded_images.size_bytes("?") == 0
    assert superseded_images.human(8_400_000_000) == "8.4GB"


def test_the_catalog_images_the_install_names_are_a_separate_offer_never_listed_as_superseded(
    tmp_path,
):
    """An update builds the catalog again over the new worker, so the images it names now may go first, on their own
    yes: `current_catalog` lists exactly the catalog images `superseded` does not (here the one over the current
    parent), by label only."""
    state, repo = install(tmp_path)
    docker = Docker()
    listed = {item["id"] for item in superseded_images.superseded(state, repo, docker)}
    assert CATALOG_OLD in listed and CATALOG_NEW not in listed
    current = superseded_images.current_catalog(state, repo, docker)
    assert [item["id"] for item in current] == [CATALOG_NEW]
    assert current[0]["kind"] == "catalog_current"
    # Nothing outside the label is offered: no worker, analysis or other program's image.
    assert not any(item["id"] in (CURRENT, ANALYSIS, OTHER, OLD) for item in current)


def test_the_catalog_commands_remove_only_those_images_without_force(tmp_path, capsys):
    state, repo = install(tmp_path)
    docker = Docker()
    args = ["--state-dir", str(state), "--repo", str(repo)]
    assert superseded_images.main(["catalog-list", *args], docker) == 0
    listing = capsys.readouterr().out
    assert "catalog images this update builds again: 1" in listing
    assert "frees about 2.0GB" in listing
    docker.calls.clear()
    assert superseded_images.main(["catalog-remove", *args], docker) == 0
    removals = [c for c in docker.calls if c[0] == "rm" or c[:2] == ("image", "rm")]
    assert removals == [("image", "rm", CATALOG_NEW)]
    assert not any("--force" in call or "-f" in call for call in docker.calls)
    # A refusal (a container still uses it) is reported, not overridden.
    refusing = Docker(refuse={CATALOG_NEW})
    assert superseded_images.main(["catalog-remove", *args], refusing) == 1
    assert "kept " + CATALOG_NEW in capsys.readouterr().out
    # The ordinary removal never touches it.
    docker.calls.clear()
    superseded_images.remove(superseded_images.superseded(state, repo, docker), docker)
    assert ("image", "rm", CATALOG_NEW) not in docker.calls


def test_the_module_and_installer_never_name_a_docker_prune():
    """The never-prunes rule (LA-F7): Docker's build cache is the miner's, not Carbon's. The word is simply absent."""
    root = Path(__file__).resolve().parents[2]
    for name in (
        "scripts/install_miner.sh",
        "scripts/dev/miner_launchpad/superseded_images.py",
    ):
        assert "prune" not in (root / name).read_text(encoding="utf-8").lower(), name


def test_the_installer_offers_the_current_catalog_only_on_its_own_flag_and_yes():
    script = (
        Path(__file__).resolve().parents[2] / "scripts/install_miner.sh"
    ).read_text(encoding="utf-8")
    assert "--remove-catalog-images) REMOVE_CATALOG_IMAGES=1" in script
    assert "REMOVE_CATALOG_IMAGES=0" in script
    body = script.split("offer_current_catalog() {")[1].split("old_images_offered=0")[0]
    assert "REMOVE_OLD_IMAGES" not in body
    assert "catalog-remove" in body and "catalog-list" in body
