"""Carbon's own images from earlier installs, and nothing else (M1 E2E R6-1).

Docker is a stand-in: no engine is reached. The rules held here:
- only Carbon's own repositories are listed, never another program's image
  or an untagged one;
- no image a record of the current install names is listed: the images
  setup's installer record points to, the installer's manifests, and any
  parent they name;
- a tag is removed without force, and a refusal is reported, not overridden.
"""

from __future__ import annotations

import json
import subprocess

from scripts.dev.miner_launchpad import installed, superseded_images

CURRENT = "sha256:" + "a" * 64
ANALYSIS = "sha256:" + "b" * 64
PARENT = "sha256:" + "c" * 64
OLD = "sha256:" + "d" * 64
OTHER = "sha256:" + "e" * 64


def image(repository, tag, image_id):
    return json.dumps(
        {"Repository": repository, "Tag": tag, "ID": image_id, "Size": "1.2GB"}
    )


class Docker:
    def __init__(self, listing, refuse=()):
        self.listing, self.refuse, self.calls = listing, set(refuse), []

    def __call__(self, *argv):
        self.calls.append(argv)
        if argv[:2] == ("image", "ls"):
            return subprocess.CompletedProcess(argv, 0, "\n".join(self.listing), "")
        if argv[:2] == ("image", "rm"):
            refused = argv[2] in self.refuse
            return subprocess.CompletedProcess(
                argv,
                1 if refused else 0,
                "",
                "conflict: image is being used by a container" if refused else "",
            )
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


LISTING = [
    image("carbon-c03-worker", "new", CURRENT),
    image("carbon-analysis", "new", ANALYSIS),
    image("carbon-cw1d4-parent", "x", PARENT),
    image("carbon-c03-worker", "old", OLD),
    image("carbon-analysis", "old", OLD),
    image("carbon-c03-worker", "<none>", OLD),
    image("postgres", "16", OTHER),
    image("someone/carbon-c03-worker", "old", OLD),
]


def test_only_carbons_superseded_tags_are_listed(tmp_path):
    state, repo = install(tmp_path)
    found = superseded_images.superseded(state, repo, Docker(LISTING))
    assert [i["ref"] for i in found] == [
        "carbon-c03-worker:old",
        "carbon-analysis:old",
    ]
    assert superseded_images.kept(state, repo) >= {CURRENT, ANALYSIS, PARENT}


def test_removal_is_by_tag_without_force_and_reports_a_refusal(tmp_path, capsys):
    state, repo = install(tmp_path)
    docker = Docker(LISTING, refuse={"carbon-analysis:old"})
    code = superseded_images.main(
        ["remove", "--state-dir", str(state), "--repo", str(repo)], docker
    )
    assert code == 1
    removals = [c for c in docker.calls if c[:2] == ("image", "rm")]
    assert removals == [
        ("image", "rm", "carbon-c03-worker:old"),
        ("image", "rm", "carbon-analysis:old"),
    ]
    out = capsys.readouterr().out
    assert "removed carbon-c03-worker:old" in out
    assert "kept carbon-analysis:old: conflict" in out


def test_listing_prints_each_and_docker_failure_lists_nothing(tmp_path, capsys):
    state, repo = install(tmp_path)
    assert (
        superseded_images.main(
            ["list", "--state-dir", str(state), "--repo", str(repo)], Docker(LISTING)
        )
        == 0
    )
    assert capsys.readouterr().out.splitlines() == [
        "  carbon-c03-worker:old  (1.2GB)",
        "  carbon-analysis:old  (1.2GB)",
    ]

    def broken(*argv):
        return subprocess.CompletedProcess(argv, 1, "", "no daemon")

    assert superseded_images.superseded(state, repo, broken) == []
