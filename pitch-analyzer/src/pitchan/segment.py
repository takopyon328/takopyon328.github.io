"""単語アラインメント結果をアクセント句に割り当てる。"""

from __future__ import annotations

import logging

from .textproc import AccentPhrase

logger = logging.getLogger(__name__)

# 1 モーラあたりの長さがこの範囲を外れる AP は low_confidence とする
MIN_SEC_PER_MORA = 0.03
MAX_SEC_PER_MORA = 0.5


def assign_times(
    aps: list[AccentPhrase], word_intervals: list[tuple[float, float, str]]
) -> None:
    """各 AP・単語に時刻を割り当てる(word_intervals は全 AP の単語の通し列)。"""
    n_words = sum(len(ap.words) for ap in aps)
    if n_words != len(word_intervals):
        raise ValueError(
            f"単語数が一致しません (AP 側 {n_words}, アラインメント側 {len(word_intervals)})"
        )
    i = 0
    for ap in aps:
        for w in ap.words:
            start, end, label = word_intervals[i]
            if label != w.pron:
                logger.warning(
                    "AP %d: 単語ラベル不一致 %r vs %r", ap.index, label, w.pron
                )
            w.t_start, w.t_end = start, end
            i += 1
        ap.t_start = ap.words[0].t_start
        ap.t_end = ap.words[-1].t_end
        _check_confidence(ap)


def _check_confidence(ap: AccentPhrase) -> None:
    if ap.duration is None or ap.mora_count == 0:
        ap.low_confidence = True
        return
    per_mora = ap.duration / ap.mora_count
    if not (MIN_SEC_PER_MORA <= per_mora <= MAX_SEC_PER_MORA):
        ap.low_confidence = True
        logger.warning(
            "AP %d (%s): モーラあたり %.0f ms と極端なため low_confidence",
            ap.index, ap.kana, per_mora * 1000,
        )
