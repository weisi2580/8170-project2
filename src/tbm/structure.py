"""Sequence/structure I/O and residue mapping onto target numbering."""

from __future__ import annotations

import gzip
import io
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from Bio import BiopythonWarning
from Bio.Align import PairwiseAligner
from Bio.Data.PDBData import protein_letters_3to1_extended
from Bio.PDB import MMCIFParser, PDBIO, PDBParser
from Bio.PDB.Atom import Atom
from Bio.PDB.Chain import Chain
from Bio.PDB.Model import Model
from Bio.PDB.Residue import Residue
from Bio.PDB.Structure import Structure

warnings.simplefilter("ignore", BiopythonWarning)

THREE_TO_ONE = {k.upper(): v for k, v in protein_letters_3to1_extended.items()}
ONE_TO_THREE = {
    "A": "ALA", "R": "ARG", "N": "ASN", "D": "ASP", "C": "CYS", "Q": "GLN", "E": "GLU",
    "G": "GLY", "H": "HIS", "I": "ILE", "L": "LEU", "K": "LYS", "M": "MET", "F": "PHE",
    "P": "PRO", "S": "SER", "T": "THR", "W": "TRP", "Y": "TYR", "V": "VAL",
}
# Modified residues written back as their parent amino acid.
PARENT_RESNAME = {"MSE": "MET"}


# ---------------------------------------------------------------- sequences

def read_fasta(path: Path) -> tuple[str, str]:
    """Return (header, sequence) of the first record."""
    header, seq = None, []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if header is not None:
                break
            header = line[1:].strip()
        else:
            seq.append(line)
    if header is None:
        raise ValueError(f"{path}: not a FASTA file")
    sequence = "".join(seq).upper().replace("*", "")
    if not sequence.isalpha():
        raise ValueError(f"{path}: sequence contains non-letter characters")
    return header, sequence


def write_fasta(path: Path, name: str, seq: str) -> None:
    lines = [f">{name}"] + [seq[i:i + 60] for i in range(0, len(seq), 60)]
    Path(path).write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------- structures

def load_structure(path: Path, name: str = "s") -> Structure:
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    stem = path.name[:-3] if path.suffix == ".gz" else path.name
    with opener(path, "rt") as fh:
        text = fh.read()
    if stem.endswith((".cif", ".mmcif")):
        return MMCIFParser(QUIET=True).get_structure(name, io.StringIO(text))
    return PDBParser(QUIET=True).get_structure(name, io.StringIO(text))


def is_amino_acid(res: Residue) -> bool:
    hetflag = res.id[0]
    resname = res.get_resname().upper()
    if hetflag == "W":
        return False
    if resname not in THREE_TO_ONE:
        return False
    if hetflag.strip() and resname not in PARENT_RESNAME:
        return False
    return "CA" in res


def chain_residues(chain: Chain) -> list[Residue]:
    return [r for r in chain if is_amino_acid(r)]


def residues_sequence(residues: list[Residue]) -> str:
    return "".join(THREE_TO_ONE[r.get_resname().upper()] for r in residues)


def _aligner() -> PairwiseAligner:
    al = PairwiseAligner()
    al.mode = "global"
    al.match_score = 2.0
    al.mismatch_score = -1.0
    al.open_gap_score = -5.0
    al.extend_gap_score = -0.5
    al.end_gap_score = 0.0
    return al


def map_sequence(target_seq: str, observed_seq: str) -> dict[int, int]:
    """Align observed residues to the target; return {observed_index: target_index(1-based)}."""
    aln = _aligner().align(target_seq, observed_seq)[0]
    mapping: dict[int, int] = {}
    for (t0, t1), (o0, o1) in zip(*aln.aligned):
        for k in range(t1 - t0):
            mapping[int(o0 + k)] = int(t0 + k + 1)
    return mapping


