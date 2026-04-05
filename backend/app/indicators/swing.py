"""
Shared swing‑point detection and alternation logic.

Used by MSS, CHoCH, and Lateralization indicators.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


@dataclass(slots=True)
class Swing:
    """A confirmed swing point."""
    bar: int          # bar index in the DataFrame
    price: float
    kind: Literal["SH", "SL"]


def detect_swings(
    highs: np.ndarray,
    lows: np.ndarray,
    swing_length: int,
) -> list[Swing]:
    """
    Detect alternating swing highs / lows.

    1. Find raw candidates where the high (or low) is the highest (lowest)
       within *swing_length* bars on each side.
    2. Enforce strict SH → SL → SH → SL alternation — when two
       consecutive same‑type swings appear, keep only the most extreme.

    Returns a list of :class:`Swing` in bar‑order.
    """
    n = swing_length
    length = len(highs)

    # ── 1. Raw candidates ────────────────────────────────────────────
    raw: list[Swing] = []
    for i in range(n, length - n):
        if all(highs[i] >= highs[i - j] for j in range(1, n + 1)) and \
           all(highs[i] >= highs[i + j] for j in range(1, n + 1)):
            raw.append(Swing(bar=i, price=highs[i], kind="SH"))
        if all(lows[i] <= lows[i - j] for j in range(1, n + 1)) and \
           all(lows[i] <= lows[i + j] for j in range(1, n + 1)):
            raw.append(Swing(bar=i, price=lows[i], kind="SL"))
    raw.sort(key=lambda s: s.bar)

    # ── 2. Enforce alternation ───────────────────────────────────────
    alt: list[Swing] = []
    for sw in raw:
        if not alt:
            alt.append(sw)
            continue
        last = alt[-1]
        if sw.kind == last.kind:
            if sw.kind == "SH" and sw.price >= last.price:
                alt[-1] = sw
            elif sw.kind == "SL" and sw.price <= last.price:
                alt[-1] = sw
        else:
            alt.append(sw)
    return alt


def swings_to_arrays(
    swings: list[Swing],
    length: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Convert a swing list into two arrays of shape (*length*,):
    ``swing_high`` and ``swing_low`` (NaN where no swing).
    """
    swing_high = np.full(length, np.nan)
    swing_low = np.full(length, np.nan)
    for sw in swings:
        if sw.kind == "SH":
            swing_high[sw.bar] = sw.price
        else:
            swing_low[sw.bar] = sw.price
    return swing_high, swing_low


def determine_initial_structure(
    sh_list: list[Swing],
    sl_list: list[Swing],
) -> int | None:
    """
    From two lists (≥ 2 each), return initial trend direction:
    ``1`` (bull) if HH+HL, ``-1`` (bear) if LH+LL, else ``None``.
    """
    if len(sh_list) < 2 or len(sl_list) < 2:
        return None
    hh = sh_list[-1].price > sh_list[-2].price
    hl = sl_list[-1].price > sl_list[-2].price
    lh = sh_list[-1].price < sh_list[-2].price
    ll = sl_list[-1].price < sl_list[-2].price
    if hh and hl:
        return 1
    if lh and ll:
        return -1
    return None
