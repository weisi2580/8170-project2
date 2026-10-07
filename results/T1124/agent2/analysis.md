# Agent 2 analysis: T1124 (TBM-easy)

Written by Claude from the tool outputs; full trace in `agent_transcript.md`.

## T1124 (TBM-easy, EU 7–384): evaluation of the MODELLER and AlphaFold3 models

### Summary
AlphaFold3 is far better than MODELLER on this target. MODELLER's catalytic domain is roughly right, but its whole N-terminal region (residues 7–135) is placed tens of Å away from where it sits in the crystal structure. Only the C-terminal tail is wrong in the AlphaFold3 model.

### Scores
The model was compared with experimental structure 7UX8 chain A (100% identical to the target). All 378 EU residues are present in the native structure and in both models (n_common = 378 = EU size).

| Metric | MODELLER (5I2H:A template) | AlphaFold3 |
|---|---|---|
| TM-score (ours / TMscore program) | 0.537 / 0.5367 | 0.940 / 0.9397 |
| GDT-TS (ours / TMscore program) | 41.27 / 40.94 | 90.81 / 90.81 |
| GDT at 1 / 2 / 4 / 8 Å | 0.23 / 0.38 / 0.48 / 0.57 | 0.82 / 0.92 / 0.94 / 0.96 |
| lDDT (all atoms) / lDDT using only CA atoms | 0.542 / 0.637 | 0.870 / 0.928 |
| CA RMSD (all 378 residues) | 21.29 Å | 6.59 Å |

**Consistency checks:**
- Our TM-score and CA RMSD match the TMscore program to within rounding.
- MODELLER's GDT-TS differs slightly (41.27 vs 40.94), which is consistent with small differences in how the superposition is searched.
- AlphaFold3's own confidence scores were ranking score 0.90 and pTM 0.86.

### What Agent 1 did
- **Search:** jackhmmer, 3 rounds, 250 hits. All hits were O-methyltransferases of this family (N-terminal dimerisation domain plus a Rossmann-type methyltransferase domain).
- **Template:** 5I2H chain A, an X-ray structure at 1.55 Å. It was chosen over 3GWZ and 1QZZ because it had the best z-DOPE score (0.291).
- **Alignment:** 312 aligned residues at 26.6% identity, covering 81% of the target. The search hit covers target residues 33–364.
- **Gaps in the EU** (no template residues): 7–31, 365–384 (379–384 is a masked tag), and short loop gaps at 94–96, 100, 124–127, 156–159, 187–190, 261 and 312–315.
- Agent 1 itself flagged that the angle between the N-terminal dimerisation helices and the catalytic domain might be wrong.

### Where the MODELLER errors are
After the best superposition, CA atoms deviate by 16.78 Å on average, and only 37% of residues are within 2 Å.

**The main error is one continuous segment, residues 7–135 (129 residues), with a mean CA deviation of 38.0 Å.**
- Most of this segment is covered by the template (32–135). So the problem is not just regions without a template; the whole N-terminal block is misplaced.
- The worst residues deviate by 59–69 Å (residues 96–99 and 59–66). Yet residues 59–66 still have lDDT 0.64–0.71. lDDT compares inter-atomic distances within each structure, so high lDDT despite a large CA deviation means the local structure is roughly right but the block is in the wrong place.
- That is the domain-orientation risk Agent 1 predicted. In this family the N-terminal dimerisation region typically meshes with the partner subunit, so a monomer modelled on a homologue at 27% identity can put it in the wrong place. I have not checked this against the native dimer.

**Catalytic domain (about 136–364):** mostly within 4 Å. The exceptions are:
- loops 148–162 (12.5 Å) and 182–193 (10.9 Å), which overlap the gaps at 156–159 and 187–190;
- 308–315 (7.8 Å), which overlaps the gap at 312–315;
- a few short 1–3-residue stretches at 4–6 Å.

The GDT plateau of about 0.48 at 4 Å fits this picture: roughly the C-terminal domain is right and the N-terminal block is wrong.

**C-terminal tail 365–384:** mean deviation 35.6 Å, with no template.

**By template coverage:**

| Residues | n | Mean CA deviation | Within 2 Å | Mean lDDT |
|---|---|---|---|---|
| Covered by template | 312 | 13.76 Å | 44.9% | 0.568 |
| Not covered | 66 | 31.05 Å | 0% | 0.27 |

The covered-residue average is high mainly because of the misplaced residues 32–135.

### Where the AlphaFold3 errors are
- **Template-covered residues:** mean CA deviation 0.80 Å, 97.1% within 2 Å, mean lDDT 0.878. The N-terminal domain is correctly placed (residues 7 and 18 are the only N-terminal residues above 4 Å, at about 5 Å).
- **Residues not covered by the template:** mean 8.07 Å, 65.2% within 2 Å, lDDT 0.693. So AlphaFold3 also models most of the gap regions well.
- **Errors above 4 Å:**
  - loop 147–152 (8.1 Å);
  - C-terminal tail 369–384 (mean 29.7 Å; worst residues 375–384 at 25–53 Å, with lDDT 0.13–0.30).
- The tail is what raises AlphaFold3's RMSD to 6.59 Å; GDT and TM-score are hardly affected.

### Caveats
- **Tag residues 379–384 are scored.** This is the masked TEV/tag sequence. It is inside the EU and present in the native structure, so it counts against both models. Its position in the crystal may reflect crystal packing or contacts within the dimer rather than something predictable.
- **RMSD is not a useful headline number here.** For both models it is dominated by a few large errors: the misplaced N-terminal block for MODELLER and the tail for AlphaFold3. TM-score, GDT and lDDT give a fairer picture.
- **Only a single chain was evaluated.** I did not check dimer contacts, so the reason given above for MODELLER's N-terminal misplacement is a likely explanation, not a verified one.
- **The class label overstates how easy this was for template modelling.** Even for a TBM-easy target, building from a single template at 27% identity gave TM-score 0.54. The local structure was largely right, but domains were arranged wrongly.
