# Agent 2 analysis: T1151s2 (FM/TBM)

Written by Claude from the tool outputs; full trace in `agent_transcript.md`.

## T1151s2: evaluation unit 28–111, compared against 8d5v chain A

MODELLER failed on this target: TM-score 0.16, CA RMSD 16.4 Å. AlphaFold3 gets the structure nearly right: TM-score 0.92, CA RMSD 1.5 Å. Almost all of MODELLER's error is in residues the template alignment claims to cover, so the cause is the template and alignment, not the 4-residue gap.

### Scores
All 84 EU residues were compared for both models (84 of 84 in the native EU).

| Metric | MODELLER | AlphaFold3 |
|---|---|---|
| TM-score (ours / TMscore program) | 0.162 / 0.161 | 0.916 / 0.916 |
| GDT-TS (ours / TMscore program) | 19.05 / 18.45 | 92.86 / 92.86 |
| GDT at 1 / 2 / 4 / 8 Å | 0.13 / 0.14 / 0.15 / 0.33 | 0.80 / 0.94 / 0.98 / 1.00 |
| lDDT / lDDT-CA | 0.244 / 0.277 | 0.817 / 0.899 |
| CA RMSD | 16.44 Å | 1.53 Å |

**Consistency checks:**
- Our TM-score and RMSD match the TMscore program for both models.
- MODELLER's GDT-TS differs by about 0.6 points (19.05 vs 18.45). That is a small difference in how the superposition is searched, not a mismatch in residues.
- The per-residue tool reports a mean CA deviation of 26.8 Å for MODELLER, which is larger than the 16.4 Å RMSD. This is because the per-residue numbers use the TM-score superposition. That superposition fits only a small local piece, so everything else ends up very far away. The RMSD uses its own, different superposition.

### What Agent 1 did
- The RCSB search found no eligible templates; its only hit was the target's own structure, which is excluded.
- A local MMseqs2 search allowing E-values up to 1000 gave 22 eligible chains. Agent 1 picked **7F7N:A**, an NMR structure of the transcriptional regulator WhiB4.
- The match was weak: E-value 3.9, bitscore 31, 34% identity. The search alignment covered only target residues 42–79, which is 33% of the chain.
- The fold call also relied on Agent 1's own reading of the sequence: cysteine spacing like a WhiB cluster and a GLWAGV motif. The tools did not report this.
- The align2d alignment was then extended to 111 of 116 residues at 28.8% identity, nominally covering about 95% of the EU. Only residues 80–83 had no template.
- MODELLER's own quality scores already flagged the model as unreliable: GA341 about 0.01 in all five models and z-DOPE 1.91. Agent 1 labelled the result low-confidence.

### Where MODELLER is wrong
- **Template-covered residues (80):** mean CA deviation 27.6 Å, 13.8% within 2 Å, mean lDDT 0.265.
- **Residues with no template (80–83, 4 residues):** mean CA deviation 11.3 Å, none within 2 Å, mean lDDT 0.18.
- **Segments off by more than 4 Å:**
  - 28–83 (56 residues), mean 34.7 Å.
  - 97–111 (15 residues), mean 19.5 Å.
  - The worst residues are 43–51, deviating 55–61 Å, and the N-terminus at 28–30, deviating 53–56 Å.
- **The only region within 4 Å is 84–96**, about 13 residues. This is consistent with the 13% within 2 Å and GDT-4 of 0.15, though the tool does not name these residues directly.

Residues 42–79, the only part the search alignment actually supported, are inside the badly wrong 28–83 segment. Deviations of 55–61 Å within an 84-residue domain mean the model's overall shape bears no resemblance to the native, not just that loops are misplaced. The weak hit to 7F7N therefore did not give a usable fold for this EU. Either the WhiB assignment is wrong, or the alignment register and the extension beyond 42–79 are wrong; these numbers cannot tell the two apart. The 4 residues without a template account for very little of the total error.

### AlphaFold3
- Overall: mean CA deviation 0.93 Å, 94% of residues within 2 Å, mean lDDT 0.81.
- The only segment off by more than 4 Å is the C-terminal pair 110–111 (7.5 and 8.0 Å). Residue 109 is at 3.9 Å and the N-terminal residues 28–29 are at 2.9–3.5 Å, so the remaining error is fraying at the termini.
- Residues 80–83, which had no MODELLER template, are modelled well (mean 0.87 Å). This split refers to MODELLER's template coverage and has no bearing on how AlphaFold3 built them.

### Caveats
- AlphaFold3's own confidence scores were low (pTM 0.64, ranking score 0.82) even though its accuracy on this EU is high (TM-score 0.92). The pTM may be computed over a larger chain or complex; "s2" suggests a subunit, but I have not confirmed this.
- MODELLER's mean CA B-factor (107) is not a confidence measure and should not be read as one.
- The template was a low-identity NMR structure, and only one template was used. No other WhiB-family structure was available to check the fold assignment against.
- Scores cover only EU residues 28–111.
