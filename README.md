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
target FASTA ─┬─ Agent 1 (Claude + tools): search → leakage filter → rank → align2d/automodel
              │                            (one or more templates) → choose final model ──────┐
              └─ AlphaFold3 Server (default settings, run manually) ──────────────────────────┤
                                                                                              ▼
                  Agent 2 (Claude + tools): map to target numbering, trim to EU, compare with the
                  experimental structure → TM-score, GDT-TS, lDDT, RMSD, per-residue error analysis
                                                                                              ▼
                  tbm report: tables, figures, agent-vs-baseline comparison, Claude's interpretation
```

Both agents are Claude (`claude-opus-5-5`) running a tool-use loop: Claude decides what to do
next and why, the tools do the computation and enforce the hard rules. Every step is saved
in `agent_transcript.md`. A score-only **baseline** without Claude (`tbm --baseline …`) runs
the same tools with fixed rules and serves as the control.

**Agent 1 — template-based model building** (`tbm agent1`)

Tools Claude can call:

| Tool | What it does |
|---|---|
| `search_templates(backend, evalue_cutoff)` | Search the PDB with the target sequence: `rcsb` (RCSB sequence search, MMseqs2 at fixed sensitivity) or `local` (MMseqs2 at `-s 7.5` against all PDB chains; downloads `pdb_seqres.txt` once). Applies leakage control and ranks the eligible hits. |
| `show_candidates(search_id, offset)` | Page through further ranked candidates. |
| `build_model(search_id, entry_id, chain, n_models)` | MODELLER `align2d` + `automodel` on one template chain; returns align2d identity/coverage, which EU residues the template covers, and DOPE, normalized DOPE (z-DOPE), GA341, molpdf per model. At most 4 builds per target. |
| `finalize(build_id, model_name, rationale)` | Keep one model (or none, if no usable template exists) and record the rationale. |

Rules enforced by code, not by Claude:

- **Leakage control**: the target's own PDB entry and every entry released after
  `template_release_cutoff` (default 2022-05-01, the start of the CASP15 season) are
  excluded; `build_model` refuses them. Excluded hits stay in `candidates_*.csv` with the reason.
- **Ranking signals** shown to Claude: weighted score of sequence identity, target coverage,
  E-value, resolution and completeness (fraction of aligned template residues with
  coordinates, measured for the top candidates). Weights live in `config/targets.toml`.
- **No ground truth**: Agent 1's tools never read the experimental structure, and the PDB
  ID of the target is not given to Claude.

The baseline does: one RCSB search (E ≤ 10) → top-scoring template → 5 models → lowest DOPE.

**Agent 2 — evaluation** (`tbm agent2`)

Tools: `evaluate_models` (scores below, plus figures), `per_residue_errors` (CA deviation
and lDDT per residue, split into template-covered vs uncovered residues, error segments),
`get_agent1_decision`, `finish` (writes `analysis.md`).

Each structure (experimental, MODELLER, AF3) is mapped onto target-sequence numbering by
sequence alignment, trimmed to the evaluation unit, and compared with a fixed residue
correspondence:

- **TM-score** and **GDT-TS**: TM-score-program style search over superpositions,
  normalised by the number of experimental residues in the EU.
- **lDDT**: all heavy atoms, 15 Å radius, thresholds 0.5/1/2/4 Å (superposition-free;
  no stereochemistry penalties; symmetric side-chain atoms are not swapped).
- **RMSD**: CA atoms, all common residues, optimal superposition.

If the `TMscore` binary is on `PATH` its numbers are stored next to ours as a cross-check.

`tbm report` collects everything into `results/summary.{csv,md}`,
`results/summary_metrics.png` and Claude's draft `results/interpretation.md`.

## Current results (2026-10-06, MODELLER only; AF3 pending)

| Target | Agent 1 decision | TM | GDT-TS | lDDT | Baseline |
|---|---|---|---|---|---|
| T1124 (TBM-easy) | built 2R3S:A, 5I2H:A, 4A6D:A → kept 5I2H:A | 0.519 | 38.6 | 0.532 | same template, same scores |
| T1127 (TBM-hard) | built 2FE7:B, 2BEI:B → kept 2FE7:B | 0.658 | 59.3 | 0.488 | same template, same scores |
| T1123 (FM/TBM) | no usable template ([why](#why-t1123-has-no-modeller-model)) | – | – | – | no eligible hit |

Details: `results/summary.md`, `results/interpretation.md`, and each target's
`agent1/decision.md` and `agent2/analysis.md`.

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

### Claude agents

Agents 1 and 2 are run by Claude (`claude-opus-5-5`) through tool use. The tools do the
computation (search, MODELLER, metrics) and enforce the hard rules (leakage control; Agent 1
never sees the experimental structure); Claude decides what to run and why:

- **Agent 1** chooses search settings (RCSB or sensitive local MMseqs2, E-value), reads the
  candidates, builds models from one or more templates (up to 4), compares them by EU
  coverage, align2d identity and normalized DOPE, and picks the final model.
- **Agent 2** computes the scores, examines per-residue errors (template-covered vs not),
  checks consistency against the TMscore program, and writes `analysis.md`.
- `tbm report` has Claude draft `results/interpretation.md`.

Every step (Claude's reasoning summary, each tool call and result) is saved to
`agent_transcript.md` / `.jsonl` next to the outputs.

Setup: create a key at <https://platform.claude.com/settings/keys> (API credit is billed to
the Console organisation; a claude.ai subscription doesn't cover API calls) and add
`export ANTHROPIC_API_KEY=…` to `~/.zshrc`. A user key (`sk-ant-usr-…`) isn't tied to a
workspace, so also add `export ANTHROPIC_WORKSPACE_ID=wrkspc_…` (the workspace ID from
Console → Settings → Workspaces). Never commit either. Without a key the agent commands
stop with an error.

**Baseline without an agent** (`tbm --baseline …`, results in `results/baseline/`): one
RCSB search with the configured settings, the top-scoring template by the fixed weights,
the lowest-DOPE model, the same metrics. It is the control for "does the agent's judgement
help?", and `results/summary.md` compares the two when both exist.

## Inputs

You download three kinds of files by hand and put them in fixed folders in this
repository. The pipeline finds them by path, so the names and folders matter.

| What | Where it comes from | Put it here (exact path) |
|---|---|---|
| T1124 sequence | CASP15 target page | `data/fasta/T1124.fasta` |
| T1123 sequence | CASP15 target page | `data/fasta/T1123.fasta` |
| T1127 sequence | CASP15 target page | `data/fasta/T1127.fasta` |
| T1124 experimental structure | RCSB PDB 7UX8 | `data/native/7ux8.cif` |
| T1123 experimental structure | RCSB PDB 7UZT | `data/native/7uzt.cif` |
| T1127 experimental structure | RCSB PDB 8XBP | `data/native/8xbp.cif` |
| T1124 AlphaFold3 result | AlphaFold Server download | `data/af3/T1124/` (the zip or its unzipped files) |
| T1123 AlphaFold3 result | AlphaFold Server download | `data/af3/T1123/` |
| T1127 AlphaFold3 result | AlphaFold Server download | `data/af3/T1127/` |

The `data/af3/T1124/` etc. folders don't exist yet; create them when you add the files.

### Step 1 — Target sequences (CASP15 website)

1. Open the target's sequence page:
   - T1124: <https://predictioncenter.org/casp15/target.cgi?target=T1124&view=sequence>
   - T1123: <https://predictioncenter.org/casp15/target.cgi?target=T1123&view=sequence>
   - T1127: <https://predictioncenter.org/casp15/target.cgi?target=T1127&view=sequence>

   (The full target list is at <https://predictioncenter.org/casp15/targetlist.cgi>.)
2. Copy the header line (starting with `>T1124`) and the sequence line beneath it into a
   plain-text file. Save it as `data/fasta/T1124.fasta` (and likewise for the other two).
   Use a plain-text editor, not Word, so no formatting is added.
3. Check the lengths: T1124 is 384 aa, T1123 266 aa and T1127 211 aa (also stated in the
   header line). `tbm agent1` prints a warning if a length differs from
   `config/targets.toml`.

Optional shortcut: the same sequences are in one CASP file,
<https://predictioncenter.org/download_area/CASP15/sequences/casp15.seq.txt>. This command
splits it into the three FASTA files. On 2026-10-02 its output was identical to the
target pages for all three targets.

```bash
curl -sL https://predictioncenter.org/download_area/CASP15/sequences/casp15.seq.txt -o casp15.seq.txt
for t in T1124 T1123 T1127; do
  awk -v t=">$t" '/^>/{p = ($1 == t)} p' casp15.seq.txt > data/fasta/$t.fasta
