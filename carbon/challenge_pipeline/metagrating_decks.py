"""Source-pinned Meep/S4 3D deck drafts. Rendering never runs either solver.

API/field-convention smoke tests and convergence in the pinned image remain
Data Collection's responsibility. Every deck is explicitly unverified.
"""

from __future__ import annotations

import json
import math

from carbon.challenge_pipeline import benchmark_mg as b
from carbon.design_search import tasks


def _validate(action, hardware, controls):
    b.binary_mask(action["mask"])
    thickness = b.number(action["thickness_nm"], positive=True)
    px, py = [b.number(v, positive=True) for v in hardware["periods_nm"]]
    verification = hardware.get("verification_case")
    if verification not in (
        None,
        "zero-contrast-periodic-grating",
        "planar-lossless-slab",
    ):
        raise b.PreparationError("unsupported analytic verification case")
    if verification == "zero-contrast-periodic-grating":
        if (
            hardware["n_in"] != 1
            or hardware["n_out"] != 1
            or hardware.get("n_layer") != 1
        ):
            raise b.PreparationError(
                "zero-contrast verification requires identical media"
            )
    elif (
        hardware["wavelength_nm"] != 1050
        or hardware["n_in"] != 1.45
        or hardware["n_out"] != 1
    ):
        raise b.PreparationError(
            "source-supported monochromatic substrate/air route required"
        )
    if (
        verification != "zero-contrast-periodic-grating"
        and hardware.get("n_layer", 3.45) != 3.45
    ):
        raise b.PreparationError(
            "source layer index fixed outside explicit analytic test"
        )
    if not b.feature_check(
        action["mask"],
        periods_nm=[px, py],
        minimum_feature_nm=hardware["minimum_feature_nm"],
    )["passes_registered_run_rule"]:
        raise b.PreparationError("mask violates registered minimum run-width")
    for key in ("package_spec_sha256", "observer_sha256", "grammar_sha256"):
        if (
            not isinstance(controls.get(key), str)
            or len(controls[key]) != 64
            or any(c not in "0123456789abcdef" for c in controls[key])
        ):
            raise b.PreparationError(
                "complete explicit package/observer/grammar identity required"
            )
    for index in (hardware["n_in"], hardware["n_out"]):
        b.propagating_orders(periods_nm=[px, py], wavelength_nm=1050, index=index)
    return thickness, px, py


