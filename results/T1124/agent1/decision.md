# Agent 1 decision log: T1124 (TBM-easy)

Decisions made by Claude through tool calls; full reasoning in `agent_transcript.md`.

## Searches

- rcsb, E ≤ 10: 21 hits, 6 excluded by leakage control, 15 eligible
- local, E ≤ 10: 54 hits, 8 excluded by leakage control, 46 eligible

## Decision: template 5I2H:A, model T1124.B99990002.pdb

**Decision:** build 5I2HA, model T1124.B99990002.pdb. The template is 5I2H:A, an O-methyltransferase family 2 structure solved by X-ray at 1.55 Å.

**Decisive numbers:**
- align2d identity 29.1% over 333 aligned residues.
- 87.6% of the EU (residues 7-384) is covered by the template.
- z-DOPE −0.052, the best of 15 models across the three builds. GA341 is 1.0.

**Alternatives built:**
- **2R3S:A** (RCSB search hit E = 2.4e-19, the strongest E-value): align2d identity 29.1%, 86.8% of the EU covered, best z-DOPE 0.268. Rejected because z-DOPE is clearly worse at about the same identity and coverage.
- **4A6D:A** (hydroxyindole O-methyltransferase): identity 26.6%, 88.1% of the EU covered, best z-DOPE 0.822. Rejected because both identity and z-DOPE are worse.

**Searches:** The RCSB and the high-sensitivity local MMseqs2 searches returned the same top candidates. Every hit is a SAM-dependent class-I O-methyltransferase (OMT family 2: a dimerisation helices plus Rossmann-like domain) at about 22–27% sequence identity. No closer homolog exists.

**Risks:**
- Identity is low (~29%), so expect alignment shifts in loops and in the N-terminal dimerisation helices.
- These EU stretches have no template and were modelled without one: 7-10, 22-28, 161-164, 307-309, and the C-terminus 364-384. Residues 364-384 are probably a disordered linker plus a TEV-site/tag (…ENLYFQ) and will likely be inaccurate.
- The model is a single chain, so packing that depends on the dimer is not represented.

### Build 2R3SA

| model | DOPE | z-DOPE | GA341 | molpdf |
|---|---|---|---|---|
| T1124.B99990001.pdb | -38023.4 | 0.29 | 1.000 | 2571.1 |
| T1124.B99990002.pdb | -38148.8 | 0.27 | 1.000 | 2636.4 |
| T1124.B99990003.pdb | -37931.0 | 0.31 | 1.000 | 2540.1 |
| T1124.B99990004.pdb | -37907.7 | 0.31 | 1.000 | 2457.6 |
| T1124.B99990005.pdb | -37697.4 | 0.35 | 1.000 | 2427.5 |

align2d: 330 aligned residues, identity 29.1%, target coverage 85.9%

### Build 5I2HA (selected)

| model | DOPE | z-DOPE | GA341 | molpdf |
|---|---|---|---|---|
| T1124.B99990001.pdb | -38637.7 | 0.18 | 1.000 | 2580.2 |
| T1124.B99990002.pdb (selected) | -39883.2 | -0.05 | 1.000 | 2980.3 |
| T1124.B99990003.pdb | -39237.2 | 0.07 | 1.000 | 2809.8 |
| T1124.B99990004.pdb | -39401.3 | 0.04 | 1.000 | 2870.4 |
| T1124.B99990005.pdb | -39616.0 | -0.00 | 1.000 | 2724.4 |

align2d: 333 aligned residues, identity 29.1%, target coverage 86.7%

### Build 4A6DA

| model | DOPE | z-DOPE | GA341 | molpdf |
|---|---|---|---|---|
| T1124.B99990001.pdb | -35116.6 | 0.83 | 0.999 | 2268.4 |
| T1124.B99990002.pdb | -34751.3 | 0.89 | 0.986 | 2241.4 |
| T1124.B99990003.pdb | -35125.2 | 0.83 | 0.992 | 2087.9 |
| T1124.B99990004.pdb | -35142.9 | 0.82 | 0.942 | 2172.6 |
| T1124.B99990005.pdb | -35046.2 | 0.84 | 0.999 | 2128.5 |

align2d: 335 aligned residues, identity 26.6%, target coverage 87.2%

