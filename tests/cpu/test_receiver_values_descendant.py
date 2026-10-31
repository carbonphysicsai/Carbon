"""A receiver accepts a clean, values-only descendant of its accepted revision (OWNER-STOP-RULES-THAT-BLOCK-ITERATION-01).

`research_campaign.accepted_values_descendant` is used only by the direct receiver's `installed_source`; the exact-revision
`accepted_implementation` (miner_mcp, battery, Launchpad) is unchanged. Every grade slot names the commit it ran on.
"""

from __future__ import annotations

import subprocess

import pytest

from carbon.development_session import research_campaign as rc
from carbon.reconstruction.worker import build_inputs

INPUTS = "carbon/reconstruction/worker/build_inputs.txt"


class Repo:
    def __init__(self, path):
        self.path = path
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.invalid")
        self.git("config", "user.name", "t")
        self.git("config", "commit.gpgsign", "false")
        self.write(
            INPUTS, "# build inputs\ncarbon/engine.py\npyproject.toml\ndocs/listed.md\n"
        )
        self.write("carbon/engine.py", "ENGINE = 1\n")
        self.write("carbon/other.py", "OTHER = 1\n")
        self.write("pyproject.toml", "[project]\n")
        self.write("docs/listed.md", "listed\n")
        self.write("README.md", "readme\n")
        self.write("scripts/validator_host_classes/a.json", "{}\n")
        self.accepted = self.commit("accepted")
        self.publish()

    def git(self, *args):
        return subprocess.run(
            ["git", *args],
            cwd=self.path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def write(self, name, text):
        target = self.path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def publish(self):
        """HEAD is now what fetched origin/main says."""
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")

    def accept(self, revision=None):
        return rc.accepted_values_descendant(
            self.accepted if revision is None else revision, repository=self.path
        )


@pytest.fixture
def repo(tmp_path):
    return Repo(tmp_path)


def refused(repo, code, **kwargs):
    with pytest.raises(rc.DescendantRefused) as caught:
        repo.accept(**kwargs)
    assert caught.value.code == code


def test_the_accepted_revision_itself_is_accepted_with_its_identity(repo):
    found = repo.accept()
    assert found == {
        "revision": repo.accepted,
        "tree": repo.git("rev-parse", f"{repo.accepted}^{{tree}}"),
        "source_tree_digest": build_inputs.digest(repo.path, revision=repo.accepted),
        "running_head": repo.accepted,
    }


def test_a_values_only_descendant_on_main_is_accepted_and_names_the_accepted_identity(
    repo,
):
    accepted_digest = build_inputs.digest(repo.path, revision=repo.accepted)
    repo.write("scripts/validator_host_classes/b.json", '{"v": 2}\n')
    repo.write("carbon/challenge_validator/exam_cadence.json", "{}\n")
    repo.write("scripts/dev/miner_launchpad/published_endpoints.json", "[]\n")
    repo.write("docs/deep/new.md", "x\n")
    repo.write("tests/cpu/test_new.py", "pass\n")
    repo.write("NOTES.md", "n\n")
    head = repo.commit("values")
    repo.publish()
    found = repo.accept()
    assert found["running_head"] == head != repo.accepted
    assert found["revision"] == repo.accepted
    assert found["source_tree_digest"] == accepted_digest
    assert found["tree"] == repo.git("rev-parse", f"{repo.accepted}^{{tree}}")


def test_a_carbon_change_is_refused_even_when_the_build_inputs_digest_is_unchanged(
    repo,
):
    repo.write("carbon/other.py", "OTHER = 2\n")  # not a build input
    repo.commit("code")
    repo.publish()
    assert build_inputs.digest(repo.path) == build_inputs.digest(
        repo.path, revision=repo.accepted
    )
    refused(repo, "receiver_descendant_path_not_allowed")


def test_an_allowed_path_that_is_a_build_input_moves_the_digest_and_is_refused(repo):
    repo.write(
        "docs/listed.md", "listed, changed\n"
    )  # a docs path the image build reads
    repo.commit("docs")
    repo.publish()
    refused(repo, "receiver_build_inputs_moved")


def test_a_rename_out_of_a_forbidden_path_is_refused(repo):
    repo.git("mv", "carbon/other.py", "docs/other.py")
    repo.commit("rename")
    repo.publish()
    refused(repo, "receiver_descendant_path_not_allowed")


def test_a_descendant_that_is_not_on_fetched_main_is_refused(repo):
    repo.write("docs/new.md", "x\n")
    repo.commit("local only")  # origin/main still at the accepted revision
    refused(repo, "receiver_revision_not_descendant")


def test_a_head_that_is_not_a_descendant_is_refused(repo):
    repo.write("docs/a.md", "a\n")
    sibling = repo.commit("sibling of the accepted revision's child")
    repo.git("checkout", "-q", "-b", "other", repo.accepted)
    repo.write("docs/b.md", "b\n")
    repo.commit("other branch")
    repo.publish()
    refused(repo, "receiver_revision_not_descendant", revision=sibling)


def test_a_head_behind_the_accepted_revision_is_refused(repo):
    repo.write("docs/a.md", "a\n")
    later = repo.commit("later")
    repo.publish()
    repo.git("checkout", "-q", "--detach", repo.accepted)
    refused(repo, "receiver_revision_not_descendant", revision=later)


def test_a_dirty_tracked_tree_is_refused_at_the_revision_and_at_a_descendant(repo):
    (repo.path / "README.md").write_text("edited\n", encoding="utf-8")
    refused(repo, "receiver_tree_dirty")
    repo.git("checkout", "--", "README.md")
    repo.write("docs/a.md", "a\n")
    repo.commit("values")
    repo.publish()
    repo.accept()
    (repo.path / "docs" / "a.md").write_text("edited\n", encoding="utf-8")
    refused(repo, "receiver_tree_dirty")


def test_an_untracked_file_does_not_make_the_tree_dirty(repo):
    repo.write("scratch.txt", "x\n")
    assert repo.accept()["running_head"] == repo.accepted


@pytest.mark.parametrize("revision", ["", "abc", "A" * 40, "g" * 40, None, 7])
def test_a_malformed_revision_is_refused(repo, revision):
    with pytest.raises(rc.DescendantRefused) as caught:
        rc.accepted_values_descendant(revision, repository=repo.path)
    assert caught.value.code == "receiver_revision_not_descendant"


@pytest.mark.parametrize(
    "path,allowed",
    [
        ("scripts/validator_host_classes/a.json", True),
        ("scripts/validator_host_classes/sub/a.json", False),
        ("scripts/validator_host_classes/a.py", False),
        ("scripts/validator_host_classes/.json", False),
        ("carbon/challenge_validator/exam_cadence.json", True),
        ("carbon/challenge_validator/exam_cap.py", False),
        ("scripts/dev/miner_launchpad/published_endpoints.json", True),
        ("scripts/dev/miner_launchpad/app.js", False),
        ("docs/a.md", True),
        ("docs/deep/er/a.png", True),
        ("docs", False),
        ("docs/", False),
        ("tests/cpu/test_a.py", True),
        ("tests", False),
        (".ci/workflows/ci.yml", True),
        (".ci/x", True),
        (".ci", False),
        (".ci/", False),
        (".cix/x", False),
        (".github/workflows/ci.yml", False),
        ("scripts/dev/miner_launchpad/runner.py", False),
        ("scripts/dev/miner_launchpad/installed.py", False),
        ("scripts/dev/miner_launchpad/controller.py", False),
        ("README.md", True),
        (".md", False),
        ("sub/README.md", False),
        ("carbon/x.py", False),
        ("pyproject.toml", False),
    ],
)
def test_the_allowed_paths_are_exactly_the_values_paths(path, allowed):
    assert rc.descendant_path_allowed(path) is allowed


def test_the_exact_revision_rule_is_unchanged_for_its_other_callers():
    import inspect

    source = inspect.getsource(rc.accepted_implementation)
    assert "head != revision" in source and "origin/main" in source
    assert "accepted_values_descendant" not in source


# --- the grade record names the commit it ran on ----------------------------------------------------------------


def test_the_grade_record_names_the_running_head(repo):
    """`grade-installed-commit.json` (written once beside every official grade's private binding) is read from the same
    checkout HEAD that `accepted_values_descendant` reports as `running_head`, with the build-inputs digest of that commit.
    """
    from carbon.challenge_validator import lean_recipe_retention as retention

    repo.write("docs/new.md", "x\n")
    head = repo.commit("values")
    repo.publish()
    record = retention.read_installed_commit(repo.path)
    found = repo.accept()
    assert record["commit"] == found["running_head"] == head
    assert record["dirty"] is False
    assert record["build_inputs_digest"] == found["source_tree_digest"]
    assert (
        record["commit"] != found["revision"]
    )  # the accepted revision stays the identity; the record names the head


def test_the_sidecar_is_written_with_every_official_grade():
    import inspect

    from carbon.challenge_validator import lean_recipe_retention as retention

    source = inspect.getsource(retention)
    assert "write_once(directory / INSTALLED_COMMIT_SIDECAR" in source


def test_a_local_only_revision_is_refused_even_when_head_is_exactly_it(repo):
    """`accepted_implementation` always required the revision to be in fetched main; so does this."""
    repo.write("docs/local.md", "x\n")
    local = repo.commit(
        "never pushed"
    )  # origin/main stays at the first accepted revision
    refused(repo, "receiver_revision_not_descendant", revision=local)


def test_an_unknown_object_or_unreadable_repository_is_typed_not_a_traceback(
    repo, tmp_path
):
    refused(repo, "receiver_revision_not_descendant", revision="0" * 40)
    with pytest.raises(rc.DescendantRefused) as caught:
        rc.accepted_values_descendant(repo.accepted, repository=tmp_path / "absent")
    assert caught.value.code == "receiver_revision_not_descendant"