def meep_deck(action, hardware, controls):
    t, px, py = _validate(action, hardware, controls)
    if type(controls["eps_averaging"]) is not bool:
        raise b.PreparationError("explicit subpixel averaging convention required")
    for key in (
        "resolution_per_um",
        "pml_nm",
        "guard_nm",
        "source_fwidth_fraction",
        "after_sources_time",
    ):
        b.number(controls[key], positive=True)
    if controls["source_fwidth_fraction"] >= 1:
        raise b.PreparationError("explicit narrowband source required")
    geometry = {"action": action, "hardware": hardware, "controls": controls}
    script = """import json
import meep as mp
from carbon.challenge_pipeline import benchmark_mg as observer
SPEC = json.loads(__REGISTERED_SPEC__)
a, h, c = SPEC['action'], SPEC['hardware'], SPEC['controls']
px, py = [v * 1e-3 for v in h['periods_nm']]
t, guard, pml = a['thickness_nm'] * 1e-3, c['guard_nm'] * 1e-3, c['pml_nm'] * 1e-3
sz = 2 * (t + 3 * guard + pml)
f = 1 / (h['wavelength_nm'] * 1e-3)
cell = mp.Vector3(px, py, sz)
source = [mp.Source(mp.GaussianSource(f, fwidth=f*c['source_fwidth_fraction']), component=mp.Ex,
                    center=mp.Vector3(0, 0, -2*guard), size=mp.Vector3(px, py, 0))]
def simulation(geometry, default):
    return mp.Simulation(cell_size=cell, dimensions=3, resolution=c['resolution_per_um'],
                         boundary_layers=[mp.PML(pml, direction=mp.Z)], k_point=mp.Vector3(),
                         geometry=geometry, default_material=default, sources=source, eps_averaging=c['eps_averaging'])
def monitors(sim):
    r = sim.add_mode_monitor(f, 0, 1, mp.ModeRegion(center=mp.Vector3(0,0,-guard), size=mp.Vector3(px,py,0)))
    tr = sim.add_mode_monitor(f, 0, 1, mp.ModeRegion(center=mp.Vector3(0,0,t+guard), size=mp.Vector3(px,py,0)))
    return r, tr
norm = simulation([], mp.Medium(index=h['n_in']))
nr, nt = monitors(norm)
norm.run(until_after_sources=c['after_sources_time'])
incoming = mp.get_fluxes(nr)[0]
if incoming <= 0: raise ValueError('normalization failed; reference unresolved')
incident_data = norm.get_flux_data(nr)
norm.reset_meep()
geom = [mp.Block(center=mp.Vector3(0,0,-sz/4), size=mp.Vector3(mp.inf,mp.inf,sz/2), material=mp.Medium(index=h['n_in']))]
nx, ny = len(a['mask']), len(a['mask'][0])
for i in range(nx):
    for j in range(ny):
        if a['mask'][i][j]:
            geom.append(mp.Block(center=mp.Vector3(-px/2+(i+.5)*px/nx,-py/2+(j+.5)*py/ny,t/2),
                                 size=mp.Vector3(px/nx,py/ny,t), material=mp.Medium(index=h.get('n_layer',3.45))))
sim = simulation(geom, mp.air)
rm, tm = monitors(sim)
sim.load_minus_flux_data(rm, incident_data)
sim.run(until_after_sources=c['after_sources_time'])
rows = []
for side, index, mon, direction in [('R',h['n_in'],rm,1),('T',h['n_out'],tm,0)]:
    for m,n in observer.propagating_orders(periods_nm=h['periods_nm'], wavelength_nm=h['wavelength_nm'], index=index):
        powers = []
        for s,p in [(1,0),(0,1)]:
            coeff = sim.get_eigenmode_coefficients(mon, mp.DiffractedPlanewave((m,n,0),mp.Vector3(0,1,0),s,p))
            if coeff is None or coeff.alpha.size == 0: raise ValueError('missing propagating channel')
            powers.append(float(abs(coeff.alpha[0,0,direction])**2/incoming))
        rows.append(dict(side=side,order=[m,n],co_power=powers[0],cross_power=powers[1]))
result = observer.observe(rows, periods_nm=h['periods_nm'], wavelength_nm=h['wavelength_nm'], n_in=h['n_in'], n_out=h['n_out'],
                          flux_totals={'R':-mp.get_fluxes(rm)[0]/incoming,'T':mp.get_fluxes(tm)[0]/incoming})
print(json.dumps({'status':'UNVERIFIED_DECK_OUTPUT','rows':rows,'observables':result,'source':observer.MEEP_SOURCE}))
""".replace("__REGISTERED_SPEC__", repr(json.dumps(geometry, allow_nan=False)))
    return {
        "solver": "Meep",
        "source": b.MEEP_SOURCE,
        "status": "UNVERIFIED_DECK_DRAFT",
        "dispatchable": False,
        "dimensions": 3,
        "periods_nm": [px, py],
        "thickness_nm": t,
        "spec_digest": tasks.digest(geometry),
        "python": script,
        "holds": [
            "image/dependency lock",
            "actual API/parser smoke",
            "normalization/polarization validation",
            "spatial/time/PML convergence",
        ],
    }


