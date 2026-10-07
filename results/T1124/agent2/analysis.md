# Agent 2 analysis: T1124 (TBM-easy)

Written by Claude from the tool outputs; full trace in `agent_transcript.md`.

## T1124 (TBM-easy, EU 7-384): MODELLER evaluation

**Result:** The catalytic Rossmann-like domain (about residues 136-362) is modelled reasonably well. The N-terminal region (residues 7-135) is folded but placed in the wrong position relative to that domain. Because of this placement error, the global scores are mediocre for a TBM-easy target. There was no AlphaFold3 model for this target, so no comparison with AF3 was possible.

### Scores (MODELLER, model T1124.B99990002, template 5I2H:A)
| Metric | Our value | TMscore program |
|---|---|---|
| TM-score | 0.519 | 0.5193 |
| GDT-TS | 38.56 | 38.36 |
| CA RMSD | 21.21 Å | 21.211 Å |
| lDDT (all-atom) | 0.532 | – |
| lDDT (CA) | 0.628 | – |

GDT fractions: 0.188 within 1 Å, 0.349 within 2 Å, 0.450 within 4 Å, 0.556 within 8 Å.

**Consistency checks:**
- All 378 EU residues were compared (n_common = n_native_eu = 378). The native is 7ux8 chain A at 100% identity to the target.
- TM-score and RMSD agree with the TMscore program. GDT-TS differs by only 0.2 points, which is normal variation between superposition searches.
- Agent 1 reported 87.6% of the EU as template-covered. That matches the 331 template-aligned EU residues in the per-residue analysis (331/378 = 0.876). The align2d count of 333 aligned residues probably includes 2 residues outside the EU.

### What Agent 1 did
- Agent 1 chose the O-methyltransferase family 2 structure 5I2H:A (X-ray, 1.55 Å). Its search identity was 26.7%, and align2d gave 29.1% identity over 333 residues.
- It chose 5I2H over 2R3S:A and 4A6D:A on z-DOPE. The selected model scored z-DOPE −0.052 and GA341 1.0.
- All candidate templates were family-2 O-methyltransferases at about 22-27% identity. Agent 1 flagged three risks in advance: the N-terminal dimerisation helices, the untemplated C-terminal tail, and missing dimer context.

### Where the errors are (CA deviation after TM superposition, 4 Å threshold)
- **Residues 7-135 are displaced as a block.** This 129-residue segment averages 37.7 Å CA deviation. The worst residues reach about 60-69 Å (residues 59-66 and 95-100).
  - Even so, local lDDT stays fairly high in parts of this region: 0.69-0.75 at residues 59-62 and about 0.50-0.54 at residues 95-99.
  - lDDT does not depend on superposition. High local lDDT alongside huge CA deviations means the local structure is roughly right but the region sits in the wrong place relative to the catalytic domain.
  - This matches Agent 1's warning about the N-terminal dimerisation helices. In this family those helices pack against the partner subunit, and the model was built as a single chain.
  - The data do not tell us whether the native has a different interdomain hinge or a domain-swapped arrangement. They only show that the N-terminal region is misplaced as a whole.
- **The catalytic domain is mostly accurate.** Most residues from 136 to 362 are below 4 Å. About 170 residues are within 4 Å and about 132 within 2 Å (from the GDT fractions). Errors above 4 Å in this domain are limited to:
  - 142-166 (mean 10.3 Å), which contains the untemplated 161-164
  - 184-194 (9.6 Å), next to the untemplated 183-184
  - 307-314 (10.7 Å), which contains the untemplated 307-309
  - short stretches between 317 and 329 (4-5.5 Å), around the untemplated 328
- **C-terminus 363-384** (mean 22.8 Å) is mostly untemplated (364-377 and 382-384). Agent 1 flagged it as a likely disordered linker or tag region.

### Template-covered vs uncovered residues
| Residues | n | Mean CA deviation | Within 2 Å | Mean lDDT |
|---|---|---|---|---|
| Template-covered | 331 | 14.9 Å | 37.8% | 0.542 |
| Not covered | 47 | 26.0 Å | 0% | 0.308 |

- The mean deviation for covered residues is high because the misplaced N-terminal block is itself mostly template-covered. Template coverage alone does not explain the main error: the alignment was there, but the domain placement was wrong.
- Agent 1's list of untemplated segments left out several short gaps that the per-residue analysis finds: 96-98, 100, 120, 125-127, 183-184, 262 and 328.

### MODELLER vs AlphaFold3
No AlphaFold3 model was available, so no comparison is possible.

### Caveats
- The scores are for a single chain compared with chain A of the native. Contacts across the dimer, which probably set where the N-terminal region sits, are not represented in the model.
- The mean CA B-factor (116.5) is a MODELLER output field, not a confidence score, so I did not use it.
- A local or per-domain superposition would probably score the catalytic domain much higher than the global TM-score of 0.519 suggests. I did not compute per-domain scores.

Figures: T1124_per_residue.png, T1124_overlay.cxc.
