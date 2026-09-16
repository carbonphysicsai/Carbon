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


def build():
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
            goal_app,
            atlas,
            studies,
            cpes,
            c05_index,
            assessment_profile,
            assessment_index,
        ]
    )
    csp = f"default-src 'none'; script-src {scripts}; style-src '{digest(style)}'; img-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'; object-src 'none'"
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
        "GOAL_APP": goal_app,
    }.items():
        html = html.replace("{{" + k + "}}", v)
    (ROOT / "Carbon_Opportunity_Workbench.html").write_text(html)
    intake_style = (ROOT / "src/intake_styles.css").read_text()
    intake_app = (ROOT / "src/intake_app.js").read_text()
    intake_csp = (
        "default-src 'none'; script-src "
        + " ".join("'" + digest(value) + "'" for value in [intake, intake_app])
        + "; style-src '"
        + digest(intake_style)
        + "'; img-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'; object-src 'none'"
    )
    preview = (ROOT / "src/intake_shell.html").read_text()
    for key, value in {
        "CSP": intake_csp,
        "STYLE": intake_style,
        "INTAKE": intake,
        "APP": intake_app,
    }.items():
        preview = preview.replace("{{" + key + "}}", value)
    (ROOT / "Carbon_Client_Intake_Preview.html").write_text(preview)
    return ROOT / "Carbon_Opportunity_Workbench.html"


if __name__ == "__main__":
    print(build())