def s4_deck(action, hardware, controls):
    t, px, py = _validate(action, hardware, controls)
    basis, grid = controls["num_basis"], controls["field_grid"]
    if (
        type(basis) is not int
        or not 1 <= basis <= 4096
        or type(grid) is not int
        or not 4 <= grid <= 2048
    ):
        raise b.PreparationError(
            "explicit bounded harmonic and sampling controls required"
        )
    b.number(controls["guard_nm"], positive=True)
    geometry = {"action": action, "hardware": hardware, "controls": controls}
    script = """import json
import numpy as np
import S4
from carbon.challenge_pipeline import benchmark_mg as observer
SPEC = json.loads(__REGISTERED_SPEC__)
a,h,c = SPEC['action'], SPEC['hardware'], SPEC['controls']
px,py = [v * 1e-3 for v in h['periods_nm']]
t,guard = a['thickness_nm']*1e-3, c['guard_nm']*1e-3
def setup(normalization=False):
    s = S4.New(Lattice=((px,0),(0,py)), NumBasis=c['num_basis'])
    s.SetMaterial(Name='substrate',Epsilon=h['n_in']**2)
    s.SetMaterial(Name='air',Epsilon=h['n_out']**2)
    s.SetMaterial(Name='silicon',Epsilon=h.get('n_layer',3.45)**2)
    s.AddLayer(Name='input',Thickness=0,Material='substrate')
    s.AddLayer(Name='pattern',Thickness=t,Material='substrate' if normalization else 'air')
    s.AddLayer(Name='output',Thickness=0,Material='substrate' if normalization else 'air')
    nx,ny = len(a['mask']),len(a['mask'][0])
    if not normalization:
        for i in range(nx):
            for j in range(ny):
                if a['mask'][i][j]:
                    s.SetRegionRectangle(Layer='pattern',Material='silicon',Center=(-px/2+(i+.5)*px/nx,-py/2+(j+.5)*py/ny),
                                         Angle=0,Halfwidths=(px/(2*nx),py/(2*ny)))
    s.SetExcitationPlanewave(IncidenceAngles=(0,0),sAmplitude=0,pAmplitude=1)
    s.SetFrequency(1/(h['wavelength_nm']*1e-3))
    return s
norm, sim = setup(True), setup(False)
incoming = float(norm.GetPowerFlux(Layer='input')[0].real)
if incoming <= 0: raise ValueError('normalization failed')
incident_e,incident_h = [np.asarray(v,dtype=complex) for v in norm.GetFieldsOnGrid(z=-guard,NumSamples=(c['field_grid'],c['field_grid']),Format='Array')]
incident_density = float(np.mean(np.cross(incident_e,np.conj(incident_h))[...,2].real))
if incident_density <= 0: raise ValueError('field normalization convention failed')
re,rh = [np.asarray(v,dtype=complex) for v in sim.GetFieldsOnGrid(z=-guard,NumSamples=(c['field_grid'],c['field_grid']),Format='Array')]
te,th = [np.asarray(v,dtype=complex) for v in sim.GetFieldsOnGrid(z=t+guard,NumSamples=(c['field_grid'],c['field_grid']),Format='Array')]
rows = []
for side,index,e,hh in [('R',h['n_in'],re-incident_e,rh-incident_h),('T',h['n_out'],te,th)]:
    required = observer.propagating_orders(periods_nm=h['periods_nm'],wavelength_nm=h['wavelength_nm'],index=index)
    if not set(map(tuple,required)) <= set(map(tuple,sim.GetBasisSet())): raise ValueError('harmonic basis omits propagating orders')
    rows += observer.powers_from_fields(e,hh,periods_nm=h['periods_nm'],wavelength_nm=h['wavelength_nm'],index=index,
                                       side=side,incident_power=incident_density)
result = observer.observe(rows,periods_nm=h['periods_nm'],wavelength_nm=h['wavelength_nm'],n_in=h['n_in'],n_out=h['n_out'],
                          flux_totals={'R':-float(sim.GetPowerFlux(Layer='input')[1].real)/incoming,'T':float(sim.GetPowerFlux(Layer='output')[0].real)/incoming})
by_order = {'R':sim.GetPowerFluxByOrder(Layer='input'),'T':sim.GetPowerFluxByOrder(Layer='output')}
print(json.dumps({'status':'UNVERIFIED_DECK_OUTPUT','rows':rows,'observables':result,'basis':sim.GetBasisSet(),
                  'raw_flux_by_order':{s:[[float(v.real) for v in pair] for pair in pairs] for s,pairs in by_order.items()},'source':observer.S4_SOURCE}))
""".replace("__REGISTERED_SPEC__", repr(json.dumps(geometry, allow_nan=False)))
    return {
        "solver": "S4",
        "source": b.S4_SOURCE,
        "status": "UNVERIFIED_DECK_DRAFT",
        "dispatchable": False,
        "dimensions": "FULL_VECTOR_LAYERED_3D",
        "periods_nm": [px, py],
        "thickness_nm": t,
        "spec_digest": tasks.digest(geometry),
        "python": script,
        "holds": [
            "image/dependency lock",
            "actual API/parser smoke",
            "Fourier axis and normalization validation",
            "harmonic/field-grid convergence",
        ],
    }


