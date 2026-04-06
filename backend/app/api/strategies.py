"""
REST endpoints for strategy CRUD — create, list, get, update, delete strategies.

Supports compound condition trees (AND / OR grouping) per step and
risk management with stop-based position sizing and partial exits.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.strategy import (
    Strategy,
    StrategyIndicator,
    StrategyMode,
    StrategyStep,
)

router = APIRouter(prefix="/strategies", tags=["strategies"])


# ------------------------------------------------------------------ #
#  Risk schemas                                                        #
# ------------------------------------------------------------------ #


class PartialExitIn(BaseModel):
    pct: float = Field(ge=1, le=100, description="% of position to close")
    target_type: str = Field(description="'rr_ratio' | 'fixed_pct' | 'trailing_pct'")
    target_value: float = Field(description="R:R ratio, fixed %, or trailing %")


class RiskConfigIn(BaseModel):
    stop_loss_type: str | None = None  # "fixed_pct" | "atr" | "swing"
    stop_loss_value: float | None = None
    take_profit_type: str | None = None  # "fixed_pct" | "rr_ratio"
    take_profit_value: float | None = None
    # Position sizing
    sizing_mode: str | None = Field(
        None,
        description="'fixed_pct' = % fixo do capital | 'risk_based' = calcula pelo stop",
    )
    position_size_pct: float | None = Field(None, ge=0.1, le=100)
    risk_pct: float | None = Field(
        None,
        ge=0.1,
        le=100,
        description="% do capital a arriscar (usado quando sizing_mode='risk_based')",
    )
    # Partial exits
    partial_exits: list[PartialExitIn] = []


# ------------------------------------------------------------------ #
#  Strategy schemas                                                    #
# ------------------------------------------------------------------ #


class StrategyIndicatorIn(BaseModel):
    indicator_type: str
    params: dict[str, Any] = {}
    timeframe: str = "5m"
    label: str | None = None
    notify_telegram: bool = False


class StrategyIndicatorOut(BaseModel):
    id: int
    indicator_type: str
    params: dict[str, Any]
    timeframe: str
    label: str | None
    notify_telegram: bool

    model_config = {"from_attributes": True}


class StrategyStepIn(BaseModel):
    step_index: int = Field(ge=0)
    # Legacy flat fields (optional — used when condition_tree is absent)
    indicator_ref: int | None = Field(
        None, description="0-based index into the indicators array"
    )
    condition_type: str | None = None
    condition_value: str | None = None
    output_key: str | None = None
    description: str | None = None
    # New: compound condition tree (takes precedence over flat fields)
    condition_tree: dict[str, Any] | None = Field(
        None,
        description="Condition tree with AND/OR grouping. When set, flat fields are ignored.",
    )


class StrategyStepOut(BaseModel):
    id: int
    step_index: int
    indicator_id: int | None
    condition_type: str
    condition_value: str | None
    condition_tree: dict[str, Any] | None
    description: str | None

    model_config = {"from_attributes": True}


class StrategyIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    mode: StrategyMode = StrategyMode.SINAL_APENAS
    indicators: list[StrategyIndicatorIn] = []
    steps: list[StrategyStepIn] = []
    risk_config: RiskConfigIn | None = None


class StrategyOut(BaseModel):
    id: int
    name: str
    description: str | None
    mode: StrategyMode
    indicators: list[StrategyIndicatorOut]
    steps: list[StrategyStepOut]
    risk_config: dict[str, Any]
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class StrategySummary(BaseModel):
    id: int
    name: str
    description: str | None
    mode: StrategyMode
    step_count: int
    indicator_count: int
    created_at: str
    updated_at: str


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #


def _strategy_to_out(strategy: Strategy) -> StrategyOut:
    return StrategyOut(
        id=strategy.id,
        name=strategy.name,
        description=strategy.description,
        mode=strategy.mode,
        indicators=[StrategyIndicatorOut.model_validate(i) for i in strategy.indicators],
        steps=[StrategyStepOut.model_validate(s) for s in sorted(strategy.steps, key=lambda s: s.step_index)],
        risk_config=strategy.risk_config or {},
        created_at=strategy.created_at.isoformat(),
        updated_at=strategy.updated_at.isoformat(),
    )


def _strategy_to_summary(strategy: Strategy) -> StrategySummary:
    return StrategySummary(
        id=strategy.id,
        name=strategy.name,
        description=strategy.description,
        mode=strategy.mode,
        step_count=len(strategy.steps),
        indicator_count=len(strategy.indicators),
        created_at=strategy.created_at.isoformat(),
        updated_at=strategy.updated_at.isoformat(),
    )


async def _load_strategy(db: AsyncSession, strategy_id: int) -> Strategy:
    stmt = (
        select(Strategy)
        .options(
            selectinload(Strategy.indicators),
            selectinload(Strategy.steps),
        )
        .where(Strategy.id == strategy_id)
    )
    result = await db.execute(stmt)
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(404, f"Strategy {strategy_id} not found")
    return strategy


def _validate_step_refs(step: StrategyStepIn, indicator_count: int) -> None:
    """Validate indicator_ref values in a step (flat or tree)."""
    if step.condition_tree:
        _validate_tree_refs(step.condition_tree, indicator_count, step.step_index)
    elif step.indicator_ref is not None:
        if step.indicator_ref < 0 or step.indicator_ref >= indicator_count:
            raise HTTPException(
                400,
                f"Step {step.step_index} references indicator_ref={step.indicator_ref} "
                f"but only {indicator_count} indicators provided",
            )


def _validate_tree_refs(tree: dict[str, Any], count: int, step_idx: int) -> None:
    """Recursively validate indicator_ref in a condition tree."""
    node_type = tree.get("type", "condition")
    if node_type in ("and", "or"):
        for child in tree.get("conditions", []):
            _validate_tree_refs(child, count, step_idx)
    else:
        ref = tree.get("indicator_ref")
        if ref is not None and (ref < 0 or ref >= count):
            raise HTTPException(
                400,
                f"Step {step_idx} condition tree references indicator_ref={ref} "
                f"but only {count} indicators provided",
            )


def _create_step(
    strategy_id: int,
    step_in: StrategyStepIn,
    indicator_objs: list[StrategyIndicator],
    indicators_in: list[StrategyIndicatorIn],
) -> StrategyStep:
    """Create a StrategyStep ORM object from API input."""
    if step_in.condition_tree:
        return StrategyStep(
            strategy_id=strategy_id,
            step_index=step_in.step_index,
            indicator_id=None,
            condition_type="group",
            condition_value=None,
            condition_tree=step_in.condition_tree,
            description=step_in.description or _auto_describe_tree(step_in.condition_tree, indicators_in),
        )
    else:
        ref = step_in.indicator_ref or 0
        ref_indicator = indicator_objs[ref]
        return StrategyStep(
            strategy_id=strategy_id,
            step_index=step_in.step_index,
            indicator_id=ref_indicator.id,
            condition_type=step_in.condition_type or "gt",
            condition_value=step_in.condition_value,
            condition_tree=None,
            description=step_in.description or _auto_describe(step_in, indicators_in[ref]),
        )


# ------------------------------------------------------------------ #
#  Endpoints                                                           #
# ------------------------------------------------------------------ #


@router.post("/", response_model=StrategyOut, status_code=201)
async def create_strategy(
    body: StrategyIn,
    db: AsyncSession = Depends(get_db),
) -> StrategyOut:
    """Create a new strategy with indicators and steps."""
    for step in body.steps:
        _validate_step_refs(step, len(body.indicators))

    strategy = Strategy(
        name=body.name,
        description=body.description,
        mode=body.mode,
        risk_config=body.risk_config.model_dump(exclude_none=True) if body.risk_config else {},
    )
    db.add(strategy)
    await db.flush()

    indicator_objs: list[StrategyIndicator] = []
    for ind_in in body.indicators:
        ind = StrategyIndicator(
            strategy_id=strategy.id,
            indicator_type=ind_in.indicator_type,
            params=ind_in.params,
            timeframe=ind_in.timeframe,
            label=ind_in.label,
            notify_telegram=ind_in.notify_telegram,
        )
        db.add(ind)
        indicator_objs.append(ind)
    await db.flush()

    for step_in in body.steps:
        db.add(_create_step(strategy.id, step_in, indicator_objs, body.indicators))

    await db.commit()
    return _strategy_to_out(await _load_strategy(db, strategy.id))


@router.get("/", response_model=list[StrategySummary])
async def list_strategies(
    db: AsyncSession = Depends(get_db),
) -> list[StrategySummary]:
    """List all strategies (summaries)."""
    stmt = (
        select(Strategy)
        .options(
            selectinload(Strategy.indicators),
            selectinload(Strategy.steps),
        )
        .order_by(Strategy.created_at.desc())
    )
    result = await db.execute(stmt)
    strategies = result.scalars().all()
    return [_strategy_to_summary(s) for s in strategies]


@router.get("/{strategy_id}", response_model=StrategyOut)
async def get_strategy(
    strategy_id: int,
    db: AsyncSession = Depends(get_db),
) -> StrategyOut:
    """Get full strategy details including indicators and steps."""
    strategy = await _load_strategy(db, strategy_id)
    return _strategy_to_out(strategy)


@router.put("/{strategy_id}", response_model=StrategyOut)
async def update_strategy(
    strategy_id: int,
    body: StrategyIn,
    db: AsyncSession = Depends(get_db),
) -> StrategyOut:
    """Replace strategy definition (indicators + steps are recreated)."""
    strategy = await _load_strategy(db, strategy_id)

    for step in body.steps:
        _validate_step_refs(step, len(body.indicators))

    strategy.name = body.name
    strategy.description = body.description
    strategy.mode = body.mode
    strategy.risk_config = body.risk_config.model_dump(exclude_none=True) if body.risk_config else {}

    strategy.indicators.clear()
    strategy.steps.clear()
    await db.flush()

    indicator_objs: list[StrategyIndicator] = []
    for ind_in in body.indicators:
        ind = StrategyIndicator(
            strategy_id=strategy.id,
            indicator_type=ind_in.indicator_type,
            params=ind_in.params,
            timeframe=ind_in.timeframe,
            label=ind_in.label,
            notify_telegram=ind_in.notify_telegram,
        )
        db.add(ind)
        indicator_objs.append(ind)
    await db.flush()

    for step_in in body.steps:
        db.add(_create_step(strategy.id, step_in, indicator_objs, body.indicators))

    await db.commit()
    return _strategy_to_out(await _load_strategy(db, strategy.id))


@router.delete("/{strategy_id}", status_code=204)
async def delete_strategy(
    strategy_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a strategy and all related indicators/steps."""
    strategy = await _load_strategy(db, strategy_id)
    await db.delete(strategy)
    await db.commit()


