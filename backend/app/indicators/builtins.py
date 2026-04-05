"""
Built-in indicator plugins — pandas-ta wrappers implementing IndicatorPlugin.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pandas_ta as ta


# ------------------------------------------------------------------ #
#  EMA — Exponential Moving Average                                    #
# ------------------------------------------------------------------ #

class EMAIndicator:
    name = "ema"
    display_name = "EMA"
    params_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "length": {"type": "integer", "default": 20, "minimum": 1, "description": "EMA period"},
            "color": {"type": "string", "default": "#f59e0b"},
        },
        "required": ["length"],
    }

    def calculate(self, candles: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = candles.copy()
        length = params.get("length", 20)
        col = f"ema_{length}"
        df[col] = ta.ema(df["close"], length=length)
        return df


# ------------------------------------------------------------------ #
#  SMA — Simple Moving Average                                         #
# ------------------------------------------------------------------ #

class SMAIndicator:
    name = "sma"
    display_name = "SMA"
    params_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "length": {"type": "integer", "default": 50, "minimum": 1, "description": "SMA period"},
            "color": {"type": "string", "default": "#3b82f6"},
        },
        "required": ["length"],
    }

    def calculate(self, candles: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = candles.copy()
        length = params.get("length", 50)
        col = f"sma_{length}"
        df[col] = ta.sma(df["close"], length=length)
        return df


# ------------------------------------------------------------------ #
#  RSI — Relative Strength Index                                       #
# ------------------------------------------------------------------ #

class RSIIndicator:
    name = "rsi"
    display_name = "RSI"
    params_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "length": {"type": "integer", "default": 14, "minimum": 1, "description": "RSI period"},
            "overbought": {"type": "number", "default": 70, "description": "Overbought level"},
            "oversold": {"type": "number", "default": 30, "description": "Oversold level"},
            "color": {"type": "string", "default": "#a855f7"},
        },
        "required": ["length"],
    }

    def calculate(self, candles: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = candles.copy()
        length = params.get("length", 14)
        df[f"rsi_{length}"] = ta.rsi(df["close"], length=length)
        return df


# ------------------------------------------------------------------ #
#  MACD — Moving Average Convergence Divergence                        #
# ------------------------------------------------------------------ #

class MACDIndicator:
    name = "macd"
    display_name = "MACD"
    params_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "fast": {"type": "integer", "default": 12, "minimum": 1},
            "slow": {"type": "integer", "default": 26, "minimum": 1},
            "signal": {"type": "integer", "default": 9, "minimum": 1},
        },
        "required": ["fast", "slow", "signal"],
    }

    def calculate(self, candles: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = candles.copy()
        fast = params.get("fast", 12)
        slow = params.get("slow", 26)
        signal = params.get("signal", 9)
        macd_df = ta.macd(df["close"], fast=fast, slow=slow, signal=signal)
        if macd_df is not None:
            for col in macd_df.columns:
                df[col] = macd_df[col]
        return df


# ------------------------------------------------------------------ #
#  Bollinger Bands                                                     #
# ------------------------------------------------------------------ #

class BollingerIndicator:
    name = "bbands"
    display_name = "Bollinger Bands"
    params_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "length": {"type": "integer", "default": 20, "minimum": 1},
            "std": {"type": "number", "default": 2.0, "minimum": 0.1},
        },
        "required": ["length", "std"],
    }

    def calculate(self, candles: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = candles.copy()
        length = params.get("length", 20)
        std = params.get("std", 2.0)
        bb = ta.bbands(df["close"], length=length, std=std)
        if bb is not None:
            for col in bb.columns:
                df[col] = bb[col]
        return df


# ------------------------------------------------------------------ #
#  ATR — Average True Range                                            #
# ------------------------------------------------------------------ #

class ATRIndicator:
    name = "atr"
    display_name = "ATR"
    params_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "length": {"type": "integer", "default": 14, "minimum": 1},
        },
        "required": ["length"],
    }

    def calculate(self, candles: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = candles.copy()
        length = params.get("length", 14)
        df[f"atr_{length}"] = ta.atr(df["high"], df["low"], df["close"], length=length)
        return df


# ------------------------------------------------------------------ #
#  Volume (displayed as histogram)                                     #
# ------------------------------------------------------------------ #

class VolumeIndicator:
    name = "volume"
    display_name = "Volume"
    params_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "sma_length": {"type": "integer", "default": 20, "minimum": 1, "description": "Volume SMA overlay"},
        },
    }

    def calculate(self, candles: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = candles.copy()
        sma_length = params.get("sma_length", 20)
        df["vol_sma"] = ta.sma(df["volume"], length=sma_length)
        return df


# ------------------------------------------------------------------ #
#  Stochastic                                                          #
# ------------------------------------------------------------------ #

class StochasticIndicator:
    name = "stoch"
    display_name = "Stochastic"
    params_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "k": {"type": "integer", "default": 14, "minimum": 1},
            "d": {"type": "integer", "default": 3, "minimum": 1},
            "smooth_k": {"type": "integer", "default": 3, "minimum": 1},
        },
        "required": ["k", "d"],
    }

    def calculate(self, candles: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = candles.copy()
        k = params.get("k", 14)
        d = params.get("d", 3)
        smooth_k = params.get("smooth_k", 3)
        stoch = ta.stoch(df["high"], df["low"], df["close"], k=k, d=d, smooth_k=smooth_k)
        if stoch is not None:
            for col in stoch.columns:
                df[col] = stoch[col]
        return df


# ------------------------------------------------------------------ #
#  VWAP — Volume Weighted Average Price                                #
# ------------------------------------------------------------------ #

class VWAPIndicator:
    name = "vwap"
    display_name = "VWAP"
    params_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "color": {"type": "string", "default": "#06b6d4"},
        },
    }

    def calculate(self, candles: pd.DataFrame, params: dict) -> pd.DataFrame:
        df = candles.copy()
        # pandas-ta vwap requires a DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
            if "ts" in df.columns:
                df = df.set_index(pd.DatetimeIndex(df["ts"]))
            else:
                # Fallback: manual VWAP calculation
                tp = (df["high"] + df["low"] + df["close"]) / 3
                df["vwap"] = (tp * df["volume"]).cumsum() / df["volume"].cumsum()
                return df
        vwap = ta.vwap(df["high"], df["low"], df["close"], df["volume"])
        if vwap is not None:
            df["vwap"] = vwap
        # Restore original index so ts column stays
        df = df.reset_index(drop=True)
        df["ts"] = candles["ts"].values
        return df
