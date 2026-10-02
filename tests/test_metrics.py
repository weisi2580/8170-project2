import numpy as np
import pytest

from tbm import metrics


def helix(n, seed=0):
    t = np.arange(n) * 100.0 * np.pi / 180.0
    xyz = np.stack([2.3 * np.cos(t), 2.3 * np.sin(t), 1.5 * np.arange(n)], axis=1)
    # bend it so it is not a perfect line
    xyz[:, 0] += 0.02 * (np.arange(n) - n / 2) ** 2 / 10
    return xyz


def random_rotation(seed=1):
    q, _ = np.linalg.qr(np.random.default_rng(seed).normal(size=(3, 3)))
    if np.linalg.det(q) < 0:
        q[:, 0] *= -1
    return q


def test_kabsch_recovers_rigid_motion():
    x = helix(60)
    rot = random_rotation()
    y = x @ rot.T + np.array([5.0, -3.0, 2.0])
    r, t = metrics.kabsch(x, y)
    assert np.allclose(metrics.superpose(x, r, t), y, atol=1e-8)
    assert metrics.rmsd(x, y) == pytest.approx(0.0, abs=1e-6)


def test_identical_structures_score_perfectly():
    x = helix(80)
    y = x @ random_rotation(3).T + 10.0
    tm, _ = metrics.tm_score(x, y)
    assert tm == pytest.approx(1.0, abs=1e-6)
    assert metrics.gdt_ts(x, y) == pytest.approx(100.0)


def test_scores_drop_with_noise_and_partial_errors():
    x = helix(100)
    noisy = x + np.random.default_rng(0).normal(scale=1.5, size=x.shape)
    tm_noisy, _ = metrics.tm_score(noisy, x)
    assert 0.3 < tm_noisy < 1.0

    # second half displaced: the best superposition should still fit the first half
    broken = x.copy()
    broken[50:] += np.array([15.0, 0.0, 0.0])
    tm_broken, _ = metrics.tm_score(broken, x)
    gdt = metrics.gdt(broken, x)
    assert 0.4 < tm_broken < 0.7
    assert gdt[1.0] == pytest.approx(0.5, abs=0.05)


def test_normalisation_by_native_length():
    x = helix(80)
    tm_full, _ = metrics.tm_score(x, x, n_ref=80)
    tm_half, _ = metrics.tm_score(x[:40], x[:40], n_ref=80)
    assert tm_full == pytest.approx(1.0)
    assert tm_half < 0.55


def atoms_from(xyz):
    return {(i, "CA"): c for i, c in enumerate(xyz, 1)}


def test_lddt_is_superposition_free():
    x = helix(50)
    y = x @ random_rotation(5).T - 4.0
    score, per_res = metrics.lddt(atoms_from(y), atoms_from(x))
    assert score == pytest.approx(1.0)
    assert all(v == pytest.approx(1.0) for v in per_res.values())


def test_lddt_penalises_distortion_and_missing_atoms():
    x = helix(50)
    y = x.copy()
    y[20:30] += np.random.default_rng(2).normal(scale=3.0, size=(10, 3))
    score, per_res = metrics.lddt(atoms_from(y), atoms_from(x))
    assert score < 0.95
    assert per_res[25] < per_res[45]

    partial = {k: v for k, v in atoms_from(x).items() if k[0] <= 25}
    score_partial, _ = metrics.lddt(partial, atoms_from(x))
    assert score_partial < 0.75


def test_tm_d0():
    assert metrics.tm_d0(10) == 0.5
    assert metrics.tm_d0(200) == pytest.approx(1.24 * 185 ** (1 / 3) - 1.8)
