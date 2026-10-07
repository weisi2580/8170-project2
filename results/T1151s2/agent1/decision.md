# Agent 1 decision log: T1151s2 (FM/TBM)

Decisions made by Claude through tool calls; full reasoning in `agent_transcript.md`.

## Searches

- jackhmmer, 3 round(s) (3 run, converged), inclusion E ≤ 0.001, report E ≤ 1: 8 hits, 0 excluded by leakage control, 8 eligible
- jackhmmer, 5 round(s) (3 run, converged), inclusion E ≤ 0.01, report E ≤ 1: 8 hits, 0 excluded by leakage control, 8 eligible

## Decision: template 7KUG:A, model T1151s2.B99990003.pdb

**Decision:** I kept build 7KUGA, model 3 (lowest DOPE). The template is WhiB7, chain 7KUG:A (X-ray, 1.55 Å).

**Search:** The target belongs to the WhiB family (Fe-S transcription regulators). The default search (3 rounds) and a looser one (5 rounds requested, inclusion E 0.01; it converged after 3) found the same 8 hits, all WhiB proteins: WhiB7 (7KUG, 7KUF, 7KIF, 7KIM), WhiB1 (6ONO, 6ONU, 5OAY) and WhiB4 (7F7N).

**Builds compared:**
- **7KUG:A (chosen):** 55 residues aligned, 38% identity, covers target 30-84 (65.5% of the EU). z-DOPE is 2.05–2.12 and GA341 is 0.21–0.69. The chosen model scores z-DOPE 2.045 and GA341 0.60.
- **6ONO:C (WhiB1):** same coverage, 30-84. Identity is lower (29%). z-DOPE is better (best 1.58) but GA341 is poor (0.13–0.22).
- **7F7N:A (WhiB4, NMR):** covers 7-83 (66.7% of the EU), 29% identity. It is the worst on both measures: z-DOPE 2.62–2.79, GA341 at most 0.02.

I picked 7KUG over 6ONO because the gap in identity (38% vs 29%) and the better GA341 should matter more than the z-DOPE difference (2.05 vs 1.58). This was a close call. In the looser search, 6ONO's alignment reached a little further (27-87). I tried to rebuild it from that alignment, but the tool refused because build 6ONOC already existed.

**Risks:**
- No template covers EU residues 85-111, about a third of the EU, so that tail is modeled without a template and is likely wrong.
- EU residues 28-29 are also not covered.
- Identity in the covered region is only 38%.
- z-DOPE above 2 points to a mediocre model overall.

The core WhiB fold (the four-cysteine Fe-S cluster region at residues 30-84) should be roughly right.

### Build 7KUGA (selected)

| model | DOPE | z-DOPE | GA341 | molpdf |
|---|---|---|---|---|
| T1151s2.B99990001.pdb | -5876.3 | 2.08 | 0.685 | 544.6 |
| T1151s2.B99990002.pdb | -5828.8 | 2.11 | 0.666 | 536.7 |
| T1151s2.B99990003.pdb (selected) | -5933.2 | 2.04 | 0.597 | 567.6 |
| T1151s2.B99990004.pdb | -5841.6 | 2.10 | 0.209 | 566.5 |
| T1151s2.B99990005.pdb | -5817.2 | 2.12 | 0.492 | 606.1 |

alignment: 55 aligned residues, identity 38.2%, target coverage 47.4%

### Build 6ONOC

| model | DOPE | z-DOPE | GA341 | molpdf |
|---|---|---|---|---|
| T1151s2.B99990001.pdb | -6088.2 | 1.95 | 0.176 | 583.3 |
| T1151s2.B99990002.pdb | -6297.2 | 1.82 | 0.131 | 573.7 |
| T1151s2.B99990003.pdb | -6473.3 | 1.72 | 0.222 | 486.9 |
| T1151s2.B99990004.pdb | -6700.1 | 1.58 | 0.180 | 488.6 |
| T1151s2.B99990005.pdb | -5885.9 | 2.07 | 0.147 | 581.9 |

alignment: 55 aligned residues, identity 29.1%, target coverage 47.4%

### Build 7F7NA

| model | DOPE | z-DOPE | GA341 | molpdf |
|---|---|---|---|---|
| T1151s2.B99990001.pdb | -4852.0 | 2.70 | 0.004 | 709.8 |
| T1151s2.B99990002.pdb | -4710.8 | 2.79 | 0.013 | 696.6 |
| T1151s2.B99990003.pdb | -4984.6 | 2.62 | 0.019 | 621.7 |
| T1151s2.B99990004.pdb | -4954.9 | 2.64 | 0.004 | 707.9 |
| T1151s2.B99990005.pdb | -4898.3 | 2.68 | 0.007 | 721.6 |

alignment: 76 aligned residues, identity 28.9%, target coverage 65.5%

