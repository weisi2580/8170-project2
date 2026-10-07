"""Template search against the PDB: iterative profile HMM search (HMMER jackhmmer)."""

from __future__ import annotations

import gzip
import hashlib
import re
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


# ------------------------------------------------------------------ profile search (HMMER)

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


def released_after(cutoff: str, cache: Path = CACHE) -> set[str]:
    """Lower-case ids of PDB entries released on or after the cutoff date (cached)."""
    out = cache / f"pdb_released_since_{cutoff}.txt"
    if not out.exists():
        query = {"query": {"type": "terminal", "service": "text", "parameters": {
            "attribute": "rcsb_accession_info.initial_release_date",
            "operator": "greater_or_equal", "value": cutoff}},
            "return_type": "entry", "request_options": {"return_all_hits": True}}
        r = _post(SEARCH_URL, query)
        r.raise_for_status()
        ids = sorted(x["identifier"].lower() for x in r.json()["result_set"])
        out.write_text("\n".join(ids) + "\n")
    return set(out.read_text().split())


def search_db(cutoff: str, exclude: set[str], cache: Path = CACHE) -> Path:
    """pdb_seqres restricted to entries released before the cutoff, minus `exclude` (the
    benchmark targets' own entries). Searching this database keeps post-cutoff structures
    out of the profile as well as out of the template list."""
    drop = {e.lower() for e in exclude} | (released_after(cutoff) if cutoff else set())
    tag = hashlib.sha1(",".join(sorted(e.lower() for e in exclude)).encode()).hexdigest()[:8]
    out = cache / f"pdb_seqres_before_{cutoff or 'any'}_{tag}.fasta"
    if not out.exists():
        tmp = out.with_suffix(".part")
        with open(_seqres_db(cache)) as src, open(tmp, "w") as dst:
            keep = True
            for line in src:
                if line.startswith(">"):
                    keep = line[1:5].lower() not in drop
                if keep:
                    dst.write(line)
        tmp.rename(out)
    return out


# Expression tags and protease sites: they match thousands of unrelated tagged constructs.
TAG_PATTERNS = [r"H{5,}", r"ENLYFQ[GS]?", r"LVPRGS", r"LEVLFQ[GS]P?", r"DYKDDDDK", r"WSHPQFEK"]


def mask_tags(seq: str) -> tuple[str, list[tuple[int, int]]]:
    """Replace tags with X for searching; returns the masked sequence and 1-based spans."""
    masked, spans = list(seq), []
    for pat in TAG_PATTERNS:
        for m in re.finditer(pat, seq):
            masked[m.start():m.end()] = "X" * (m.end() - m.start())
            spans.append((m.start() + 1, m.end()))
    return "".join(masked), sorted(spans)


def _read_a2m(text: str) -> dict[str, str]:
    recs, cur = {}, None
    for line in text.splitlines():
        if line.startswith(">"):
            cur = line[1:].split()[0]
            recs[cur] = ""
        elif cur:
            recs[cur] += line.strip()
    return recs


def _columns(a2m: str) -> tuple[list[tuple[str, str]], str]:
    """Per profile match column: (residue or '-', insertion before it); trailing insertion."""
    cols, ins = [], ""
    for ch in a2m:
        if ch.islower():
            ins += ch.upper()
        elif ch != ".":
            cols.append((ch, ins))
            ins = ""
    return cols, ins


def pairwise_from_a2m(a: str, b: str) -> tuple[str, str]:
    """Pairwise alignment of two sequences aligned to the same profile (A2M rows):
    residues in the same match column are aligned, insertions are aligned to gaps."""
    (ac, aend), (bc, bend) = _columns(a), _columns(b)
    x, y = [], []
    for (ra, ia), (rb, ib) in zip(ac, bc):
        x += [ia, "-" * len(ib), ra]
        y += ["-" * len(ia), ib, rb]
    x += [aend, "-" * len(bend)]
    y += ["-" * len(aend), bend]
    x, y = "".join(x), "".join(y)
    keep = [i for i in range(len(x)) if not (x[i] == "-" and y[i] == "-")]
    return "".join(x[i] for i in keep), "".join(y[i] for i in keep)


def profile_align(hmm: Path, query: str, others: dict[str, str]) -> dict[str, tuple[str, str]]:
    """Align the query and each other sequence to the search profile (hmmalign);
    returns {name: (query_aligned, other_aligned)}."""
    with tempfile.TemporaryDirectory() as tmp:
        fa = Path(tmp) / "seqs.fa"
        fa.write_text(f">__query__\n{query}\n" + "".join(f">{k}\n{v}\n" for k, v in others.items()))
        out = subprocess.run(["hmmalign", "--outformat", "A2M", str(hmm), str(fa)],
                             check=True, capture_output=True, text=True).stdout
    recs = _read_a2m(out)
    return {k: pairwise_from_a2m(recs["__query__"], recs[k]) for k in others}


