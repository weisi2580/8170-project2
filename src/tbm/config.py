"""Project configuration and file layout."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "targets.toml"
DATA = ROOT / "data"
RESULTS = ROOT / "results"
CACHE = DATA / "cache"


@dataclass
class Target:
    id: str
    difficulty: str
    pdb: str
    length: int
    eu: tuple[int, int]
    chain: str = ""

    @property
    def fasta(self) -> Path:
        return DATA / "fasta" / f"{self.id}.fasta"

    @property
    def af3_dir(self) -> Path:
        return DATA / "af3" / self.id

    @property
    def result_dir(self) -> Path:
        return results_root() / self.id

    def native_path(self) -> Path:
        """Experimental structure; .cif preferred, .pdb accepted."""
        native = DATA / "native"
        for name in (self.pdb.lower(), self.pdb.upper(), self.id):
            for ext in (".cif", ".pdb", ".ent"):
                p = native / f"{name}{ext}"
                if p.exists():
                    return p
        raise FileNotFoundError(
            f"No experimental structure for {self.id} in {native} "
            f"(expected {self.pdb.lower()}.cif or .pdb; try `tbm fetch-native {self.id}`)"
        )


def results_root() -> Path:
    """results/ for the Claude-agent run, results/baseline/ for the score-only run."""
    return RESULTS / "baseline" if os.environ.get("TBM_BASELINE") else RESULTS


@dataclass
class Settings:
    template_release_cutoff: str = "2022-05-01"
    search_iterations: int = 3
    inclusion_evalue: float = 1e-3
    evalue_cutoff: float = 1.0
    identity_cutoff: float = 0.0
    max_hits: int = 250
    n_detailed: int = 10
    n_models: int = 5
    rank_weights: dict[str, float] = field(
        default_factory=lambda: {
            "identity": 0.40,
            "coverage": 0.30,
            "evalue": 0.10,
            "resolution": 0.10,
            "completeness": 0.10,
        }
    )


@dataclass
class Config:
    settings: Settings
    targets: dict[str, Target]

    def target(self, target_id: str) -> Target:
        by_upper = {k.upper(): t for k, t in self.targets.items()}
        try:
            return by_upper[target_id.upper()]
        except KeyError:
            raise SystemExit(f"Unknown target {target_id!r}; known: {', '.join(self.targets)}")


def load_config(path: Path = CONFIG_PATH) -> Config:
    raw = tomllib.loads(Path(path).read_text())
    settings = Settings(**raw.get("settings", {}))
    targets = {}
    for t in raw["targets"]:
        tgt = Target(
            id=t["id"],
            difficulty=t["difficulty"],
            pdb=t["pdb"].upper(),
            length=int(t["length"]),
            eu=(int(t["eu"][0]), int(t["eu"][1])),
            chain=t.get("chain", ""),
        )
        targets[tgt.id] = tgt
    return Config(settings=settings, targets=targets)
