# Standards crosswalk — proposed evidence indexing

This is a record-location crosswalk, **not a compliance determination**. Retrieval date: 2026-10-09. Standard identifiers, editions and clause numbers are metadata, not uncertain estimates. The sources establish the anchors below; a qualified reviewer must determine applicability, sufficiency and acceptance. No standard was purchased.

**NASA anchors verified from the full public text:** [NASA-STD-7009B, 5 March 2024](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf), §§4.1–4.3 and Appendix A. Each M&S number below is a requirement ID, not an awarded level. Report capability under M&S 48/50 and results under M&S 31/35 separately. Proposed section mappings are Carbon research judgments.

**ASME bounds:** [publisher standards list](https://www.asme.org/codes-standards/publications-information/verification-validation-uncertainty) establishes V&V 10–2019, V&V 20–2009 and V&V 40–2018 scopes/editions. [V&V 20 official preview](https://files.asme.org/Catalog/Codes/PrintBook/21356.pdf) verifies the cited section anchors only, not full requirements. **V&V 10 and 40 exact clause IDs remain HUMAN_INPUT**: the full licensed text was not reviewed. Their columns below are topic mappings to guide authorized clause review. No cross-domain equivalence or medical qualification is implied.

**DoD anchors:** [MIL-STD-3022 with Change 1, official document](https://quicksearch.dla.mil/WMX/Default.aspx?token=5715233) verifies Appendices A (Accreditation Plan), B (V&V Plan), C (V&V Report), D (Accreditation Report), their outline clauses A.4/B.4/C.4/D.4, A.14 traceability and C.16 basis of comparison. [DLA catalogue](https://quicksearch.dla.mil/qsDocDetails.aspx?ident_number=275961) records active status and the validation notice. [DoDI 5000.61, September 17, 2024](https://www.esd.whs.mil/Portals/54/Documents/DD/issuances/dodi/500061p.pdf) public indexed contents verify §§3.1–3.3; full retrieval was unavailable, so substantive instruction compliance is not assessed. Accreditation belongs to the designated authority.

| Common section | NASA-STD-7009B verified anchors | ASME V&V 10 topic; clause IDs HUMAN_INPUT | ASME V&V 20 preview anchors | ASME V&V 40 topic; clause IDs HUMAN_INPUT | DoD verified template anchors |
| --- | --- | --- | --- | --- | --- |
| D01 Use/decision | §4.1.1.1 M&S 40; §4.3.1.1–2 M&S 22–23 | Intended use | §1-2 | Context of use, model risk | A.4/B.4/C.4/D.4 problem statement |
| D02 Requirements | §4.1.1.4–5 M&S 42–43 | Acceptance/validation plan | §1-2, §6 | Credibility goals/plan | A.14; C.7 |
| D03 Domain | §4.2.1.6–7 M&S 13–14; §4.2.3.2 M&S 16; §4.2.5.2 M&S 18; §4.3.1.5 M&S 26 | Validation domain | §6 | Applicability | A.4/B.4/C.4/D.4 scope/limitations |
| D04 Reference | §4.2.1.1 M&S 10; §4.2.3.1 M&S 15; §4.2.5.1 M&S 17 | Verification/comparator | §§2-3,2-4,4,5 | Verification/comparator | C.16 |
| D05 Validation | §4.2.5.1–2 M&S 17–18; §4.3.6.1 M&S 31 | Validation comparison | §§5,6 | Credibility assessment | C.4/C.7; A.14 |
| D06 Uncertainty | §4.2.7.1–2 M&S 19,21; §4.3.3.1–2 M&S 28–29; §4.3.5 M&S 30; §4.3.8.2–3 M&S 33–34 | UQ/error | §§3,4,5 | Verification/validation uncertainty | C.16; DoDI §3.3(b) contents anchor |
| D07 Adverse/robustness | §4.1.1.8 M&S 51; §4.3.5 M&S 30; §4.3.8.1 M&S 32 | Robustness/discrepancy | §§3,6 (proposed linkage) | Credibility limitations | C.4/D.4 issues |
| D08 Provenance | §4.2.1.2–3 M&S 45–46; §4.3.1.3–4 M&S 24–25 | Configuration/records | §§2,4 (proposed linkage) | Evidence traceability | A.2/B.2/C.2/D.2; record-of-changes clauses *.3 |
| D09 Fallback | §4.3.1.5–6 M&S 26–27; §4.3.6.2 M&S 49 | Permitted use/limits | §6 (proposed linkage) | Risk/context of use | A.4/D.4 risks/impacts |
| D10 Gaps | §4.2.1.4,6 M&S 11,13; §4.3.8.1 M&S 32 | Unvalidated aspects | §6 | Applicability/gaps | A.4/C.4/D.4 limitations/issues |
| D11 Audit | §4.1.1.3,7–8 M&S 41,9,51; §4.3.8.4–9 M&S 50,35–39; Appendix A | V&V documentation | §§1,6 (proposed linkage) | Documentation/assessment | All four templates; A.14; DoDI §§3.1–3.2 contents anchors |

The preview's section titles substantiate V&V 20 anchors; links to D07–D11 are proposed indexing choices, not a claim that those clauses require Carbon's adversarial testing or provenance architecture. None of these standards certifies a hidden exam merely because it is hidden.

## Rendering and review contract

Keep one fact store. A standard profile contains edition, verified/topic-only mapping status, applicable anchor, common section IDs, evidence references, gaps, human applicability decision and responsible authority. Emit a missing-clause warning if the profile cannot be clause-complete. Do not silently replace V&V 10 with 10.1, V&V 20 with a newer companion document, or 7009B with an older credibility-factor list.

For NASA include the five capability factors from §4.2.1.8 and the six results factors from §4.3.6.1, with separate evidence-coverage labels. The proposed eleven common sections are not those eleven factors. A cross-index connects them. Formal levels and threshold decisions remain HUMAN_INPUT; neither count implies a pass rate.

Before an external ASME rendering: authorized reviewer obtains the applicable licensed edition through existing rights, verifies clause IDs and normative content, records applicability, and approves the completed mapping. Before any DoD use: contracting/program authorities tailor the templates and the accreditation authority assesses the actual application. These missing decisions limit customer claims; they do not prevent a development sample that explicitly carries the gaps.
