# Results: Claude agents

Scores over the CASP evaluation unit; TM-score/GDT-TS/lDDT higher is better, RMSD (CA, all common residues) lower is better.

| Target | Difficulty | Method | TM | GDT-TS | lDDT | RMSD (Å) |
|---|---|---|---|---|---|---|
| T1124 | TBM-easy | MODELLER | 0.519 | 38.6 | 0.532 | 21.21 |
| T1124 | TBM-easy | AlphaFold3 | 0.940 | 90.8 | 0.870 | 6.59 |
| T1127 | TBM-hard | MODELLER | 0.658 | 59.3 | 0.488 | 13.45 |
| T1127 | TBM-hard | AlphaFold3 | 0.973 | 95.5 | 0.882 | 0.92 |
| T1151s2 | FM/TBM | MODELLER | 0.162 | 19.0 | 0.244 | 16.44 |
| T1151s2 | FM/TBM | AlphaFold3 | 0.916 | 92.9 | 0.817 | 1.53 |

## Template signal (MODELLER)

| Target | Template | Identity | Coverage | align2d identity | align2d coverage | DOPE |
|---|---|---|---|---|---|---|
| T1124 | 5I2H:A | 0.267 | 0.779 | 0.291 | 0.867 | -39883.2 |
| T1127 | 2FE7:B | 0.313 | 0.739 | 0.401 | 0.768 | -19426.5 |
| T1151s2 | 7F7N:A | 0.340 | 0.328 | 0.288 | 0.957 | -6160.1 |

## MODELLER: Claude agent vs score-only baseline

| Target | Agent template | Agent TM | Baseline template | Baseline TM | Agent GDT-TS | Baseline GDT-TS |
|---|---|---|---|---|---|---|
| T1124 | 5I2H:A | 0.519 | 5I2H:A | 0.519 | 38.6 | 38.6 |
| T1127 | 2FE7:B | 0.658 | 2FE7:B | 0.658 | 59.3 | 59.3 |
