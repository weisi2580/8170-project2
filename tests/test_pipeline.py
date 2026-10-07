import json

import numpy as np
import pytest
from Bio.PDB.Atom import Atom
from Bio.PDB.Residue import Residue

from tbm import af3, agent2, template_select
from tbm.config import Target
from tbm.modeller_build import alignment_stats, read_pir, write_pir
from tbm.structure import (ONE_TO_THREE, best_chain, build_structure, load_structure, map_sequence,
                           write_pdb)
from tbm.template_search import Hit

SEQ = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQ"


# ------------------------------------------------------------- sequence mapping

def test_map_sequence_handles_missing_residues():
    observed = SEQ[5:20] + SEQ[25:]  # N-terminus and a loop unresolved
    m = map_sequence(SEQ, observed)
    assert m[0] == 6
    assert m[14] == 20
    assert m[15] == 26
    assert len(m) == len(observed)


def test_pir_roundtrip_and_stats(tmp_path):
    write_pir(tmp_path / "t.ali", "T1", SEQ)
    assert read_pir(tmp_path / "t.ali") == {"T1": SEQ}
    s = alignment_stats("ACDEFG--", "AC-EFHKL")
    assert s["aligned_residues"] == 5
    assert s["identity"] == pytest.approx(0.8)
    assert s["coverage"] == pytest.approx(5 / 6)


# ------------------------------------------------------------- leakage + ranking

def hit(entry, identity, cov_end, evalue, res, date):
    return Hit(entity_id=f"{entry}_1", entry_id=entry, chains=["A"], identity=identity,
               evalue=evalue, bitscore=100, query_beg=1, query_end=cov_end, subject_beg=1,
               subject_end=cov_end, query_length=100, subject_length=100,
               resolution=res, release_date=date)


def test_leakage_filter_and_ranking():
    hits = [
        hit("7UX8", 1.0, 100, 1e-80, 1.8, "2022-11-01"),  # the target itself
        hit("9NEW", 0.9, 100, 1e-70, 1.5, "2023-01-01"),  # released after cutoff
        hit("1AAA", 0.35, 95, 1e-20, 2.0, "2010-01-01"),
        hit("2BBB", 0.60, 60, 1e-25, 3.5, "2015-01-01"),
        hit("3CCC", 0.30, 40, 1e-3, None, "2001-01-01"),
    ]
    template_select.apply_leakage_filter(hits, "7ux8", "2022-05-01")
    assert "own experimental structure" in hits[0].excluded
    assert "after cutoff" in hits[1].excluded
    weights = {"identity": 0.4, "coverage": 0.3, "evalue": 0.1, "resolution": 0.1,
               "completeness": 0.1}
    ranked = template_select.rank(hits, weights, n_detailed=0, check_completeness=False)
    assert [h.entry_id for h in ranked] == ["1AAA", "2BBB", "3CCC"]
    text = template_select.explain(ranked[0], ranked, 2)
    assert "1AAA" in text and "2 hit(s) were excluded" in text


def test_no_date_cutoff_keeps_recent_entries():
    hits = [hit("9NEW", 0.9, 100, 1e-70, 1.5, "2023-01-01")]
    template_select.apply_leakage_filter(hits, "7UX8", "")
    assert hits[0].excluded == ""


# ------------------------------------------------------------- AF3 discovery

def test_af3_models_sorted_by_ranking_score(tmp_path):
    for i, score in enumerate([0.71, 0.85, 0.60]):
        (tmp_path / f"fold_t1124_model_{i}.cif").write_text("data_x\n")
        (tmp_path / f"fold_t1124_summary_confidences_{i}.json").write_text(
            json.dumps({"ranking_score": score, "ptm": score}))
    models = af3.find_models(tmp_path)
    assert [m["index"] for m in models] == [1, 0, 2]
    assert af3.top_model(tmp_path)["ranking_score"] == 0.85


# ------------------------------------------------------------- end-to-end agent2

def fake_chain(seq, coords, start_number=1):
    residues = []
    for k, (aa, ca) in enumerate(zip(seq, coords)):
        res = Residue((" ", start_number + k, " "), ONE_TO_THREE[aa], "    ")
        for name, off in (("N", (-1.2, 0.5, 0)), ("CA", (0, 0, 0)), ("C", (1.2, 0.5, 0)),
                          ("O", (1.5, 1.6, 0.3))):
            res.add(Atom(name, np.asarray(ca) + off, 50.0, 1.0, " ", f" {name:<3}", None,
                         name[0]))
        residues.append((start_number + k, res))
    return residues


def test_agent2_evaluate_on_synthetic_structures(tmp_path):
    n = len(SEQ)
    t = np.arange(n) * 100.0 * np.pi / 180.0
    ca = np.stack([2.3 * np.cos(t), 2.3 * np.sin(t), 1.5 * np.arange(n)], axis=1)

    # native: residues 4..n with author numbering offset by 100, a loop missing
    keep = [i for i in range(3, n) if not 30 <= i < 34]
    native_res = fake_chain("".join(SEQ[i] for i in keep), ca[keep], 104)
    write_pdb(build_structure(native_res, "B"), tmp_path / "native.pdb")

    # model: full sequence numbered 1..n, slightly perturbed
    noise = np.random.default_rng(0).normal(scale=0.4, size=ca.shape)
    write_pdb(build_structure(fake_chain(SEQ, ca + noise), "A"), tmp_path / "model.pdb")

    nat = best_chain(load_structure(tmp_path / "native.pdb"), SEQ)
    assert nat.chain_id == "B" and nat.identity == 1.0
    eu = (5, n - 2)
    _, native_eu = agent2._prepared(tmp_path / "native.pdb", SEQ, eu, tmp_path / "n.pdb")
    _, model_eu = agent2._prepared(tmp_path / "model.pdb", SEQ, eu, tmp_path / "m.pdb")
    assert min(native_eu) == 5 and max(native_eu) == n - 2
    assert 31 not in native_eu  # missing loop (0-based 30 -> target index 31)

    res = agent2.evaluate_model(model_eu, native_eu, tmp_path / "m.pdb", tmp_path / "n.pdb")
    assert res["n_common"] == len(native_eu)
    assert res["tm_score"] > 0.8
    assert res["gdt_ts"] > 80
    assert 0.6 < res["lddt"] <= 1.0
    assert res["rmsd"] < 1.0


def test_mask_tags_keeps_length_and_reports_spans():
    from tbm.template_search import mask_tags
    seq = "MHHHHHHHHSSGENLYFQGAKLVCNRC"
    masked, spans = mask_tags(seq)
    assert len(masked) == len(seq)
    assert masked.startswith("MXXXXXXXX") and "ENLYFQG" not in masked
    assert masked.endswith("AKLVCNRC")
    assert spans == [(2, 9), (13, 19)]


def test_pairwise_from_profile_rows():
    from tbm.template_search import pairwise_from_a2m
    # 4 match columns; target has an insertion 'k' after column 2, template lacks column 3.
    target, template = "ACkDE", "AC-E"
    ta, pa = pairwise_from_a2m(target, template)
    assert ta.replace("-", "") == "ACKDE" and pa.replace("-", "") == "ACE"
    assert list(zip(ta, pa)) == [("A", "A"), ("C", "C"), ("K", "-"), ("D", "-"), ("E", "E")]
