# OWNER-GPU-REBUILD-RENTED-4090-01: validator rebuilds on GPU; rent a 4090 now

- **Received by:** the Lead session, directly from the owner in chat, 2026-10-26 ~19:50Z.
- **Owner's words:** "No I want these rebuilding on GPUs." / "I don't care about grading I care about rebuilding. Grading can be done on the 4090s CPU." / "Use a rented 4090 now".
- **Decided:**
  - The validator REBUILD (training a miner's model from its recipe) runs on the GPU; GRADING (inference + scoring) runs on the same machine's CPU. One validator machine (OWNER-MAINNET-ONE-VALIDATOR-MACHINE-01).
  - Rent ONE RTX 4090 machine now, so GPU rebuild work starts today. Rate as quoted to the owner: about USD 0.40-0.70/h (at most USD 0.70/h). The Lead checks back with the owner before this rental passes USD 30 total.
  - Work items: the GPU rebuild path in the validator (graph route + catalog training builds, tested entries first); GPU rebuild repeatability (second rebuild matches; noise measured on the GPU class, which feeds the crown margin); rebuild wall re-measured on the GPU; recal on the GPU class.
- **Open (owner):** launch timing (testnet on CPU rebuilds now with a versioned switch, or hold); the parity tolerance stays owner-picked (GPU-FOR-EVERY-CHALLENGE, 10-22); the owned 4090 order stays post-testnet unless the owner says otherwise.
