# Agent 1 decision log: T1123 (FM/TBM)

Decisions made by Claude through tool calls; full reasoning in `agent_transcript.md`.

## Searches

- rcsb, E ≤ 10: 1 hits, 1 excluded by leakage control, 0 eligible
- local, E ≤ 1000: 250 hits, 111 excluded by leakage control, 139 eligible

## Decision: no template

## Decision: no usable template (build_id null)

**Searches**
- RCSB MMseqs2, E ≤ 10: the only hit was the target's own entry, which is excluded. No eligible templates.
- Local high-sensitivity MMseqs2, E ≤ 1000: 139 eligible hits, and I went through all the ranked pages. Every hit looks like noise:
  - Most are antibody Fab heavy chains (2G12, 21H3, b12 and many others), all matching target residues about 16–84. That is roughly 24% coverage at about 33% identity, with E-values of 28–470. The best is 37 (2G12).
  - The rest are short fragments of 19–35 residues with E ≥ 66: cytohesin (211–229), acetylornithine aminotransferase (234–264), silicatein (206–240) and BoNT light chain (92–118).
  - None reaches an E-value anywhere near significance, and none covers most of the evaluation unit (residues 33–258) through a real local alignment.

**Test build (3OAZ:H, the 2G12 Fab heavy chain)**
- MODELLER's align2d spread the target over the whole VH+CH1 chain: 220 residues aligned at **18.6% identity**. That is twilight-zone identity, from an alignment the search itself did not support beyond residues 16–84.
- Nominal coverage of the evaluation unit is 82.7%, with 15 gaps.
- **GA341 = 0.005–0.010** across all 5 models, which signals an unreliable fold.
- **z-DOPE = +1.64 to +1.80**, which is well above the roughly −1 or lower expected for native-like models.
- Together these say the model is almost certainly the wrong fold or a wrong alignment, so I rejected it.

**Alternatives considered:** the other Fab heavy chains are redundant copies of the same weak, spurious match. The fragment hits cover at most 35 evaluation-unit residues with no statistical support, so I did not build them.

**Risk / note:** This target looks like a genuine free-modelling case with no detectable homologue in the PDB before the cutoff. It would need template-free methods. If any model must be submitted anyway, build 3OAZH (lowest-DOPE model T1123.B99990002.pdb) exists. It might score a little above zero if the target happens to be a β-sandwich, but nothing supports its fold, and it should be treated as essentially random.