def memory_hypothesis(hardware, controls, *, thickness_nm):
    """Grid arithmetic, not peak RSS or a solver cost measurement."""
    resolution = b.number(controls["resolution_per_um"], positive=True)
    pml = b.number(controls["pml_nm"], positive=True)
    guard = b.number(controls["guard_nm"], positive=True)
    sz = 2 * (b.number(thickness_nm, positive=True) + 3 * guard + pml)
    cells = math.prod(
        math.ceil(v * 1e-3 * resolution) for v in [*hardware["periods_nm"], sz]
    )
    return {
        "cells": cells,
        "bytes_per_cell_assumption": [96, 192, 384],
        "field_storage_GiB_hypothesis": [cells * n / 2**30 for n in [96, 192, 384]],
        "peak_RSS": "UNMEASURED_INCLUDES_DFT_PML_MATERIAL_MPI_OVERHEAD",
        "cpu_hours": "UNMEASURED",
    }


def verification_decks(case, controls):
    """Headless CPU scripts for exact analytic checks, still unverified syntax.

    This explicit analytic-test route does not broaden the physical task model.
    Operator runs each declared rung inside the exact pinned image, retains
    output and compares it to the returned truth; no solver is called here.
    """
    if case not in ("zero-contrast-periodic-grating", "planar-lossless-slab"):
        raise b.PreparationError("explicit supported analytic case required")
    zero = case == "zero-contrast-periodic-grating"
    hardware = {
        "periods_nm": [1050 / math.sin(math.radians(50)), 525],
        "wavelength_nm": 1050,
        "n_in": 1 if zero else 1.45,
        "n_out": 1,
        "n_layer": 1 if zero else 3.45,
        "minimum_feature_nm": 10,
        "verification_case": case,
    }
    action = {
        "mask": [
            [int((i + j) % 2 == 0) if zero else 1 for j in range(4)] for i in range(4)
        ],
        "thickness_nm": 325,
    }
    truth = b.slab_truth(
        n_in=hardware["n_in"],
        n_layer=hardware["n_layer"],
        n_out=1,
        thickness_nm=325,
        wavelength_nm=1050,
    )
    return {
        "case": case,
        "hardware": hardware,
        "analytic_truth": truth,
        "required_checks": [
            "R/T00 co",
            "zero cross",
            "zero all other orders",
            "energy residual",
            "order-vs-plane flux",
        ],
        "Meep": meep_deck(action, hardware, controls),
        "S4": s4_deck(action, hardware, controls),
        "pass_band": "HUMAN_INPUT",
        "dispatchable": False,
    }


def verify_analytic_output(case, rows, controls, *, acceptance):
    """Run the numeric test on retained deck outputs, never run the solver.

    Supplied bands require an explicit external acceptance identity. This
    comparison does not verify that identity's scientific authority or image.
    Missing order channels/flux evidence is unresolved, not a zero-error pass.
    """
    spec = verification_decks(case, controls)
    if (
        not isinstance(acceptance.get("record_sha256"), str)
        or len(acceptance["record_sha256"]) != 64
        or any(c not in "0123456789abcdef" for c in acceptance["record_sha256"])
    ):
        raise b.PreparationError("registered numerical acceptance identity required")
    power_band = b.number(acceptance["absolute_power_fraction"], positive=True)
    energy_band = b.number(acceptance["energy_residual_fraction"], positive=True)
    hardware = spec["hardware"]
    measured = b.observe(
        rows,
        periods_nm=hardware["periods_nm"],
        wavelength_nm=1050,
        n_in=hardware["n_in"],
        n_out=hardware["n_out"],
    )
    errors = []
    for row in rows:
        expected = spec["analytic_truth"][row["side"]] if row["order"] == [0, 0] else 0
        errors.extend([abs(row["co_power"] - expected), abs(row["cross_power"])])
    maximum = max(errors)
    passed = maximum <= power_band and abs(measured["energy_residual"]) <= energy_band
    return {
        "case": case,
        "channel_count": len(errors),
        "maximum_absolute_power_error": maximum,
        "energy_residual": measured["energy_residual"],
        "acceptance_record": acceptance["record_sha256"],
        "status": "WITHIN_SUPPLIED_BANDS" if passed else "OUTSIDE_SUPPLIED_BANDS",
        "qualified": False,
        "unchecked": [
            "image identity/code execution",
            "convergence",
            "order-sum vs plane-flux",
            "acceptance authority",
        ],
    }
