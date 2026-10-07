# Agent 2 analysis: T1127 (TBM-hard)

Written by Claude from the tool outputs; full trace in `agent_transcript.md`.

## T1127: MODELLER vs AlphaFold3 over EU residues 6–210

AlphaFold3 got the structure almost exactly right (TM 0.973, CA RMSD 0.92 Å). MODELLER got the core GNAT fold right where it had a template, but a long stretch with no template came out in the wrong place (TM 0.722, CA RMSD 11.47 Å). Nearly all of MODELLER's error comes from that missing template coverage, not from the template being wrong.

### Scores
The experimental structure is 8xbp chain A, which matches the target sequence exactly (identity 1.0). It has 198 residues in the EU. Both models were compared on all 198, with none missing.

| Metric | MODELLER | AlphaFold3 |
|---|---|---|
| TM-score | 0.722 | 0.973 |
| GDT-TS | 65.53 | 95.45 |
| GDT within 1/2/4/8 Å (fraction of residues) | 0.44 / 0.65 / 0.72 / 0.81 | 0.86 / 0.96 / 1.00 / 1.00 |
| lDDT (all atoms) | 0.529 | 0.882 |
| lDDT (CA only) | 0.625 | 0.958 |
| CA RMSD | 11.47 Å | 0.92 Å |

**Cross-check:** the separate TMscore program gives the same results.
- MODELLER: 0.7221 / 65.66 / 11.474
- AlphaFold3: 0.9731 / 95.45 / 0.923

GDT-TS differs by 0.13 for MODELLER, which is within normal rounding and implementation differences.

### What Agent 1 did
- **Search:** three rounds of jackhmmer, with 250 eligible hits.
- **Template:** 2FE7 chain B, a probable N-acetyltransferase (X-ray, 2.0 Å, E = 2.5e-47).
- **Search hit vs final alignment:** the search hit itself covered only target residues 107–207 (39.6% identity, 47.9% coverage). The MODELLER alignment extended this to residues 4–59 and 105–207: 159 aligned residues, 35.8% identity, 75.4% coverage.
- **Choice:** Agent 1 picked 2FE7 over 2BEI (SSAT2) for its higher identity and coverage, while noting that 2BEI was a close alternative.
- **Risk flagged in advance:** Agent 1 said residues ~60–104 are an insertion that no template covers and would probably be unreliable. That turned out to be correct.

### Where MODELLER is right and wrong
Across all 198 residues, the mean CA deviation is 6.11 Å and 63.6% of residues are within 2 Å.

| Residues | Count | Mean CA deviation | Within 2 Å | Mean lDDT |
|---|---|---|---|---|
| Covered by the template | 157 | 1.88 Å | 80.3% | 0.622 |
| Not covered (60–72, 79–104, 208–209) | 41 | 22.32 Å | 0% | 0.224 |

**Segments off by more than 4 Å:**
- **54–63** (mean 6.58 Å): the end of the covered N-terminal block running into the start of the insertion.
- **65–72** (16.54 Å).
- **79–109** (25.38 Å): this is the main failure. The worst residues are 79–84, at 33–52 Å off (residue 80 is 51.9 Å off). The error carries into covered residues 105–109 next to the gap.
- **200–209** (7.89 Å): the C-terminal end, including uncovered 208–209.
- Residue 52 is slightly over the threshold (4.13 Å).

**Interpretation:** the core built from the template is accurate, with 80% of its residues within 2 Å. The ~40-residue insertion was built without a template, and MODELLER put it in the wrong place relative to the core. Because RMSD weights large errors heavily, these few residues push the overall RMSD to 11.5 Å. TM-score is less sensitive to them and stays at 0.72.

### AlphaFold3
- **Overall:** mean CA deviation 0.71 Å, 96% of residues within 2 Å. Only residue 209 is more than 4 Å off (4.01 Å).
- **Template-covered residues:** 0.66 Å, lDDT 0.879.
- **Residues the template did not cover:** still accurate at 0.89 Å, 90.2% within 2 Å, lDDT 0.824.
- **Weakest spots:** residues 91–92 (2.4–3.2 Å, lDDT 0.54–0.63) and 200–202 / 208–209 (up to 4.0 Å). These are the same loop and C-terminal regions where MODELLER struggles, but the errors here are much smaller.
- **Confidence:** AlphaFold3's own confidence was high (ranking score 0.95, pTM 0.90, mean pLDDT 92.1) and matches its actual accuracy.

### Caveats
- **Residue counts:** the EU spans 205 residue numbers, but the experimental structure has only 198 residues there. Scores cover those 198 only; which 7 are missing was not reported.
- **Insertion boundaries don't match exactly:** Agent 1's rationale describes 60–104 as one uncovered stretch. The per-residue mapping instead lists 60–72 and 79–104, so residues 73–78 count as covered. Agent 1 also gives coverage as 76.6% of the EU, while 157 of 198 observed residues is 79.3%. These are bookkeeping differences in how coverage is measured and do not change the conclusions.
- **MODELLER's "confidence" number means nothing here:** its mean CA B-factor of 118.9 is not a confidence measure. AlphaFold3's B-factor column, by contrast, is pLDDT.
- **AlphaFold3 training overlap not checked:** I did not check whether AlphaFold3's training data includes this structure or close homologs. The 0.92 Å agreement should be read with that in mind.
- **2BEI not evaluated:** the alternative template was not scored, so whether it would have done better is unknown. It leaves residues 67–111 uncovered, a similar gap, so it would probably have the same problem.
