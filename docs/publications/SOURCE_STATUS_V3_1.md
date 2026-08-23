# Carbon Publication Source Status v3.1

**Status:** build/source identity record for the current reconciliation workspace.  
**Date:** 2026-08-23.  
**Purpose:** make the exact prepared v3.1 source/build artifacts identifiable while source-control and final release review are completed.

---

## Prepared source identities

```text
Carbon_Whitepaper_v3.1.tex
sha256 a17390c40375037b724ad9239e96e70f188acbd26349120c85f513e196947a7b

Carbon_Academic_Litepaper_v3.1.tex
sha256 2d8eb0902f8cd61cc0a61d7b3ae5541fd636518b83a6ab132ee64f06ffa0cfe5

Carbon_Exploit_Summit_Pitch_Deck_Review_v5.md
sha256 7761798b816f3d0d1fecdb6f52d515f85cd62b20a6c292e624696209e2ed39a2
```

The deck-review Markdown is now source-controlled in this folder. The two LaTeX source files represented by the hashes above are prepared in the publication workspace but are **not yet committed to this repository path** at the time of this record. Therefore the v3.1 papers should not yet be treated as fully source-controlled release artifacts.

---

## Prepared PDF identities

```text
Carbon_Whitepaper_v3.1.pdf
sha256 0bb5b67a5fc71eb7bc0ef4d83c4757e6577231c365a4cc62e23b800c1a6df56f

Carbon_Academic_Litepaper_v3.1.pdf
sha256 b04015d9c982947d6b5854cbb81b04d094d559a2a6c8548e92226e68efb4f3ea
```

The PDFs were generated from the prepared source generation above after reconciliation fixes.

---

## Build verification

Whitepaper:

- 42 pages;
- compiled successfully;
- the reconciliation pass removed material overfull-box warnings introduced/exposed in the source path;
- remaining warnings are non-fatal typography/table/font warnings and should be reviewed again at release;
- complete-page contact-sheet review found no obvious clipping/overlap;
- key changed pages were inspected at larger scale during the edit loop.

Academic Litepaper:

- 10 pages;
- compiled successfully;
- no overfull/undefined-reference warning found in the final build log;
- complete-page contact-sheet review found no obvious clipping/overlap;
- the newly inserted commercial section was inspected directly.

---

## Release rule

A future external v3.1 release should use new hashes if any source edit occurs after this record. The release process should:

1. commit exact source;
2. build from committed source;
3. compute fresh source/PDF hashes;
4. run citation/internal-reference audit;
5. run scientific/business claim audit;
6. render and visually inspect the final PDFs;
7. record the release identities prospectively.
