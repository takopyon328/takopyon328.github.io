"""F0 抽出(WORLD harvest + stonemask)。"""

from __future__ import annotations

import numpy as np
import pyworld
import soundfile as sf


def load_wav(path: str) -> tuple[np.ndarray, int]:
    """WAV を読み込み、モノラル float64 で返す。"""
    data, sr = sf.read(path, dtype="float64", always_2d=True)
    return data.mean(axis=1), sr


def extract_f0(
    x: np.ndarray,
    sr: int,
    f0_floor: float = 60.0,
    f0_ceil: float = 500.0,
    frame_shift_ms: float = 5.0,
    median_filter: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """F0 系列を抽出する。

    Returns:
        (times, f0): 秒単位の時刻と Hz 単位の F0。無声フレームは 0。
    """
    f0, t = pyworld.harvest(
        x, sr, f0_floor=f0_floor, f0_ceil=f0_ceil, frame_period=frame_shift_ms
    )
    f0 = pyworld.stonemask(x, f0, t, sr)
    if median_filter:
        f0 = _median5_voiced(f0)
    return t, f0


def _median5_voiced(f0: np.ndarray) -> np.ndarray:
    """有声区間のみに 5 点メディアンフィルタを適用する(倍/半ピッチ誤りの緩和)。"""
    out = f0.copy()
    voiced = f0 > 0
    n = len(f0)
    for i in np.where(voiced)[0]:
        lo, hi = max(0, i - 2), min(n, i + 3)
        win = f0[lo:hi]
        win = win[win > 0]
        out[i] = np.median(win)
    return out


def interpolate_unvoiced_in_spans(
    times: np.ndarray, f0: np.ndarray, spans: list[tuple[float, float]]
) -> np.ndarray:
    """指定区間(アクセント句)内の無声フレームを線形補間した F0 を返す。

    区間の外側は変更しない。区間内に有声フレームが 2 未満なら何もしない。
    """
    out = f0.copy()
    for t0, t1 in spans:
        idx = np.where((times >= t0) & (times <= t1))[0]
        if len(idx) == 0:
            continue
        seg = f0[idx]
        voiced = seg > 0
        if voiced.sum() < 2:
            continue
        seg_t = times[idx]
        out[idx] = np.where(
            voiced, seg, np.interp(seg_t, seg_t[voiced], seg[voiced])
        )
    return out
