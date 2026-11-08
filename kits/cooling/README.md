# Cooling data kit (Cooling 1.8)

Make your own Cooling training data on your own machine, with the same public
reference solver, case writer, sampler and reader Carbon used to make the
Cooling TRAIN set.

**Read this first.** Your results can differ from Carbon's pinned reference,
and only Carbon's pinned reference grades. Run `verify` before you train on
your own data. Kit data is practice data: it is never an exam, a grade or a
score.

## What you need

- Linux x86-64 with Docker (you in the `docker` group) and Python 3.10 or
  newer with numpy (the parser writes Cooling's encoded TRAIN layout with
  Carbon's own encoder, which uses numpy). The `score` command needs the full
  miner install.
- This Carbon checkout (the one the miner installer set up, or a plain
  `git clone`). The kit needs no Carbon account, wallet or key, and makes no
  network connection while it solves.
- Network access to Docker Hub once, to pull the OpenFOAM image.
- Disk for the OpenFOAM image (a few GiB) and CPU time. Carbon's own
  measurement: about 0.5 to 1 hour of one core per case at Carbon's TRAIN
  settings (2,000 iterations). Your times vary with your machine and the case.
  Every case records its own cost (wall time, peak memory, cores); `cost`
  prints them.

## Run it

From the checkout's root:

```bash
python3 -m kits.cooling build                          # pull the OpenFOAM image by its pinned digest
python3 -m kits.cooling range                          # the internal range the kit samples
python3 -m kits.cooling generate --nominal --out runs/first      # one case
python3 -m kits.cooling generate --n 50 --seed 7 --out runs/s7 --parallel 4
python3 -m kits.cooling parse runs/s7                  # runs/s7/train.npz + train.provenance.json
python3 -m kits.cooling check runs/s7/train.npz
python3 -m kits.cooling cost runs/s7
python3 -m kits.cooling verify --out runs/verify       # Cooling 1.8's published verify set
python3 -m kits.cooling score runs/s7 --predictions my_predictions.json
python3 -m kits.cooling licences                       # every licence in the image
```

- `--seed` is yours. The same seed gives the same cases; Carbon's own draws
  use labels the kit never uses.
- `generate --plan CASES.json` runs your own cases: `{"cases": [{"case_id":
  "...", "inputs": {nine inputs}}]}`. Each case must be inside the internal
  range and pass its screen; the kit refuses anything else.
- A case ends as one of: `OK`; `REFERENCE_INVALID` (a reference check
  failed, for example the coolant passes the PG25 model's 99 C or the flow
  leaves the laminar range; such a design is dropped, never scored);
  `REFERENCE_SOLVER_FAILED`; `REFERENCE_TIMEOUT`; `FAILED_INFRA` (the
  container could not start). Only `OK` cases enter `train.npz`; the rest are
  counted in the provenance file.
- `score` takes your model's predictions on your own cases, as JSON
  `{"case_id": [32 values in the TRAIN layout], ...}`, and prints the
  **practice score**: the native gates per case and the accuracy part, each
  computed by the grade's own code in this checkout (pinned; it refuses if
  that code changed without the kit). Design value on hidden targets, the
  sealed minimums, the information budget and the speed gate on the
  validator's machine print "not evaluated locally". A practice score is
  never an exam score or grade.
- `verify` solves Cooling 1.8's published verify set (6 designs with
  Carbon's pinned truths, outside every sealed set) and compares within U; it
  refuses any verify-set file whose bytes differ from the receipted digest.

## What is inside

| Piece | Where it comes from |
|---|---|
| Solver | OpenFOAM, upstream image `opencfd/openfoam-default` pulled by its pinned digest (`carbon/cold_plate/openfoam.py` `IMAGE`) |
| Case writer and commands | `carbon/cold_plate/openfoam.py`: blockMesh, splitMeshRegions, chtMultiRegionSimpleFoam (laminar, steady, conjugate; one repeating channel-and-fin cell), at the TRAIN's own settings |
| Case law | `carbon/cold_plate/domain.py` (inputs, fixed plate, PG25 property fits, heat map) |
| Sampler and screen | `carbon/cold_plate/population.py`: uniform over the box, kept if the closed-form model keeps the hottest wall at most 95 C and the flow laminar |
| Reader | `carbon/cold_plate/analysis.py` |
| Parser | `kits/cooling/kit.py`: Cooling's encoded TRAIN layout (`inputs` (N, 9), `targets` (N, 32): slot 0 the peak excess, 1-30 the profile, 31 the pressure, through `carbon/cold_plate/output_encoding.py`) |

## What a case gives you

32 numbers per case: the peak face temperature, the 30-segment face profile
along the flow and the pressure drop. No fields: Carbon's published outputs
are these 32 values, and its own TRAIN case directories were not kept.

## Download sources and licences

You pull the solver yourself; this kit ships no binary and no image.

| Component | Source | Licence |
|---|---|---|
| OpenFOAM (ESI-OpenCFD) | Docker Hub `opencfd/openfoam-default`, by the digest in `carbon/cold_plate/openfoam.py` | GPL-3.0-or-later |
| The image's operating-system packages | inside the same image | each package's own licence, in `/usr/share/doc/<package>/copyright` |
| PG25 property fits (numbers in `carbon/cold_plate/domain.py`, fitted to CoolProp 6.8.0) | CoolProp, used to make the fits; the kit does not run it | MIT |
| Carbon's code in this checkout (case writer, reader, kit) | this checkout | MIT (repository `LICENSE`) |

`python3 -m kits.cooling licences` prints OpenFOAM's licence files and every
package in the image, so you can read each one.

## How you're tested

See [HOW_YOURE_TESTED.md](HOW_YOURE_TESTED.md): the internal range, all the
rules, and what the exam tests.
