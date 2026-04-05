"""
IndicatorPlugin — Protocol that all indicator plugins must satisfy.
Plugins are auto-discovered at startup from this package.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class IndicatorPlugin(Protocol):
    name: str          # unique machine-readable key, e.g. "ema"
    display_name: str  # human label shown in Strategy Builder, e.g. "EMA"
    params_schema: dict  # JSON Schema describing accepted params

    def calculate(
        self,
        candles: pd.DataFrame,
        params: dict,
    ) -> pd.DataFrame:
        """
        Receive a DataFrame with columns [ts, open, high, low, close, volume]
        and return a new DataFrame with the indicator column(s) appended.
        The input DataFrame must not be mutated.
        """
        ...
