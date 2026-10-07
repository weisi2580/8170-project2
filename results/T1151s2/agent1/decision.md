# Agent 1 decision log: T1151s2 (FM/TBM)

Decisions made by Claude through tool calls; full reasoning in `agent_transcript.md`.

## Searches

- rcsb, E ≤ 10: 1 hits, 1 excluded by leakage control, 0 eligible
- local, E ≤ 1000: 73 hits, 51 excluded by leakage control, 22 eligible

## Decision: template 7F7N:A, model T1151s2.B99990003.pdb

**Decision:** I kept the build from 7F7N chain A (an NMR structure of the transcriptional regulator WhiB4) and the model with the lowest DOPE, T1151s2.B99990003.pdb. This is a low-confidence model.

**How I chose the template:**
- The default RCSB search found no eligible templates. Its only hit was the target's own structure, which is excluded.
- I then ran the local MMseqs2 search with E-value up to 1000. It returned 22 eligible chains.
- Almost all of them are short matches with E-values of 150 to 930: an AiiA-like protein, the polyketide synthase PikAII, an antibody heavy chain, elongation factor 2, and nuclear pore proteins. I treated these as chance matches. Each covers only 15–37% of the target, and they would not give a coherent fold for the EU (residues 28–111).
- 7F7N:A had by far the best E-value (3.9) and covers target residues 42–79 in the search alignment. The target also looks like a WhiB-family protein: it has four cysteines (C34, C53, C56, C62) spaced like the WhiB iron-sulfur cluster motif, and a GLWAGV stretch (residues 74–79) resembling the family's conserved G-V/L-W-G-G motif. That family evidence is my own reading of the sequence; the tools did not report it.

**Build numbers:** The align2d alignment covers 111 of 116 residues at 28.8% identity. It covers 95.2% of the EU; only residues 80–83 have no template. Best z-DOPE was 1.91, and GA341 was about 0.01 in all five models.

**Risks:**
- The fold assignment rests on a marginal E-value plus the family motifs.
- Identity is low and the template is an NMR structure. The weak z-DOPE and GA341 scores say the model is not reliable in detail, so errors in alignment register and loop placement are likely.
- No other WhiB structure turned up in the eligible search results to cross-check against.
- The four-residue gap at 80–83, inside the EU, was modelled without a template.

### Build 7F7NA (selected)

| model | DOPE | z-DOPE | GA341 | molpdf |
|---|---|---|---|---|
| T1151s2.B99990001.pdb | -5870.4 | 2.08 | 0.014 | 718.9 |
| T1151s2.B99990002.pdb | -5987.0 | 2.01 | 0.012 | 692.4 |
| T1151s2.B99990003.pdb (selected) | -6160.1 | 1.91 | 0.015 | 722.9 |
| T1151s2.B99990004.pdb | -5874.3 | 2.08 | 0.006 | 713.8 |
| T1151s2.B99990005.pdb | -5958.7 | 2.03 | 0.014 | 709.2 |

align2d: 111 aligned residues, identity 28.8%, target coverage 95.7%

