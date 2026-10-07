# Agent 1 decision log: T1124 (TBM-easy)

Decisions made by Claude through tool calls; full reasoning in `agent_transcript.md`.

## Searches

- jackhmmer, 3 round(s) (3 run), inclusion E ≤ 0.001, report E ≤ 1: 250 hits, 0 excluded by leakage control, 250 eligible

## Decision: template 5I2H:A, model T1124.B99990001.pdb

**Decision:** I chose build 5I2HA, model T1124.B99990001.pdb. The template is 5I2H chain A, an O-methyltransferase family 2 protein solved by X-ray at 1.55 Å.

**Search:** The default jackhmmer search (3 rounds, inclusion E 1e-3) returned 250 hits, all class I SAM-dependent O-methyltransferases (dimerisation domain plus Rossmann-type MTase domain). The hits agree with one another, so the profile did not drift. Every top hit covers target residues ~30–364, at 18–28% identity with E-values of 1e-68 or lower.

**Builds compared (5 models each):**

| Build | Identity | EU covered | Best z-DOPE | GA341 |
|---|---|---|---|---|
| 5I2H:A | 26.6% | 0.825 | **0.291** | 1.0 |
| 3GWZ:A (MmcR) | 24.0% | 0.849 | 0.728 | 1.0 |
| 1QZZ:A | 22.5% | 0.847 | 0.864 | 1.0 |

5I2H has the highest alignment identity and a clearly better z-DOPE than the other two, roughly 0.44 or more lower. That outweighs its ~2–3% smaller EU coverage. The lowest-DOPE model in the 5I2H build also has the best z-DOPE (0.291).

**Risks:**
- About 17.5% of the EU is not covered by the template and is modelled without template restraints, so those parts are unreliable:
  - the N-terminal segment 7–31 (25 residues)
  - the C-terminal segment 365–384 (20 residues; 379–384 is a masked TEV/tag sequence)
  - several short loop gaps: 94–96, 100, 124–127, 156–159, 187–190, 261, 312–315
- Identity is only ~27%, so loop and side-chain placement will be approximate. The relative orientation of the N-terminal dimerisation helices and the catalytic domain may also be off, since it can vary between homologues in this family.

### Build 5I2HA (selected)

| model | DOPE | z-DOPE | GA341 | molpdf |
|---|---|---|---|---|
| T1124.B99990001.pdb (selected) | -38023.4 | 0.29 | 1.000 | 2393.0 |
| T1124.B99990002.pdb | -37483.9 | 0.39 | 1.000 | 2246.1 |
| T1124.B99990003.pdb | -37516.3 | 0.38 | 1.000 | 2191.9 |
| T1124.B99990004.pdb | -37316.4 | 0.42 | 1.000 | 2436.7 |
| T1124.B99990005.pdb | -36986.7 | 0.48 | 1.000 | 2556.4 |

alignment: 312 aligned residues, identity 26.6%, target coverage 81.2%

### Build 1QZZA

| model | DOPE | z-DOPE | GA341 | molpdf |
|---|---|---|---|---|
| T1124.B99990001.pdb | -33570.6 | 1.11 | 0.997 | 3080.9 |
| T1124.B99990002.pdb | -33246.4 | 1.17 | 1.000 | 2902.3 |
| T1124.B99990003.pdb | -34915.5 | 0.86 | 1.000 | 2689.2 |
| T1124.B99990004.pdb | -34282.0 | 0.98 | 1.000 | 2921.9 |
| T1124.B99990005.pdb | -34635.1 | 0.92 | 0.999 | 2713.3 |

alignment: 320 aligned residues, identity 22.5%, target coverage 83.3%

### Build 3GWZA

| model | DOPE | z-DOPE | GA341 | molpdf |
|---|---|---|---|---|
| T1124.B99990001.pdb | -35493.6 | 0.76 | 1.000 | 1741.7 |
| T1124.B99990002.pdb | -35655.5 | 0.73 | 1.000 | 1935.2 |
| T1124.B99990003.pdb | -35244.4 | 0.80 | 1.000 | 1989.6 |
| T1124.B99990004.pdb | -35457.0 | 0.76 | 1.000 | 1918.3 |
| T1124.B99990005.pdb | -35300.0 | 0.79 | 1.000 | 1864.3 |

alignment: 321 aligned residues, identity 24.0%, target coverage 83.6%

