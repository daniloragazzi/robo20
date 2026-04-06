"""
StateEngine — evaluates strategy steps sequentially against indicator data.

Each strategy is a linear sequence of steps (conditions). The engine keeps
track of the *current step index* and, on each tick (new candle), checks
whether the current step's condition is satisfied. When satisfied it
advances to the next step. When all steps are satisfied it emits a SIGNAL
event and resets to step 0.

Steps support compound conditions via AND / OR grouping:

    ConditionLeaf  — a single indicator check
    ConditionGroup — AND / OR with nested children (leaf or group)

Example tree for "(RSI 1h > 70 AND CHoCH BEAR) OR (RSI 1h < 30 AND CHoCH BULL)":

    ConditionGroup("or", [
        ConditionGroup("and", [
            ConditionLeaf("rsi", "gt", "70"),
            ConditionLeaf("choch", "signal_bear"),
        ]),
        ConditionGroup("and", [
            ConditionLeaf("rsi", "lt", "30"),
            ConditionLeaf("choch", "signal_bull"),
        ]),
    ])

For backward compatibility, StepDef still accepts flat fields (indicator_type,
condition_type, etc.) which are auto-wrapped into a single ConditionLeaf.

Supported condition_type values:
  "gt"          — indicator value > threshold
  "lt"          — indicator value < threshold
  "gte"         — indicator value >= threshold
  "lte"         — indicator value <= threshold
  "eq"          — indicator value == threshold
  "cross_above" — value was <= threshold on previous tick, now > threshold
  "cross_below" — value was >= threshold on previous tick, now < threshold
  "signal_bull" — indicator signal column > 0  (for MSS, CHoCH, etc.)
  "signal_bear" — indicator signal column < 0
  "in_range"    — for lateralization: currently inside range
  "breakout"    — for lateralization: range_signal != 0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Union

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    STEP_ADVANCED = "step_advanced"
    SIGNAL = "signal"           # all steps satisfied
    RESET = "reset"


# ------------------------------------------------------------------ #
#  Condition tree                                                      #
# ------------------------------------------------------------------ #


@dataclass
class ConditionLeaf:
    """Single indicator condition."""
    indicator_type: str
    condition_type: str
    condition_value: str | None = None
    output_key: str | None = None


@dataclass
class ConditionGroup:
    """AND / OR group of conditions (can be nested)."""
    logic: str  # "and" | "or"
    conditions: list[Union[ConditionLeaf, ConditionGroup]] = field(default_factory=list)


ConditionNode = Union[ConditionLeaf, ConditionGroup]


def condition_from_dict(d: dict[str, Any]) -> ConditionNode:
    """Deserialise a JSON dict into a ConditionNode tree."""
    node_type = d.get("type", "condition")
    if node_type in ("and", "or"):
        children = [condition_from_dict(c) for c in d.get("conditions", [])]
        return ConditionGroup(logic=node_type, conditions=children)
    return ConditionLeaf(
        indicator_type=d.get("indicator_type", ""),
        condition_type=d.get("condition_type", ""),
        condition_value=d.get("condition_value"),
        output_key=d.get("output_key"),
    )


def condition_to_dict(node: ConditionNode) -> dict[str, Any]:
    """Serialise a ConditionNode tree into a JSON-safe dict."""
    if isinstance(node, ConditionGroup):
        return {
            "type": node.logic,
            "conditions": [condition_to_dict(c) for c in node.conditions],
        }
    d: dict[str, Any] = {
        "type": "condition",
        "indicator_type": node.indicator_type,
        "condition_type": node.condition_type,
    }
    if node.condition_value is not None:
        d["condition_value"] = node.condition_value
    if node.output_key is not None:
        d["output_key"] = node.output_key
    return d


# ------------------------------------------------------------------ #
#  Step definition                                                     #
# ------------------------------------------------------------------ #


@dataclass
class StepDef:
    """One step in the strategy sequence.

    Supports two modes:
      1. **Tree mode** — set ``condition`` to a ``ConditionNode``.
      2. **Legacy flat mode** — set ``indicator_type``, ``condition_type``,
         etc. directly. Internally converted to a ``ConditionLeaf``.
    """
    step_index: int
    # Tree mode
    condition: ConditionNode | None = None
    # Legacy flat fields (used when condition is None)
    indicator_type: str | None = None
    condition_type: str | None = None
    condition_value: str | None = None
    output_key: str | None = None
    description: str | None = None

    def get_condition(self) -> ConditionNode:
        if self.condition is not None:
            return self.condition
        return ConditionLeaf(
            indicator_type=self.indicator_type or "",
            condition_type=self.condition_type or "",
            condition_value=self.condition_value,
            output_key=self.output_key,
        )


@dataclass
class EngineEvent:
    event_type: EventType
    step_index: int
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class EngineState:
    """Mutable state tracked per execution."""
    current_step: int = 0
    prev_values: dict[str, float | None] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------------ #
#  Condition evaluators                                                #
# ------------------------------------------------------------------ #

def _to_float(v: str | None) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _eval_compare(op: str, value: float | None, threshold: float | None) -> bool:
    if value is None or threshold is None:
        return False
    if op == "gt":
        return value > threshold
    if op == "lt":
        return value < threshold
    if op == "gte":
        return value >= threshold
    if op == "lte":
        return value <= threshold
    if op == "eq":
        return value == threshold
    return False


def _eval_cross(direction: str, current: float | None, prev: float | None, threshold: float | None) -> bool:
    if current is None or prev is None or threshold is None:
        return False
    if direction == "above":
        return prev <= threshold and current > threshold
    if direction == "below":
        return prev >= threshold and current < threshold
    return False


# ------------------------------------------------------------------ #
#  Engine                                                              #
# ------------------------------------------------------------------ #

class StateEngine:
    """
    Evaluate a strategy definition against indicator snapshots.

    Usage:
        engine = StateEngine(steps=[...])
        state = EngineState()
        events = engine.evaluate(state, indicator_snapshot)
    """

    def __init__(self, steps: list[StepDef]) -> None:
        # Sort steps by index
        self.steps = sorted(steps, key=lambda s: s.step_index)
        if not self.steps:
            raise ValueError("Strategy must have at least one step")

    # ------------------------------------------------------------------ #

    def evaluate(
        self,
        state: EngineState,
        indicator_values: dict[str, dict[str, float | None]],
    ) -> list[EngineEvent]:
        """
        Evaluate current step condition.

        Args:
            state: mutable execution state
            indicator_values: mapping of indicator_type → {output_key: value}
                              e.g. {"rsi": {"RSI_14": 28.5}, "mss": {"mss_signal": 1.0}}

        Returns:
            list of events produced (may be empty, one STEP_ADVANCED, or SIGNAL).
        """
        events: list[EngineEvent] = []

        if state.current_step >= len(self.steps):
            # Already signalled — do nothing until reset
            return events

        step = self.steps[state.current_step]
        node = step.get_condition()
        satisfied = self._eval_node(state, node, indicator_values)

        if satisfied:
            events.append(EngineEvent(
                event_type=EventType.STEP_ADVANCED,
                step_index=step.step_index,
                detail={"description": step.description or "step satisfied"},
            ))
            state.current_step += 1

            # All steps satisfied → signal
            if state.current_step >= len(self.steps):
                events.append(EngineEvent(
                    event_type=EventType.SIGNAL,
                    step_index=step.step_index,
                    detail={"message": "All steps satisfied"},
                ))

        # Store current values as prev for cross detection
        for ind_type, vals in indicator_values.items():
            for key, val in vals.items():
                state.prev_values[f"{ind_type}.{key}"] = val

        return events

    def reset(self, state: EngineState) -> EngineEvent:
        """Reset execution to step 0."""
        state.current_step = 0
        state.prev_values.clear()
        state.context.clear()
        return EngineEvent(event_type=EventType.RESET, step_index=0)

    # ------------------------------------------------------------------ #
    #  Recursive condition evaluator                                      #
    # ------------------------------------------------------------------ #

    def _eval_node(
        self,
        state: EngineState,
        node: ConditionNode,
        indicator_values: dict[str, dict[str, float | None]],
    ) -> bool:
        if isinstance(node, ConditionGroup):
            if node.logic == "and":
                return all(
                    self._eval_node(state, c, indicator_values)
                    for c in node.conditions
                )
            if node.logic == "or":
                return any(
                    self._eval_node(state, c, indicator_values)
                    for c in node.conditions
                )
            return False
        # ConditionLeaf
        return self._eval_leaf(state, node, indicator_values)

    def _eval_leaf(
        self,
        state: EngineState,
        leaf: ConditionLeaf,
        indicator_values: dict[str, dict[str, float | None]],
    ) -> bool:
        ind_data = indicator_values.get(leaf.indicator_type, {})
        if not ind_data:
            return False

        ctype = leaf.condition_type
        threshold = _to_float(leaf.condition_value)

        # Determine which output key to use
        output_key = leaf.output_key
        if not output_key:
            output_key = self._default_output_key(leaf.indicator_type, ind_data)
        if not output_key:
            return False

        current_val = ind_data.get(output_key)

        # Signal-type conditions (no threshold needed)
        if ctype == "signal_bull":
            return current_val is not None and current_val > 0
        if ctype == "signal_bear":
            return current_val is not None and current_val < 0
        if ctype == "in_range":
            rt = ind_data.get("range_top")
            rb = ind_data.get("range_bottom")
            return rt is not None and rb is not None
        if ctype == "breakout":
            sig = ind_data.get("range_signal")
            return sig is not None and sig != 0

        # Comparison conditions
        if ctype in ("gt", "lt", "gte", "lte", "eq"):
            val = current_val if isinstance(current_val, (int, float)) else _to_float(str(current_val)) if current_val is not None else None
            return _eval_compare(ctype, val, threshold)

        # Cross conditions
        if ctype in ("cross_above", "cross_below"):
            prev_key = f"{leaf.indicator_type}.{output_key}"
            prev_val = state.prev_values.get(prev_key)
            val = current_val if isinstance(current_val, (int, float)) else _to_float(str(current_val)) if current_val is not None else None
            direction = "above" if ctype == "cross_above" else "below"
            return _eval_cross(direction, val, prev_val, threshold)

        logger.warning("Unknown condition_type: %s", ctype)
        return False

    def _default_output_key(self, indicator_type: str, ind_data: dict[str, float | None]) -> str | None:
        """Pick the most likely output key for a given indicator type."""
        # Well-known mappings
        defaults: dict[str, str] = {
            "rsi": "RSI_14",
            "ema": "EMA_20",
            "sma": "SMA_20",
            "mss": "mss_signal",
            "choch": "choch_signal",
            "lateralization": "range_signal",
            "fvg": "fvg_direction",
        }
        if indicator_type in defaults and defaults[indicator_type] in ind_data:
            return defaults[indicator_type]
        # Fallback: first key with a non-None value
        for k, v in ind_data.items():
            if v is not None:
                return k
        return next(iter(ind_data), None)
