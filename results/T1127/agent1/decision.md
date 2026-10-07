# Agent 1 decision log: T1127 (TBM-hard)

Decisions made by Claude through tool calls; full reasoning in `agent_transcript.md`.

## Searches

- rcsb, E ≤ 10: 32 hits, 13 excluded by leakage control, 19 eligible
- local, E ≤ 10: 42 hits, 16 excluded by leakage control, 26 eligible

## Decision: template 2FE7:B, model T1127.B99990005.pdb

**Decision:** I kept build 2FE7B, model T1127.B99990005.pdb. It has the lowest DOPE in its build, z-DOPE 0.879 and GA341 0.912.

**Template search:** The RCSB search and the more sensitive local MMseqs2 search (both at E-value cutoff 10) returned the same set of hits. All are GNAT-family acetyltransferases: 2FE7 (a probable N-acetyltransferase) and many redundant SSAT1/SSAT2 diamine acetyltransferase entries (2B5G, 2BEI, 2Q4V, 2G3T and others). The local search found nothing new.

**Builds compared:**
- **2FE7:B (2.0 Å, chosen):** align2d identity 40.1% over 162 aligned residues. It covers 76.6% of the EU, including part of the target's insertion (77-79 and 82-94). Best z-DOPE is 0.879.
- **2BEI:B (1.84 Å, SSAT2):** align2d identity 31.0% over 155 aligned residues. It covers 75.1% of the EU and leaves residues 66-110 entirely uncovered. Best z-DOPE is 0.871 (GA341 0.998), which is essentially tied with 2FE7.

**Why 2FE7:** z-DOPE was a tie, so I chose on the other numbers. 2FE7 has clearly higher identity and slightly better EU coverage, including partial coverage of the insertion region. It also had the best E-value of any hit (2.3e-18, against roughly 1e-10 for the SSAT entries). All builds score GA341 0.88 or higher, so the fold looks reliable.

**Risks:**
- About 23% of the EU has no template and was modelled ab initio by MODELLER, so it will probably be inaccurate. The uncovered segments are 51-56, 58-63, 65-76, 80-81 and 95-113, plus single residues 196 and 209-210. Most of this is an insertion relative to the template, around residues 51-113, within the GNAT fold.
- Identity is about 40% in the aligned region. The core GNAT fold should be roughly right, but loops and the register of the insertion region are uncertain.

### Build 2FE7B (selected)

| model | DOPE | z-DOPE | GA341 | molpdf |
|---|---|---|---|---|
| T1127.B99990001.pdb | -18235.6 | 1.28 | 0.999 | 1475.1 |
| T1127.B99990002.pdb | -19424.1 | 0.88 | 0.901 | 1481.7 |
| T1127.B99990003.pdb | -18408.2 | 1.22 | 0.890 | 1500.6 |
| T1127.B99990004.pdb | -19090.2 | 0.99 | 0.876 | 1636.6 |
| T1127.B99990005.pdb (selected) | -19426.5 | 0.88 | 0.912 | 1469.9 |

align2d: 162 aligned residues, identity 40.1%, target coverage 76.8%

### Build 2BEIB

| model | DOPE | z-DOPE | GA341 | molpdf |
|---|---|---|---|---|
| T1127.B99990001.pdb | -19449.4 | 0.87 | 0.998 | 1345.7 |
| T1127.B99990002.pdb | -19136.1 | 0.98 | 0.983 | 1257.5 |
| T1127.B99990003.pdb | -18936.3 | 1.04 | 0.997 | 1231.2 |
| T1127.B99990004.pdb | -18977.1 | 1.03 | 0.994 | 1019.3 |
| T1127.B99990005.pdb | -18469.3 | 1.20 | 0.998 | 1247.5 |

align2d: 155 aligned residues, identity 31.0%, target coverage 73.5%

