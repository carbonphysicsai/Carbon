"""f17 OpenFOAM v2506 decks: mesh, steady laminar flow, steady passive scalar.

    python3 f17_deck.py DIR --depth 40 --pitch 100 --reversal 6 --h 10 \
        [--flows 1 3 5] [--diffusivities 5e-11 1e-10 2e-10]

One case directory = one design at one mesh rung with every requested flow
and diffusivity, run by ONE container command (`bash Allrun`):

    mesh/      blockMesh + snappyHexMesh on the conforming floor-sheet STL,
               scaled um -> m, checkMesh (`mesh` stage; may be pre-frozen)
    flow_qQ/   simpleFoam (laminar, SIMPLEC) to the registered residuals;
               receipt.txt binds flow key and sha256 of U, p, phi
    scalar_qQ_dD/  scalarTransportFoam, steady, reading that flow's EXACT phi;
               refuses to start unless the flow receipt's key equals the key
               this scalar case was frozen against and the copied phi hash
               equals the receipt (fail closed; no createPhi fallback)

Numerical settings are the registered DEVELOPMENT values of
`.agent/decisions/2026-10-15-F17-SCIENCE-VALUES-01.md` (N1-N6).
Everything is written deterministically (sorted, fixed formatting).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f17_geometry as geo

RHO, MU = 998.0, 0.001
NU = MU / RHO
FLOWS = (1, 3, 5)
DIFFUSIVITIES = (5e-11, 1e-10, 2e-10)
SCALAR_SCHEMES = {
    "linearUpwind": "bounded Gauss linearUpwind grad(T)",
    "limitedLinear01": "bounded Gauss limitedLinear01 1",
    "upwind": "bounded Gauss upwind",
}
PRIMARY_SCHEME = "linearUpwind"  # N3
#: N1-N6 of the science-values decision (flow/scalar iteration controls)
FLOW_RESIDUAL = {"p": 1e-6, "U": 1e-7}
FLOW_MAX_ITER = 4000
SCALAR_STEADY_TOL = 1e-7  # N5: |window mean - current| of outlet <c^2>
SCALAR_WINDOW = 10
SCALAR_MAX_ITER = 300
IMAGE = json.loads((HERE / "image.lock.json").read_text())["run_reference"]


def header(cls, obj, location=None):
    loc = f' location "{location}";' if location else ""
    return (
        f"FoamFile {{ version 2.0; format ascii; class {cls};{loc} object {obj}; }}\n"
    )


def fmt(v):
    return f"{v:.17g}"


def counts(design, h_um):
    d = float(design["depth_um"])
    return {
        "nx": round(geo.L_UM / h_um),
        "ny_half": round(geo.W_UM / 2 / h_um),
        "nz_channel": round(geo.H_UM / h_um),
        "nz_groove": max(2, round(d / h_um)),
    }


def block_mesh(design, h_um):
    d = float(design["depth_um"])
    c = counts(design, h_um)
    zb = -d - d / c["nz_groove"]  # one sacrificial layer below the recess
    xs, ys, zs = (0.0, geo.L_UM), (0.0, geo.W_UM / 2, geo.W_UM), (zb, -d, 0.0, geo.H_UM)
    nzs = (1, c["nz_groove"], c["nz_channel"])
    verts, index = [], {}
    for k, z in enumerate(zs):
        for j, y in enumerate(ys):
            for i, x in enumerate(xs):
                index[i, j, k] = len(verts)
                verts.append(f"({fmt(x)} {fmt(y)} {fmt(z)})")
    blocks, patches = [], {
        "inlet0": [], "inlet1": [], "outlet": [], "sides": [], "top": [], "outside": [],
    }  # fmt: skip
    for k in range(3):
        for j in range(2):
            v = [
                index[0, j, k], index[1, j, k], index[1, j + 1, k], index[0, j + 1, k],
                index[0, j, k + 1], index[1, j, k + 1], index[1, j + 1, k + 1],
                index[0, j + 1, k + 1],
            ]  # fmt: skip
            blocks.append(
                f"hex ({' '.join(map(str, v))}) ({c['nx']} {c['ny_half']} {nzs[k]}) "
                "simpleGrading (1 1 1)"
            )
            inlet = (v[0], v[4], v[7], v[3])
            outlet = (v[1], v[2], v[6], v[5])
            patches[f"inlet{j}" if k == 2 else "outside"].append(inlet)
            patches["outlet" if k == 2 else "outside"].append(outlet)
            if j == 0:
                patches["sides" if k == 2 else "outside"].append(
                    (v[0], v[1], v[5], v[4])
                )
            else:
                patches["sides" if k == 2 else "outside"].append(
                    (v[3], v[7], v[6], v[2])
                )
            if k == 0:
                patches["outside"].append((v[0], v[3], v[2], v[1]))
            if k == 2:
                patches["top"].append((v[4], v[5], v[6], v[7]))
    kinds = {"sides": "wall", "top": "wall"}
    body = header("dictionary", "blockMeshDict") + "scale 1;\nvertices\n(\n"
    body += "\n".join(verts) + "\n);\nblocks\n(\n" + "\n".join(blocks) + "\n);\n"
    body += "edges ();\nboundary\n(\n"
    for name, faces in patches.items():
        body += f"{name} {{ type {kinds.get(name, 'patch')}; faces ("
        body += " ".join("(" + " ".join(map(str, f)) + ")" for f in faces) + "); }\n"
    return body + ");\nmergePatchPairs ();\n"


def snappy(design, h_um):
    # a point inside the fluid, off every face and cell centre
    loc = (geo.L_UM / 2 + 0.37 * h_um, geo.W_UM / 2 + 0.31 * h_um, 50 + 0.29 * h_um)
    return (
        header("dictionary", "snappyHexMeshDict")
        + f"""castellatedMesh true;
