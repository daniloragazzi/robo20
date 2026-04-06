"""
Unit tests for the StateEngine — strategy state machine.
"""

import pytest

from app.statemachine.engine import (
    ConditionGroup,
    ConditionLeaf,
    EngineEvent,
    EngineState,
    EventType,
    StateEngine,
    StepDef,
    condition_from_dict,
    condition_to_dict,
)


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #


def _rsi_step(index: int, condition: str, value: str, output_key: str = "RSI_14") -> StepDef:
    return StepDef(
        step_index=index,
        indicator_type="rsi",
        condition_type=condition,
        condition_value=value,
        output_key=output_key,
    )


def _mss_step(index: int, condition: str = "signal_bull") -> StepDef:
    return StepDef(
        step_index=index,
        indicator_type="mss",
        condition_type=condition,
        output_key="mss_signal",
    )


# ------------------------------------------------------------------ #
#  Basic construction                                                  #
# ------------------------------------------------------------------ #


class TestEngineConstruction:
    def test_requires_at_least_one_step(self):
        with pytest.raises(ValueError, match="at least one step"):
            StateEngine(steps=[])

    def test_steps_sorted_by_index(self):
        s2 = _rsi_step(2, "lt", "30")
        s0 = _rsi_step(0, "gt", "70")
        s1 = _mss_step(1)
        engine = StateEngine(steps=[s2, s0, s1])
        assert [s.step_index for s in engine.steps] == [0, 1, 2]


# ------------------------------------------------------------------ #
#  Comparison conditions                                               #
# ------------------------------------------------------------------ #


class TestComparisonConditions:
    def test_gt_satisfied(self):
        engine = StateEngine(steps=[_rsi_step(0, "gt", "70")])
        state = EngineState()
        events = engine.evaluate(state, {"rsi": {"RSI_14": 72.0}})
        assert len(events) == 2  # STEP_ADVANCED + SIGNAL (single step)
        assert events[0].event_type == EventType.STEP_ADVANCED
        assert events[1].event_type == EventType.SIGNAL

    def test_gt_not_satisfied(self):
        engine = StateEngine(steps=[_rsi_step(0, "gt", "70")])
        state = EngineState()
        events = engine.evaluate(state, {"rsi": {"RSI_14": 65.0}})
        assert events == []

    def test_lt_satisfied(self):
        engine = StateEngine(steps=[_rsi_step(0, "lt", "30")])
        state = EngineState()
        events = engine.evaluate(state, {"rsi": {"RSI_14": 25.0}})
        assert len(events) == 2

    def test_gte_boundary(self):
        engine = StateEngine(steps=[_rsi_step(0, "gte", "30")])
        state = EngineState()
        events = engine.evaluate(state, {"rsi": {"RSI_14": 30.0}})
        assert events[0].event_type == EventType.STEP_ADVANCED

    def test_lte_boundary(self):
        engine = StateEngine(steps=[_rsi_step(0, "lte", "70")])
        state = EngineState()
        events = engine.evaluate(state, {"rsi": {"RSI_14": 70.0}})
        assert events[0].event_type == EventType.STEP_ADVANCED

    def test_eq(self):
        engine = StateEngine(steps=[_rsi_step(0, "eq", "50")])
        state = EngineState()
        events = engine.evaluate(state, {"rsi": {"RSI_14": 50.0}})
        assert events[0].event_type == EventType.STEP_ADVANCED

    def test_none_value_not_satisfied(self):
        engine = StateEngine(steps=[_rsi_step(0, "gt", "30")])
        state = EngineState()
        events = engine.evaluate(state, {"rsi": {"RSI_14": None}})
        assert events == []

    def test_missing_indicator_not_satisfied(self):
        engine = StateEngine(steps=[_rsi_step(0, "gt", "30")])
        state = EngineState()
        events = engine.evaluate(state, {})
        assert events == []


# ------------------------------------------------------------------ #
#  Cross conditions                                                    #
# ------------------------------------------------------------------ #


