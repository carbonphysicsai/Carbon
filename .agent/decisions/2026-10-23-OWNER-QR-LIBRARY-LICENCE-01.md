# OWNER-QR-LIBRARY-LICENCE-01: the qrcode-generator library (MIT) is cleared for Launchpad's wallet QR

Date: 2026-10-23
Status: APPROVED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae). Offered "(a) vendor qrcode-generator (MIT, one JavaScript file)" or "(b) write our own encoder", the owner replied: "a".

## Decided

- Launchpad may vendor **qrcode-generator**, one JavaScript file, under the **MIT licence**. It is used only to draw the miner's wallet address as a QR code, locally in the page.
- Conditions:
  - keep its copyright and licence notice in the vendored file and in the licence inventory;
  - pin the exact upstream version and its sha256;
  - no network fetch at runtime;
  - a test that decodes the generated QR back to the exact address.
- This clearance covers only that file under MIT. Any other dependency still needs its licence named and cleared separately.
