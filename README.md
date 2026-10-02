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

### Step 1 — Target sequences (CASP15)

All CASP15 sequences are in one file:
<https://predictioncenter.org/download_area/CASP15/sequences/casp15.seq.txt>

Per-target pages, if you want to look at a sequence in the browser:
<https://predictioncenter.org/casp15/target.cgi?target=T1124&view=sequence> (replace
`T1124` with `T1123` or `T1127`). The full target list is at
<https://predictioncenter.org/casp15/targetlist.cgi>.

To save the three targets as separate FASTA files, run this from the repository root:

```bash
curl -sL https://predictioncenter.org/download_area/CASP15/sequences/casp15.seq.txt -o casp15.seq.txt
for t in T1124 T1123 T1127; do
  awk -v t=">$t" '/^>/{p = ($1 == t)} p' casp15.seq.txt > data/fasta/$t.fasta
done
rm casp15.seq.txt
```

Check the lengths: T1124 should be 384 aa, T1123 266 aa and T1127 211 aa. `tbm agent1`
prints a warning if they differ from `config/targets.toml`.

### Step 2 — Experimental structures (RCSB PDB)

| Target | Entry page | mmCIF download |
|---|---|---|
| T1124 | <https://www.rcsb.org/structure/7UX8> | <https://files.rcsb.org/download/7UX8.cif> |
| T1123 | <https://www.rcsb.org/structure/7UZT> | <https://files.rcsb.org/download/7UZT.cif> |
| T1127 | <https://www.rcsb.org/structure/8XBP> | <https://files.rcsb.org/download/8XBP.cif> |

Save them as `data/native/7ux8.cif`, `7uzt.cif` and `8xbp.cif`. On the entry page you can
also use *Download Files → PDBx/mmCIF Format*, or just run `tbm fetch-native`, which does
the same thing. PDB-format files (`.pdb`) work too.

These files are only used by Agent 2. Agent 1 never reads them.

Optional reference: CASP's own domain-trimmed target structures (the official evaluation
units) are in
<https://predictioncenter.org/download_area/CASP15/targets/casp15.targets.TS-domains.public_12.20.2022.tar.gz>.
The pipeline trims the PDB entry to the same evaluation-unit ranges, so you don't need
this file. It's useful as a cross-check.

### Step 3 — AlphaFold3 predictions (AlphaFold Server)

1. Go to <https://alphafoldserver.com> and sign in with a Google account. The server has a
   daily job quota, and its outputs are for non-commercial use only.
2. Click **Add entity**. Set the type to **Protein** and the copy number to **1**.
3. Paste the sequence from `data/fasta/<target>.fasta`. Paste only the sequence line, not
   the `>` header, and use the full sequence, not just the evaluation unit.
4. Don't add ligands, ions or other chains, and keep all settings at their defaults
   (seed: auto). The plan calls for a default single-chain prediction.
5. Click **Continue and preview job**. Name the job after the target (e.g. `T1124`) so
   the output files are easy to recognise, then click **Confirm and submit job**.
6. When the job shows as finished in the job history, open it and click **Download**.
   You'll get a zip file such as `fold_t1124.zip`. It contains five models
   (`fold_t1124_model_0.cif` … `_model_4.cif`), `summary_confidences_*.json`,
   `full_data_*.json` and the job request.
7. Put the zip (unzipped or not) into the target's folder: `data/af3/T1124/`,
   `data/af3/T1123/` or `data/af3/T1127/`. Agent 2 extracts it if needed and uses the
   model with the highest `ranking_score` (normally `model_0`). It also records that
   model's pTM and its mean pLDDT over the evaluation unit.

Repeat steps 2–7 for each target. Write down the submission date for the report.

### Step 4 — Check

```bash
tbm status
```

For every target this should report `fasta: ok`, a native file name and `af3: 5 model(s)`.

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
