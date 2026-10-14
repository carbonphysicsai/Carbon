# V8_8-PUBLIC-RUNTIME-MATERIAL-01

Actual merged42f875 operator image1e371c4b built, but import-only initialization
failed closed. The public bundle excluded the runtime's exact pinned OCV/TRAIN,
calibration and truth-overlay lock. An image build and payload hash pass were
insufficient evidence of runtime completeness.

Select an exact public data-file allow-list and require it when producing new
bundles. Include the published input index consumed by the existing contamination
refusal. Reuse all existing loaders/digests and science values; no defaults or
replacement data. Keep historical old bundle verification as byte verification;
do not reinterpret it as install readiness or silently change old evidence.

The input index alone carries 2188 unique published tuples; the public refs-b
battery records add 1588 more. Include that exact tracked public file too, and
compare the actual published-input refusal sets between source and package.
Other reference files add no battery tuples outside this set and stay excluded.

Alternatives: exporting whole docs/evidence/scripts would widen disclosure;
mounting a Ryan checkout hides the portability defect; relaxing loaders or
inventing fixture calibration changes the ruler. This repair adds none of those.
Reverse by restoring the allow-list, retaining the measured runtime failure.

Public fixture tests must fail on the old package and initialize an import-only,
development-only synthetic deployment from the new exact bundle in a fresh
process. No real signer/chain/solver/official case or protected root. Docker
build/rehearsal remains local and Root-resource coordinated, with publication,
fresh external installation and qualification separately unearned.
