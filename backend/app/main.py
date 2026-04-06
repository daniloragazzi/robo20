"""
Robo 2.0 — FastAPI application entry-point.
Start with:  uvicorn app.main:app --reload
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.candles import router as candles_router
from app.api.health import router as health_router
from app.api.indicators import router as indicators_router
from app.api.strategies import router as strategies_router
from app.connectors.bybit import BybitConnector
from app.ws.candles import router as ws_candles_router
from app.core.database import AsyncSessionLocal
from app.core.redis import close_redis, get_redis
from app.services import market_data as mds_module
from app.services.market_data import MarketDataService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown lifecycle hook."""
    # --- startup ---
    connector = BybitConnector()
    redis = await get_redis()
    service = MarketDataService(connector, AsyncSessionLocal, redis)
    mds_module._market_data_service = service

    # Auto-subscribe to default pairs
    service.subscribe("BTC/USDT", "5m")
    logger.info("MarketDataService started — subscribed to BTC/USDT:5m")

    yield

    # --- shutdown ---
    await service.shutdown()
    await close_redis()
    logger.info("MarketDataService stopped")


app = FastAPI(
    title="Robo 2.0 API",
    description="Crypto trading assistant — CEX Fase 1",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow local Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- routers ----
app.include_router(health_router, prefix="/api")
app.include_router(candles_router, prefix="/api")
app.include_router(indicators_router, prefix="/api")
app.include_router(strategies_router, prefix="/api")
app.include_router(ws_candles_router, prefix="/ws")