done
rm casp15.seq.txt
```

### Step 2 — Experimental structures (RCSB PDB)

| Target | Entry page | Direct mmCIF download | Save as |
|---|---|---|---|
| T1124 | <https://www.rcsb.org/structure/7UX8> | <https://files.rcsb.org/download/7UX8.cif> | `data/native/7ux8.cif` |
| T1123 | <https://www.rcsb.org/structure/7UZT> | <https://files.rcsb.org/download/7UZT.cif> | `data/native/7uzt.cif` |
| T1127 | <https://www.rcsb.org/structure/8XBP> | <https://files.rcsb.org/download/8XBP.cif> | `data/native/8xbp.cif` |

On the entry page, use **Download Files → PDBx/mmCIF Format**. The browser may save the
file as `7UX8.cif`; upper or lower case both work. A PDB-format file (`7ux8.pdb`) also
works. `tbm fetch-native` downloads the same three files automatically.

These files are only used by Agent 2. Agent 1 never reads them.

Optional cross-check: CASP's own domain-trimmed target structures (the official evaluation
units) are in
<https://predictioncenter.org/download_area/CASP15/targets/casp15.targets.TS-domains.public_12.20.2022.tar.gz>.
The pipeline trims the PDB entry to the same evaluation-unit ranges, so this file isn't
needed.

### Step 3 — AlphaFold3 predictions (AlphaFold Server)

> **Note: the steps below may change.** The AlphaFold Server interface, button names,
> quota and download format can change over time. If what you see differs from this
> description, follow the actual interface. What matters is: one protein chain, the full
> target sequence, default settings, and the downloaded result in `data/af3/<target>/`.

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
   You'll get a zip file such as `fold_t1124.zip`. It normally contains five models
   (`fold_t1124_model_0.cif` … `_model_4.cif`), `summary_confidences_*.json`,
   `full_data_*.json` and the job request.
7. Create the folder `data/af3/T1124/` and put the zip in it, either as is or unzipped.
   Do the same for T1123 (`data/af3/T1123/`) and T1127 (`data/af3/T1127/`). Agent 2
   extracts the zip if needed and uses the model with the highest `ranking_score`
   (normally `model_0`). It also records that model's pTM and its mean pLDDT over the
   evaluation unit.

   If the file names differ from the pattern above, the pipeline needs `*model_<n>.cif`
   files (and ideally the matching `*summary_confidences_<n>.json`). Tell whoever
   maintains the code if the format has changed.

Repeat steps 2–7 for each target. Write down the submission date for the report.

### Step 4 — Check

```bash
tbm status
```

For every target this should report `fasta: ok`, a native file name and `af3: 5 model(s)`.

If the experimental entry has several chains, Agent 2 uses the one that best matches the
target sequence; set `chain` in `config/targets.toml` to force one.

### Step 5 — Upload to the GitHub repository

The input files are small and should be committed, so everyone in the group runs on the
same data. Repository: <https://github.com/weisi2580/8170-project2>
(SSH: `git@github.com:weisi2580/8170-project2.git`).

```bash
git pull
git add data/fasta data/native data/af3
git commit -m "Add CASP15 sequences, experimental structures and AF3 predictions"
git push
```

Without the command line, you can also upload on the GitHub website: open the target
folder (e.g. `data/fasta`), click **Add file → Upload files**, and drag the files in.
For the AF3 results, name a local folder `T1124` (containing the zip or its unzipped
files), open `data/af3` on GitHub, and drag the whole folder in. GitHub keeps the
folder structure.

## Running

```bash
conda activate tbm
tbm status                    # what is present / missing
tbm agent1                    # Claude Agent 1, all targets; or e.g. `tbm agent1 T1124`
tbm agent2                    # Claude Agent 2
tbm report                    # tables, figures, Claude's interpretation
tbm run-all                   # agent1 + agent2 + report