class TestCrossConditions:
    def test_cross_above(self):
        engine = StateEngine(steps=[_rsi_step(0, "cross_above", "30")])
        state = EngineState()

        # Tick 1: below threshold — not satisfied
        events = engine.evaluate(state, {"rsi": {"RSI_14": 28.0}})
        assert events == []

        # Tick 2: crosses above — satisfied
        events = engine.evaluate(state, {"rsi": {"RSI_14": 32.0}})
        assert events[0].event_type == EventType.STEP_ADVANCED

    def test_cross_below(self):
        engine = StateEngine(steps=[_rsi_step(0, "cross_below", "70")])
        state = EngineState()

        # Tick 1: above threshold
        events = engine.evaluate(state, {"rsi": {"RSI_14": 75.0}})
        assert events == []

        # Tick 2: crosses below
        events = engine.evaluate(state, {"rsi": {"RSI_14": 68.0}})
        assert events[0].event_type == EventType.STEP_ADVANCED

    def test_cross_above_no_prev(self):
        """With no previous value, cross cannot be detected."""
        engine = StateEngine(steps=[_rsi_step(0, "cross_above", "30")])
        state = EngineState()
        events = engine.evaluate(state, {"rsi": {"RSI_14": 32.0}})
        assert events == []  # no prev → cannot detect cross

    def test_already_above_not_cross(self):
        engine = StateEngine(steps=[_rsi_step(0, "cross_above", "30")])
        state = EngineState()

        # Both above — not a cross
        engine.evaluate(state, {"rsi": {"RSI_14": 35.0}})
        events = engine.evaluate(state, {"rsi": {"RSI_14": 40.0}})
        assert events == []


# ------------------------------------------------------------------ #
#  Signal-type conditions                                              #
# ------------------------------------------------------------------ #


class TestSignalConditions:
    def test_signal_bull(self):
        engine = StateEngine(steps=[_mss_step(0, "signal_bull")])
        state = EngineState()
        events = engine.evaluate(state, {"mss": {"mss_signal": 1.0}})
        assert events[0].event_type == EventType.STEP_ADVANCED

    def test_signal_bull_zero(self):
        engine = StateEngine(steps=[_mss_step(0, "signal_bull")])
        state = EngineState()
        events = engine.evaluate(state, {"mss": {"mss_signal": 0.0}})
        assert events == []

    def test_signal_bear(self):
        engine = StateEngine(steps=[_mss_step(0, "signal_bear")])
        state = EngineState()
        events = engine.evaluate(state, {"mss": {"mss_signal": -1.0}})
        assert events[0].event_type == EventType.STEP_ADVANCED

    def test_signal_bear_positive(self):
        engine = StateEngine(steps=[_mss_step(0, "signal_bear")])
        state = EngineState()
        events = engine.evaluate(state, {"mss": {"mss_signal": 1.0}})
        assert events == []


# ------------------------------------------------------------------ #
#  Multi-step strategies                                               #
# ------------------------------------------------------------------ #


