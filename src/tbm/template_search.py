"""Template search against the PDB (RCSB MMseqs2 service, or local MMseqs2)."""

from __future__ import annotations

import gzip
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import requests

from .config import CACHE

SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
GRAPHQL_URL = "https://data.rcsb.org/graphql"
DOWNLOAD_URL = "https://files.rcsb.org/download/{}.cif"
SEQRES_URL = "https://files.wwpdb.org/pub/pdb/derived_data/pdb_seqres.txt.gz"


@dataclass
class Hit:
    """One target-template sequence match. Positions are 1-based; subject positions
    index the full entity (SEQRES) sequence."""

    entity_id: str  # e.g. "7UX8_1"
    entry_id: str
    chains: list[str]
    identity: float  # 0..1 over the aligned region
    evalue: float
    bitscore: float
    query_beg: int
    query_end: int
    subject_beg: int
    subject_end: int
    query_length: int
    subject_length: int
    query_aligned: str = ""
    subject_aligned: str = ""
    # filled from RCSB metadata
    description: str = ""
    release_date: str = ""
    resolution: float | None = None
    method: str = ""
    # filled during filtering / ranking
    excluded: str = ""
    completeness: float | None = None
    chain: str = ""
    score: float | None = None
    signals: dict = field(default_factory=dict)

    @property
    def coverage(self) -> float:
        if self.query_aligned:
            aligned = sum(1 for q, s in zip(self.query_aligned, self.subject_aligned)
                          if q != "-" and s != "-")
            return aligned / self.query_length
        return (self.query_end - self.query_beg + 1) / self.query_length

    def to_row(self) -> dict:
        d = asdict(self)
        d.pop("query_aligned")
        d.pop("subject_aligned")
        d["chains"] = ",".join(self.chains)
        d["coverage"] = round(self.coverage, 4)
        d["signals"] = ";".join(f"{k}={v:.3f}" for k, v in self.signals.items())
        for k in ("identity", "completeness", "score"):
            if isinstance(d[k], float):
                d[k] = round(d[k], 4)
        return d


# ------------------------------------------------------------------ HTTP

def _post(url: str, payload: dict, retries: int = 3) -> requests.Response:
    for attempt in range(retries):
        try:
            r = requests.post(url, json=payload, timeout=120)
            if r.status_code < 500:
                return r
        except requests.RequestException:
            if attempt == retries - 1:
                raise
        time.sleep(2 ** attempt)
    r.raise_for_status()
    return r


def rcsb_sequence_search(seq: str, evalue_cutoff: float, identity_cutoff: float,
                         max_hits: int) -> list[Hit]:
    query = {
        "query": {
            "type": "terminal",
            "service": "sequence",
            "parameters": {
                "evalue_cutoff": evalue_cutoff,
                "identity_cutoff": identity_cutoff,
                "sequence_type": "protein",
                "value": seq,
            },
        },
        "request_options": {
            "scoring_strategy": "sequence",
            "results_verbosity": "verbose",
            "paginate": {"start": 0, "rows": max_hits},
        },
        "return_type": "polymer_entity",
    }
    r = _post(SEARCH_URL, query)
    if r.status_code == 204:
        return []
    r.raise_for_status()
    hits = []
    for res in r.json().get("result_set", []):
        entity_id = res["identifier"]
        for service in res["services"]:
            for node in service["nodes"]:
                for m in node["match_context"]:
                    hits.append(Hit(
                        entity_id=entity_id,
                        entry_id=entity_id.split("_")[0],
                        chains=[],
                        identity=float(m["sequence_identity"]),
                        evalue=float(m["evalue"]),
                        bitscore=float(m["bitscore"]),
                        query_beg=int(m["query_beg"]),
                        query_end=int(m["query_end"]),
                        subject_beg=int(m["subject_beg"]),
                        subject_end=int(m["subject_end"]),
                        query_length=int(m["query_length"]),
                        subject_length=int(m["subject_length"]),
                        query_aligned=m.get("query_aligned_seq", ""),
                        subject_aligned=m.get("subject_aligned_seq", ""),
                    ))
    return hits


# ------------------------------------------------------------------ local MMseqs2

