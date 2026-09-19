"""Regression coverage for the Workbench release freshness gate.

The determinism test in test_sources.py rebuilds the artifact before capturing
its first comparison bytes, so it can only show that a build repeats itself. It
cannot show that the tracked artifact was produced by the tracked sources. The
cases here pin the missing condition and, just as importantly, pin that a
failure reports staleness instead of silently repairing it.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = "tools/check_release_freshness.py"
HTML = "Carbon_Opportunity_Workbench.html"
MANIFEST = "MANIFEST.json"
ARCHIVE = "Carbon_Physics_Goal_Workbench_v0_10.zip"
ARCHIVE_PREFIX = "carbon_goal_workbench_v0_10/"
SCIENTIFIC_STUDIES = "src/scientific_studies.js"

GENERATORS = (
    "tools/build.py",
    "tools/build_goal_schema.py",
    "tools/package_release.py",
)

# Historical archives are excluded from the payload list, so omitting them from
# a staged copy cannot change generated output and keeps each case cheap.
HISTORICAL_ARCHIVE_PREFIX = "Carbon_Physics_Goal_Workbench_v0_"
CURRENT_ARCHIVE_SUFFIX = "v0_10.zip"
LEGACY_ARCHIVE = "Carbon_Physics_Opportunity_Workbench_v0_2.zip"


def _is_historical_archive(relative: str) -> bool:
    if relative == LEGACY_ARCHIVE:
        return True
    return relative.startswith(HISTORICAL_ARCHIVE_PREFIX) and not relative.endswith(
        CURRENT_ARCHIVE_SUFFIX
    )


def _tracked() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "."],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [entry for entry in result.stdout.split("\0") if entry]


def _git(tree: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=tree,
        check=True,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
        },
    )


def _stage(tree: Path) -> None:
    """Build a self-contained, Git-tracked copy of the Workbench."""
    for relative in _tracked():
        if _is_historical_archive(relative):
            continue
        source = ROOT / relative
        if not source.is_file():
            continue
        target = tree / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    _git(tree, "init", "--quiet")
    _git(tree, "add", "-A")
    _git(
        tree,
        "-c",
        "user.email=t@t",
        "-c",
        "user.name=t",
        "commit",
        "--quiet",
        "-m",
        "staged",
    )


def _regenerate(tree: Path) -> None:
    for generator in GENERATORS:
        subprocess.run(
            [sys.executable, generator],
            cwd=tree,
            check=True,
            capture_output=True,
            text=True,
        )


def _gate(tree: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, TOOL],
        cwd=tree,
        capture_output=True,
        text=True,
        check=False,
    )


class FreshnessGateTest(unittest.TestCase):
    """Each case works on an isolated staged copy, never the real tree."""

    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        import tempfile

        cls._baseline = Path(tempfile.mkdtemp(prefix="carbon-freshness-baseline-"))
        _stage(cls._baseline)
        # A staged copy inherits whatever staleness the repository has, so make
        # the baseline genuinely current before any case asserts on it.
        _regenerate(cls._baseline)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._baseline, ignore_errors=True)

    def fresh_tree(self) -> Path:
        import tempfile

        tree = Path(tempfile.mkdtemp(prefix="carbon-freshness-case-"))
        shutil.rmtree(tree)
        shutil.copytree(self._baseline, tree, symlinks=True)
        self.addCleanup(shutil.rmtree, tree, ignore_errors=True)
        return tree

    # --- the condition the determinism test cannot express -----------------

    def test_regenerated_tree_passes(self):
        result = _gate(self.fresh_tree())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("current", result.stdout)

    def test_tracked_repository_release_is_current(self):
        """The real tracked artifacts must match their tracked sources."""
        result = _gate(ROOT)
        self.assertEqual(
            result.returncode,
            0,
            "tracked Workbench release is stale:\n" + result.stderr,
        )

    def test_source_change_without_regeneration_fails(self):
        tree = self.fresh_tree()
        target = tree / SCIENTIFIC_STUDIES
        target.write_text(
            target.read_text(encoding="utf-8") + "\n// upstream change\n",
            encoding="utf-8",
        )
        result = _gate(tree)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(HTML, result.stderr)

    def test_upstream_scientific_studies_drift_is_reported_in_the_archive(self):
        """The real defect: a merged science source change, never rebuilt."""
        tree = self.fresh_tree()
        target = tree / SCIENTIFIC_STUDIES
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                "const BUNDLE", "const BUNDLE_RENAMED_UPSTREAM", 1
            ),
            encoding="utf-8",
        )
        result = _gate(tree)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(ARCHIVE, result.stderr)
        self.assertIn("src/scientific_studies.js", result.stderr)

    # --- failures must not repair, overwrite or repin ----------------------

    def test_edited_artifact_fails_and_is_not_overwritten(self):
        tree = self.fresh_tree()
        target = tree / HTML
        tampered = target.read_bytes() + b"<!-- hand edited -->"
        target.write_bytes(tampered)
        result = _gate(tree)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(
            target.read_bytes(),
            tampered,
            "the gate overwrote the artifact it was asked to verify",
        )

    def test_failure_does_not_repin_the_manifest(self):
        tree = self.fresh_tree()
        (tree / SCIENTIFIC_STUDIES).write_text("// emptied\n", encoding="utf-8")
        before = (tree / MANIFEST).read_bytes()
        result = _gate(tree)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(
            (tree / MANIFEST).read_bytes(),
            before,
            "the gate rewrote the expected digests instead of reporting drift",
        )

    def test_missing_generated_artifact_fails(self):
        """A tracked artifact that is absent stops the comparison outright."""
        tree = self.fresh_tree()
        (tree / HTML).unlink()
        result = _gate(tree)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("missing", result.stderr)
        self.assertIn(HTML, result.stderr)

    # --- manifest and archive integrity ------------------------------------

    def test_manifest_entry_disagreeing_with_its_payload_fails(self):
        tree = self.fresh_tree()
        manifest = json.loads((tree / MANIFEST).read_text(encoding="utf-8"))
        entry = manifest["files"]["src/team_review.js"]
        entry["sha256"] = "0" * 64
        (tree / MANIFEST).write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        result = _gate(tree)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(MANIFEST, result.stderr)

    def test_archive_member_drift_fails(self):
        tree = self.fresh_tree()
        archive = tree / ARCHIVE
        with zipfile.ZipFile(archive) as bundle:
            keep = [n for n in bundle.namelist() if not n.endswith("src/workflow.js")]
            payloads = {name: bundle.read(name) for name in keep}
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as out:
            for name, payload in payloads.items():
                out.writestr(name, payload)
        result = _gate(tree)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(ARCHIVE, result.stderr)

    # --- provenance must stay acyclic --------------------------------------

    def test_packaging_provenance_is_not_treated_as_staleness(self):
        """A commit cannot contain its own hash; this field must not be compared."""
        tree = self.fresh_tree()
        manifest = json.loads((tree / MANIFEST).read_text(encoding="utf-8"))
        manifest["integration_revision_at_packaging"] = "f" * 40
        (tree / MANIFEST).write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        result = _gate(tree)
        self.assertEqual(
            result.returncode,
            0,
            "packaging provenance was mistaken for stale content:\n" + result.stderr,
        )

    # --- generation properties ---------------------------------------------

    def test_repeated_generation_is_identical(self):
        tree = self.fresh_tree()
        first = {name: (tree / name).read_bytes() for name in (HTML, ARCHIVE)}
        _regenerate(tree)
        for name, payload in first.items():
            self.assertEqual((tree / name).read_bytes(), payload, name)

    def test_generator_failure_reaches_the_caller(self):
        """A broken generator must surface, not be reported as fresh or stale."""
        tree = self.fresh_tree()
        (tree / "tools/build.py").write_text(
            "import sys\nsys.exit(3)\n", encoding="utf-8"
        )
        result = _gate(tree)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("exited 3", result.stderr)

    # --- authority and offline boundaries ----------------------------------

    def test_regeneration_keeps_the_offline_build_offline(self):
        tree = self.fresh_tree()
        html = (tree / HTML).read_text(encoding="utf-8", errors="ignore")
        for scheme in ("http://", "https://"):
            for marker in ("src=", "href=", "fetch("):
                self.assertNotIn(
                    marker + '"' + scheme,
                    html,
                    "the default build must not reference an external origin",
                )

    def test_regeneration_does_not_promote_qualification_or_launch(self):
        tree = self.fresh_tree()
        html = (tree / HTML).read_text(encoding="utf-8", errors="ignore")
        self.assertIn("NOT_QUALIFIED", html)
        self.assertNotIn("SCIENTIFICALLY_QUALIFIED", html)

    # --- a zero exit is not evidence of output ------------------------------

    def test_generator_exiting_zero_without_output_fails(self):
        """The artifact under test must be produced, not inherited.

        Staging the existing artifacts into the comparison tree would let a
        generator that writes nothing be credited with the file that was
        already there, and the run would compare that file against itself.
        """
        tree = self.fresh_tree()
        (tree / SCIENTIFIC_STUDIES).write_text(
            (tree / SCIENTIFIC_STUDIES).read_text(encoding="utf-8")
            + "\n// upstream change never built\n",
            encoding="utf-8",
        )
        (tree / "tools/build.py").write_text(
            "import sys\nsys.exit(0)\n", encoding="utf-8"
        )
        before = (tree / HTML).read_bytes()
        result = _gate(tree)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("did not produce", result.stderr)
        self.assertIn(HTML, result.stderr)
        self.assertEqual(
            (tree / HTML).read_bytes(), before, "the gate rewrote the artifact"
        )

    def test_generator_producing_only_some_outputs_fails(self):
        """A partial generator must fail on the output it skipped."""
        tree = self.fresh_tree()
        (tree / "tools/build.py").write_text(
            "from pathlib import Path\n"
            "Path('Carbon_Opportunity_Workbench.html').write_text('partial')\n",
            encoding="utf-8",
        )
        result = _gate(tree)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Carbon_Client_Intake_Preview.html", result.stderr)

    def test_untracked_artifact_on_disk_is_not_release_content(self):
        """Membership comes from Git, not from the filesystem."""
        tree = self.fresh_tree()
        _git(tree, "rm", "--cached", "-q", HTML)
        _git(
            tree,
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "--quiet",
            "-m",
            "untrack the artifact",
        )
        result = _gate(tree)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("not tracked", result.stderr)

    # --- archive structure, not just member payloads ------------------------

    def _rewrite_archive(self, tree: Path, mutate) -> bytes:
        archive = tree / ARCHIVE
        original = archive.read_bytes()
        buffer = io.BytesIO()
        with (
            zipfile.ZipFile(io.BytesIO(original)) as source,
            zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as out,
        ):
            mutate(source, out)
        archive.write_bytes(buffer.getvalue())
        return original

    def test_duplicate_archive_member_is_rejected(self):
        """Reading by name collapses duplicates and hides the first entry."""
        tree = self.fresh_tree()
        victim = ARCHIVE_PREFIX + "src/team_review.js"

        def mutate(source, out):
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename == victim:
                    out.writestr(info.filename, b"// tampered first entry\n")
                out.writestr(info.filename, data)

        original = self._rewrite_archive(tree, mutate)
        result = _gate(tree)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("repeats the member name", result.stderr)
        self.assertNotEqual((tree / ARCHIVE).read_bytes(), original)

    def test_link_typed_archive_member_is_rejected(self):
        """Identical bytes, different extraction meaning."""
        tree = self.fresh_tree()
        victim = ARCHIVE_PREFIX + "src/team_review.js"

        def mutate(source, out):
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename == victim:
                    link = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                    link.create_system = 3
                    link.external_attr = 0o120777 << 16
                    link.compress_type = zipfile.ZIP_DEFLATED
                    out.writestr(link, data)
                    continue
                out.writestr(info, data)

        self._rewrite_archive(tree, mutate)
        result = _gate(tree)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("not a regular file", result.stderr)

    def test_archive_member_outside_the_release_prefix_is_rejected(self):
        tree = self.fresh_tree()

        def mutate(source, out):
            for info in source.infolist():
                out.writestr(info, source.read(info.filename))
            out.writestr("../escape.txt", b"traversal\n")

        self._rewrite_archive(tree, mutate)
        result = _gate(tree)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("outside", result.stderr)

    def test_archive_passes_with_only_the_allowed_provenance_difference(self):
        """A legitimately regenerated archive differs only in that one field."""
        result = _gate(self.fresh_tree())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_malformed_packaging_provenance_is_rejected(self):
        """The excluded field's shape is still checked."""
        tree = self.fresh_tree()
        manifest = json.loads((tree / MANIFEST).read_text(encoding="utf-8"))
        manifest["integration_revision_at_packaging"] = "not-a-commit"
        (tree / MANIFEST).write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        result = _gate(tree)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("integration_revision_at_packaging", result.stderr)


if __name__ == "__main__":
    unittest.main()