class TestMultiStep:
    def test_three_step_rsi_mss_fib(self):
        """Classic RSI oversold → MSS bull → then signal."""
        steps = [
            _rsi_step(0, "lt", "30"),
            _mss_step(1, "signal_bull"),
            StepDef(
                step_index=2,
                indicator_type="fibonacci",
                condition_type="gt",
                condition_value="0",
                output_key="fib_signal",
            ),
        ]
        engine = StateEngine(steps=steps)
        state = EngineState()

        # Step 0: RSI not yet below 30
        events = engine.evaluate(state, {"rsi": {"RSI_14": 45.0}})
        assert events == []
        assert state.current_step == 0

        # Step 0: RSI below 30 → advance
        events = engine.evaluate(state, {"rsi": {"RSI_14": 25.0}})
        assert len(events) == 1
        assert events[0].event_type == EventType.STEP_ADVANCED
        assert state.current_step == 1

        # Step 1: MSS no signal yet
        events = engine.evaluate(state, {"mss": {"mss_signal": 0.0}})
        assert events == []
        assert state.current_step == 1

        # Step 1: MSS bullish signal → advance
        events = engine.evaluate(state, {"mss": {"mss_signal": 1.0}})
        assert len(events) == 1
        assert events[0].event_type == EventType.STEP_ADVANCED
        assert state.current_step == 2

        # Step 2: Fibonacci not triggered
        events = engine.evaluate(state, {"fibonacci": {"fib_signal": 0.0}})
        assert events == []
        assert state.current_step == 2

        # Step 2: Fibonacci triggered → SIGNAL
        events = engine.evaluate(state, {"fibonacci": {"fib_signal": 1.0}})
        assert len(events) == 2
        assert events[0].event_type == EventType.STEP_ADVANCED
        assert events[1].event_type == EventType.SIGNAL
        assert state.current_step == 3  # past last

    def test_does_nothing_after_signal(self):
        engine = StateEngine(steps=[_rsi_step(0, "lt", "30")])
        state = EngineState()

        engine.evaluate(state, {"rsi": {"RSI_14": 25.0}})
        assert state.current_step == 1

        # Further evaluations produce nothing
        events = engine.evaluate(state, {"rsi": {"RSI_14": 20.0}})
        assert events == []


# ------------------------------------------------------------------ #
#  Reset                                                               #
# ------------------------------------------------------------------ #


class TestReset:
    def test_reset_clears_state(self):
        engine = StateEngine(steps=[_rsi_step(0, "lt", "30")])
        state = EngineState()

        engine.evaluate(state, {"rsi": {"RSI_14": 25.0}})
        assert state.current_step == 1

        event = engine.reset(state)
        assert event.event_type == EventType.RESET
        assert state.current_step == 0
        assert state.prev_values == {}

    def test_can_signal_again_after_reset(self):
        engine = StateEngine(steps=[_rsi_step(0, "lt", "30")])
        state = EngineState()

        engine.evaluate(state, {"rsi": {"RSI_14": 25.0}})
        engine.reset(state)

        events = engine.evaluate(state, {"rsi": {"RSI_14": 20.0}})
        assert events[0].event_type == EventType.STEP_ADVANCED
        assert events[1].event_type == EventType.SIGNAL


# ------------------------------------------------------------------ #
#  Default output key detection                                        #
# ------------------------------------------------------------------ #


class TestDefaultOutputKey:
    def test_rsi_auto_key(self):
        """When no output_key specified, should fallback to well-known key."""
        step = StepDef(step_index=0, indicator_type="rsi", condition_type="lt", condition_value="30")
        engine = StateEngine(steps=[step])
        state = EngineState()
        events = engine.evaluate(state, {"rsi": {"RSI_14": 25.0}})
        assert events[0].event_type == EventType.STEP_ADVANCED

    def test_unknown_indicator_uses_first_key(self):
        step = StepDef(step_index=0, indicator_type="custom_x", condition_type="gt", condition_value="100")
        engine = StateEngine(steps=[step])
        state = EngineState()
        events = engine.evaluate(state, {"custom_x": {"metric_a": 200.0, "metric_b": 50.0}})
        assert events[0].event_type == EventType.STEP_ADVANCED


# ------------------------------------------------------------------ #
#  Lateralization special conditions                                   #
# ------------------------------------------------------------------ #