@dataclass
class MappedChain:
    chain_id: str
    residues: dict[int, Residue]  # target index -> residue
    identity: float  # identical / mapped
    coverage: float  # mapped / target length


def map_chain(chain: Chain, target_seq: str) -> MappedChain:
    residues = chain_residues(chain)
    obs = residues_sequence(residues)
    mapping = map_sequence(target_seq, obs) if obs else {}
    mapped = {mapping[i]: residues[i] for i in mapping}
    ident = sum(1 for i, t in mapping.items() if obs[i] == target_seq[t - 1])
    return MappedChain(
        chain_id=chain.id,
        residues=mapped,
        identity=ident / len(mapping) if mapping else 0.0,
        coverage=len(mapping) / len(target_seq),
    )


def best_chain(structure: Structure, target_seq: str, chain_id: str = "") -> MappedChain:
    """Map the requested chain, or the chain that best covers the target."""
    model = next(iter(structure))
    if chain_id:
        if chain_id not in model:
            raise ValueError(f"chain {chain_id!r} not in structure (has {[c.id for c in model]})")
        return map_chain(model[chain_id], target_seq)
    candidates = [map_chain(c, target_seq) for c in model if chain_residues(c)]
    if not candidates:
        raise ValueError("structure has no protein chains")
    return max(candidates, key=lambda m: (m.identity * m.coverage, m.coverage))


# ---------------------------------------------------------------- writing

def _clean_atoms(res: Residue) -> list[Atom]:
    """Heavy atoms only, one altloc each, selenomethionine converted to Met."""
    resname = res.get_resname().upper()
    atoms = []
    for a in res.get_atoms():  # selected altloc for disordered atoms
        element = (a.element or a.get_name()[0]).upper()
        if element in ("H", "D"):
            continue
        name = a.get_name()
        if resname == "MSE" and name == "SE":
            name, element = "SD", "S"
        atoms.append(Atom(name, a.coord.copy(), a.bfactor, 1.0, " ",
                          f" {name:<3}" if len(name) < 4 else name, None, element))
    return atoms


def build_structure(residues: list[tuple[int, Residue]], chain_id: str = "A",
                    name: str = "s") -> Structure:
    """New single-chain structure; residues given as (new_number, residue)."""
    st = Structure(name)
    model = Model(0)
    chain = Chain(chain_id)
    st.add(model)
    model.add(chain)
    for num, res in residues:
        resname = PARENT_RESNAME.get(res.get_resname().upper(), res.get_resname().upper())
        new = Residue((" ", int(num), " "), resname, "    ")
        for atom in _clean_atoms(res):
            new.add(atom)
        chain.add(new)
    return st


def write_pdb(structure: Structure, path: Path) -> None:
    io_ = PDBIO()
    io_.set_structure(structure)
    io_.save(str(path))


def write_mapped(mapped: dict[int, Residue], path: Path, keep: tuple[int, int] | None = None,
                 chain_id: str = "A") -> int:
    """Write residues renumbered to target numbering, optionally restricted to a range."""
    items = sorted(mapped.items())
    if keep:
        items = [(i, r) for i, r in items if keep[0] <= i <= keep[1]]
    write_pdb(build_structure(items, chain_id), path)
    return len(items)


# ---------------------------------------------------------------- coordinates

def ca_coords(mapped: dict[int, Residue], indices: list[int]) -> np.ndarray:
    return np.array([mapped[i]["CA"].coord for i in indices], dtype=float)


def heavy_atoms(mapped: dict[int, Residue], indices: list[int]) -> dict[tuple[int, str], np.ndarray]:
    out = {}
    for i in indices:
        for a in _clean_atoms(mapped[i]):
            out[(i, a.get_name())] = a.coord.astype(float)
    return out


def mean_bfactor_ca(mapped: dict[int, Residue], indices: list[int]) -> float:
    vals = [mapped[i]["CA"].bfactor for i in indices if "CA" in mapped[i]]
    return float(np.mean(vals)) if vals else float("nan")
