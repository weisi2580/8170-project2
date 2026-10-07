# Interpretation (drafted by claude-opus-5-5)

**Table 1. MODELLER vs AlphaFold3 on the CASP15 evaluation units (EU).** Identity and coverage are given as search hit / align2d.

| Target (difficulty) | Template | Identity | Coverage | MODELLER TM / GDT-TS / lDDT / RMSD | AlphaFold3 TM / GDT-TS / lDDT / RMSD |
|---|---|---|---|---|---|
| T1124 (TBM-easy) | 5I2H:A | 26.7% / 29.1% | 77.9% / 86.7% | 0.519 / 38.6 / 0.532 / 21.2 Å | 0.940 / 90.8 / 0.870 / 6.6 Å |
| T1151s2 (FM/TBM) | 7F7N:A | 34.0% / 28.8% | 32.8% / 95.7% | 0.162 / 19.0 / 0.244 / 16.4 Å | 0.916 / 92.9 / 0.817 / 1.5 Å |
| T1127 (TBM-hard) | 2FE7:B | 31.3% / 40.1% | 73.9% / 76.8% | 0.658 / 59.3 / 0.488 / 13.5 Å | 0.973 / 95.5 / 0.882 / 0.9 Å |

**MODELLER accuracy versus template quality.** MODELLER's ranking does not follow the CASP difficulty labels. The "hard" target T1127 gave the best model (TM 0.658), and it also had the highest align2d identity (40.1%). On its template-covered residues the GNAT core is placed with a mean Cα deviation of 3.27 Å, against 24.79 Å for the 43 uncovered residues, which form mostly an insertion around residues 51–113. Coverage therefore explains most of the T1127 error.

T1124 shows that coverage alone is not enough. About 87.6% of its EU is template-aligned, yet the TM-score is only 0.519. Agent 2 traced this to residues 7–135, which are misplaced as a block (mean 37.7 Å) even where they are aligned. Their local lDDT stays moderate, so this is a domain-placement error, not a failed local fold. One untested explanation is the template's dimer context at ~29% identity.

T1151s2 is the clearest failure (TM 0.162). The nominal align2d coverage (95.7%) is the highest of the three targets. However, it comes from extending a marginal hit (E = 3.9) that originally covered only residues 42–79. The template-covered residues deviate by 27.6 Å on average. Alignment coverage is therefore only meaningful when the underlying homology is real.

MODELLER's own scores flagged this model as unreliable (GA341 ≈ 0.01, z-DOPE 1.91). For T1124, a good z-DOPE (−0.052) did not detect the misplaced domain.

**Comparison with AlphaFold3.** AlphaFold3 is better on every target and metric, with TM 0.916–0.973 and GDT-TS 90.8–95.5. Its remaining errors are confined to termini. On T1124, the probable linker/tag tail (369–384) accounts for most of its 6.59 Å RMSD. It also models correctly the regions where MODELLER had no usable template:
- the T1127 insertion (0.81 Å mean on uncovered residues);
- the whole T1151s2 domain.

**Effect of the agent's decisions.** For T1124 and T1127, the agent selected the same templates as the score-only baseline, so the MODELLER scores are identical. The agent's comparison of alternative builds (2R3S/4A6D for T1124, 2BEI for T1127) did not change the outcome.

The only difference is T1151s2. Here the baseline produced no MODELLER model, since the default RCSB search found no eligible template. The agent widened the search and built from 7F7N:A. This turned a missing model into a modelled one, but the result has essentially no structural value (GDT-TS 19.0). The agent did label it low-confidence. On these three targets, the agent's added value was transparency about risk rather than better accuracy.

**Caveats.**
- **Sample size:** there are only three targets, each with a single MODELLER and a single AlphaFold3 model. No general trend between identity, coverage and accuracy can be claimed.
- **Missing baseline model:** the baseline has no MODELLER entry for T1151s2, so a like-for-like comparison is impossible there.
- **No-template target:** T1151s2 effectively had no valid template at default settings, so it tests fold assignment rather than template-based modelling.
- **Unscored alternatives:** the rejected alternative builds were not scored against the experimental structure. Whether they would have avoided the T1124 domain misplacement is unknown.
- **Confidence-score mismatch:** AlphaFold3's pTM on T1151s2 (0.64) understates its EU accuracy, possibly because pTM covers a larger chain or complex. This was not confirmed.
- **EU definitions:** scores cover only the CASP EUs. For T1127, 7 EU residues are unobserved in the experimental structure.