class TestLateralization:
    def test_in_range(self):
        step = StepDef(step_index=0, indicator_type="lateralization", condition_type="in_range")
        engine = StateEngine(steps=[step])
        state = EngineState()
        events = engine.evaluate(state, {"lateralization": {"range_top": 100.0, "range_bottom": 95.0, "range_signal": 0.0}})
        assert events[0].event_type == EventType.STEP_ADVANCED

    def test_in_range_no_range(self):
        step = StepDef(step_index=0, indicator_type="lateralization", condition_type="in_range")
        engine = StateEngine(steps=[step])
        state = EngineState()
        events = engine.evaluate(state, {"lateralization": {"range_top": None, "range_bottom": None, "range_signal": 0.0}})
        assert events == []

    def test_breakout(self):
        step = StepDef(step_index=0, indicator_type="lateralization", condition_type="breakout")
        engine = StateEngine(steps=[step])
        state = EngineState()
        events = engine.evaluate(state, {"lateralization": {"range_signal": 1.0}})
        assert events[0].event_type == EventType.STEP_ADVANCED

    def test_breakout_no_signal(self):
        step = StepDef(step_index=0, indicator_type="lateralization", condition_type="breakout")
        engine = StateEngine(steps=[step])
        state = EngineState()
        events = engine.evaluate(state, {"lateralization": {"range_signal": 0.0}})
        assert events == []


# ------------------------------------------------------------------ #
#  AND / OR group conditions                                           #
# ------------------------------------------------------------------ #


class TestConditionGroups:
    def test_and_group_both_true(self):
        """AND group: RSI > 70 AND CHoCH bearish → satisfied."""
        step = StepDef(
            step_index=0,
            condition=ConditionGroup("and", [
                ConditionLeaf("rsi", "gt", "70", output_key="RSI_14"),
                ConditionLeaf("choch", "signal_bear", output_key="choch_signal"),
            ]),
        )
        engine = StateEngine(steps=[step])
        state = EngineState()
        events = engine.evaluate(state, {
            "rsi": {"RSI_14": 75.0},
            "choch": {"choch_signal": -1.0},
        })
        assert len(events) == 2  # STEP_ADVANCED + SIGNAL
        assert events[0].event_type == EventType.STEP_ADVANCED

    def test_and_group_one_false(self):
        """AND group: RSI > 70 AND CHoCH bearish — only RSI true → not satisfied."""
        step = StepDef(
            step_index=0,
            condition=ConditionGroup("and", [
                ConditionLeaf("rsi", "gt", "70", output_key="RSI_14"),
                ConditionLeaf("choch", "signal_bear", output_key="choch_signal"),
            ]),
        )
        engine = StateEngine(steps=[step])
        state = EngineState()
        events = engine.evaluate(state, {
            "rsi": {"RSI_14": 75.0},
            "choch": {"choch_signal": 1.0},  # bullish, not bearish
        })
        assert events == []

    def test_or_group_first_true(self):
        """OR group: one branch true → satisfied."""
        step = StepDef(
            step_index=0,
            condition=ConditionGroup("or", [
                ConditionLeaf("rsi", "gt", "70", output_key="RSI_14"),
                ConditionLeaf("rsi", "lt", "30", output_key="RSI_14"),
            ]),
        )
        engine = StateEngine(steps=[step])
        state = EngineState()
        events = engine.evaluate(state, {"rsi": {"RSI_14": 75.0}})
        assert events[0].event_type == EventType.STEP_ADVANCED

    def test_or_group_all_false(self):
        """OR group: both false → not satisfied."""
        step = StepDef(
            step_index=0,
            condition=ConditionGroup("or", [
                ConditionLeaf("rsi", "gt", "70", output_key="RSI_14"),
                ConditionLeaf("rsi", "lt", "30", output_key="RSI_14"),
            ]),
        )
        engine = StateEngine(steps=[step])
        state = EngineState()
        events = engine.evaluate(state, {"rsi": {"RSI_14": 50.0}})
        assert events == []

    def test_nested_or_of_ands(self):
        """(RSI > 70 AND CHoCH bear) OR (RSI < 30 AND CHoCH bull)."""
        step = StepDef(
            step_index=0,
            condition=ConditionGroup("or", [
                ConditionGroup("and", [
                    ConditionLeaf("rsi", "gt", "70", output_key="RSI_14"),
                    ConditionLeaf("choch", "signal_bear", output_key="choch_signal"),
                ]),
                ConditionGroup("and", [
                    ConditionLeaf("rsi", "lt", "30", output_key="RSI_14"),
                    ConditionLeaf("choch", "signal_bull", output_key="choch_signal"),
                ]),
            ]),
        )
        engine = StateEngine(steps=[step])

        # First OR branch satisfied: RSI > 70 + CHoCH bear
        state = EngineState()
        events = engine.evaluate(state, {
            "rsi": {"RSI_14": 75.0},
            "choch": {"choch_signal": -1.0},
        })
        assert events[0].event_type == EventType.STEP_ADVANCED

        # Second OR branch satisfied: RSI < 30 + CHoCH bull
        state2 = EngineState()
        events2 = engine.evaluate(state2, {
            "rsi": {"RSI_14": 25.0},
            "choch": {"choch_signal": 1.0},
        })
        assert events2[0].event_type == EventType.STEP_ADVANCED

        # Neither branch satisfied: RSI > 70 but CHoCH bull
        state3 = EngineState()
        events3 = engine.evaluate(state3, {
            "rsi": {"RSI_14": 75.0},
            "choch": {"choch_signal": 1.0},
        })
        assert events3 == []

    def test_multistep_with_groups(self):
        """Step 0: RSI < 30 AND MSS bull, Step 1: simple Fib signal."""
        steps = [
            StepDef(
                step_index=0,
                condition=ConditionGroup("and", [
                    ConditionLeaf("rsi", "lt", "30", output_key="RSI_14"),
                    ConditionLeaf("mss", "signal_bull", output_key="mss_signal"),
                ]),
            ),
            StepDef(
                step_index=1,
                indicator_type="fibonacci",
                condition_type="gt",
                condition_value="0",
                output_key="fib_signal",
            ),
        ]
        engine = StateEngine(steps=steps)
        state = EngineState()

        # Step 0: only RSI matches → not satisfied
        events = engine.evaluate(state, {
            "rsi": {"RSI_14": 25.0},
            "mss": {"mss_signal": 0.0},
        })
        assert events == []

        # Step 0: both match → advance
        events = engine.evaluate(state, {
            "rsi": {"RSI_14": 25.0},
            "mss": {"mss_signal": 1.0},
        })
        assert events[0].event_type == EventType.STEP_ADVANCED
        assert state.current_step == 1

        # Step 1: fibonacci signal → SIGNAL
        events = engine.evaluate(state, {"fibonacci": {"fib_signal": 1.0}})
        assert len(events) == 2
        assert events[1].event_type == EventType.SIGNAL


