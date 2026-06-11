import numpy as np
import pytest

from pitchan.normalize import (
    speaker_reference,
    time_normalized_contour,
    to_log_z,
    to_semitone,
)


def test_speaker_reference_geometric_mean():
    f0 = np.array([100.0, 0.0, 400.0])
    ref, mu, sigma = speaker_reference([f0])
    assert ref == pytest.approx(200.0)  # 幾何平均、無声(0)は除外
    assert mu == pytest.approx(np.log(200.0))


def test_to_semitone():
    st = to_semitone(np.array([200.0, 400.0, 0.0]), ref_hz=200.0)
    assert st[0] == pytest.approx(0.0)
    assert st[1] == pytest.approx(12.0)  # 1 オクターブ = 12 半音
    assert np.isnan(st[2])


def test_to_log_z():
    f0 = np.array([100.0, 200.0, 0.0])
    z = to_log_z(f0, mu=np.log(100.0), sigma=np.log(2.0))
    assert z[0] == pytest.approx(0.0)
    assert z[1] == pytest.approx(1.0)
    assert np.isnan(z[2])


def test_contour_resampling():
    times = np.arange(0, 1.0, 0.005)
    values = times * 10.0  # 線形に上昇する輪郭
    c = time_normalized_contour(times, values, 0.0, 1.0, n_points=11)
    assert c[0] == pytest.approx(0.0, abs=0.1)
    assert c[-1] == pytest.approx(10.0, abs=0.1)
    assert c[5] == pytest.approx(5.0, abs=0.1)


def test_contour_too_few_voiced():
    times = np.arange(0, 1.0, 0.005)
    values = np.full_like(times, np.nan)
    values[10] = 5.0
    c = time_normalized_contour(times, values, 0.0, 1.0, n_points=10)
    assert np.isnan(c).all()
