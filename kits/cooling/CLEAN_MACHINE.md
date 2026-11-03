# Cooling data kit: clean-machine run

A plain Ubuntu 24.04 x86-64 box with Docker, git, Python 3 and numpy, no
Carbon credentials, no Carbon checkout before step 1. Pass = every step below
exits 0 (except `verify`, which must refuse today), both sampled cases end
`OK` with a cost (or a typed reference outcome, counted), and `check` reads
back shapes (n, 9) and (n, 32), all finite. Keep the full terminal log.

## 0. The box

```bash
cat /etc/os-release | head -2; uname -m
docker version --format '{{.Server.Version}}'; python3 --version; git --version
id -nG                                   # must list docker
sudo apt-get install -y python3-numpy    # the parser's one dependency
```

## 1. The code

From the desk (one exact commit):

```bash
git -C CHECKOUT archive --format=tar.gz -o carbon-kit-src.tgz COMMIT
sha256sum carbon-kit-src.tgz          # record it
# copy carbon-kit-src.tgz to the box, then on the box:
sha256sum carbon-kit-src.tgz          # must equal the desk's
mkdir carbon && tar xzf carbon-kit-src.tgz -C carbon && cd carbon
```

## 2. The kit

```bash
python3 -m kits.cooling range
python3 -m kits.cooling build                                   # docker pull by digest
python3 -m kits.cooling generate --nominal --out runs/nominal  # smoke, one case
python3 -m kits.cooling generate --n 2 --seed 7 --out runs/s7 --parallel 2
python3 -m kits.cooling parse runs/s7
python3 -m kits.cooling check runs/s7/train.npz
python3 -m kits.cooling cost runs/s7
python3 -m kits.cooling licences > licences.txt
python3 -m kits.cooling verify --out runs/verify   # expected today: "refused: no verify set is published"
sha256sum runs/s7/train.npz runs/s7/records.jsonl licences.txt
```

Expected cost: Carbon measured about 0.5 to 1 hour of one core per case at
2,000 iterations; it varies with the machine and the case. `verify` must PASS
once the Cooling verify set is published; today it must refuse. The `score`
step needs the full miner install and a trained model's predictions; it joins
this list with the Control Center page.

## 3. After

Copy `runs/s7/records.jsonl`, `train.npz`, `train.provenance.json`,
`licences.txt` and the log to the desk, check their sha256, then delete the
box. Then the Validator's leak check on the same commit.