tbm --baseline run-all                                   # score-only control, no Claude
tbm --baseline agent1 T1127 --search-only --backend local --evalue 100
tbm --baseline agent1 T1127 --template 1ABC:A           # manual template override
```

(`python -m tbm …` works the same without installing the entry point.)

To render the 3D overlays: `chimerax --offscreen --nogui results/T1124/agent2/T1124_overlay.cxc`
(or open the `.cxc` in ChimeraX). Colors: experimental gray, MODELLER blue, AlphaFold3
orange, template green.

## Outputs

```
results/<target>/agent1/agent_transcript.md  Claude's steps: reasoning, tool calls, results
results/<target>/agent1/candidates_*.csv   every hit per search, signals, score or exclusion
results/<target>/agent1/builds/<id>/       each MODELLER build Claude ran
results/<target>/agent1/decision.{json,md} template choice, rationale, DOPE/GA341 per model
results/<target>/agent1/alignment.ali      align2d target-template alignment (PIR)
results/<target>/agent1/template.pdb       template chain used
results/<target>/agent1/final_model.pdb    the model Claude kept
results/<target>/agent2/metrics.json       scores + per-residue CA deviation and lDDT
results/<target>/agent2/analysis.md        Claude's analysis (+ agent_transcript.md)
results/<target>/agent2/*_eu.pdb           EU-trimmed structures in target numbering
results/<target>/agent2/<target>_per_residue.png
results/<target>/agent2/<target>_overlay.cxc
results/summary.{csv,md}, results/summary_metrics.png, results/interpretation.md
results/baseline/…                         same layout, score-only run
```

## Notes on weak templates

### Why T1123 has no MODELLER model

MODELLER only builds from a template it is given; for T1123 the template search found none,
so no model was built. This is a property of the PDB, not a failure of MODELLER:

- **RCSB search (E ≤ 10)** returns a single hit, 7UZT itself (the target's own experimental
  structure, capsid polyprotein VP90), which leakage control removes. The baseline stops here.
- **Local MMseqs2 at maximum sensitivity (E ≤ 1000, run by the agent)** searches the whole
  current PDB: 250 hits. The only real homologue is again 7UZT (100% identity,
  E = 5e-179). All other hits, the 110 excluded by the date cutoff as well as the 139
  eligible ones, are antibody Fab heavy chains (~33% identity over ~24% of the sequence,
  residues ~16–84) and short fragments, with E-values from 12 to several hundred, i.e.
  chance matches (a credible hit needs E ≲ 1e-3). So the cutoff did not hide a usable
  template: even without it, the PDB has no sequence-detectable homologue of T1123.
- **Test build on the best eligible hit** (3OAZ:H, Fab 2G12): align2d identity 18.6%,
  GA341 0.005–0.010 (≈1 means a reliable fold), z-DOPE ≈ +1.7. The agent rejected it and
  finalized with no template; the build is kept in `results/T1123/agent1/builds/3OAZH/`.

Caveat: "no template" here means none detectable by single-sequence search. CASP classed
T1123 as FM/TBM, so structurally similar but highly divergent proteins may exist; finding
them would need profile-based remote-homology search (HHblits/HHpred), which this pipeline
does not use. For the report: template-based modeling could not be applied to T1123 with
sequence search against the pre-CASP15 PDB, which is exactly the case where a
template-free method such as AlphaFold3 is needed.

For T1124 the date cutoff matters: 7UX6 and 7UX7 are 100%-identical structures of the
same protein released after the CASP15 season, and would otherwise be selected.
