# Results: score-only baseline (no agent)

Scores over the CASP evaluation unit; TM-score/GDT-TS/lDDT higher is better, RMSD (CA, all common residues) lower is better.

| Target | Difficulty | Method | TM | GDT-TS | lDDT | RMSD (Å) |
|---|---|---|---|---|---|---|
| T1124 | TBM-easy | MODELLER | 0.537 | 41.3 | 0.542 | 21.29 |
| T1124 | TBM-easy | AlphaFold3 | 0.940 | 90.8 | 0.870 | 6.59 |
| T1127 | TBM-hard | MODELLER | 0.722 | 65.5 | 0.529 | 11.47 |
| T1127 | TBM-hard | AlphaFold3 | 0.973 | 95.5 | 0.882 | 0.92 |
| T1151s2 | FM/TBM | MODELLER | 0.524 | 52.7 | 0.407 | 17.33 |
| T1151s2 | FM/TBM | AlphaFold3 | 0.916 | 92.9 | 0.817 | 1.53 |

## Template signal (MODELLER)

| Target | Template | Identity | Coverage | alignment identity | alignment coverage | DOPE |
|---|---|---|---|---|---|---|
| T1124 | 5I2H:A | 0.281 | 0.833 | 0.266 | 0.812 | -38023.4 |
| T1127 | 2FE7:B | 0.396 | 0.479 | 0.358 | 0.754 | -18349.4 |
| T1151s2 | 7KUG:A | 0.356 | 0.509 | 0.382 | 0.474 | -5933.2 |
