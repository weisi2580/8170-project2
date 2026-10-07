# Agent 2 analysis: T1127 (TBM-hard)

Written by Claude from the tool outputs; full trace in `agent_transcript.md`.

## T1127 (TBM-hard), EU 6-210: MODELLER vs AlphaFold3

**In short:** MODELLER (template 2FE7:B, a GNAT N-acetyltransferase) gets the core GNAT fold roughly right but misses the target's insertion completely. Its TM-score is 0.658 and its CA RMSD is 13.45 Å. AlphaFold3 matches the experimental structure almost exactly everywhere (TM-score 0.973, RMSD 0.92 Å), including the insertion.

### Scores (experimental structure 8xbp chain A, 198 residues observed in the EU)
| Metric | MODELLER | AlphaFold3 |
|---|---|---|
| TM-score (ours / TMscore program) | 0.6582 / 0.6582 | 0.9731 / 0.9731 |
| GDT-TS (ours / TMscore program) | 59.34 / 59.60 | 95.45 / 95.45 |
| GDT at 1/2/4/8 Å | 0.41 / 0.61 / 0.64 / 0.71 | 0.86 / 0.96 / 1.00 / 1.00 |
| lDDT (all-atom) / lDDT (CA only) | 0.488 / 0.582 | 0.882 / 0.958 |
| CA RMSD (Å) | 13.45 | 0.92 |
| Residues compared | 198 / 198 | 198 / 198 |

**Consistency checks:**
- Our TM-score matches the TMscore program to four decimal places for both models.
- For MODELLER, GDT-TS differs slightly (59.34 vs 59.60), which is within the usual variation between superposition searches.
- All 198 residues observed in the experimental EU were compared for both models. The EU spans 205 residue numbers, but 7 of them are not observed in the experimental structure.
- AlphaFold3's own confidence agreed with the outcome: ranking score 0.95, pTM 0.90, mean pLDDT 92.

### What Agent 1 did
- Both template searches (RCSB and local MMseqs2) found only GNAT-family acetyltransferases.
- Agent 1 chose 2FE7:B (2.0 Å X-ray; E-value 2.3e-18). The alignment has 40.1% identity over 162 aligned residues and covers 76.7% of the target.
- The runner-up, 2BEI:B, had essentially the same z-DOPE (0.871 vs 0.879). Agent 1 chose 2FE7 for its higher identity and partial coverage of the insertion.
- Agent 1 predicted the problem correctly: about 23% of the EU has no template, mostly an insertion around residues 51-113, and would "probably be inaccurate".

### Where MODELLER is right and wrong
- **Residues covered by the template (n=155):** mean CA deviation 3.27 Å, 76.8% within 2 Å, mean lDDT 0.59. The GNAT core is placed reasonably well; GDT at 2 Å is 0.61, about 78% of 0.768.
- **Residues not covered by the template (n=43):** mean CA deviation 24.79 Å, none within 2 Å, mean lDDT 0.21. These segments are 51-56, 58-63, 65-72, 80-81, 95-113, 196 and 209.
- **Segments deviating by more than 4 Å:**
  - **51-72** (mean 24.5 Å): the worst residues, 66-70, are off by 38-46 Å.
  - **79-113** (mean 21.3 Å): the worst residues, 103-107, are off by 37-45 Å. This segment includes 82-94, which Agent 1 said is template-aligned, so partial coverage of the insertion did not place it correctly.
  - **194-209** (mean 10.7 Å): the C-terminal region is also misplaced, even though only 196 and 209 lack template coverage.
- **Why RMSD is high but TM-score is moderate:** the 13.45 Å RMSD is driven by these misplaced segments, about 73 residues in total. TM-score and GDT down-weight large errors, so they mainly reflect the reasonably modelled core.
- **All-atom quality:** all-atom lDDT (0.488) is well below CA-only lDDT (0.582). This suggests that local side-chain and backbone detail is also poor, not just the overall placement.

### AlphaFold3
- Uniform high accuracy: mean CA deviation 0.68 Å on template-covered residues and 0.81 Å on uncovered ones. 96% of residues are within 2 Å.
- Only residue 209 at the C-terminus deviates by more than 4 Å (4.01 Å). The next largest deviations are at 200-202 and 208 (2.1-3.3 Å) and at 91-92 (2.4-3.2 Å).
- AlphaFold3 got right exactly the region that has no template in this search, which is where MODELLER fails.

### Caveats
- The MODELLER model's B-factor column is not a confidence measure, so its mean "B-factor" of 124.7 is not meaningful.
- Agent 1's uncovered-segment list (51-56, 58-63, 65-76, 80-81, 95-113, 196, 209-210) differs slightly from the list used in this evaluation (65-72, no 210). The most likely reason is the 7 residues missing from the experimental structure, but I did not check this.
- The template-covered vs uncovered split uses Agent 1's align2d alignment. The AlphaFold3 per-region numbers are shown on the same split only for comparison; AlphaFold3 did not use this template.
- These numbers come from one MODELLER model and one AlphaFold3 model.
- Choosing 2BEI instead would probably not have helped: Agent 1 reports it leaves residues 66-110 entirely uncovered.
