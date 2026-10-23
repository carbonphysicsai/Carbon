# OWNER-ONE-PUBLIC-VALIDATOR-01: grading is public and built into one validator machine serving every launch Challenge

Date: 2026-10-23
Status: APPROVED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae): "Yes graders must be public and built in to the validator. … shouldn't we just have a validator machine doing all of this".
Amends: OWNER-AX42-DOOR-PRIVATE-01 for the validator only. Custody hosts (the AX42, custody2, and any other exam-production host) stay private and never face miners.

## Decided

- One validator machine on the registered RTX 4090 class (OWNER-VALIDATOR-GPU-CLASS-01) does everything, for all four launch Challenges: Motor, Cooling, Ribbed Bracket and Burst Thermal. It provides:
  - a public submission intake with TLS and a published address;
  - from-scratch rebuild;
  - grading on its own signed copy of the sealed exam;
  - KOTH;
  - setting weights. On testnet 567 this is authorized by OWNER-TESTNET-WEIGHTS-01.
- The per-Challenge DEVELOPMENT receivers are a stopgap. They are retired once the validator serves all four end to end.
- Testnet first. The public intake on mainnet still requires the human security review and the owner's mainnet containment acceptance (critical path #8). That is a security acceptance and is not given here.

## Why

- Miners need one public place to submit, built into the validator that actually grades. Today's private, tunnelled, one-per-Challenge receivers are not the launch architecture.
