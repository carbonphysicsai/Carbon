# OWNER-5950X-GRADING-CLASS-01: the Ryzen 9 5950X boxes accepted as the mainnet 116 grading class

Date: 2026-11-16 (owner's local day, CST).
Status: DRAFT of the record of an owner acceptance. The owner typed the line directly in the Deploy-B session; it is
recorded here from the Deploy-B relay. Deploy-B or the Lead confirms the wording against the session before this folds.

Owner's words (the two box addresses are replaced by `[address]`: this repository records no host address; they are held
with the box records outside it): "Deploy-B: I accept the Ryzen 9 5950X (FSN1 [address], HEL1 [address]) as the mainnet
grading class for 116 with every limit unchanged; run ≥2 uncounted re-grades of finished grades on it (must score
identically) plus containment; cut over to it as soon as A18's remote lane, the box kit and those checks pass, same switch
procedure. Standing until I say stop."

## Scope

- **Machines:** the two Hetzner boxes named FSN1 and HEL1, each one AMD Ryzen 9 5950X (16 cores, 32 threads), bare
  metal. The exact CPU model string, ISA flags, logical CPU count, microcode, kernel and memory floor are those READ on the
  boxes by the read-only identity kit and entered in the class record (below); nothing here is assumed.
- **Network:** finney (mainnet 116). Testnet is not included.
- **Role:** grading. The boxes run a grading round's worker containers as REMOTE grade lanes
  (`carbon/reconstruction/remote_lane.py`), reached over ssh as the unprivileged grade user from the door host only. The
  controller (door, ledger, scoring, truths, keys) stays on the grading host.
- **Limits:** every limit unchanged, in the owner's words: walls, memory, the worker's CPU count, score rules, gates and
  every registered value stay as registered. This record sets none.

## Conditions (the owner's)

1. At least two UNCOUNTED re-grades of finished 116 grades run on this class and score identically to their records.
2. Containment passes on the boxes (the existing pass rule: every part passes, nothing skipped).
3. A18's remote lane is landed and switched by the normal procedure, and the box kit is receipted.
4. Then the cutover, by the same switch procedure as any door switch.

Entering this class in code satisfies none of these. The class record, the remote-lane record and any values-row change
are separate commits, each receipted on its own.

## Open, not decided by this record

- **Lane shape on SMT (CV-Motor, B2):** how many lanes per box and which logical CPUs each lane gets (4 physical cores
  with their SMT siblings left idle, or another shape). Until CV-Motor rules, any lane cpuset is PROPOSED.
- **One cutover, no mixing (CV-Motor):** whether grades on the GPUYard EPYC class and on this class may run side by side.
  A remote lane listed in the HOST record is only ever used beside the door's local lanes; a door's OWN record with
  `"only": true` grades on the remote lanes alone.
- **Stage root:** a container's inputs are mirrored to the same absolute path on the box, under the lane's `stage_root`,
  so the door's input directories must lie under that path on the door host as well.

## Class record

`scripts/validator_host_classes/RYZEN5950X-01.json` (schema `carbon.validator.host-class.v2`, id
`VALIDATOR-HOST-CLASS-RYZEN5950X-01`, scope MAINNET, `recorded.owner_decision` = `OWNER-5950X-GRADING-CLASS-01
(finney)`) is filled by `scripts/dev/host_class_record.py` from the two boxes' identity reads only, and only if the two
boxes agree on model, ISA flags, logical CPU count, virtualization, microcode, kernel, OS and Docker. It is committed after
the reads, not before.

This record sets no score, threshold, tolerance or economics and records no host address.