def _read_fasta_ids(path: Path, ids: set[str]) -> dict[str, str]:
    seqs, cur = {}, None
    with open(path) as fh:
        for line in fh:
            if line.startswith(">"):
                cur = line[1:].split()[0]
                cur = cur if cur in ids else None
            elif cur:
                seqs[cur] = seqs.get(cur, "") + line.strip()
    return seqs


def hmmer_search(seq: str, db: Path, workdir: Path, evalue_cutoff: float,
                 inclusion_evalue: float, iterations: int, max_hits: int,
                 cpu: int = 8) -> tuple[list[Hit], dict]:
    """Iterative profile search (jackhmmer) of the target against PDB chains.

    Round 1 compares the sequence itself; each further round builds a profile HMM from the
    hits with E <= inclusion_evalue and searches again, which detects remote homologues that
    single-sequence comparison scores as noise. The final profile is kept as
    workdir/profile.hmm and is also used to align target and template for MODELLER."""
    for tool in ("jackhmmer", "hmmalign"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} not found: conda install -c bioconda hmmer")
    workdir.mkdir(parents=True, exist_ok=True)
    masked, tag_spans = mask_tags(seq)
    q = workdir / "query.fasta"
    q.write_text(f">query\n{masked}\n")
    dom = workdir / "hits.domtbl"
    for old in workdir.glob("round-*.hmm"):
        old.unlink()
    subprocess.run(
        ["jackhmmer", "--cpu", str(cpu), "-N", str(iterations), "-E", str(evalue_cutoff),
         "--domE", str(evalue_cutoff), "--incE", str(inclusion_evalue),
         "--incdomE", str(inclusion_evalue), "--noali", "--domtblout", str(dom),
         "--chkhmm", str(workdir / "round"), "-o", str(workdir / "jackhmmer.log"),
         str(q), str(db)],
        check=True,
    )
    rounds = sorted(workdir.glob("round-*.hmm"), key=lambda p: int(p.stem.split("-")[1]))
    hmm = workdir / "profile.hmm"
    shutil.copy(rounds[-1], hmm)
    log = (workdir / "jackhmmer.log").read_text()
    info = {"rounds": len(rounds), "converged": "CONVERGED" in log,
            "masked_tags": tag_spans, "profile": str(hmm)}

    best: dict[str, list[str]] = {}
    for line in dom.read_text().splitlines():
        if line.startswith("#"):
            continue
        f = line.split()
        name, i_eval = f[0], float(f[12])
        if name not in best or i_eval < float(best[name][12]):
            best[name] = f
    if not best:
        return [], info
    seqs = _read_fasta_ids(db, set(best))
    segments = {n: seqs[n][int(f[19]) - 1:int(f[20])] for n, f in best.items()}
    pairs = profile_align(hmm, seq, segments)

    hits: dict[str, Hit] = {}
    for name, f in sorted(best.items(), key=lambda kv: float(kv[1][6])):
        entry, chain = name.split("_", 1)
        key = f"{entry.upper()}:{segments[name]}"
        if key in hits:
            hits[key].chains.append(chain)
            continue
        qa, sa = pairs[name]
        aligned = [(a, b) for a, b in zip(qa, sa) if a != "-" and b != "-"]
        q_idx, k = [], 0
        for a, b in zip(qa, sa):
            if a != "-":
                k += 1
                if b != "-":
                    q_idx.append(k)
        hits[key] = Hit(
            entity_id="", entry_id=entry.upper(), chains=[chain],
            identity=sum(a == b for a, b in aligned) / len(aligned) if aligned else 0.0,
            evalue=float(f[6]), bitscore=float(f[7]),
            query_beg=q_idx[0] if q_idx else 0, query_end=q_idx[-1] if q_idx else 0,
            subject_beg=int(f[19]), subject_end=int(f[20]),
            query_length=len(seq), subject_length=int(f[2]),
            query_aligned=qa, subject_aligned=sa,
        )
    ranked = list(hits.values())[:max_hits]
    _resolve_entities(ranked)
    return ranked, info


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


def search(seq: str, db: Path, workdir: Path, evalue_cutoff: float, inclusion_evalue: float,
           iterations: int, identity_cutoff: float, max_hits: int) -> tuple[list[Hit], dict]:
    hits, info = hmmer_search(seq, db, workdir, evalue_cutoff, inclusion_evalue, iterations,
                              max_hits)
    hits = [h for h in hits if h.identity >= identity_cutoff]
    annotate(hits)
    return hits, info


# ------------------------------------------------------------------ downloads

def download_cif(pdb_id: str, dest_dir: Path = CACHE / "mmcif") -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"{pdb_id.lower()}.cif"
    if not out.exists():
        r = requests.get(DOWNLOAD_URL.format(pdb_id.upper()), timeout=120)
        r.raise_for_status()
        out.write_text(r.text)
    return out
