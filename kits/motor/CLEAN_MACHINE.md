# Motor data kit: clean-machine run

A plain Ubuntu 24.04 x86-64 box with Docker, git and Python 3, no Carbon
credentials, no Carbon checkout before step 1. Pass = every step below exits
0, both sampled cases end `OK` with a cost, and `check` reads back shapes
(2, 8) and (2, 60), all finite. Keep the full terminal log.

## 0. The box

```bash
cat /etc/os-release | head -2; uname -m
docker version --format '{{.Server.Version}}'; python3 --version; git --version
id -nG        # must list docker
```

## 1. The code

Before the kit is on main, from the desk (one exact commit):

```bash
git -C CHECKOUT archive --format=tar.gz -o carbon-kit-src.tgz COMMIT
sha256sum carbon-kit-src.tgz          # record it
# copy carbon-kit-src.tgz to the box, then on the box:
sha256sum carbon-kit-src.tgz          # must equal the desk's
mkdir carbon && tar xzf carbon-kit-src.tgz -C carbon && cd carbon
```

Once it is on main: `git clone` the public repository, `git checkout COMMIT`, `cd` into it.

## 2. The kit

```bash
python3 -m kits.motor range
python3 -m kits.motor build                                   # builds from the recipe; needs the network
python3 -m kits.motor generate --nominal --out runs/nominal  # smoke, one case
python3 -m kits.motor generate --n 2 --seed 7 --out runs/s7 --parallel 2
python3 -m kits.motor parse runs/s7
python3 -m kits.motor check runs/s7/train.npz
python3 -m kits.motor cost runs/s7
python3 -m kits.motor licences > licences.txt
python3 -m kits.motor verify --out runs/verify   # expected today: "refused: no verify set is published"
sha256sum runs/s7/train.npz runs/s7/records.jsonl licences.txt
```

Measured on the first clean run (fresh Ubuntu 24.04, 2 cores per case): the
nominal case 750 s and 402 MiB peak; the two sampled cases 1,263 s and
1,458 s, 654 to 770 MiB peak. Costs vary with the machine and the case. If
the build cannot reach getdp.info or gmsh.info (curl error 28), use a box
whose network reaches them; see the README. `verify` must PASS once the Motor verify set is published; today it must
refuse. The `score` step needs the full miner install (the grade code's Python
dependencies) and a trained model's predictions; it joins this list with the
Control Center page.

## 3. After

Copy `runs/s7/records.jsonl`, `train.npz`, `train.provenance.json` and the log
to the desk, check their sha256, then delete the box. Then the Validator's leak
check on the same commit.