snap true;
addLayers false;
geometry {{ bottom.stl {{ type triSurfaceMesh; name bottom; }} }}
castellatedMeshControls
{{
    maxLocalCells 100000000; maxGlobalCells 200000000; minRefinementCells 0;
    maxLoadUnbalance 0.10; nCellsBetweenLevels 2;
    features ( {{ file "bottom.eMesh"; level 0; }} );
    refinementSurfaces {{ bottom {{ level (0 0); patchInfo {{ type wall; }} }} }}
    resolveFeatureAngle 30;
    refinementRegions {{ }}
    locationInMesh ({fmt(loc[0])} {fmt(loc[1])} {fmt(loc[2])});
    allowFreeStandingZoneFaces true;
}}
snapControls
{{
    nSmoothPatch 3; tolerance 2.0; nSolveIter 100; nRelaxIter 5;
    nFeatureSnapIter 15; implicitFeatureSnap false; explicitFeatureSnap true;
    multiRegionFeatureSnap false;
}}
addLayersControls
{{
    relativeSizes true; layers {{ }}; expansionRatio 1.0; finalLayerThickness 0.3;
    minThickness 0.1; nGrow 0; featureAngle 60; nRelaxIter 3; nSmoothSurfaceNormals 1;
    nSmoothNormals 3; nSmoothThickness 10; maxFaceThicknessRatio 0.5;
    maxThicknessToMedialRatio 0.3; minMedialAxisAngle 90; nBufferCellsNoExtrude 0;
    nLayerIter 50;
}}
meshQualityControls
{{
    #includeEtc "caseDicts/mesh/generation/meshQualityDict.cfg"
}}
mergeTolerance 1e-6;
"""
    )


def smooth_block_mesh(h_um):
    """Smooth-duct control: the channel block only, z = 0 is the 'bottom' wall."""
    nx, ny, nz = (
        round(geo.L_UM / h_um),
        round(geo.W_UM / 2 / h_um),
        round(geo.H_UM / h_um),
    )
    xs, ys, zs = (0.0, geo.L_UM), (0.0, geo.W_UM / 2, geo.W_UM), (0.0, geo.H_UM)
    verts, index = [], {}
    for k, z in enumerate(zs):
        for j, y in enumerate(ys):
            for i, x in enumerate(xs):
                index[i, j, k] = len(verts)
                verts.append(f"({fmt(x)} {fmt(y)} {fmt(z)})")
    blocks, patches = (
        [],
        {n: [] for n in ("inlet0", "inlet1", "outlet", "sides", "top", "bottom")},
    )
    for j in range(2):
        v = [index[0, j, 0], index[1, j, 0], index[1, j + 1, 0], index[0, j + 1, 0],
             index[0, j, 1], index[1, j, 1], index[1, j + 1, 1], index[0, j + 1, 1]]  # fmt: skip
        blocks.append(
            f"hex ({' '.join(map(str, v))}) ({nx} {ny} {nz}) simpleGrading (1 1 1)"
        )
        patches[f"inlet{j}"].append((v[0], v[4], v[7], v[3]))
        patches["outlet"].append((v[1], v[2], v[6], v[5]))
        patches["sides"].append(
            (v[0], v[1], v[5], v[4]) if j == 0 else (v[3], v[7], v[6], v[2])
        )
        patches["bottom"].append((v[0], v[3], v[2], v[1]))
        patches["top"].append((v[4], v[5], v[6], v[7]))
    body = header("dictionary", "blockMeshDict") + "scale 1;\nvertices\n(\n"
    body += "\n".join(verts) + "\n);\nblocks\n(\n" + "\n".join(blocks) + "\n);\n"
    body += "edges ();\nboundary\n(\n"
    for name, faces in patches.items():
        kind = "wall" if name in ("sides", "top", "bottom") else "patch"
        body += f"{name} {{ type {kind}; faces ("
        body += " ".join("(" + " ".join(map(str, f)) + ")" for f in faces) + "); }\n"
    return body + ");\nmergePatchPairs ();\n"


def mesh_files(design, h_um):
    common = "writeFormat binary; writeCompression off; writePrecision 17; "
    if design is None:
        return {
            "mesh/system/controlDict": header("dictionary", "controlDict")
            + "application blockMesh; startFrom startTime; startTime 0; "
            "stopAt endTime; endTime 0; deltaT 1; writeControl timeStep; "
            f"writeInterval 1; {common}runTimeModifiable false;\n",
            "mesh/system/fvSchemes": header("dictionary", "fvSchemes")
            + "ddtSchemes { default steadyState; } gradSchemes { default Gauss linear; }"
            " divSchemes { default none; } laplacianSchemes { default Gauss linear corrected; }"
            " interpolationSchemes { default linear; } snGradSchemes { default corrected; }\n",
            "mesh/system/fvSolution": header("dictionary", "fvSolution")
            + "solvers { }\n",
            "mesh/system/blockMeshDict": smooth_block_mesh(h_um),
        }
    return {
        "mesh/system/controlDict": header("dictionary", "controlDict")
        + "application snappyHexMesh; startFrom startTime; startTime 0; "
        "stopAt endTime; endTime 0; deltaT 1; writeControl timeStep; "
        f"writeInterval 1; {common}runTimeModifiable false;\n",
        "mesh/system/fvSchemes": header("dictionary", "fvSchemes")
        + "ddtSchemes { default steadyState; } gradSchemes { default Gauss linear; }"
        " divSchemes { default none; } laplacianSchemes { default Gauss linear corrected; }"
        " interpolationSchemes { default linear; } snGradSchemes { default corrected; }\n",
        "mesh/system/fvSolution": header("dictionary", "fvSolution") + "solvers { }\n",
        "mesh/system/blockMeshDict": block_mesh(design, h_um),
        "mesh/system/snappyHexMeshDict": snappy(design, h_um),
        "mesh/constant/triSurface/bottom.stl": geo.stl(design),
        "mesh/constant/triSurface/bottom.eMesh": geo.feature_edges(design),
    }


MESH_SCRIPT = """#!/bin/bash
# f17 mesh stage: background block, snapped recesses, um -> m, checks.
set -e
cd mesh
blockMesh > log.blockMesh 2>&1
[ -f system/snappyHexMeshDict ] && snappyHexMesh -overwrite > log.snappyHexMesh 2>&1
transformPoints -scale 1e-6 > log.transformPoints 2>&1
checkMesh -constant > log.checkMesh 2>&1 || true
grep -q "Mesh OK" log.checkMesh
postProcess -constant -func writeCellVolumes > log.cellVolumes 2>&1
postProcess -constant -func writeCellCentres > log.cellCentres 2>&1
rm -rf constant/polyMesh/sets constant/extendedFeatureEdgeMesh constant/polyMesh/{cellLevel,pointLevel,level0Edge,surfaceIndex}
cd constant/polyMesh && sha256sum boundary faces neighbour owner points > ../../mesh.sha256
"""


def flow_files(q_ul_min, scalar_names=()):
    q = q_ul_min * 1e-9 / 60
    speed = q / (geo.W_UM * geo.H_UM * 1e-12)
    common = (
        "writeFormat binary; writeCompression off; writePrecision 17; "
        "timeFormat general; timePrecision 8; runTimeModifiable false;"
    )
    probes = (
        "functions { inletP { type surfaceFieldValue; libs (fieldFunctionObjects); "
        "regionType patch; name inlet1; operation areaAverage; fields (p); "
        "writeFields false; log false; writeControl timeStep; writeInterval 1; } "
        "inletP0 { $inletP; name inlet0; } "
        "outletPhi { type surfaceFieldValue; libs (fieldFunctionObjects); "
        "regionType patch; name outlet; operation sum; fields (phi); writeFields false; "
        "log false; writeControl timeStep; writeInterval 1; } }"
    )
    d = f"flow_q{q_ul_min:g}/"
    v = f"uniform ({fmt(speed)} 0 0)"
    return {
        d + "system/controlDict": header("dictionary", "controlDict")
        + f"application simpleFoam; startFrom startTime; startTime 0; stopAt endTime; "
        f"endTime {FLOW_MAX_ITER}; deltaT 1; writeControl timeStep; "
        f"writeInterval {FLOW_MAX_ITER}; purgeWrite 0; {common}\n{probes}\n",
        d + "system/fvSchemes": header("dictionary", "fvSchemes")
        + "ddtSchemes { default steadyState; } gradSchemes { default Gauss linear; } "
        "divSchemes { default none; div(phi,U) bounded Gauss linearUpwind grad(U); "
        "div((nuEff*dev2(T(grad(U))))) Gauss linear; } "
        "laplacianSchemes { default Gauss linear corrected; } "
        "interpolationSchemes { default linear; } snGradSchemes { default corrected; }\n",
        d + "system/fvSolution": header("dictionary", "fvSolution")
        + "solvers { p { solver GAMG; smoother GaussSeidel; tolerance 1e-12; relTol 0.01; } "
        "U { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-14; relTol 0.1; } } "
        "SIMPLE { consistent yes; nNonOrthogonalCorrectors 1; "
        f"residualControl {{ p {FLOW_RESIDUAL['p']:g}; U {FLOW_RESIDUAL['U']:g}; }} }} "
        "relaxationFactors { fields { p 1; } equations { U 0.9; } }\n",
        d + "constant/transportProperties": header("dictionary", "transportProperties")
        + f"transportModel Newtonian;\nnu {fmt(NU)};\n",
        d + "constant/turbulenceProperties": header(
            "dictionary", "turbulenceProperties"
        )
        + "simulationType laminar;\n",
        d + "0/U": header("volVectorField", "U", "0")
        + f"dimensions [0 1 -1 0 0 0 0];\ninternalField {v};\nboundaryField\n{{\n"
        f"    inlet0 {{ type fixedValue; value {v}; }}\n"
        f"    inlet1 {{ type fixedValue; value {v}; }}\n"
        "    outlet { type zeroGradient; }\n"
        '    "(sides|top|bottom|outside)" { type noSlip; }\n}\n',
        d + "0/p": header("volScalarField", "p", "0")
        + "dimensions [0 2 -2 0 0 0 0];\ninternalField uniform 0;\nboundaryField\n{\n"
        '    "(inlet0|inlet1|sides|top|bottom|outside)" { type zeroGradient; }\n'
        "    outlet { type fixedValue; value uniform 0; }\n}\n",
    }


def scalar_files(q_ul_min, d_m2_s, scheme=PRIMARY_SCHEME, tag=None, inlet=(0, 1)):
    """Steady passive scalar on a frozen flow (N3-N5): second-order upwind
    (deferred correction, a linear fixed point) from a uniform start whose
    first iterate is the exact first-order upwind solution; stops when the
    outlet flux-weighted mean square of c is stationary (N5) or at the
    iteration ceiling (then NOT_CONVERGED)."""
    common = (
        "writeFormat binary; writeCompression off; writePrecision 17; "
        "timeFormat general; timePrecision 8; runTimeModifiable false;"
    )
    d = f"{tag or scalar_dir(q_ul_min, d_m2_s, scheme, inlet)}/"
    monitors = (
        "functions {\n"
        " sqT { type magSqr; libs (fieldFunctionObjects); field T; result T2; "
        "executeControl timeStep; writeControl none; }\n"
        " outletMix { type surfaceFieldValue; libs (fieldFunctionObjects); "
        "regionType patch; name outlet; operation weightedAverage; weightField phi; "
        "fields (T T2); writeFields false; log false; writeControl timeStep; "
        "writeInterval 1; }\n"
        " stopWhenSteady { type runTimeControl; libs (utilityFunctionObjects); "
        "conditions { outletSquare { type average; functionObject outletMix; "
        f"fields (weightedAverage(outlet,T2)); tolerance {SCALAR_STEADY_TOL:g}; "
        f"window {SCALAR_WINDOW}; windowType exact; nIterStartUp {SCALAR_WINDOW}; }} }} "
        "satisfiedAction end; }\n}"
    )
    return {
        d + "system/controlDict": header("dictionary", "controlDict")
        + "application scalarTransportFoam; startFrom startTime; startTime 0; "
        f"stopAt endTime; endTime {SCALAR_MAX_ITER}; deltaT 1; writeControl timeStep; "
        f"writeInterval {SCALAR_MAX_ITER}; purgeWrite 0; {common}\n{monitors}\n",
        d + "system/fvSchemes": header("dictionary", "fvSchemes")
        + "ddtSchemes { default steadyState; } gradSchemes { default Gauss linear; } "
        f"divSchemes {{ default none; div(phi,T) {SCALAR_SCHEMES[scheme]}; }} "
        "laplacianSchemes { default Gauss linear corrected; } "
        "interpolationSchemes { default linear; } snGradSchemes { default corrected; }\n",
        d + "system/fvSolution": header("dictionary", "fvSolution")
        + "solvers { T { solver PBiCGStab; preconditioner DILU; tolerance 1e-13; "
        "relTol 0.001; maxIter 1000; } } "
        "SIMPLE { nNonOrthogonalCorrectors 0; } "
        "relaxationFactors { equations { T 1; } }\n",
        d + "constant/transportProperties": header("dictionary", "transportProperties")
        + f"DT {fmt(d_m2_s)};\n",
        d + "0/T": header("volScalarField", "T", "0")
        + "dimensions [0 0 0 0 0 0 0];\ninternalField uniform 0.5;\nboundaryField\n{\n"
        f"    inlet0 {{ type fixedValue; value uniform {inlet[0]:g}; }}\n"
        f"    inlet1 {{ type fixedValue; value uniform {inlet[1]:g}; }}\n"
        '    "(outlet|sides|top|bottom|outside)" { type zeroGradient; }\n}\n',
    }


def scalar_dir(q, d, scheme=None, inlet=(0, 1)):
    scheme = scheme or PRIMARY_SCHEME
    suffix = "" if scheme == PRIMARY_SCHEME else f"_{scheme}"
    if tuple(inlet) != (0, 1):
        suffix += "_uniform" if inlet[0] == inlet[1] else f"_in{inlet[0]:g}{inlet[1]:g}"
    return f"scalar_q{q:g}_d{d * 1e10:g}{suffix}"


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def flow_key(mesh_sha_text, files, q):
    """Cache identity: mesh file hashes + every flow input file + Q + image.
    D is excluded only because the scalar is passive (one-way proof)."""
    parts = [f"image {IMAGE}", f"flow_ul_min {q:g}", mesh_sha_text.strip()]
    prefix = f"flow_q{q:g}/"
    parts += [
        f"{sha(t)}  {p}" for p, t in sorted(files.items()) if p.startswith(prefix)
    ]
    return sha("\n".join(parts) + "\n")


FLOW_SCRIPT = """
body_sha() {  # sha256 of a field file's data (from 'dimensions'), header excluded
  local off; off=$(grep -abo -m1 '^dimensions' "$1" | cut -d: -f1)
  tail -c +$((off + 1)) "$1" | sha256sum | cut -d' ' -f1
}
run_flow() {  # $1 = flow dir, $2 = frozen flow key
  ( cd "$1" && ln -sfn ../../mesh/constant/polyMesh constant/polyMesh &&
    simpleFoam > log.simpleFoam 2>&1 ) || return 1
  local t; t=$(cd "$1" && foamListTimes -latestTime -noZero 2>/dev/null | tail -1)
  [ -n "$t" ] || return 1
  grep -q "SIMPLE solution converged" "$1/log.simpleFoam" || echo NOT_CONVERGED > "$1/STATUS"
  { echo "flow_key $2"; echo "time $t"; echo "phi_data $(body_sha "$1/$t/phi")";
    (cd "$1/$t" && sha256sum U p phi); } > "$1/receipt.txt"
}
run_scalar() {  # $1 = scalar dir, $2 = flow dir, $3 = flow key this scalar was frozen against
  local r="$2/receipt.txt"
  [ -f "$r" ] || { echo "REFUSED no flow receipt" > "$1/STATUS"; return 2; }
  [ "$(sed -n 's/^flow_key //p' "$r")" = "$3" ] ||
    { echo "REFUSED flow key mismatch" > "$1/STATUS"; return 2; }
  local t; t=$(sed -n 's/^time //p' "$r")
  cp "$2/$t/U" "$2/$t/phi" "$1/0/"
  [ "$(cd "$1/0" && sha256sum phi)" = "$(grep ' phi$' "$r")" ] ||
    { echo "REFUSED phi hash mismatch" > "$1/STATUS"; return 2; }
  ( cd "$1" && ln -sfn ../../mesh/constant/polyMesh constant/polyMesh &&
    scalarTransportFoam > log.scalarTransportFoam 2>&1 ) || return 1
  local s; s=$(cd "$1" && foamListTimes -latestTime -noZero 2>/dev/null | tail -1)
  # the solver must have kept the exact retained phi (never recomputed it)
  [ "$(body_sha "$1/$s/phi")" = "$(sed -n 's/^phi_data //p' "$r")" ] ||
    { echo "PHI_CHANGED" > "$1/STATUS"; return 1; }
  grep -q "^End" "$1/log.scalarTransportFoam" || return 1
  [ "$s" -lt "$(sed -n 's/.*endTime \\([0-9]*\\);.*/\\1/p' "$1/system/controlDict")" ] ||
    echo NOT_CONVERGED > "$1/STATUS"
  return 0
}
"""


def write_case(out, design, h_um, flows=FLOWS, diffusivities=DIFFUSIVITIES,
               scalar_specs=None, mesh_stage=True, label=None):  # fmt: skip
    """Write one case directory; returns its deck.json payload.

    scalar_specs: optional list of (q, D, scheme) overriding flows x diffusivities.
    """
    out = Path(out)
    smooth = design is None  # smooth-duct control
    report = None if smooth else geo.check(design)
    files = mesh_files(design, h_um)
    for q in flows:
        files.update(flow_files(q))
    specs = (
        scalar_specs
        if scalar_specs is not None
        else [(q, d, PRIMARY_SCHEME) for q in flows for d in diffusivities]
    )
    specs = [tuple(sp) + ((0, 1),) * (4 - len(sp)) for sp in specs]
    for q, d, scheme, inlet in specs:
        files.update(scalar_files(q, d, scheme, inlet=inlet))
    for path, text in sorted(files.items()):
        p = out / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    deck = {
        "schema": "carbon.f17.openfoam-deck.v1",
        "scope": "PUBLIC_DEVELOPMENT",
        "label": label,
        "design": design,
        "mesh_h_um": h_um,
        "block_counts": None if smooth else counts(design, h_um),
        "geometry": report,
        "analytic_volume_m3": (
            geo.L_UM * geo.W_UM * geo.H_UM if smooth else report["fluid_volume_um3"]
        )
        * 1e-18,
        "surface": None if smooth else geo.surface_check(design),
        "flows_ul_min": list(flows),
        "scalars": [
            {
                "dir": scalar_dir(q, d, s, i),
                "flow_ul_min": q,
                "diffusivity_m2_s": d,
                "scheme": s,
                "inlet_c": list(i),
            }
            for q, d, s, i in specs
        ],
        "rho_kg_m3": RHO,
        "mu_pa_s": MU,
        "image": IMAGE,
        "decision": ".agent/decisions/2026-10-15-F17-SCIENCE-VALUES-01.md",
    }
    (out / "deck.json").write_text(json.dumps(deck, indent=1, sort_keys=True) + "\n")
    (out / "Allmesh").write_text(MESH_SCRIPT)
    write_allrun(out, deck, mesh_stage)
    return deck


def write_allrun(out, deck, mesh_stage):
    """Allrun = mesh (unless frozen) + flows + scalars; keys bind mesh hashes."""
    out = Path(out)
    (out / "functions.sh").write_text(FLOW_SCRIPT.lstrip())
    files = {
        str(p.relative_to(out)): p.read_text()
        for p in sorted(out.glob("flow_q*/**/*"))
        if p.is_file() and p.name not in ("receipt.txt", "STATUS")
    }
    keys = [f"K{q:g}=$({key_command(files, q)})" for q in deck["flows_ul_min"]]
    (out / "keys.sh").write_text("\n".join(keys) + "\n")
    lines = [
        "#!/bin/bash",
        "# f17 one-design case: one container command (bash Allrun).",
        'cd "$(dirname "$0")"',
        (
            "command -v simpleFoam > /dev/null ||"
            " source /usr/lib/openfoam/openfoam2506/etc/bashrc"
        ),
    ]
    if mesh_stage:
        lines.append("[ -f mesh/mesh.sha256 ] || bash Allmesh || exit 3")
    lines += ["source functions.sh", "source keys.sh", "rc=0"]
    for q in deck["flows_ul_min"]:
        lines.append(f'run_flow flow_q{q:g} "$K{q:g}" || rc=1')
    for s in deck["scalars"]:
        q = s["flow_ul_min"]
        lines.append(f'run_scalar {s["dir"]} flow_q{q:g} "$K{q:g}" || rc=1')
    lines.append("exit $rc")
    (out / "Allrun").write_text("\n".join(lines) + "\n")


def key_command(files, q):
    """Shell that prints flow_key(): mesh hashes + flow input hashes + Q + image."""
    prefix = f"flow_q{q:g}/"
    names = " ".join(p for p in sorted(files) if p.startswith(prefix))
    return (
        f"{{ echo 'image {IMAGE}'; echo 'flow_ul_min {q:g}'; cat mesh/mesh.sha256; "
        f"sha256sum {names}; }} | sha256sum | cut -d' ' -f1"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("--depth", type=float, required=True)
    parser.add_argument("--pitch", type=float, required=True)
    parser.add_argument("--reversal", type=int, required=True)
    parser.add_argument("--h", type=float, default=10.0)
    parser.add_argument("--flows", type=float, nargs="+", default=list(FLOWS))
    parser.add_argument(
        "--diffusivities", type=float, nargs="+", default=list(DIFFUSIVITIES)
    )
    args = parser.parse_args(argv)
    design = {"depth_um": args.depth, "pitch_um": args.pitch, "reversal": args.reversal}
    deck = write_case(args.out, design, args.h, args.flows, args.diffusivities)
    print(json.dumps(deck["geometry"]))


if __name__ == "__main__":
    main()
