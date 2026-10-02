# AI-Assisted Template-Based Protein Structure Modeling

CMP_SC 8170 · Project 2 — Parthaw Goswami, Vinaya Santhosh Kumar, Weisi Liu, Arwa Mashaqbeh

How does template-based modeling (MODELLER) perform on easy, intermediate and hard CASP15
targets compared with AlphaFold3? The plan is in
[`Project_2_Plan_Template_Based_Modeling_Final.pdf`](Project_2_Plan_Template_Based_Modeling_Final.pdf).

| Target | Class | Length | PDB | Evaluation unit |
|---|---|---|---|---|
| T1124 | TBM-easy | 384 | 7UX8 | 7–384 |
| T1123 | FM/TBM | 266 | 7UZT | 33–258 |
| T1127 | TBM-hard | 211 | 8XBP | 6–210 |

## Pipeline

```
target FASTA ─┬─ Agent 1: RCSB/MMseqs2 search → leakage filter → rank → align2d → automodel → lowest DOPE ─┐
              └─ AlphaFold3 Server (default settings, run manually) ─────────────────────────────────────┤
                                                                                                         ▼
                             Agent 2: map to target numbering, trim to EU, compare with experimental structure
                                      → TM-score, GDT-TS, lDDT, RMSD, per-residue plots, ChimeraX overlays
```

**Agent 1 — template-based model building** (`tbm agent1`)

1. Search the PDB with the target sequence (RCSB sequence search, which runs MMseqs2;
   or a more sensitive local MMseqs2 search with `--backend local`).
2. Leakage control: drop the target's own PDB entry and every entry released after
   `template_release_cutoff` (default 2022-05-01, the start of the CASP15 season).
   Excluded hits stay in the log with the reason.
3. Rank the remaining hits by a weighted score of sequence identity, target coverage,
   E-value, experimental resolution and completeness (fraction of aligned template residues
   that have coordinates, read from the mmCIF for the top candidates). Weights live in
   `config/targets.toml`.
4. Align target and template with MODELLER `align2d`, build `n_models` models with
   `automodel`, and keep the lowest-DOPE model.
5. Every candidate is written to `candidates.csv`; the choice and its rationale go to
   `decision.json` / `decision.md`.

The experimental structure is never read by Agent 1.

**Agent 2 — evaluation** (`tbm agent2`)

Each structure (experimental, MODELLER, AF3) is mapped onto target-sequence numbering by
sequence alignment, trimmed to the evaluation unit, and compared with a fixed residue
correspondence:

- **TM-score** and **GDT-TS**: TM-score-program style search over superpositions,
  normalised by the number of experimental residues in the EU.
- **lDDT**: all heavy atoms, 15 Å radius, thresholds 0.5/1/2/4 Å (superposition-free;
  no stereochemistry penalties; symmetric side-chain atoms are not swapped).
- **RMSD**: CA atoms, all common residues, optimal superposition.

If the `TMscore` binary is on `PATH` its numbers are stored next to ours as a cross-check.
Outputs: `metrics.json`, EU-trimmed PDBs, a per-residue plot and a ChimeraX script.

`tbm report` collects everything into `results/summary.{csv,md}` and
`results/summary_metrics.png`.

## Setup

MODELLER is distributed through conda and needs a free academic license key
(<https://salilab.org/modeller/registration.html>).

```bash
export KEY_MODELLER=XXXXXXXX
conda env create -f environment.yml
conda activate tbm
pytest            # offline unit tests
```

Without conda, `pip install -e ".[test]"` gives everything except MODELLER (template search,
evaluation and reporting still work).

## Inputs

```
data/fasta/T1124.fasta     # CASP15 target sequences (one record each)
data/fasta/T1123.fasta
data/fasta/T1127.fasta
data/native/7ux8.cif       # experimental structures (.cif or .pdb); or: tbm fetch-native
data/native/7uzt.cif
data/native/8xbp.cif
data/af3/T1124/            # unzipped AlphaFold3 Server download (or drop the .zip here)
data/af3/T1123/
data/af3/T1127/
```

For AlphaFold3 use the full target sequence from the FASTA, one protein chain, default
settings. Agent 2 picks the model with the highest `ranking_score` from the
`summary_confidences_*.json` files.

If the experimental entry has several chains, Agent 2 uses the one that best matches the
target sequence; set `chain` in `config/targets.toml` to force one.

## Running

```bash
tbm status                    # what is present / missing
tbm agent1                    # all targets; or e.g. `tbm agent1 T1124`
tbm agent1 T1127 --search-only --backend local --evalue 100   # explore weak templates
tbm agent1 T1127 --template 1ABC:A                           # override the choice
tbm agent2
tbm report
tbm run-all                   # agent1 + agent2 + report
```

(`python -m tbm …` works the same without installing the entry point.)

To render the 3D overlays: `chimerax --offscreen --nogui results/T1124/agent2/T1124_overlay.cxc`
(or open the `.cxc` in ChimeraX). Colors: experimental gray, MODELLER blue, AlphaFold3
orange, template green.

## Outputs

```
results/<target>/agent1/candidates.csv     every hit, its signals, score or exclusion reason
results/<target>/agent1/decision.{json,md} template choice, rationale, DOPE/GA341 per model
results/<target>/agent1/alignment.ali      align2d target-template alignment (PIR)
results/<target>/agent1/template.pdb       template chain used
results/<target>/agent1/final_model.pdb    lowest-DOPE MODELLER model
results/<target>/agent2/metrics.json       scores + per-residue CA deviation and lDDT
results/<target>/agent2/*_eu.pdb           EU-trimmed structures in target numbering
results/<target>/agent2/<target>_per_residue.png
results/<target>/agent2/<target>_overlay.cxc
results/summary.{csv,md}, results/summary_metrics.png
```

## Notes on weak templates

The RCSB sequence service runs MMseqs2 at fixed sensitivity. In a dry run with the 7UZT
sequence it returned only 7UZT itself, so T1123 (and likely T1127) may have no template at
E ≤ 10. Agent 1 records this as `status: no_template` rather than failing. Options:
`--backend local` (MMseqs2 at `-s 7.5` against all PDB chains; downloads `pdb_seqres.txt`
once), a larger `--evalue`, or a manually chosen template with `--template`; whatever is
used should be reported, since the hard-target result depends on it.

For T1124 the date cutoff matters: 7UX6 and 7UX7 are 100%-identical structures of the
same protein released after the CASP15 season, and would otherwise be selected.
