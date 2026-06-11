"""分析結果の出力(CSV / JSON / TextGrid / PNG)。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from praatio import textgrid as ptg

from .textproc import AccentPhrase

logger = logging.getLogger(__name__)


def build_frames_df(
    name: str,
    times: np.ndarray,
    f0_hz: np.ndarray,
    f0_st: np.ndarray,
    f0_z: np.ndarray,
    aps: list[AccentPhrase],
) -> pd.DataFrame:
    ap_index = np.full(len(times), -1, dtype=int)
    word_index = np.full(len(times), -1, dtype=int)
    ap_text = np.full(len(times), "", dtype=object)
    for ap in aps:
        if ap.t_start is None:
            continue
        sel = (times >= ap.t_start) & (times <= ap.t_end)
        ap_index[sel] = ap.index
        ap_text[sel] = ap.kana
        for wi, w in enumerate(ap.words):
            wsel = (times >= w.t_start) & (times <= w.t_end)
            word_index[wsel] = wi
    return pd.DataFrame(
        {
            "file": name,
            "time_sec": np.round(times, 4),
            "f0_hz": np.round(f0_hz, 2),
            "f0_st": np.round(f0_st, 3),
            "f0_z": np.round(f0_z, 3),
            "voiced": (f0_hz > 0).astype(int),
            "ap_index": ap_index,
            "word_index": word_index,
            "ap_text": ap_text,
        }
    )


def build_ap_summary_df(
    name: str,
    times: np.ndarray,
    f0_st: np.ndarray,
    aps: list[AccentPhrase],
) -> pd.DataFrame:
    rows = []
    for ap in aps:
        row: dict = {
            "file": name,
            "ap_index": ap.index,
            "ap_surface": ap.surface,
            "ap_kana": ap.kana,
            "accent_type": ap.accent_type,
            "mora_count": ap.mora_count,
            "follows_pause": int(ap.follows_pause),
            "t_start": ap.t_start,
            "t_end": ap.t_end,
            "duration_sec": ap.duration,
            "low_confidence": int(ap.low_confidence),
        }
        if ap.t_start is not None:
            sel = (times >= ap.t_start) & (times <= ap.t_end)
            st = f0_st[sel]
            voiced = ~np.isnan(st)
            row["voiced_ratio"] = round(float(voiced.mean()), 3) if len(st) else np.nan
            if voiced.any():
                st_v = st[voiced]
                t_v = times[sel][voiced]
                peak = float(t_v[np.argmax(st_v)])
                row.update(
                    f0_mean_st=round(float(st_v.mean()), 3),
                    f0_max_st=round(float(st_v.max()), 3),
                    f0_min_st=round(float(st_v.min()), 3),
                    f0_range_st=round(float(st_v.max() - st_v.min()), 3),
                    peak_time_ratio=round((peak - ap.t_start) / ap.duration, 3)
                    if ap.duration
                    else np.nan,
                )
        rows.append(row)
    return pd.DataFrame(rows)


def build_contours_df(
    name: str,
    times: np.ndarray,
    f0_st: np.ndarray,
    aps: list[AccentPhrase],
    n_points: int,
) -> pd.DataFrame:
    from .normalize import time_normalized_contour

    rows = []
    for ap in aps:
        contour = (
            time_normalized_contour(times, f0_st, ap.t_start, ap.t_end, n_points)
            if ap.t_start is not None
            else np.full(n_points, np.nan)
        )
        row = {"file": name, "ap_index": ap.index, "ap_kana": ap.kana}
        row.update(
            {f"p{i+1:02d}": round(float(v), 3) if not np.isnan(v) else np.nan
             for i, v in enumerate(contour)}
        )
        rows.append(row)
    return pd.DataFrame(rows)


def write_json(
    path: Path,
    name: str,
    aps: list[AccentPhrase],
    params: dict,
    contours: pd.DataFrame,
) -> None:
    contour_cols = [c for c in contours.columns if c.startswith("p")]
    data = {
        "file": name,
        "params": params,
        "accent_phrases": [
            {
                "index": ap.index,
                "surface": ap.surface,
                "kana": ap.kana,
                "accent_type": ap.accent_type,
                "mora_count": ap.mora_count,
                "follows_pause": ap.follows_pause,
                "t_start": ap.t_start,
                "t_end": ap.t_end,
                "low_confidence": ap.low_confidence,
                "words": [
                    {
                        "surface": w.surface,
                        "pron": w.pron,
                        "pos": w.pos,
                        "t_start": w.t_start,
                        "t_end": w.t_end,
                    }
                    for w in ap.words
                ],
                "contour_st": [
                    None if pd.isna(v) else v
                    for v in contours.iloc[ap.index][contour_cols]
                ],
            }
            for ap in aps
        ],
    }
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def write_textgrid(
    path: Path,
    aps: list[AccentPhrase],
    phones: list[tuple[float, float, str]],
    duration: float,
) -> None:
    tg = ptg.Textgrid()
    word_entries = [
        (w.t_start, w.t_end, w.pron)
        for ap in aps
        for w in ap.words
        if w.t_start is not None
    ]
    ap_entries = [
        (
            ap.t_start,
            ap.t_end,
            f"{ap.kana}({ap.accent_type if ap.accent_type is not None else '?'})",
        )
        for ap in aps
        if ap.t_start is not None
    ]
    tg.addTier(ptg.IntervalTier("accent_phrases", ap_entries, 0, duration))
    tg.addTier(ptg.IntervalTier("words", word_entries, 0, duration))
    if phones:
        tg.addTier(ptg.IntervalTier("phones", phones, 0, duration))
    tg.save(str(path), format="long_textgrid", includeBlankSpaces=True)


def plot_f0(
    path: Path,
    times: np.ndarray,
    f0_st: np.ndarray,
    aps: list[AccentPhrase],
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager

        jp_fonts = [
            f for f in ("Noto Sans CJK JP", "IPAexGothic", "Hiragino Sans")
            if any(f == fm.name for fm in font_manager.fontManager.ttflist)
        ]
        if jp_fonts:
            matplotlib.rcParams["font.family"] = jp_fonts[0]
    except ImportError:
        logger.warning("matplotlib がないため PNG 出力をスキップします")
        return

    total = times[-1] if len(times) else 1.0
    n_panels = max(1, int(np.ceil(total / 30.0)))
    fig, axes = plt.subplots(
        n_panels, 1, figsize=(16, 2.2 * n_panels), squeeze=False
    )
    for p in range(n_panels):
        ax = axes[p][0]
        t0, t1 = p * 30.0, (p + 1) * 30.0
        sel = (times >= t0) & (times < t1)
        ax.plot(times[sel], f0_st[sel], ".", markersize=2)
        for ap in aps:
            if ap.t_start is None or ap.t_end < t0 or ap.t_start >= t1:
                continue
            ax.axvspan(ap.t_start, ap.t_end, alpha=0.08, color="C1")
            ax.text(
                (ap.t_start + ap.t_end) / 2, ax.get_ylim()[1],
                ap.kana, rotation=45, fontsize=6, ha="left", va="bottom",
            )
        ax.set_xlim(t0, t1)
        ax.set_ylabel("F0 [st]")
    axes[-1][0].set_xlabel("time [s]")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
