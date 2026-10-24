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
from pathlib import Path
import subprocess

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
        # `docker system df`: Docker's own build cache, reclaimable (none unless a test sets it).
        self.df = []

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
        if argv[:2] == ("system", "df"):
            return ok("\n".join(self.df))
        if argv[:2] == ("builder", "prune"):
            assert argv == ("builder", "prune", "--all", "--force")
            return ok("Total reclaimed space: 3.2GB")
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


CACHE = json.dumps({"Type": "Build Cache", "Size": "9GB", "Reclaimable": "3.2GB (35%)"})


def test_docker_build_cache_is_never_listed_with_carbons_images_and_has_its_own_listing(
    tmp_path,
):
    state, repo = install(tmp_path)
    docker = Docker()
    docker.df = [json.dumps({"Type": "Images", "Reclaimable": "1GB (10%)"}), CACHE]
    assert "build_cache" not in {
        item["kind"] for item in superseded_images.superseded(state, repo, docker)
    }
    item = superseded_images.build_cache(docker)
    assert item["kind"] == "build_cache"
    assert superseded_images.size_bytes(item["size"]) == 3_200_000_000
    docker.df = [json.dumps({"Type": "Build Cache", "Reclaimable": "0B (0%)"})]
    assert superseded_images.build_cache(docker) is None


def test_the_cache_commands_prune_only_the_cache_with_the_exact_command(
    tmp_path, capsys
):
    state, repo = install(tmp_path)
    docker = Docker()
    docker.df = [CACHE]
    args = ["--state-dir", str(state), "--repo", str(repo)]
    assert superseded_images.main(["cache-list", *args], docker) == 0
    assert "shared with every Docker build on this machine" in capsys.readouterr().out
    docker.calls.clear()
    assert superseded_images.main(["cache-remove", *args], docker) == 0
    assert docker.calls[-1] == ("builder", "prune", "--all", "--force")
    assert not any(
        call[0] in ("rm",) or call[:2] == ("image", "rm") for call in docker.calls
    )
    # The ordinary removal never touches the cache.
    docker.calls.clear()
    superseded_images.remove(superseded_images.superseded(state, repo, docker), docker)
    assert ("builder", "prune", "--all", "--force") not in docker.calls


def test_the_installer_has_its_own_flag_and_prompt_and_never_prunes_by_default_or_with_the_images():
    script = (
        Path(__file__).resolve().parents[2] / "scripts/install_miner.sh"
    ).read_text(encoding="utf-8")
    assert "--prune-build-cache) PRUNE_BUILD_CACHE=1" in script
    assert "PRUNE_BUILD_CACHE=0" in script
    assert (
        "REMOVE_OLD_IMAGES"
        not in script.split("offer_build_cache() {")[1].split("old_images_offered=0")[0]
    )
    assert "affects EVERY Docker build on this machine" in script
    assert "cache-remove" in script
