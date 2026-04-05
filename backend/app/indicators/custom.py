"""
Custom price-action indicator plugins — MSS, FVG, CHoCH, Lateralization, Fibonacci.
These detect structural patterns in price data.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.indicators.swing import Swing, detect_swings, swings_to_arrays, determine_initial_structure


def _ts_column(break_start_ts: list, timestamps: np.ndarray, length: int) -> pd.array:
    """Convert a list of timestamp refs to an ISO-string pandas column."""
    col = pd.array([None] * length, dtype=object)
    for i in range(length):
        if break_start_ts[i] is not None:
            iso = pd.Timestamp(break_start_ts[i]).isoformat()
            if not iso.endswith('Z') and '+' not in iso:
                iso += 'Z'
            col[i] = iso
    return col


# ------------------------------------------------------------------ #
#  MSS — Market Structure Shift                                        #
# ------------------------------------------------------------------ #

class MSSIndicator:
    """
    Detects Market Structure Shifts by tracking swing highs/lows.
    - BULLISH: Higher High after a sequence of Lower Highs (break of structure up)
    - BEARISH: Lower Low after a sequence of Higher Lows (break of structure down)
    """

    name = "mss"
    display_name = "MSS (Market Structure Shift)"
    params_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "swing_length": {
                "type": "integer",
                "default": 5,
                "minimum": 2,
                "description": "Number of bars on each side to confirm a swing point",
            },
        },
        "required": ["swing_length"],
    }

    def calculate(self, candles: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = candles.copy()
        n = params.get("swing_length", 5)
        highs = df["high"].values
        lows = df["low"].values
        timestamps = df["ts"].values
        length = len(df)

        # ── 1–2. Detect swings with strict alternation ──────────────
        swings = detect_swings(highs, lows, n)
        swing_high, swing_low = swings_to_arrays(swings, length)

        mss_signal = np.full(length, np.nan)
        break_level = np.full(length, np.nan)
        break_start_ts = [None] * length

        # ── 3. MSS detection via level breaks ────────────────────────
        swing_at: dict[int, Swing] = {sw.bar: sw for sw in swings}

        current_structure: int | None = None
        watch_level: float | None = None
        watch_idx: int | None = None

        sh_list: list[Swing] = []
        sl_list: list[Swing] = []

        for i in range(length):
            if current_structure is not None and watch_level is not None:
                if current_structure == 1 and lows[i] < watch_level:
                    mss_signal[i] = -1
                    break_level[i] = watch_level
                    break_start_ts[i] = timestamps[watch_idx]
                    current_structure = -1
                    watch_level = sh_list[-1].price if sh_list else None
                    watch_idx = sh_list[-1].bar if sh_list else None
                elif current_structure == -1 and highs[i] > watch_level:
                    mss_signal[i] = 1
                    break_level[i] = watch_level
                    break_start_ts[i] = timestamps[watch_idx]
                    current_structure = 1
                    watch_level = sl_list[-1].price if sl_list else None
                    watch_idx = sl_list[-1].bar if sl_list else None

            if i in swing_at:
                sw = swing_at[i]
                if sw.kind == "SH":
                    sh_list.append(sw)
                else:
                    sl_list.append(sw)

                if current_structure is None:
                    direction = determine_initial_structure(sh_list, sl_list)
                    if direction is not None:
                        current_structure = direction
                        if direction == 1:
                            watch_level = sl_list[-1].price
                            watch_idx = sl_list[-1].bar
                        else:
                            watch_level = sh_list[-1].price
                            watch_idx = sh_list[-1].bar
                else:
                    if current_structure == 1 and sw.kind == "SL":
                        watch_level = sw.price
                        watch_idx = sw.bar
                    elif current_structure == -1 and sw.kind == "SH":
                        watch_level = sw.price
                        watch_idx = sw.bar

        df["mss_signal"] = mss_signal
        df["break_level"] = break_level
        df["swing_high"] = swing_high
        df["swing_low"] = swing_low
        df["break_start_ts"] = _ts_column(break_start_ts, timestamps, length)
        return df


# ------------------------------------------------------------------ #
#  FVG — Fair Value Gap                                                #
# ------------------------------------------------------------------ #

class FVGIndicator:
    """
    Detects Fair Value Gaps (imbalance zones) — 3-candle pattern where
    there's a gap between candle 1's range and candle 3's range.
    """

    name = "fvg"
    display_name = "FVG (Fair Value Gap)"
    params_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "min_gap_pct": {
                "type": "number",
                "default": 0.0,
                "minimum": 0.0,
                "description": "Minimum gap size as % of price to qualify",
            },
        },
    }

    def calculate(self, candles: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = candles.copy()
        min_gap_pct = params.get("min_gap_pct", 0.0)

        highs = df["high"].values
        lows = df["low"].values
        length = len(df)

        fvg_top = np.full(length, np.nan)
        fvg_bottom = np.full(length, np.nan)
        fvg_direction = np.full(length, np.nan)  # 1 = bullish, -1 = bearish

        for i in range(2, length):
            # Bullish FVG: candle 3's low > candle 1's high
            if lows[i] > highs[i - 2]:
                gap = lows[i] - highs[i - 2]
                mid_price = (lows[i] + highs[i - 2]) / 2
                if mid_price > 0 and (gap / mid_price * 100) >= min_gap_pct:
                    fvg_top[i] = lows[i]
                    fvg_bottom[i] = highs[i - 2]
                    fvg_direction[i] = 1

            # Bearish FVG: candle 3's high < candle 1's low
            elif highs[i] < lows[i - 2]:
                gap = lows[i - 2] - highs[i]
                mid_price = (lows[i - 2] + highs[i]) / 2
                if mid_price > 0 and (gap / mid_price * 100) >= min_gap_pct:
                    fvg_top[i] = lows[i - 2]
                    fvg_bottom[i] = highs[i]
                    fvg_direction[i] = -1

        df["fvg_top"] = fvg_top
        df["fvg_bottom"] = fvg_bottom
        df["fvg_direction"] = fvg_direction
        return df


# ------------------------------------------------------------------ #
#  CHoCH — Change of Character                                         #
# ------------------------------------------------------------------ #

class CHoCHIndicator:
    """
    Change of Character — fires on the *first* break of the immediately
    preceding opposite-type swing point.

    Unlike MSS (which needs a confirmed trend via HH+HL / LH+LL before
    it can fire), CHoCH does NOT require trend confirmation.
    It simply tracks the most recent SH and SL, and:
    - Bullish CHoCH: price breaks ABOVE the last SH
    - Bearish CHoCH: price breaks BELOW the last SL

    Each swing level is "consumed" once broken, so the same level
    can only produce one signal.

    Outputs: choch_signal (1/-1), break_level, break_start_ts,
             swing_high, swing_low (for zigzag rendering).
    """

    name = "choch"
    display_name = "CHoCH (Change of Character)"
    params_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "swing_length": {
                "type": "integer",
                "default": 5,
                "minimum": 2,
                "description": "Bars on each side to confirm swing point",
            },
        },
        "required": ["swing_length"],
    }

    def calculate(self, candles: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = candles.copy()
        n = params.get("swing_length", 5)
        highs = df["high"].values
        lows = df["low"].values
        timestamps = df["ts"].values
        length = len(df)

        swings = detect_swings(highs, lows, n)
        swing_high, swing_low = swings_to_arrays(swings, length)

        choch_signal = np.full(length, np.nan)
        break_level = np.full(length, np.nan)
        break_start_ts = [None] * length

        # Track the latest unbroken SH and SL
        active_sh: Swing | None = None  # last swing high not yet broken
        active_sl: Swing | None = None  # last swing low  not yet broken

        swing_at: dict[int, Swing] = {sw.bar: sw for sw in swings}

        for i in range(length):
            # ─ A. Check for break of the active opposite swing ─
            # Bullish CHoCH: price breaks above the last swing high
            if active_sh is not None and highs[i] > active_sh.price:
                choch_signal[i] = 1
                break_level[i] = active_sh.price
                break_start_ts[i] = timestamps[active_sh.bar]
                active_sh = None  # consumed

            # Bearish CHoCH: price breaks below the last swing low
            if active_sl is not None and lows[i] < active_sl.price:
                choch_signal[i] = -1
                break_level[i] = active_sl.price
                break_start_ts[i] = timestamps[active_sl.bar]
                active_sl = None  # consumed

            # ─ B. Update active swings when a new one is confirmed ─
            if i in swing_at:
                sw = swing_at[i]
                if sw.kind == "SH":
                    active_sh = sw
                else:
                    active_sl = sw

        df["choch_signal"] = choch_signal
        df["break_level"] = break_level
        df["swing_high"] = swing_high
        df["swing_low"] = swing_low
        df["break_start_ts"] = _ts_column(break_start_ts, timestamps, length)
        return df


# ------------------------------------------------------------------ #
#  Lateralization — Range / Consolidation Detection                    #
# ------------------------------------------------------------------ #

class LateralizationIndicator:
    """
    Detects consolidation (ranging) zones and signals when price breaks out.

    Uses the shared zigzag swing detection.  A *range* is identified when
    consecutive swing highs and lows stay within a tolerance band —
    i.e., neither HH+HL nor LH+LL patterns form.

    Outputs:
    - ``range_top`` / ``range_bottom``: upper/lower bounds while ranging.
    - ``range_signal``: ``1`` = bullish breakout (close above range_top),
      ``-1`` = bearish breakout (close below range_bottom).
    - ``swing_high`` / ``swing_low``: zigzag for rendering.
    - ``break_start_ts``: timestamp of the swing that defined the broken bound.
    """

    name = "lateralization"
    display_name = "Lateralization (Range Breakout)"
    params_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "swing_length": {
                "type": "integer",
                "default": 5,
                "minimum": 2,
                "description": "Bars on each side to confirm swing point",
            },
            "min_touches": {
                "type": "integer",
                "default": 3,
                "minimum": 2,
                "description": "Minimum swing touches (SH+SL) to qualify as a range",
            },
            "tolerance_pct": {
                "type": "number",
                "default": 0.3,
                "minimum": 0.0,
                "description": "% tolerance for considering swings within the range band",
            },
        },
        "required": ["swing_length"],
    }

    def calculate(self, candles: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = candles.copy()
        n = params.get("swing_length", 5)
        min_touches = params.get("min_touches", 3)
        tol_pct = params.get("tolerance_pct", 0.3) / 100.0
        highs = df["high"].values
        lows = df["low"].values
        closes = df["close"].values
        timestamps = df["ts"].values
        length = len(df)

        swings = detect_swings(highs, lows, n)
        swing_high, swing_low = swings_to_arrays(swings, length)

        range_top_arr = np.full(length, np.nan)
        range_bottom_arr = np.full(length, np.nan)
        range_signal = np.full(length, np.nan)
        break_level_arr = np.full(length, np.nan)
        break_start_ts = [None] * length

        # Sliding window of recent swings to detect range
        swing_at: dict[int, Swing] = {sw.bar: sw for sw in swings}
        recent_swings: list[Swing] = []
        in_range = False
        r_top: float = 0.0
        r_bottom: float = 0.0
        r_top_bar: int = 0
        r_bottom_bar: int = 0

        for i in range(length):
            # Update swings
            if i in swing_at:
                recent_swings.append(swing_at[i])

            # ─ A. While in range: check for breakout first ─
            if in_range:
                range_top_arr[i] = r_top
                range_bottom_arr[i] = r_bottom

                if closes[i] > r_top:
                    range_signal[i] = 1
                    break_level_arr[i] = r_top
                    break_start_ts[i] = timestamps[r_top_bar]
                    in_range = False
                    recent_swings = recent_swings[-2:]
                    continue
                elif closes[i] < r_bottom:
                    range_signal[i] = -1
                    break_level_arr[i] = r_bottom
                    break_start_ts[i] = timestamps[r_bottom_bar]
                    in_range = False
                    recent_swings = recent_swings[-2:]
                    continue

                # Update range bounds if a new swing lands inside the range
                if i in swing_at:
                    sw = swing_at[i]
                    if sw.kind == "SH" and sw.price > r_top:
                        r_top = sw.price
                        r_top_bar = sw.bar
                    elif sw.kind == "SL" and sw.price < r_bottom:
                        r_bottom = sw.price
                        r_bottom_bar = sw.bar
                continue

            # ─ B. Not in range: try to detect a new one ─
            if len(recent_swings) >= min_touches:
                sh_prices = [s.price for s in recent_swings if s.kind == "SH"]
                sl_prices = [s.price for s in recent_swings if s.kind == "SL"]

                if sh_prices and sl_prices:
                    top = max(sh_prices)
                    bottom = min(sl_prices)
                    band = top - bottom

                    if band > 0:
                        mid = (top + bottom) / 2.0
                        is_narrow = (band / mid) <= tol_pct * 3

                        shs = [s for s in recent_swings if s.kind == "SH"]
                        sls = [s for s in recent_swings if s.kind == "SL"]
                        trending = False
                        if len(shs) >= 2 and len(sls) >= 2:
                            hh = shs[-1].price > shs[-2].price
                            hl = sls[-1].price > sls[-2].price
                            lh = shs[-1].price < shs[-2].price
                            ll = sls[-1].price < sls[-2].price
                            trending = (hh and hl) or (lh and ll)

                        if is_narrow and not trending:
                            in_range = True
                            r_top = top
                            r_bottom = bottom
                            for s in reversed(recent_swings):
                                if s.kind == "SH" and s.price == top:
                                    r_top_bar = s.bar
                                    break
                            for s in reversed(recent_swings):
                                if s.kind == "SL" and s.price == bottom:
                                    r_bottom_bar = s.bar
                                    break
                            range_top_arr[i] = r_top
                            range_bottom_arr[i] = r_bottom
                        else:
                            if len(recent_swings) > min_touches + 2:
                                recent_swings = recent_swings[-(min_touches + 2):]

        df["range_top"] = range_top_arr
        df["range_bottom"] = range_bottom_arr
        df["range_signal"] = range_signal
        df["break_level"] = break_level_arr
        df["swing_high"] = swing_high
        df["swing_low"] = swing_low
        df["break_start_ts"] = _ts_column(break_start_ts, timestamps, length)
        return df


# ------------------------------------------------------------------ #
#  Fibonacci Retracement                                               #
# ------------------------------------------------------------------ #

class FibonacciIndicator:
    """
    Auto-detects the most recent significant swing high/low and calculates
    Fibonacci retracement levels. Emits a signal when price reaches a
    configured level.
    """

    name = "fibonacci"
    display_name = "Fibonacci Retracement"
    params_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "swing_length": {
                "type": "integer",
                "default": 20,
                "minimum": 5,
                "description": "Lookback bars for swing high/low detection",
            },
            "signal_level": {
                "type": "number",
                "default": 0.618,
                "description": "Fibonacci level to trigger signal (0.236, 0.382, 0.5, 0.618, 0.786)",
            },
            "levels": {
                "type": "array",
                "default": [0.236, 0.382, 0.5, 0.618, 0.786],
                "description": "Fibonacci levels to calculate and display",
            },
        },
        "required": ["swing_length"],
    }

    def calculate(self, candles: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = candles.copy()
        n = params.get("swing_length", 20)
        signal_level = params.get("signal_level", 0.618)
        levels = params.get("levels", [0.236, 0.382, 0.5, 0.618, 0.786])
        highs = df["high"].values
        lows = df["low"].values
        length = len(df)

        # Initialize level columns
        for lvl in levels:
            df[f"fib_{lvl}"] = np.nan
        df["fib_direction"] = np.nan  # 1 = uptrend retracement, -1 = downtrend retracement
        df["fib_signal"] = np.nan     # 1 = price at signal level

        # Find the most recent significant high and low within lookback window
        for i in range(n, length):
            window_high_idx = int(np.argmax(highs[i - n : i + 1])) + (i - n)
            window_low_idx = int(np.argmin(lows[i - n : i + 1])) + (i - n)
            swing_high = highs[window_high_idx]
            swing_low = lows[window_low_idx]
            diff = swing_high - swing_low

            if diff <= 0:
                continue

            # Uptrend retracement (high came after low)
            if window_high_idx > window_low_idx:
                df.loc[df.index[i], "fib_direction"] = 1
                for lvl in levels:
                    val = swing_high - diff * lvl
                    df.loc[df.index[i], f"fib_{lvl}"] = val
                # Check signal
                target = swing_high - diff * signal_level
                if abs(lows[i] - target) / diff < 0.02 or \
                   (lows[i] <= target <= highs[i]):
                    df.loc[df.index[i], "fib_signal"] = 1
            else:
                # Downtrend retracement (low came after high)
                df.loc[df.index[i], "fib_direction"] = -1
                for lvl in levels:
                    val = swing_low + diff * lvl
                    df.loc[df.index[i], f"fib_{lvl}"] = val
                target = swing_low + diff * signal_level
                if abs(highs[i] - target) / diff < 0.02 or \
                   (lows[i] <= target <= highs[i]):
                    df.loc[df.index[i], "fib_signal"] = 1

        return df
