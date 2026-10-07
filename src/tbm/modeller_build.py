"""MODELLER alignment (align2d) and model building (automodel) for Agent 1."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

from .structure import build_structure, chain_residues, load_structure, write_pdb


def require_modeller():
    try:
        import modeller  # noqa: F401
    except ImportError as e:
        raise SystemExit(
            "MODELLER is not importable. Install it with "
            "`conda install -c salilab modeller` and set your license key "
            "(see environment.yml)."
        ) from e


@contextlib.contextmanager
def _chdir(path: Path):
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def prepare_template(cif: Path, chain: str, workdir: Path, code: str) -> Path:
    """Write the template chain as a clean PDB (protein heavy atoms, residues renumbered 1..n)."""
    st = load_structure(cif, code)
    model = next(iter(st))
    residues = chain_residues(model[chain])
    out = workdir / f"{code}.pdb"
    write_pdb(build_structure([(i + 1, r) for i, r in enumerate(residues)], "A", code), out)
    return out


def write_pir(path: Path, code: str, seq: str) -> None:
    body = "\n".join(seq[i:i + 75] for i in range(0, len(seq), 75))
    path.write_text(f">P1;{code}\nsequence:{code}:::::::0.00: 0.00\n{body}*\n")


def read_pir(path: Path) -> dict[str, str]:
    """Return {code: aligned sequence} from a PIR alignment file."""
    seqs: dict[str, str] = {}
    code, lines = None, path.read_text().splitlines()
    i = 0
    while i < len(lines):
        if lines[i].startswith(">P1;"):
            code = lines[i][4:].strip()
            i += 2  # skip description line
            buf = []
            while i < len(lines) and not lines[i].startswith(">P1;"):
                buf.append(lines[i].strip())
                i += 1
            seqs[code] = "".join(buf).rstrip("*")
        else:
            i += 1
    return seqs


def alignment_stats(target_aln: str, template_aln: str) -> dict:
    pairs = [(a, b) for a, b in zip(target_aln, template_aln) if a != "-" and b != "-"]
    n_target = sum(1 for a in target_aln if a != "-")
    ident = sum(1 for a, b in pairs if a == b)
    return {
        "aligned_residues": len(pairs),
        "identity": ident / len(pairs) if pairs else 0.0,
        "coverage": len(pairs) / n_target if n_target else 0.0,
    }


def build_models(target_id: str, target_seq: str, template_pdb: Path, template_code: str,
                 workdir: Path, n_models: int = 5, max_gap_length: int = 50) -> dict:
    """align2d + automodel; returns per-model DOPE/GA341 and the lowest-DOPE model."""
    require_modeller()
    from modeller import Alignment, Environ, Model, log
    from modeller.automodel import AutoModel, assess

    workdir = Path(workdir).resolve()
    write_pir(workdir / f"{target_id}.ali", target_id, target_seq)

    with _chdir(workdir):
        log.minimal()
        env = Environ(rand_seed=-8170)
        env.io.atom_files_directory = [str(workdir)]
        env.io.hetatm = False

        aln = Alignment(env)
        mdl = Model(env, file=template_pdb.name, model_segment=("FIRST:A", "LAST:A"))
        aln.append_model(mdl, align_codes=template_code, atom_files=template_pdb.name)
        aln.append(file=f"{target_id}.ali", align_codes=target_id)
        aln.align2d(max_gap_length=max_gap_length)
        aln.write(file="alignment.ali", alignment_format="PIR")
        aln.write(file="alignment.pap", alignment_format="PAP")

        a = AutoModel(env, alnfile="alignment.ali", knowns=template_code, sequence=target_id,
                      assess_methods=(assess.DOPE, assess.normalized_dope, assess.GA341))
        a.starting_model = 1
        a.ending_model = n_models
        a.make()

        models = []
        for out in a.outputs:
            if out["failure"] is not None:
                models.append({"name": out["name"], "failure": str(out["failure"])})
                continue
            ga341 = out.get("GA341 score")
            models.append({
                "name": out["name"],
                "molpdf": out["molpdf"],
                "dope": out["DOPE score"],
                "ga341": ga341[0] if isinstance(ga341, (list, tuple)) else ga341,
                "zdope": out.get("Normalized DOPE score"),
            })

    ok = [m for m in models if "dope" in m]
    if not ok:
        raise RuntimeError("MODELLER produced no models; see the log in " + str(workdir))
    best = min(ok, key=lambda m: m["dope"])
    aln = read_pir(workdir / "alignment.ali")
    return {
        "models": models,
        "best": best,
        "alignment": alignment_stats(aln[target_id], aln[template_code]),
        "alignment_file": str(workdir / "alignment.ali"),
    }


def covered_residues(alignment: Path, target_id: str) -> list[int]:
    """Target residues (1-based) aligned to a template residue in a PIR alignment."""
    seqs = read_pir(Path(alignment))
    tgt = seqs.pop(target_id)
    tpl = next(iter(seqs.values()))
    covered, idx = [], 0
    for a, b in zip(tgt, tpl):
        if a != "-":
            idx += 1
            if b != "-":
                covered.append(idx)
    return covered


def spans(indices: list[int]) -> list[tuple[int, int]]:
    """[1,2,3,7,8] -> [(1,3), (7,8)]"""
    out: list[tuple[int, int]] = []
    for i in indices:
        if out and i == out[-1][1] + 1:
            out[-1] = (out[-1][0], i)
        else:
            out.append((i, i))
    return out
