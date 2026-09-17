"""Build one offline HTML artifact from the canonical source JSON and JS/CSS."""

import base64
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(s):
    return "sha256-" + base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()


def data(p):
    return (
        json.dumps(json.loads(p.read_text()), ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def build(*, private_science=False, output_directory=None):
    destination = Path(output_directory).resolve() if output_directory else ROOT
    if private_science and destination == ROOT.resolve():
        raise ValueError("Private science builds require a separate output directory")
    destination.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["node", str(ROOT / "tools/check_repository_snapshot_admission.cjs")],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    style = (
        (ROOT / "src/styles.css").read_text()
        + "\n"
        + (ROOT / "src/goal_styles.css").read_text()
    )
    engine = (ROOT / "src/engine.js").read_text()
    app = (ROOT / "src/app.js").read_text()
    routing = (ROOT / "src/routing.js").read_text()
    c05_evidence = (ROOT / "src/c05_evidence.js").read_text()
    source_assessment = (ROOT / "src/source_assessment.js").read_text()
    intake = (ROOT / "src/intake.js").read_text()
    workflow = (ROOT / "src/workflow.js").read_text()
    scientific_studies = (ROOT / "src/scientific_studies.js").read_text()
    scientific_studies_ui = (ROOT / "src/scientific_studies_ui.js").read_text()
    goal_app = (ROOT / "src/goal_app.js").read_text()
    atlas = data(ROOT / "data/atlas.json")
    studies = data(ROOT / "data/studies.json")
    cpes = data(ROOT / "data/cpes_study_v1.json")
    c05_index = data(ROOT / "data/c05_fixture_index_v2.json")
    assessment_profile = data(
        ROOT / "source_assessment/repository_snapshot/v1/profile.json"
    )
    assessment_index = data(
        ROOT / "source_assessment/repository_snapshot/v1/approved_assessments.json"
    )
    scripts = " ".join(
        "'" + digest(s) + "'"
        for s in [
            engine,
            app,
            routing,
            c05_evidence,
            source_assessment,
            intake,
            workflow,
            scientific_studies,
            scientific_studies_ui,
            goal_app,
            atlas,
            studies,
            cpes,
            c05_index,
            assessment_profile,
            assessment_index,
        ]
    )
    connection_policy = "'self'" if private_science else "'none'"
    csp = f"default-src 'none'; script-src {scripts}; style-src '{digest(style)}'; img-src data:; connect-src {connection_policy}; form-action 'none'; base-uri 'none'; object-src 'none'"
    html = (ROOT / "src/shell.html").read_text()
    for k, v in {
        "CSP": csp,
        "STYLE": style,
        "ATLAS": atlas,
        "STUDIES": studies,
        "CPES": cpes,
        "C05_INDEX": c05_index,
        "SOURCE_ASSESSMENT_PROFILE": assessment_profile,
        "SOURCE_ASSESSMENT_INDEX": assessment_index,
        "ENGINE": engine,
        "APP": app,
        "ROUTING": routing,
        "C05_EVIDENCE": c05_evidence,
        "SOURCE_ASSESSMENT": source_assessment,
        "INTAKE": intake,
        "WORKFLOW": workflow,
        "SCIENTIFIC_STUDIES": scientific_studies,
        "SCIENTIFIC_STUDIES_UI": scientific_studies_ui,
        "SCIENCE_MODE": "private" if private_science else "offline",
        "GOAL_APP": goal_app,
    }.items():
        html = html.replace("{{" + k + "}}", v)
    (destination / "Carbon_Opportunity_Workbench.html").write_text(html)
    intake_style = (ROOT / "src/intake_styles.css").read_text()
    intake_app = (ROOT / "src/intake_app.js").read_text()
    intake_csp = (
        "default-src 'none'; script-src "
        + " ".join("'" + digest(value) + "'" for value in [intake, intake_app])
        + "; style-src '"
        + digest(intake_style)
        + "'; img-src data:; connect-src 'self'; form-action 'none'; base-uri 'none'; object-src 'none'"
    )
    preview = (ROOT / "src/intake_shell.html").read_text()
    for key, value in {
        "CSP": intake_csp,
        "STYLE": intake_style,
        "INTAKE": intake,
        "APP": intake_app,
    }.items():
        preview = preview.replace("{{" + key + "}}", value)
    (destination / "Carbon_Client_Intake_Preview.html").write_text(preview)
    (destination / "Carbon_Client_Pilot_Designer_Preview.html").write_text(preview)
    return destination / "Carbon_Opportunity_Workbench.html"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--private-science", action="store_true")
    parser.add_argument("--output-directory", type=Path)
    options = parser.parse_args()
    print(
        build(
            private_science=options.private_science,
            output_directory=options.output_directory,
        )
    )