# ------------------------------------------------------------------ #
#  Condition node serialisation                                        #
# ------------------------------------------------------------------ #


class TestConditionSerialisation:
    def test_leaf_roundtrip(self):
        leaf = ConditionLeaf("rsi", "gt", "70", output_key="RSI_14")
        d = condition_to_dict(leaf)
        assert d == {"type": "condition", "indicator_type": "rsi", "condition_type": "gt", "condition_value": "70", "output_key": "RSI_14"}
        restored = condition_from_dict(d)
        assert isinstance(restored, ConditionLeaf)
        assert restored.indicator_type == "rsi"
        assert restored.condition_value == "70"

    def test_group_roundtrip(self):
        tree = ConditionGroup("or", [
            ConditionGroup("and", [
                ConditionLeaf("rsi", "gt", "70"),
                ConditionLeaf("choch", "signal_bear"),
            ]),
            ConditionLeaf("mss", "signal_bull"),
        ])
        d = condition_to_dict(tree)
        assert d["type"] == "or"
        assert len(d["conditions"]) == 2
        restored = condition_from_dict(d)
        assert isinstance(restored, ConditionGroup)
        assert restored.logic == "or"
        assert len(restored.conditions) == 2
        assert isinstance(restored.conditions[0], ConditionGroup)
        assert isinstance(restored.conditions[1], ConditionLeaf)
