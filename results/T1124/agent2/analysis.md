# Agent 2 analysis: T1124 (TBM-easy)

Written by Claude from the tool outputs; full trace in `agent_transcript.md`.

# T1124 (CASP15 TBM-easy, EU residues 7-384): MODELLER vs AlphaFold3

**In short:** MODELLER's model of T1124 is only partly right (TM 0.52). Its N-terminal region, residues 7-135, sits in the wrong place relative to the rest of the protein, about 38 Å off on average. Missing template coverage does not explain this. AlphaFold3 is close to the experimental structure (TM 0.94); its only real error is the C-terminal tail.

## 1. Scores (EU 7-384, against 7UX8 chain A, 100% sequence identity to the target)

| Method | TM-score | GDT-TS | lDDT | lDDT-Cα | Cα RMSD (Å) | Residues compared |
|---|---|---|---|---|---|---|
| MODELLER (5I2H:A template) | 0.519 | 38.56 | 0.532 | 0.628 | 21.21 | 378 / 378 |
| AlphaFold3 | 0.940 | 90.81 | 0.870 | 0.928 | 6.59 | 378 / 378 |

GDT fractions at 1, 2, 4 and 8 Å:
- MODELLER: 0.19, 0.35, 0.45, 0.56
- AlphaFold3: 0.82, 0.92, 0.94, 0.96

**Consistency checks:**
- Our scores agree with the TMscore program:
  - MODELLER: TM 0.5193, GDT-TS 38.36 (ours 38.56, a 0.2-point difference), RMSD 21.211.
  - AlphaFold3: TM 0.9397, GDT-TS 90.81, RMSD 6.591.
- All 378 EU residues were compared for both models (n_common = n_native_eu = 378), so no part of the EU was left out of the scores.
- Template coverage adds up: 331 of the 378 EU residues are aligned to the template (87.6%). This matches Agent 1's stated 87.6%. The 333 aligned residues from align2d are counted over the full 384-residue sequence.

## 2. What Agent 1 did
- **Template:** 5I2H:A, an O-methyltransferase family 2 X-ray structure at 1.55 Å.
  - Search: BLAST identity 26.7%, E = 3.4e-16.
  - align2d: 29.1% identity over 333 residues.
- **Alternatives built and rejected on z-DOPE:**
  - 2R3S:A had the strongest E-value but a worse z-DOPE (0.268).
  - 4A6D:A had a worse z-DOPE (0.822).
- **Selected model:** z-DOPE −0.052, GA341 1.0.
- **Risks Agent 1 flagged:** alignment shifts in loops and in the N-terminal dimerisation helices, the untemplated C-terminal tag region, and the lack of the dimer.

## 3. Where MODELLER is wrong
Per-residue Cα deviation after TM superposition:
- Mean 16.31 Å over all residues; 33.1% of residues are within 2 Å.
- Template-aligned residues (331): mean 14.93 Å, lDDT 0.542.
- Residues not aligned to the template (47): mean 26.02 Å, lDDT 0.308, and none within 2 Å.

**The main error is residues 7-135 (129 residues, mean Cα deviation 37.72 Å).**
- The worst residues, 59-66 and 95-100, are 58-69 Å off.
- Their per-residue lDDT is still moderate (0.35-0.75, e.g. residue 59 at 0.75 and residue 60 at 0.69). lDDT only looks at each residue's local neighbourhood. So these residues are locally roughly the right shape, but the whole N-terminal block is placed in the wrong position and orientation relative to the C-terminal domain. This is a domain-placement error, not a failure of the local fold.
- Template coverage does not explain it. Only a few short stretches inside 7-135 are unaligned (7-10, 22-28, 96-98, 100, 120, 125-127), yet the aligned residues in this block are just as far off.
- **Hypothesis (not tested here):** in OMT family 2 the N-terminal helices form the dimer interface. Copying a monomer from the template, with only weak sequence identity, may have placed this block where it belongs in the dimer context rather than against its own chain. Agent 1's "single chain, no dimer" risk fits this explanation, but I did not inspect the template's chain arrangement.
- This one error largely sets the global scores. The 21.2 Å RMSD and a TM-score of about 0.52 are roughly what you get when only the C-terminal domain superposes: about 45% of residues are within 4 Å.

**Secondary errors, in the domain that is mostly correct:**
- 142-166: mean 10.3 Å. This includes the unaligned 161-164.
- 184-194: mean 9.64 Å. Next to the unaligned 183-184.
- 307-314: mean 10.7 Å. This includes the unaligned 307-309. Small deviations (4-6 Å) continue through 317-329.
- **C-terminus 363-384:** mean 22.76 Å. This stretch is mostly unaligned (364-377 and 382-384) and is probably a linker plus a TEV-site tag, as Agent 1 predicted.

Agent 1's list of untemplated EU stretches was incomplete. The per-residue mapping also finds unaligned residues at 96-98, 100, 120, 125-127, 183-184, 262 and 328, and residues 378-381 are aligned.

## 4. AlphaFold3
- Overall: mean Cα deviation 2.07 Å, 91.5% of residues within 2 Å, mean lDDT 0.845.
- On the 331 template-aligned positions: mean 1.29 Å.
- The N-terminal region is placed correctly. Only isolated residues 7 (5.12 Å) and 18 (5.37 Å) exceed 4 Å.
- Errors above 4 Å:
  - Loop 147-152: mean 8.09 Å. This loop is also wrong in MODELLER.
  - C-terminal tail 369-384: mean 29.73 Å, rising to 53.4 Å at residue 384, with lDDT 0.13-0.30. This tail accounts for most of AF3's 6.59 Å RMSD.
- AF3's own confidence scores agreed with the result: ranking score 0.90, pTM 0.86. Note that "template coverage" in AF3's breakdown is just MODELLER's alignment mask applied for comparison; AF3 did not use that alignment.

## 5. Comparison and caveats
- AF3 beats MODELLER by +0.42 TM, +52 GDT-TS and +0.34 lDDT.
- Nearly all of the gap comes from the misplaced N-terminal region. Within the C-terminal domain, MODELLER's errors are limited to the loops listed above and the tail.
- **Model choice:** z-DOPE, which Agent 1 used to pick between templates, cannot detect a wrong arrangement of domains relative to each other. A better z-DOPE did not mean a correct global fold here. The rejected models from 2R3S and 4A6D were not scored, so it is unknown whether they would have done better.
- The tail 364-384 is probably disordered or tag sequence, and both methods get it wrong. Its large deviations inflate RMSD for both, especially AF3's.
- The cause of the N-terminal misplacement (the dimer-context explanation) is a hypothesis. Checking the template's chain arrangement in the overlay file T1124_overlay.cxc would confirm or rule it out.