def _seqres_db(cache: Path = CACHE) -> Path:
    """Protein-only pdb_seqres FASTA, downloaded once."""
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / "pdb_seqres_protein.fasta"
    if out.exists():
        return out
    gz = cache / "pdb_seqres.txt.gz"
    if not gz.exists():
        with requests.get(SEQRES_URL, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(gz, "wb") as fh:
                shutil.copyfileobj(r.raw, fh)
    with gzip.open(gz, "rt") as src, open(out, "w") as dst:
        keep = False
        for line in src:
            if line.startswith(">"):
                keep = "mol:protein" in line
                if keep:
                    dst.write(line.split()[0] + "\n")  # ">101m_A"
            elif keep:
                dst.write(line)
    return out


def local_mmseqs_search(seq: str, evalue_cutoff: float, max_hits: int,
                        sensitivity: float = 7.5) -> list[Hit]:
    """Sensitive MMseqs2 search against all PDB chains (needs `mmseqs` on PATH)."""
    if not shutil.which("mmseqs"):
        raise SystemExit("search_backend='local' needs MMseqs2 (`conda install -c bioconda mmseqs2`)")
    db = _seqres_db()
    fmt = "query,target,fident,evalue,bits,qstart,qend,tstart,tend,qlen,tlen,qaln,taln"
    with tempfile.TemporaryDirectory() as tmp:
        q = Path(tmp) / "q.fasta"
        q.write_text(f">query\n{seq}\n")
        out = Path(tmp) / "hits.m8"
        subprocess.run(
            ["mmseqs", "easy-search", str(q), str(db), str(out), str(Path(tmp) / "work"),
             "-s", str(sensitivity), "-e", str(evalue_cutoff), "--max-seqs", "5000",
             "--format-output", fmt, "-v", "1"],
            check=True,
        )
        rows = [line.rstrip("\n").split("\t") for line in out.read_text().splitlines() if line]

    # One hit per (entry, identical chain set): keep the best chain per entry sequence.
    hits: dict[str, Hit] = {}
    for row in rows:
        (_, target, fident, evalue, bits, qs, qe, ts, te, qlen, tlen, qaln, taln) = row
        entry, chain = target.split("_", 1)
        key = f"{entry.upper()}:{taln.replace('-', '')}"
        if key in hits:
            hits[key].chains.append(chain)
            continue
        hits[key] = Hit(
            entity_id="", entry_id=entry.upper(), chains=[chain],
            identity=float(fident), evalue=float(evalue), bitscore=float(bits),
            query_beg=int(qs), query_end=int(qe), subject_beg=int(ts), subject_end=int(te),
            query_length=int(qlen), subject_length=int(tlen),
            query_aligned=qaln, subject_aligned=taln,
        )
    ranked = sorted(hits.values(), key=lambda h: h.evalue)[:max_hits]
    _resolve_entities(ranked)
    return ranked


def _resolve_entities(hits: list[Hit]) -> None:
    """Fill entity ids for hits that only know (entry, chain)."""
    entries = sorted({h.entry_id for h in hits})
    gql = """query($ids:[String!]!){ entries(entry_ids:$ids){ rcsb_id
      polymer_entities{ rcsb_id entity_poly{ pdbx_strand_id } } } }"""
    chain_to_entity = {}
    for i in range(0, len(entries), 200):
        data = _post(GRAPHQL_URL, {"query": gql, "variables": {"ids": entries[i:i + 200]}}).json()
        for e in data["data"]["entries"] or []:
            for pe in e["polymer_entities"] or []:
                for ch in (pe["entity_poly"]["pdbx_strand_id"] or "").split(","):
                    chain_to_entity[(e["rcsb_id"], ch.strip())] = pe["rcsb_id"]
    for h in hits:
        h.entity_id = chain_to_entity.get((h.entry_id, h.chains[0]), f"{h.entry_id}_?")


# ------------------------------------------------------------------ metadata

def annotate(hits: list[Hit]) -> None:
    """Attach release date, resolution, method, description and chains from RCSB."""
    ids = sorted({h.entity_id for h in hits if not h.entity_id.endswith("?")})
    gql = """query($ids:[String!]!){ polymer_entities(entity_ids:$ids){ rcsb_id
      rcsb_polymer_entity_container_identifiers{ entry_id auth_asym_ids }
      entity_poly{ pdbx_strand_id }
      rcsb_polymer_entity{ pdbx_description }
      entry{ rcsb_accession_info{ initial_release_date }
             rcsb_entry_info{ resolution_combined experimental_method } } } }"""
    meta = {}
    for i in range(0, len(ids), 200):
        r = _post(GRAPHQL_URL, {"query": gql, "variables": {"ids": ids[i:i + 200]}})
        r.raise_for_status()
        for pe in r.json()["data"]["polymer_entities"] or []:
            meta[pe["rcsb_id"]] = pe
    for h in hits:
        pe = meta.get(h.entity_id)
        if not pe:
            continue
        strands = (pe["entity_poly"]["pdbx_strand_id"] or "").split(",")
        if not h.chains:
            h.chains = [s.strip() for s in strands if s.strip()]
        h.description = pe["rcsb_polymer_entity"]["pdbx_description"] or ""
        entry = pe["entry"]
        h.release_date = (entry["rcsb_accession_info"]["initial_release_date"] or "")[:10]
        info = entry["rcsb_entry_info"]
        res = info.get("resolution_combined") or []
        h.resolution = float(res[0]) if res else None
        h.method = info.get("experimental_method") or ""


def search(seq: str, backend: str, evalue_cutoff: float, identity_cutoff: float,
           max_hits: int) -> list[Hit]:
    if backend == "rcsb":
        hits = rcsb_sequence_search(seq, evalue_cutoff, identity_cutoff, max_hits)
    elif backend == "local":
        hits = local_mmseqs_search(seq, evalue_cutoff, max_hits)
        hits = [h for h in hits if h.identity >= identity_cutoff]
    else:
        raise ValueError(f"unknown search backend {backend!r}")
    annotate(hits)
    return hits


# ------------------------------------------------------------------ downloads

def download_cif(pdb_id: str, dest_dir: Path = CACHE / "mmcif") -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"{pdb_id.lower()}.cif"
    if not out.exists():
        r = requests.get(DOWNLOAD_URL.format(pdb_id.upper()), timeout=120)
        r.raise_for_status()
        out.write_text(r.text)
    return out
