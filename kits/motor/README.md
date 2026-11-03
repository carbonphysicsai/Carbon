# Motor data kit (Motor 1.7)

Make your own Motor training data on your own machine, with the same public
reference recipe, decks, sampler and runner Carbon used to make the Motor
TRAIN set.

**Read this first.** Your results can differ from Carbon's pinned reference,
and only Carbon's pinned reference grades. Run `verify` before you train on
your own data. Kit data is practice data: it is never an exam, a grade or a
score.

## What you need

- Linux x86-64 with Docker (you in the `docker` group) and Python 3.10 or newer.
- This Carbon checkout (the one the miner installer set up, or a plain
  `git clone`). The kit needs no Carbon account, wallet or key, and makes no
  network connection while it solves.
- Network access to getdp.info and gmsh.info while the image builds (see
  below if your network blocks them); none while cases solve.
- Disk for the solver image (about 1 GiB) and CPU time. One Motor case solves
  61 rotor positions. Measured on a fresh Ubuntu 24.04 cloud machine at 2
  cores: the nominal case 750 s and 402 MiB peak; two sampled cases 1,263 s
  and 1,458 s, 654 to 770 MiB peak. Your times vary with your machine and
  the case. Every case records its own cost (wall time, peak memory, cores);
  `cost` prints them.

## Run it

From the checkout's root:

```bash
python3 -m kits.motor build                          # build the solver image from Carbon's recipe
python3 -m kits.motor range                          # the internal range the kit samples
python3 -m kits.motor generate --nominal --out runs/first      # one quick case
python3 -m kits.motor generate --n 50 --seed 7 --out runs/s7 --parallel 4
python3 -m kits.motor parse runs/s7                  # runs/s7/train.npz + train.provenance.json
python3 -m kits.motor check runs/s7/train.npz
python3 -m kits.motor cost runs/s7
python3 -m kits.motor verify --out runs/verify       # once the verify set is published
python3 -m kits.motor score runs/s7 --predictions my_predictions.json
python3 -m kits.motor licences                       # every licence in the image you built
```

- `score` takes your model's predictions on your own cases, as JSON
  `{"case_id": [60 torque values], ...}`, and prints the **practice score**:
  the native gates per case and the accuracy part, each computed by the
  grade's own code in this checkout (pinned; it refuses if that code changed
  without the kit). Design value on hidden targets, the sealed minimums, the
  information budget and the speed gate on the validator's machine print
  "not evaluated locally". A practice score is never an exam score or grade.
- `verify` refuses until the version's verify set (a few designs with Carbon's
  pinned truths) is published at its receipted digest.

- `--seed` is yours. The same seed gives the same cases; Carbon's own draws
  use labels the kit never uses.
- `generate --plan CASES.json` runs your own cases: `{"cases": [{"case_id":
  "...", "inputs": {eight inputs}}]}`. Each case must be inside the internal
  range and buildable; the deck refuses anything else.
- A case ends as one of: `OK`; `REFERENCE_INVALID` (a rotor position did not
  converge, or the torque at 15 degrees does not repeat the torque at 0);
  `REFERENCE_SOLVER_FAILED` (no readable torque); `REFERENCE_TIMEOUT`;
  `FAILED_INFRA` (the container could not start). Only `OK` cases enter
  `train.npz`; the rest are counted in the provenance file.

## What is inside

| Piece | Where it comes from |
|---|---|
| Solver build recipe | `scripts/dev/motor/reference/Dockerfile`: Ubuntu 24.04 by digest, Gmsh 4.15.2 and GetDP 3.5.0 upstream binaries, each checked by SHA-256 before use |
| Mesher | `carbon/motor/mesh.py` (Gmsh, exactly rotated meshes) |
| Deck | `carbon/motor/getdp.py` (2D magnetostatics; Brauer iron law) |
| Case law and buildability | `carbon/motor/domain.py` |
| Sampler | `carbon/motor/population.py`: uniform over the box, kept if buildable |
| Runner | `scripts/dev/motor/reference/run_batch.py` (its case writer, rotor currents, run script and torque reading) |
| Parser | `kits/motor/kit.py`: Carbon's Motor TRAIN format (`inputs` (N, 8), `targets` (N, 60) torque at 0 to 14.75 degrees, float64), written with the standard library |

## If the build cannot reach getdp.info or gmsh.info

`build` downloads the two solver archives from their authors' sites, and
some networks cannot reach those hosts (a curl error 28, a time-out, is the
usual sign; the kit then names the host it could not reach). Run `build` on
a network that reaches both hosts, for example another machine or a cloud
box, then move the built image with `docker save` and `docker load`. Carbon
names no mirror: whatever route you use, the recipe checks each archive
against its pinned sha256 and stops on any other bytes.

## Download sources and licences

You download and build every component yourself from its upstream source;
this kit ships no binary and no image. The recipe
(`scripts/dev/motor/reference/Dockerfile`) downloads exactly these and
checks each against its pinned sha256 before unpacking it:

| Download | Source |
|---|---|
| GetDP 3.5.0, Linux 64-bit | https://getdp.info/bin/Linux/getdp-3.5.0-Linux64r.tgz |
| Gmsh 4.15.2, Linux 64-bit SDK | https://gmsh.info/bin/Linux/gmsh-4.15.2-Linux64-sdk.tgz |
| Ubuntu 24.04 base image and packages | Docker Hub `ubuntu:24.04` by digest; packages from the Ubuntu archive and its dated snapshot |

**Gmsh's licence is the GNU General Public License, version 2 or later
(GPL-2.0-or-later), with the Gmsh exception** that permits combining Gmsh
with Netgen, METIS, OpenCASCADE and ParaView under their own licences.
**GetDP's licence is the GNU General Public License, version 2 or later
(GPL-2.0-or-later).**

| Component | Licence |
|---|---|
| Gmsh 4.15.2 (upstream Linux SDK binary) | GPL-2.0-or-later with the Gmsh exception for combining with Netgen, METIS, OpenCASCADE and ParaView under their own licences (`share/doc/gmsh/LICENSE.txt`); contributed codes each under their own licence (BSD-style, MIT and others), listed in `share/doc/gmsh/CREDITS.txt` |
| GetDP 3.5.0 (upstream Linux binary) | GPL-2.0-or-later (`share/doc/getdp/LICENSE.txt`); the libraries it uses are listed in `share/doc/getdp/CREDITS.txt` |
| Ubuntu 24.04 base and packages | each package's own licence, in `/usr/share/doc/<package>/copyright`; among them python3 (PSF-2.0), ca-certificates (MPL-2.0), the Mesa and X11 client libraries (MIT-style), libgomp1 (GPL-3.0 with the GCC Runtime Library Exception) |
| Carbon's code in this checkout (decks, mesher script, runner, kit) | MIT (repository `LICENSE`) |

`python3 -m kits.motor licences` prints every licence file Gmsh and GetDP
ship and every package in the image you built, so you can read each one.

## How you're tested

See [HOW_YOURE_TESTED.md](HOW_YOURE_TESTED.md): the internal range, all the
rules, and what the exam tests.
