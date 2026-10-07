# Agent 2 analysis: T1127 (TBM-hard)

Written by Claude from the tool outputs; full trace in `agent_transcript.md`.

# T1127 (CASP15 TBM-hard), EU residues 6–210: MODELLER evaluation

The model gets the GNAT acetyltransferase core about right (TM-score 0.658). Almost all of its error comes from the ~51–113 insertion that the template doesn't cover, plus the C-terminal segment 194–209. No AlphaFold3 model was available, so this covers MODELLER only.

## Setup
- **Native structure:** 8xbp chain A, 100% sequence identity to the target. 198 of the 205 EU residues have coordinates, so 7 are missing.
- **Template (Agent 1):** 2FE7 chain B, a probable N-acetyltransferase (GNAT family, X-ray, 2.0 Å).
  - Search identity 31.3%, E-value 2.3e-18.
  - align2d identity 40.1% over 162 aligned residues, covering 76.6% of the EU.
  - Agent 1 chose 2FE7 over 2BEI (SSAT2) because z-DOPE was tied (0.879 vs 0.871) and 2FE7 had higher identity and better coverage.
- **Chosen model:** T1127.B99990005, z-DOPE 0.879, GA341 0.912.

## Overall scores (MODELLER, EU)
| Metric | Value |
|---|---|
| TM-score | 0.658 (TMscore program: 0.6582) |
| GDT-TS | 59.34 (TMscore program: 59.6) |
| GDT at 1 / 2 / 4 / 8 Å | 41.4 / 60.6 / 64.1 / 71.2 % |
| lDDT (all-atom) / lDDT-Cα | 0.488 / 0.582 |
| Cα RMSD | 13.45 Å (TMscore program: 13.452) |
| Residues compared | 198 of 198 native EU residues |

**Consistency checks:**
- Our TM-score and RMSD match the TMscore program.
- GDT-TS differs by about 0.26 points, which is within normal variation in superposition search.
- All 198 native EU residues were compared, so the scores aren't inflated by dropping any.
- The GDT curve is bimodal: it rises steeply up to 2 Å (60.6%) and then barely grows (71.2% at 8 Å). So most residues are close to the native structure and a sizeable block is far away. That block is what drives the 13.45 Å RMSD; it doesn't reflect a uniformly mediocre model.

## Where the errors are
| Residue set | n | Mean Cα deviation | Fraction within 2 Å | Mean lDDT |
|---|---|---|---|---|
| Template-covered | 155 | 3.27 Å | 76.8% | 0.592 |
| Not covered by template | 43 | 24.79 Å | 0% | 0.213 |

The 155 covered residues are consistent with Agent 1's 162 aligned residues once you account for the EU boundaries and the residues missing from the native structure.

Segments with Cα deviation above 4 Å:
- **51–72** (22 residues, mean 24.5 Å): almost entirely uncovered, apart from 57 and 64. Residues 66–70 are the worst in the model, at 38.5–46.0 Å.
- **79–113** (35 residues, mean 21.3 Å): a mix of uncovered stretches (80–81 and 95–113, with 103–107 at 37–44.6 Å) and stretches that 2FE7 does cover (79 and 82–94). So the partial template coverage of the insertion that Agent 1 counted as an advantage over 2BEI didn't help: those residues are also badly placed. Either the alignment register in the insertion is wrong, or the template's local structure there differs from the target's.
- **194–209** (16 residues, mean 10.65 Å): C-terminal region. Most of it is template-covered; only 196 and 209 are not. This is the main error inside covered sequence. A different C-terminal strand arrangement between target and template seems a likely cause (this is common in GNAT dimers), but I haven't checked that against the structure.

Everything outside these three segments is accurate: about 60% of all residues are within 2 Å.

## Relation to Agent 1's decisions
- The GNAT fold assignment was correct, and the core built from the template is accurate.
- Agent 1 flagged the 51–113 insertion as likely to be inaccurate, and it was. MODELLER's ab initio loop building put these residues 20–46 Å from their native positions. This alone explains the low lDDT and high RMSD.
- The fold-level scores (z-DOPE, GA341 0.912) correctly said the fold was reliable. They gave no warning about how badly the insertion or the C-terminal segment would come out.

## Caveats
- **No AlphaFold3 comparison**, because no AF3 model was available.
- **Mean Cα B-factor of 124.7:** evaluate_models reports this without saying what the B-factor column holds in this model file, so I haven't interpreted it.
- **Missing native residues:** 7 EU residues have no native coordinates, so the coverage split covers 198 residues, not 205. For the same reason, Agent 1's uncovered segments (for example 65–76 and 210) differ slightly from the ones evaluated here (65–72 and 209).
- **lDDT** is computed on this single chain, so contacts at the dimer interface aren't included.
