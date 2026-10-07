# Agent 1 decision log: T1127 (TBM-hard)

Decisions made by Claude through tool calls; full reasoning in `agent_transcript.md`.

## Searches

- jackhmmer, 3 round(s) (3 run), inclusion E ≤ 0.001, report E ≤ 1: 250 hits, 0 excluded by leakage control, 250 eligible

## Decision: template 2FE7:B, model T1127.B99990005.pdb

## Choice: build 2FE7B, model T1127.B99990005.pdb

The template is 2FE7 chain B, a probable N-acetyltransferase from the GNAT family (X-ray, 2.0 Å, completeness 1.0).

**Why this build**
- It covers more of the evaluation unit than any other build: target residues 4-59 and 105-207, which is 76.6% of residues 6-210.
- It has the highest alignment identity of the three builds: 35.8% over 159 aligned residues.
- The kept model has the lowest DOPE in its build, z-DOPE 1.24, with GA341 0.93. The other models in this build have GA341 between 0.93 and 1.0.
- 2FE7 was the top-ranked search hit (E = 2.5e-47).

**Alternatives built and rejected**
- **2BEI:B (diamine acetyltransferase 2, also called SSAT2):** its best model has the better z-DOPE (0.99, GA341 0.98). However, its identity is lower (30.9%) and it covers less of the evaluation unit (74.1%). It leaves residues 67-111 and 207-210 unmodelled, a larger gap than 2FE7 leaves. The DOPE difference is modest, so I gave more weight to identity and coverage. The two choices are close, and 2BEI remains a reasonable alternative.
- **4HNY:B (ARD1, the catalytic subunit of the N-terminal acetyltransferase A complex):** it covers only 65.9% of the evaluation unit and misses the whole N-terminal region, residues 6-67. Its identity is 19%, its z-DOPE is about 2.6 and its GA341 is 0.09, so I rejected it.
- **Other hits:** the remaining top hits are redundant copies of SSAT1/2 or ARD1, or GNAT proteins with lower identity and only partial coverage.

**Risks**
- Residues 60-104 are an insertion relative to every template found. That is about 45 residues with no template, so MODELLER built them without template guidance and they are probably unreliable. Residues 208-210 at the C-terminus are also uncovered.
- Only one template was used. The fold call (GNAT acetyltransferase) is confident, but placing the insertion relative to the core is uncertain.

### Build 4HNYB

| model | DOPE | z-DOPE | GA341 | molpdf |
|---|---|---|---|---|
| T1127.B99990001.pdb | -14408.4 | 2.56 | 0.086 | 1290.7 |
| T1127.B99990002.pdb | -14065.8 | 2.68 | 0.047 | 1194.9 |
| T1127.B99990003.pdb | -14123.1 | 2.66 | 0.016 | 1309.9 |
| T1127.B99990004.pdb | -13488.6 | 2.87 | 0.026 | 1532.5 |
| T1127.B99990005.pdb | -13874.6 | 2.74 | 0.024 | 1394.2 |

alignment: 135 aligned residues, identity 19.3%, target coverage 64.0%

### Build 2FE7B (selected)

| model | DOPE | z-DOPE | GA341 | molpdf |
|---|---|---|---|---|
| T1127.B99990001.pdb | -17186.0 | 1.63 | 1.000 | 6305.7 |
| T1127.B99990002.pdb | -18162.4 | 1.30 | 0.952 | 1562.8 |
| T1127.B99990003.pdb | -17984.0 | 1.36 | 0.958 | 1333.4 |
| T1127.B99990004.pdb | -18302.7 | 1.26 | 0.997 | 1785.7 |
| T1127.B99990005.pdb (selected) | -18349.4 | 1.24 | 0.930 | 1345.2 |

alignment: 159 aligned residues, identity 35.8%, target coverage 75.4%

### Build 2BEIB

| model | DOPE | z-DOPE | GA341 | molpdf |
|---|---|---|---|---|
| T1127.B99990001.pdb | -17684.7 | 1.46 | 0.943 | 3314.9 |
| T1127.B99990002.pdb | -19108.1 | 0.99 | 0.980 | 1704.9 |
| T1127.B99990003.pdb | -18942.0 | 1.04 | 0.858 | 3277.1 |
| T1127.B99990004.pdb | -18830.6 | 1.08 | 0.863 | 3437.5 |
| T1127.B99990005.pdb | -18872.5 | 1.06 | 0.962 | 3347.9 |

alignment: 152 aligned residues, identity 30.9%, target coverage 72.0%

