# Interpretation (drafted by claude-opus-5-5)

### MODELLER accuracy versus template quality

MODELLER produced scored models for two of the three targets. Neither had a close homologue.

| Target | Template | align2d identity | align2d coverage | TM-score | GDT-TS | lDDT | RMSD (Å) |
|---|---|---|---|---|---|---|---|
| T1124 (TBM-easy) | 5I2H:A | 29.1% | 86.7% | 0.519 | 38.56 | 0.532 | 21.21 |
| T1127 (TBM-hard) | 2FE7:B | 40.1% | 76.8% | 0.658 | 59.34 | 0.488 | 13.45 |

The ranking runs against the difficulty labels. The TBM-hard target T1127 has a higher TM-score and GDT-TS than the TBM-easy target T1124, which fits its higher alignment identity (40.1% vs 29.1%). Coverage, by contrast, does not predict the outcome: T1124 had the larger template coverage but the worse global scores.

The per-residue analyses explain this.

- **T1127: errors are confined to untemplated sequence.**
  - Template-covered residues average 3.27 Å Cα deviation, with 76.8% within 2 Å.
  - The 43 uncovered residues average 24.79 Å, with none within 2 Å. They lie mostly in the ~51–113 insertion relative to the GNAT template.
  - The bimodal GDT curve (60.6% at 2 Å, only 71.2% at 8 Å) shows an accurate core plus a misplaced block.
  - Part of the insertion was template-covered (82–94), but those residues were also badly placed. Agent 1 had counted this partial coverage as an advantage of 2FE7 over 2BEI.
  - A C-terminal segment (194–209, mean 10.65 Å) was misplaced despite template coverage.
- **T1124: the main error lies within template-covered sequence.**
  - Covered residues average 14.9 Å, and only 37.8% are within 2 Å.
  - The N-terminal block 7–135 is displaced as a unit (mean 37.7 Å), yet it keeps moderate local lDDT (e.g. 0.69–0.75 at residues 59–62).
  - This indicates locally reasonable structure placed incorrectly relative to the catalytic domain. The likely cause is that the dimerisation helices were modelled as a single chain.
  - The catalytic domain (~136–362) is mostly within 4 Å. A per-domain score was not computed but would probably be considerably higher than the global 0.519.

Template identity and alignment quality therefore set the accuracy of the core. Untemplated insertions and domain/oligomeric packing, which MODELLER cannot infer from a single-chain template alignment, set the global scores.

The model-quality indicators did not anticipate these failures:

- **z-DOPE:** T1127's selected model had a worse z-DOPE (0.879) than T1124's (−0.052) but scored better against the native.
- **GA341:** T1127's GA341 (0.912) correctly indicated a reliable fold but gave no warning about the insertion.

### Comparison with AlphaFold3

No AlphaFold3 model was available for any target; the AF3 fields in the results are empty. No MODELLER-versus-AF3 comparison can be made, so this report cannot say whether AF3 would have placed the T1124 N-terminal region or the T1127 insertion better.

### Effect of the agent's decisions

For both modelled targets, the agent selected the same template and model scores as the score-only baseline. The baseline values for 5I2H:A and 2FE7:B are identical in every metric. The agent's decisions therefore did not change the outcome relative to the baseline.

The agent's main contributions were documentary:

- Its risk notes anticipated the observed failure regions: the N-terminal dimerisation helices and C-terminal tail of T1124, and the 51–113 insertion of T1127.
- For T1123 it declined to submit a model. Its best test build (3OAZ:H) had 18.6% align2d identity, GA341 0.005–0.010 and z-DOPE +1.64 to +1.80, and the agent judged it an essentially random fold.
- The baseline contains no T1123 entry either, so this decision also cannot be compared against a scored alternative.

### Caveats

- **Sample size:** only three targets were attempted and only two were scored. No general trend between identity, coverage and accuracy can be established.
- **Missing models:** T1123 has no model of any kind, and no target has an AF3 model.
- **Single-chain evaluation:** both models are single chains compared against chain A of the native. Dimer contacts, which probably determine the T1124 N-terminal placement, are not represented.
- **Incomplete native:** for T1127, 7 of the 205 evaluation-unit residues lack native coordinates, so its scores cover 198 residues.
- **Score agreement:** GDT-TS differs from the TMscore program by about 0.2–0.26 points, which is within normal superposition variation. TM-score and RMSD agree.