# ------------------------------------------------------------------ #
#  Natural language description generator                              #
# ------------------------------------------------------------------ #

_CONDITION_TEXT = {
    "gt": "is above",
    "lt": "is below",
    "gte": "is at or above",
    "lte": "is at or below",
    "eq": "equals",
    "cross_above": "crosses above",
    "cross_below": "crosses below",
    "signal_bull": "gives a BULLISH signal",
    "signal_bear": "gives a BEARISH signal",
    "in_range": "is in consolidation range",
    "breakout": "breaks out of consolidation",
}


def _auto_describe(step: StrategyStepIn, indicator: StrategyIndicatorIn) -> str:
    ctext = _CONDITION_TEXT.get(step.condition_type or "", step.condition_type or "")
    label = indicator.label or indicator.indicator_type.upper()
    if step.condition_value:
        return f"{label} ({indicator.timeframe}) {ctext} {step.condition_value}"
    return f"{label} ({indicator.timeframe}) {ctext}"


def _auto_describe_tree(tree: dict[str, Any], indicators: list[StrategyIndicatorIn]) -> str:
    """Generate natural language for a condition tree."""
    node_type = tree.get("type", "condition")
    if node_type in ("and", "or"):
        children = tree.get("conditions", [])
        parts = [_auto_describe_tree(c, indicators) for c in children]
        joiner = " AND " if node_type == "and" else " OR "
        inner = joiner.join(parts)
        return f"({inner})" if len(parts) > 1 else inner
    # Leaf
    ref = tree.get("indicator_ref", 0)
    ind = indicators[ref] if ref is not None and 0 <= ref < len(indicators) else None
    label = (ind.label or ind.indicator_type.upper()) if ind else tree.get("indicator_type", "?").upper()
    tf = ind.timeframe if ind else ""
    ctext = _CONDITION_TEXT.get(tree.get("condition_type", ""), tree.get("condition_type", ""))
    val = tree.get("condition_value", "")
    suffix = f" {val}" if val else ""
    tf_part = f" ({tf})" if tf else ""
    return f"{label}{tf_part} {ctext}{suffix}"
