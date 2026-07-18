# Paper Writing Status

Last updated: 2026-07-14 (verified reference replacement DONE — see below; LaTeX and DOCX back in sync on references).

## Reference replacement (2026-07-14)

Applied the approved plan from `docs/references/` audit follow-up. Two changes only, both
Crossref/NASA-verified before use, no invented citations:

1. **Both papers**: Wan 2014 (collection-6 MODIS RSE paper) replaced with the official dataset
   citation — Wan, Hook & Hulley, "MODIS/Terra Land Surface Temperature/Emissivity 8-Day L3
   Global 1 km SIN Grid V061," NASA EOSDIS LP DAAC, 2021, doi:10.5067/MODIS/MOD11A2.061.
   Verified against `config/config.yaml` (`MODIS/061/MOD11A2`) that V061 is the collection the
   project actually uses — this is a correctness fix, not a cosmetic recency swap. Same
   citation key, same in-text location, no renumbering: still reference **[20]** in Paper A and
   **[21]** in Paper B.
2. **Paper B only**: added Probst, Wright & Boulesteix 2019 ("Hyperparameters and tuning
   strategies for random forest," WIREs DMKD 9(3):e1301, doi:10.1002/widm.1301) as reference
   **[22]**, cited once at the existing "fixed at modest defaults... with no tuning" sentence
   in Section III-G. Its first appearance in reading order falls after all other citations, so
   it appended cleanly with zero renumbering of [1]-[21].

Declined per the approved plan (all originally-verified candidates, none used): Oke 1982,
Voogt & Oke 2003, Zha 2003, Breiman 2001 (kept as foundational/method originals), Moran 1950,
Getis-Ord 1992, Benjamini-Hochberg 1995 (kept as original method references, no strict-2015+
rule confirmed), Masson 2020, Zhou 2019, Phelan 2015, Oke 2017 (verified but not needed to
support any existing claim).

Edited `refs.bib`, both `.bbl`, and one `\cite{probst2019}` insertion in
`paper_extended_ml_xai.tex` (no other running text touched), then **recompiled both PDFs with
pdflatex+bibtex** (MiKTeX) — bibtex regenerated `.bbl` from `refs.bib` and matched the
hand-edit exactly; both converged with zero undefined-citation warnings. **Both PDFs still 6
pages.** DOCX rebuilt from the same updated sources and reverified in Microsoft Word: **both
DOCX still 6 pages**, refs contiguous (A: [1]-[20], B: [1]-[22]), zero em dashes introduced by
either edit, Paper A confirmed still ML-free, Paper B's ML/XAI framing unchanged.

**LaTeX PDFs and DOCX are now back in sync on references and running text**, except for the
2026-07-13 DOCX-only readability polish (18 wording substitutions), which remains a
deliberate, documented divergence layered on top.

## DOCX assembly (2026-07-13)

Both papers assembled as blind-submission DOCX strictly inside the official
`docs/template/ICTAR-Template.docx` package (its own styles, auto-numbering, section
geometry; template's placeholder "©20XX" footer dropped):

- `docs/blind_copy/paper_core_no_ml.docx` — **6 pages** (verified in Microsoft Word), refs [1]–[20].
- `docs/blind_copy/paper_extended_ml_xai.docx` — **6 pages**, refs [1]–[21], figures at
  0.95 column width (same as the .tex).
- Content converted programmatically from the verified `.tex`/`.bbl` — scientific text,
  numbers, tables, captions unchanged; citation numbering by first appearance from the .bbl.
- Blind verified: anonymous author block, no acknowledgments/funding, DOCX metadata
  scrubbed (creator/lastModifiedBy = Anonymous, no Grammarly/Company identifiers).
- Known cosmetic differences from the LaTeX PDFs (content identical): Word reflows text so
  figures sit inline after their first citation rather than floated to column tops; the
  contribution lists use literal "1) 2) 3)" text; reference-list line breaks differ.
- **Readability polish (2026-07-13, DOCX only)**: 18 wording-only edits applied to the DOCX
  texts (commas for em-dash asides, "memorize location" → "exploit spatial proximity",
  "core headline" → "main exposure result", softened "to our knowledge" novelty claims,
  "fully open-data" → "open-data", abstract-B scale claim reworded to model-explanation
  form). No numbers, citations, figures, tables, or references changed; the .tex/.pdf do
  NOT carry these edits — if the LaTeX is ever recompiled for submission, port them first
  (the exact list is in experiment_log.md, 2026-07-13 polish entry).
- **Page gate passed again in DOCX: Paper B fits 6 pages → B remains the preferred submission.**
- Still outstanding before submission: verify the `% VERIFY`-tagged `refs.bib` entries
  against publisher pages (checklist item 2 below) — applies equally to the DOCX reference
  text, which was generated from the same .bbl.

## Assembly status (2026-07-12)

Both papers assembled as blind-submission LaTeX in `docs/blind_copy/` (IEEE conference class,
A4 two-column, matching `docs/template/ICTAR-Template.docx` formatting) and compiled with
MiKTeX/pdflatex + bibtex:

- `docs/blind_copy/paper_core_no_ml.{tex,pdf}` — **6 pages**, 20 references.
- `docs/blind_copy/paper_extended_ml_xai.{tex,pdf}` — **6 pages**, 21 references
  (figures set at 0.95\columnwidth — design size — to pull the last reference back from p. 7).
- Shared `docs/blind_copy/refs.bib`; citation renumbering by first appearance is automatic
  (IEEEtran.bst); both PDFs verified: contiguous [1]–[20]/[1]–[21], zero unresolved citations.
- Blind verified: anonymous author block, no acknowledgments/funding footnote, no identifying
  text or PDF metadata. Scientific content is verbatim from the .md section files.
- **Page gate passed: Paper B fits 6 pages → B remains the preferred submission.**
- Still outstanding before submission: verify the "needs verification" `refs.bib` entries
  (tagged `% VERIFY` in the file) against publisher pages — checklist item 2 below.

## Current state

| Item | Status |
|---|---|
| Paper A (core GIS/RS, no ML) | Drafted — 7 section files in `paper_core_no_ml/` |
| Paper B (extended, + ML/XAI) | Drafted — 7 section files in `paper_extended_ml_xai/` |
| Reference audit | Done — `docs/references/reference_matrix.md` (25 PDFs audited, 9 kept, 16 dropped with reasons) |
| Citation alignment | Done — both papers cite only matrix-KEEP references; per-paper `reference_usage_check.md` files present |
| Paper A references | Exactly 20 ([1]–[20]; [8]=Estoque 2020, [9]=Chathuranga 2022 redefined from the prior draft's numbering; [20]=Wan/Hook/Hulley V061 as of 2026-07-14) |
| Paper B references | 22 ([1]–[22]) — [21]=Wan/Hook/Hulley V061, [22]=Probst 2019 added 2026-07-14 |
| Dropped references | None remain in either paper (verified by scan) |
| ML/XAI citations in Paper A | None (verified by scan) |
| DOCX assembly | **Done (2026-07-13)** — `docs/blind_copy/{paper_core_no_ml,paper_extended_ml_xai}.docx`, both 6 pages, built strictly inside `docs/template/ICTAR-Template.docx` |
| Reference replacement | **Done (2026-07-14)** — Wan 2014 → verified MODIS V061 dataset citation (both papers); Probst 2019 added to Paper B only; see section above |

## Submission strategy (locked decisions)

- **Paper B is the preferred submission** — its ML results met the pre-registered inclusion
  criteria (spatial-split R² = 0.765, coherent SHAP ranking, quantified leakage).
- **Paper A is the fallback**: if Paper B exceeds the 6-page blind-submission limit after
  assembly into the template, submit A rather than compressing the core methodology further
  (A is estimated ~5.8 pp and is complete on its own).
- **ML/XAI is supporting material only.** The HEI + FDR-corrected hotspot analysis remains the
  main contribution in both versions; Paper B's contribution list keeps the core items first
  and holds ML to roughly one page across sections.

## Assembly checklist (must-do at DOCX stage)

1. **Fix citation numbering**: the .md drafts keep the prior draft's numbering with deliberate
   gaps/redefinitions ([8], [9] redefined; B skips [4] and [9]). IEEE numbering is by order of
   first appearance — renumber during assembly, using each paper's `reference_usage_check.md`
   as the mapping table.
2. **Verify "needs verification" references before submission**: every reference without a
   local PDF (classics, statistics originals, dataset docs, Breiman, Lundberg & Lee — see the
   check files) must have volume/page/DOI confirmed against the publisher page. The 8
   PDF-verified references (with DOIs extracted from the files) need no further lookup.
3. **Blind-submission style**: no author names/affiliations/emails; no Acknowledgment section;
   no funding footnote; no self-identifying text or personal repo links. (Template itself has
   no blind instructions — this follows the stated 6-page blind rule + double-blind norms;
   re-check against the official CFP when available.)
4. **Figures**: A uses 5 figures + 2 tables; B uses 5 figures + 3 tables (see section-file
   header comments for the exact callouts). All figure PNGs already exist at 300 dpi/~85 mm.
5. **Page gate**: measure B's true page count after assembly; apply the A-fallback rule above.

## Standing guardrails (apply to every future edit of these drafts)

- Terminology: **"Heat Exposure Index" / "heat risk"** — never unsupported "heat vulnerability"
  (no socioeconomic sensitivity/adaptive-capacity data; "vulnerability" appears only in explicit
  disclaimers and future-work sentences).
- **MODIS is a coarse consistency comparison, not validation** (r = 0.234, n = 68 — worded as
  "pattern-consistency check" everywhere).
- **SHAP is model attribution, not causality** (Paper B only; the caveat paragraph in
  Discussion is non-negotiable content).
- **Keep the NDBI quasi-circularity caveat** (NDBI and ndbi_foc3 share the 2024 Landsat
  composite with the LST target; bounded by the no-NDBI ablation, R² = 0.682).
- **Keep the spatial-leakage caveat** (headline metrics from the spatial block split only;
  random-split figures reported solely to quantify inflation).

## Source-of-truth files

Numbers: `reports/results_summary.md` (never from memory). Methods rationale:
`reports/methodology_notes.md`. Run history: `reports/experiment_log.md`. Citations:
`docs/references/reference_matrix.md` + per-paper `reference_usage_check.md`.
