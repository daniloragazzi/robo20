"""
Indicator registry — auto-discovers all IndicatorPlugin implementations
and provides a central lookup and compute service.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from app.indicators.base import IndicatorPlugin
from app.indicators.builtins import (
    ATRIndicator,
    BollingerIndicator,
    EMAIndicator,
    MACDIndicator,
    RSIIndicator,
    SMAIndicator,
    StochasticIndicator,
    VolumeIndicator,
    VWAPIndicator,
)
from app.indicators.custom import (
    CHoCHIndicator,
    FibonacciIndicator,
    FVGIndicator,
    LateralizationIndicator,
    MSSIndicator,
)

logger = logging.getLogger(__name__)

# Global registry: name → instance
_registry: dict[str, IndicatorPlugin] = {}


def _register(plugin: IndicatorPlugin) -> None:
    if plugin.name in _registry:
        logger.warning("Duplicate indicator name %s — overwriting", plugin.name)
    _registry[plugin.name] = plugin


def _init_registry() -> None:
    """Register all known indicator plugins."""
    if _registry:
        return  # already initialized

    for cls in [
        # Built-ins
        EMAIndicator,
        SMAIndicator,
        RSIIndicator,
        MACDIndicator,
        BollingerIndicator,
        ATRIndicator,
        VolumeIndicator,
        StochasticIndicator,
        VWAPIndicator,
        # Custom / price-action
        MSSIndicator,
        FVGIndicator,
        CHoCHIndicator,
        LateralizationIndicator,
        FibonacciIndicator,
    ]:
        _register(cls())  # type: ignore[arg-type]

    logger.info("Indicator registry initialized: %d plugins", len(_registry))


def get_registry() -> dict[str, IndicatorPlugin]:
    """Return the full indicator registry, initializing if needed."""
    _init_registry()
    return _registry


def get_indicator(name: str) -> IndicatorPlugin:
    """Lookup an indicator by name. Raises KeyError if not found."""
    _init_registry()
    if name not in _registry:
        raise KeyError(f"Unknown indicator: {name}")
    return _registry[name]


def list_indicators() -> list[dict[str, Any]]:
    """Return metadata for all registered indicators."""
    _init_registry()
    return [
        {
            "name": ind.name,
            "display_name": ind.display_name,
            "params_schema": ind.params_schema,
        }
        for ind in _registry.values()
    ]


def compute_indicator(
    name: str,
    candles: pd.DataFrame,
    params: dict | None = None,
) -> pd.DataFrame:
    """Compute an indicator and return the full DataFrame with new columns."""
    ind = get_indicator(name)
    return ind.calculate(candles, params or {})
