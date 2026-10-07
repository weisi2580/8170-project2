# Agent 2 analysis: T1151s2 (FM/TBM)

Written by Claude from the tool outputs; full trace in `agent_transcript.md`.

## T1151s2 (EU residues 28–111, 84 residues): evaluation of the MODELLER and AlphaFold3 models

### Scores
Experimental structure: 8d5v, chain A. Sequence identity to the target is 1.0, and all 84 EU residues are present. Both models were compared over all 84 residues (n_common = 84 = n_native_eu), so the scores cover the whole EU.

| Method | TM-score | GDT-TS | lDDT | lDDT-Cα | CA RMSD |
|---|---|---|---|---|---|
| MODELLER | 0.524 | 52.7 | 0.407 | 0.475 | 17.33 Å |
| AlphaFold3 | **0.916** | **92.9** | **0.817** | **0.899** | **1.53 Å** |

**Cross-check against the TMscore program:** the numbers agree. MODELLER gives TM 0.5244, GDT-TS 52.98, RMSD 17.331. AlphaFold3 gives TM 0.9161, GDT-TS 92.86, RMSD 1.532. The small GDT-TS gap for MODELLER (52.68 vs 52.98) is the usual difference in superposition search between implementations.

### What Agent 1 did
- **Search:** two jackhmmer searches returned the same 8 hits, all from the WhiB family (WhiB7, WhiB1, WhiB4).
- **Template:** 7KUG chain A (WhiB7, X-ray, 1.55 Å).
- **Alignment:** 55 residues aligned at 38.2% identity. This is 47% of the 116-residue target and 55/84 = 65.5% of the EU. The aligned segment is target residues 30–84.
- **Uncovered EU residues:** 28–29 and 85–111, a total of 29 residues.
- **Choice of model:** the lowest-DOPE model, with z-DOPE 2.04 and GA341 0.60. Agent 1 called the choice between 7KUG and 6ONO a close call. It flagged in advance that the 85–111 tail would probably be wrong.

### Where the MODELLER model is right and wrong
- **Template-covered residues (n = 55):** mean CA deviation 1.74 Å, 70.9% within 2 Å, mean lDDT 0.514. The WhiB core was modelled reasonably well. Inside it, only isolated residues exceed 4 Å: residue 35 (4.07 Å), 45 (5.6 Å) and 70 (4.3 Å).
- **Uncovered residues (n = 29):** mean CA deviation 35.07 Å, none within 2 Å, mean lDDT 0.195.
  - The 84–111 segment averages 36.1 Å. Its worst residues are 101–110, at 50–56 Å (residue 103: 56.4 Å).
  - Residue 84 is the last aligned residue, but it falls inside the bad segment. So the error begins right at the template boundary.
  - The N-terminal residues 28–29 average 6.73 Å.
- **What this means:** MODELLER built the C-terminal tail with no template, and it is placed completely wrong, far from its real position.
  - The 17.3 Å RMSD comes almost entirely from this tail; the core alone deviates by only 1.74 Å.
  - The tail also limits TM-score and GDT-TS. GDT at 8 Å is 0.69, which is about 58 of 84 residues: roughly the 55 covered residues plus a few nearby.
  - With about a third of the EU unmodelled, a TM-score of about 0.52 is close to the best this template could give.

### AlphaFold3
- **Overall:** accurate across the whole EU. Mean CA deviation is 0.93 Å, 94% of residues are within 2 Å, and GDT at 8 Å is 1.0.
- **The tail MODELLER missed (residues 28–29 and 85–111):** mean deviation 1.48 Å, 82.8% within 2 Å, lDDT 0.745. AlphaFold3 correctly placed the region that no template covered.
- **The template-covered core:** 0.64 Å, all residues within 2 Å, lDDT 0.845. This also beats MODELLER's 1.74 Å.
- **Errors:** only at the very ends. Residues 110–111 average 7.76 Å (residue 111: 8.04 Å), residue 109 is 3.9 Å, and residues 28–29 are 2.9–3.5 Å.

### Comparison and caveats
- **Overall gap:** AlphaFold3 beats MODELLER by +0.39 TM-score and +40 GDT-TS. Most of the gap comes from the 27-residue C-terminal tail that had no template; AlphaFold3 is also better in the covered core.
- **Template choice:** the template was not the main problem; the 85–111 coverage gap was. Agent 1 noted that the alternative 6ONO alignment from the looser search reached residue 87, which would have covered at most a few more residues.
- **AlphaFold3 confidence understates its accuracy here:** reported pTM is 0.64 and ranking_score is 0.82, while the measured TM over the EU is 0.916. pTM probably refers to the full-length chain, which includes residues outside the EU; I did not verify this.
- **mean_ca_bfactor:** for AlphaFold3 (89.6) this is presumably pLDDT. For MODELLER (138.9) the field is not a confidence measure, so I have not interpreted it.
- **Subunit context:** this is subunit s2 of a target and was evaluated as a single chain. Interface effects on the tail's conformation were not assessed.

Figures: T1151s2_per_residue.png, T1151s2_3d_MODELLER.png, T1151s2_3d_AlphaFold3.png, and the overlay script T1151s2_overlay.cxc.
