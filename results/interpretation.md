# Interpretation (drafted by claude-opus-5-5)

### MODELLER accuracy versus template identity, coverage and alignment

MODELLER's accuracy did not follow the CASP difficulty labels. The TBM-hard target T1127 gave the best MODELLER model (TM-score 0.722, GDT-TS 65.5, lDDT 0.529). The TBM-easy target T1124 (TM 0.537, GDT-TS 41.3) and the FM/TBM target T1151s2 (TM 0.524, GDT-TS 52.7) were both worse.

T1127 combined the highest alignment identity among the well-covered targets (35.8%) with good alignment coverage (75.4%). Its template-covered residues sit at a mean CA deviation of 1.88 Å, with 80.3% of them within 2 Å. Almost all the error is in the roughly 40-residue insertion (around 60–104) that no template covered. Those 41 uncovered residues average 22.32 Å.

T1151s2 had the highest alignment identity (38.2%) but the lowest coverage: 47.4% of the target and 65.5% of the evaluation unit (EU). Its covered core is accurate (1.74 Å). The untemplated C-terminal tail (85–111) averages 35.07 Å, which caps the TM-score at about 0.52.

T1124 shows that coverage alone is not enough. Its alignment covers 81.3% of the target, but identity is only 26.6%. The whole N-terminal block (7–135), most of which is template-covered, was placed with a mean CA deviation of 38.0 Å. Local lDDT in that block stayed moderate (0.64–0.71 for 59–66), which means the domain is folded roughly correctly but oriented wrongly. Across the three targets, then, template-covered regions at about 36–38% identity were modelled to within about 2 Å. Untemplated segments and domain arrangement at low identity were where MODELLER failed.

### Comparison with AlphaFold3

AlphaFold3 was far more accurate on every target:

| Target | TM-score | GDT-TS | lDDT |
|---|---|---|---|
| T1124 | 0.940 | 90.8 | 0.870 |
| T1127 | 0.973 | 95.5 | 0.882 |
| T1151s2 | 0.916 | 92.9 | 0.817 |

AlphaFold3 also modelled the regions that MODELLER had no template for. On T1127 the uncovered residues are at 0.89 Å, and on T1151s2 the tail is at 1.48 Å. Its only notable error is the T1124 C-terminal tail (369–384, mean 29.7 Å), which includes scored tag residues. That tail raises its RMSD to 6.59 Å while barely affecting TM-score or GDT.

AlphaFold3's self-assessment was well calibrated on T1127 (ranking score 0.95, mean pLDDT 92.1). On T1151s2 it understated its accuracy: pTM was 0.64 against a measured TM of 0.916.

### Effect of the agent's decisions

The agent run and the score-only baseline gave identical results for all three targets. They chose the same templates (5I2H:A, 2FE7:B, 7KUG:A) and produced the same MODELLER scores and DOPE values. The agent's template and model choices therefore did not change the outcome.

The agent's added value was diagnostic. Before evaluation, it flagged the three failure modes that actually occurred:
- the dimerisation-domain orientation in T1124,
- the uncovered 60–104 insertion in T1127,
- the untemplated 85–111 tail in T1151s2.

The alternatives it judged as close calls (2BEI for T1127, 6ONO for T1151s2) were not built and scored. It is therefore unknown whether a different choice would have helped. Both alternatives leave similar gaps, so a large gain seems unlikely.

### Caveats

- **Sample size.** There are only three targets, so the relationships described above are qualitative, not statistical trends.
- **Missing models and template-free targets.** All three targets were modelled by both methods. No models were missing and every target had templates, so this set does not test the pipeline's behaviour on template-free targets.
- **Single-chain evaluation.** Each target was evaluated as a single chain. Oligomeric context may explain the T1124 domain misplacement and the T1151s2 tail conformation, but this was not verified.
- **Scoring details.**
  - T1127's experimental structure has only 198 of the 205 EU residues.
  - T1124's scores include tag residues 379–384.
  - RMSD is dominated by a few large outliers, so TM-score, GDT-TS and lDDT are the more informative measures here.
- **Possible AlphaFold3 advantage.** Overlap between AlphaFold3's training data and these structures was not checked.
