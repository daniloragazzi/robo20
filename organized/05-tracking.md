# Tracking de Progresso — Sistema de Trade de Criptomoedas

> **Versão:** 1.6  
> **Data início:** 2026-04-03  
> **Última atualização:** 2026-04-04  
> **Status geral:** 🟡 Em andamento — Sprint 4 100% validado, pronto para Sprint 5  
> **Referência:** `04-plano-de-acao.md`

---

## Legenda de Status

| Símbolo | Significado |
|---------|------------|
| ⬛ | Não iniciado |
| 🟡 | Em andamento |
| ✅ | Concluído |
| 🔴 | Bloqueado |
| ⏭️ | Pulado / fora do escopo atual |

---

## Visão Geral por Milestone

| Milestone | Sprint(s) | Status | Conclusão |
|-----------|-----------|--------|-----------|
| M1 — Setup & Infra | 1 | ✅ | 2026-04-03 |
| M2 — Market Data + Chart ao vivo | 2–3 | ✅ | Sprint 2–3 concluídos |
| M3 — Indicadores | 4 | ✅ | 2026-04-04 |
| M4 — State Machine + Strategy Builder | 5 | ⬛ | — |
| M5 — Strategy Runner ao vivo | 6 | ⬛ | — |
| M6 — Boleta CEX + Ordens Manuais | 7 | ⬛ | — |
| M7 — Replay | 8 | ⬛ | — |
| M8 — Backtest | 9 | ⬛ | — |
| M9 — Notificações Telegram | 10 | ⬛ | — |

---

## Sprint 1 — Setup & Infraestrutura

**Período:** 2026-04-03  
**Objetivo:** Ambiente pronto, banco criado, pipeline CI  
**Status:** ✅ Concluído

| # | Tarefa | Status | Notas |
|---|--------|--------|-------|
| 1.1 | Criar estrutura de diretórios | ✅ | `backend/app/`, `frontend/src/`, `docker/`, `.github/` |
| 1.2 | Criar `docker-compose.yml` (TimescaleDB + Redis) | ✅ | + pgAdmin (profile: tools), healthchecks |
| 1.3 | Configurar projeto Python com `pyproject.toml` | ✅ | uv, Python 3.12 pinado (`>=3.12,<3.14`), `dependency-groups` para dev deps |
| 1.4 | Modelos SQLAlchemy + Alembic setup | ✅ | 10 modelos ORM: Candle, Strategy, StrategyIndicator, StrategyStep, StrategyExecution, Order, Position, NotificationSetting, BacktestRun, BacktestTrade. Alembic async configurado |
| 1.5 | Entrypoint FastAPI mínimo (`GET /health`) | ✅ | `app/main.py` com CORS, lifespan, `/api/health` |
| 1.6 | Configurar projeto frontend (Vite + React + TS + Tailwind) | ✅ | Vite 6, React 18, TailwindCSS 3, Zustand 5, TanStack Query 5, lightweight-charts 4 |
| 1.7 | Configurar linting/formatação (ruff, mypy, eslint, prettier) | ✅ | ruff + mypy em `pyproject.toml`, eslint flat config + prettier no frontend |
| 1.8 | Configurar CI GitHub Actions | ✅ | `.github/workflows/ci.yml` — backend (ruff, mypy, pytest) + frontend (eslint, tsc) |
| 1.9 | Criar `.env.example` | ✅ | DB, Redis, Bybit vars — sem Telegram (vai no DB) |

**Critério de conclusão:**  
- [x] `docker compose up -d` levanta TimescaleDB e Redis sem erro ✅  
- [x] `uvicorn` inicia e `/health` retorna 200 ✅  
- [x] `npm run dev` abre SPA em branco ✅  
- [ ] CI passa em push para `main` (pendente primeiro push)

---

## Sprint 2 — Market Data Service

**Período:** 2026-04-03 → 2026-04-04  
**Objetivo:** Candles BTC/USDT 5m chegando no Redis Pub/Sub  
**Status:** ✅ Concluído

| # | Tarefa | Status | Notas |
|---|--------|--------|-------|
| 2.1 | `BybitConnector` com ccxt.pro — `watch_ohlcv` | ✅ | `backend/app/connectors/bybit.py` — mainnet para dados públicos |
| 2.2 | `Market Data Service` — loop asyncio base | ✅ | `backend/app/services/market_data.py` — subscribe/unsubscribe dinâmico |
| 2.3 | Persistir candles no TimescaleDB | ✅ | Upsert `INSERT ... ON CONFLICT DO UPDATE`, hypertable migration aplicada |
| 2.4 | Endpoint REST histórico de candles | ✅ | `GET /api/candles/{symbol}?timeframe=5m&limit=200` — normaliza BTC-USDT → BTC/USDT |
| 2.5 | Reconexão automática do WebSocket | ✅ | Auto-reconnect com 5s delay no `_watch_loop` |
| 2.6 | Testes unitários Market Data | ✅ | 4 testes (parse candle, integer values, small decimals, timestamp) — todos passam |

**Critério de conclusão:**  
- [x] Redis Pub/Sub `candles:BTC/USDT:5m` recebe candles ✅  
- [x] TimescaleDB acumula histórico ✅

---

## Sprint 3 — Gráfico ao Vivo

**Período:** 2026-04-04  
**Objetivo:** Candlesticks BTC/USDT ao vivo no frontend  
**Status:** ✅ Concluído

| # | Tarefa | Status | Notas |
|---|--------|--------|-------|
| 3.1 | WebSocket Gateway na API | ✅ | `backend/app/ws/candles.py` — Redis Pub/Sub → WS forward, auto-subscribe + backfill |
| 3.2 | Componente Chart (TradingView Lightweight Charts v4) | ✅ | `frontend/src/components/Chart.tsx` — dark theme, resize observer |
| 3.3 | Carregar histórico inicial via REST | ✅ | `useCandles` hook com TanStack Query, 500 candles via `/api/candles/{symbol}` |
| 3.4 | Conectar WebSocket ao vivo | ✅ | `useCandleStream` hook com auto-reconnect 3s, Vite proxy `/ws` → backend |
| 3.5 | Seletor de timeframe | ✅ | `TimeframeSelector` — 1m, 5m, 15m, 30m, 1h, 4h, 1d |
| 3.6 | Seletor de símbolo | ✅ | `SymbolSelector` — input com Enter/blur para trocar par |
| 3.7 | Indicador de status "LIVE" | ✅ | `LiveIndicator` — pulsing green dot + texto LIVE |

**Critério de conclusão:**  
- [x] Chart renderiza candles ao vivo ✅  
- [x] Trocar TF e símbolo funciona sem refresh ✅

---

## Sprint 4 — Indicadores Técnicos

**Período:** 2026-04-04  
**Objetivo:** RSI 1H e EMA no chart; plugins MSS e Fibonacci  
**Status:** ✅ Concluído

| # | Tarefa | Status | Notas |
|---|--------|--------|-------|
| 4.1 | `IndicatorPlugin` Protocol | ✅ | `base.py` — Protocol com `name`, `display_name`, `params_schema`, `calculate()` (Sprint 1) |
| 4.2 | Built-ins: RSI, EMA, SMA | ✅ | `builtins.py` — pandas-ta wrappers |
| 4.3 | Built-ins: MACD, Bollinger, ATR, Volume, Stochastic, VWAP | ✅ | `builtins.py` — 9 indicadores total |
| 4.4 | Plugin `MSS` (Market Structure Shift) | ✅ | `custom.py` — swing high/low tracking, bull/bear signals |
| 4.5 | Plugin `FVG` (Fair Value Gap) | ✅ | `custom.py` — 3-candle imbalance zones |
| 4.6 | Plugin `Fibonacci Retracement` | ✅ | `custom.py` — auto-detect swing + 5 fib levels |
| 4.7 | Plugin `CHoCH` (Change of Character) | ✅ | `custom.py` — first break of swing |
| 4.8 | Endpoint listar indicadores + registry | ✅ | `registry.py` + `GET /api/indicators/` — 13 plugins auto-registered |
| 4.9 | Endpoint salvar instância + compute | ✅ | `POST /api/indicators/compute`, CRUD `/api/indicators/chart` + `ChartIndicator` model + migration |
| 4.10 | UI: biblioteca + painel de configuração | ✅ | `IndicatorPanel.tsx` — categorized browser, dynamic params, TF selector, Telegram toggle |
| 4.11 | UI: renderizar indicador no chart | ✅ | `Chart.tsx` — overlay lines, oscillator panes (RSI/MACD/Stoch), markers (MSS/CHoCH/FVG), Fibonacci levels |
| 4.12 | Suporte a indicador em TF diferente do chart | ✅ | Auto-backfill + auto-subscribe via MarketDataService quando TF não existe no DB |
| 4.13 | Testes de validação de indicadores | ✅ | API testada: RSI 5m (199 pts), RSI 1h multi-TF (199 pts), CRUD chart instances, TypeScript 0 errors |

**Critério de conclusão:**  
- [x] UC-01 completo ✅  
- [x] RSI 1H no chart 5m ✅ (multi-TF auto-backfill)  
- [x] Configuração persiste após reload ✅ (ChartIndicator table)

---

## Sprint 5 — Construtor de Estratégias + State Machine Engine

**Período:** A definir  
**Objetivo:** Criar e salvar estratégia RSI-MSS-Fibonacci  
**Status:** ⬛ Não iniciado

| # | Tarefa | Status | Notas |
|---|--------|--------|-------|
| 5.1 | `StateEngine` — motor central | ⬛ | |
| 5.2 | Testes unitários `StateEngine` | ⬛ | |
| 5.3 | Endpoints CRUD de estratégias | ⬛ | |
| 5.4 | UI: Construtor — tela base | ⬛ | |
| 5.5 | UI: adicionar indicadores à estratégia | ⬛ | |
| 5.6 | UI: definir passos da state machine | ⬛ | |
| 5.7 | UI: gestão de risco | ⬛ | |
| 5.8 | UI: seletor de modo de execução | ⬛ | |
| 5.9 | UI: resumo em linguagem natural | ⬛ | |
| 5.10 | Salvar e listar estratégias | ⬛ | |

**Critério de conclusão:**  
- [ ] UC-02 completo  
- [ ] Estratégia de 3 passos salva e recarregada

---

## Sprint 6 — Strategy Runner ao vivo

**Período:** A definir  
**Objetivo:** Estratégia disparando sinais no live  
**Status:** ⬛ Não iniciado

| # | Tarefa | Status | Notas |
|---|--------|--------|-------|
| 6.1 | Strategy Runner — loop asyncio | ⬛ | |
| 6.2 | Subscrição dinâmica a Redis Streams | ⬛ | |
| 6.3 | Integrar `StateEngine` no Runner | ⬛ | |
| 6.4 | Persistir transições de estado | ⬛ | |
| 6.5 | Publicar eventos de sinal | ⬛ | |
| 6.6 | Endpoints ativar/pausar/desativar | ⬛ | |
| 6.7 | UI: painel de estratégias ativas | ⬛ | |
| 6.8 | UI: feed de eventos em tempo real | ⬛ | |
| 6.9 | UI: marcador visual de sinais no chart | ⬛ | |
| 6.10 | Teste de integração Strategy Runner | ⬛ | |

**Critério de conclusão:**  
- [ ] Estratégia ativa dispara evento de sinal  
- [ ] Marcador aparece no chart  
- [ ] Estado recuperado após reinício

---

## Sprint 7 — Boleta CEX e Execução de Ordens

**Período:** A definir  
**Objetivo:** Ordens na Bybit Testnet; Runner AUTO executa ordens  
**Status:** ⬛ Não iniciado

| # | Tarefa | Status | Notas |
|---|--------|--------|-------|
| 7.1 | `Order Service` | ⬛ | |
| 7.2 | `BybitConnector` — métodos de ordem | ⬛ | |
| 7.3 | `BybitConnector` — `watch_orders` | ⬛ | |
| 7.4 | Strategy Runner → Order Service (modo AUTO) | ⬛ | |
| 7.5 | Modo SEMI_AUTO — ordem pendente | ⬛ | |
| 7.6 | Endpoints de ordens | ⬛ | |
| 7.7 | UI: Boleta CEX | ⬛ | |
| 7.8 | UI: lista de ordens abertas | ⬛ | |
| 7.9 | UI: painel de posições | ⬛ | |
| 7.10 | UI: popup confirmação SEMI_AUTO | ⬛ | |
| 7.11 | UI: saldo disponível | ⬛ | |

**Critério de conclusão:**  
- [ ] UC-06 completo  
- [ ] UC-05 completo com execução automática

---

## Sprint 8 — Replay de Mercado

**Período:** A definir  
**Objetivo:** Replay funcional com estratégia ativa  
**Status:** ⬛ Não iniciado

| # | Tarefa | Status | Notas |
|---|--------|--------|-------|
| 8.1 | `Replay Service` | ⬛ | |
| 8.2 | Controle de velocidade | ⬛ | |
| 8.3 | Pausa e seek | ⬛ | |
| 8.4 | Endpoints controle do replay | ⬛ | |
| 8.5 | Isolamento de estado durante replay | ⬛ | |
| 8.6 | UI: controles de replay | ⬛ | |
| 8.7 | UI: banner modo replay | ⬛ | |
| 8.8 | Testes Replay Service | ⬛ | |

**Critério de conclusão:**  
- [ ] UC-03 completo

---

## Sprint 9 — Backtest Engine

**Período:** A definir  
**Objetivo:** Backtest 2 anos < 60s; dashboard com métricas  
**Status:** ⬛ Não iniciado

| # | Tarefa | Status | Notas |
|---|--------|--------|-------|
| 9.1 | `Backtest Service` como Celery task | ⬛ | |
| 9.2 | Simulação de slippage e taxas | ⬛ | |
| 9.3 | Calcular métricas de performance | ⬛ | |
| 9.4 | Persistir resultado no PostgreSQL | ⬛ | |
| 9.5 | Evento `backtest.completed` | ⬛ | |
| 9.6 | Endpoints de backtest | ⬛ | |
| 9.7 | UI: formulário de configuração | ⬛ | |
| 9.8 | UI: dashboard de resultado | ⬛ | |
| 9.9 | UI: equity curve | ⬛ | |
| 9.10 | UI: tabela de trades | ⬛ | |
| 9.11 | Testes unitários do backtest engine | ⬛ | |

**Critério de conclusão:**  
- [ ] UC-04 completo

---

## Sprint 10 — Notification Service + Telegram

**Período:** A definir  
**Objetivo:** Notificações Telegram + tela de configurações  
**Status:** ⬛ Não iniciado

| # | Tarefa | Status | Notas |
|---|--------|--------|-------|
| 10.1 | `Notification Service` | ⬛ | |
| 10.2 | Integrar aiogram 3 | ⬛ | |
| 10.3 | Config notificações por tipo | ⬛ | |
| 10.4 | Tela de Configurações (Bot Token, Chat ID, toggles) | ⬛ | |
| 10.5 | Resumo diário automatizado (APScheduler) | ⬛ | |

**Critério de conclusão:**  
- [ ] UC-01 passo 9 — sinal no Telegram  
- [ ] Tela de configurações permite configurar e testar o bot sem tocar em arquivos

---

## Registro de Decisões e Impedimentos

| Data | Tipo | Descrição |
|------|------|-----------|
| 2026-04-03 | Decisão | Documentação completa em `organized/` aprovada; início de desenvolvimento pelo Sprint 1 |
| 2026-04-03 | Decisão | DeFi (Solana/Orca/Pyth) movido para Fase DeFi (após Fase 2); Fase 1 foca exclusivamente em CEX (Bybit) || 2026-04-03 | Decisão | Credenciais do Telegram (bot_token, chat_id) armazenadas na tabela `notification_settings` (PostgreSQL), gerenciadas pela UI — não em `.env` |
| 2026-04-03 | Decisão | Saídas parciais são feature de primeira classe: BO-11/12/13 (boleta) e CS-12/13 (strategy builder) |
| 2026-04-03 | Conclusão | Sprint 1 scaffolding completo — 53 arquivos criados (backend + frontend + infra + CI) |
| 2026-04-03 | Validação | `uv sync` instalou 83 packages (Python 3.12.13). Fix: `requires-python <3.14`, `dependency-groups` em vez de `optional-dependencies`, `[tool.hatch.build.targets.wheel] packages = ["app"]` |
| 2026-04-03 | Validação | `npm install` — 248 packages, 0 vulnerabilidades |
| 2026-04-03 | Validação | `uvicorn app.main:app` — `/api/health` retorna `{"status": "ok"}` ✅ |
| 2026-04-03 | Validação | Vite dev server (v6.4.1) — `http://localhost:5173` retorna 200 com HTML correto ✅ |
| 2026-04-03 | Impedimento | ~~Docker não instalado na máquina~~ — RESOLVIDO: Docker Desktop v29.3.1 instalado |
| 2026-04-03 | Validação | Docker Compose: `robo_timescaledb` (healthy) + `robo_redis` (healthy) |
| 2026-04-03 | Validação | Alembic `upgrade head` — 10 tabelas criadas no TimescaleDB + `alembic_version` |
| 2026-04-03 | Conclusão | Sprint 1 **100% validado**: infra + backend + frontend + DB migrado |
| 2026-04-03 | Impedimento | ~~aiodns/c-ares DNS falha no Windows~~ — RESOLVIDO: desinstalado aiodns/pycares, aiohttp usa ThreadedResolver |
| 2026-04-04 | Conclusão | Sprint 2 **100% validado**: WebSocket Bybit → TimescaleDB + Redis Pub/Sub funcionando. Candles BTC/USDT 5m em tempo real |
| 2026-04-04 | Fix | `tsconfig.node.json` — adicionado `composite: true`, `noEmit: false` para corrigir project references |
| 2026-04-04 | Fix | `api/candles.py` — reordenação de rotas: `/subscriptions` antes de `/{symbol}` para evitar conflito |
| 2026-04-04 | Conclusão | Sprint 3 **100% validado**: Chart ao vivo com TradingView LW Charts, 500 candles históricos + live updates via WebSocket, seletores de TF e símbolo |
| 2026-04-04 | Decisão | `ChartIndicator` como modelo separado de `StrategyIndicator` — evita FK constraint para tabela strategies |
| 2026-04-04 | Decisão | Indicadores custom (MSS, FVG, CHoCH, Fibonacci) implementados com numpy puro em vez de pandas-ta |
| 2026-04-04 | Decisão | Multi-TF via auto-backfill: compute endpoint chama `MarketDataService.backfill()` + `subscribe()` quando timeframe não tem dados no DB |
| 2026-04-04 | Conclusão | Sprint 4 **100% validado**: 13 indicator plugins (9 built-in + 4 custom), registry auto-discovery, REST API compute + CRUD, panel UI, chart rendering (overlay/pane/markers), multi-TF auto-backfill. TypeScript 0 errors |
---

## Métricas de Progresso

| Fase | Total de tarefas | Concluídas | % |
|------|-----------------|------------|---|
| Fase 1 (Sprints 1–10) | 76 | 35 | 46% |
| **Total** | **76** | **35** | **46%** |

> Atualizar esta seção ao marcar tarefas como concluídas.

---

## Arquivos Criados (Sprint 1)

<details>
<summary>Expandir lista completa (53 arquivos)</summary>

**Backend — Core:**
- `backend/pyproject.toml` — dependências Python
- `backend/.env.example` — template de variáveis
- `backend/app/__init__.py`
- `backend/app/main.py` — FastAPI entrypoint
- `backend/app/core/__init__.py`
- `backend/app/core/config.py` — pydantic-settings
- `backend/app/core/database.py` — async SQLAlchemy
- `backend/app/core/redis.py` — async Redis singleton

**Backend — Models (10 classes):**
- `backend/app/models/__init__.py`
- `backend/app/models/candle.py` — Candle (hypertable)
- `backend/app/models/strategy.py` — Strategy, StrategyIndicator, StrategyStep, StrategyExecution
- `backend/app/models/order.py` — Order, Position
- `backend/app/models/notification_settings.py` — NotificationSetting
- `backend/app/models/backtest.py` — BacktestRun, BacktestTrade

**Backend — API / Packages:**
- `backend/app/api/__init__.py`
- `backend/app/api/health.py` — GET /api/health
- `backend/app/ws/__init__.py`
- `backend/app/services/__init__.py`
- `backend/app/connectors/__init__.py`
- `backend/app/connectors/base.py` — ExchangeConnector Protocol
- `backend/app/indicators/__init__.py`
- `backend/app/indicators/base.py` — IndicatorPlugin Protocol
- `backend/app/statemachine/__init__.py`

**Backend — Alembic:**
- `backend/alembic.ini`
- `backend/alembic/env.py` — async migrations
- `backend/alembic/script.py.mako`
- `backend/alembic/versions/.gitkeep`

**Frontend:**
- `frontend/package.json`
- `frontend/vite.config.ts`
- `frontend/tsconfig.json`
- `frontend/tsconfig.node.json`
- `frontend/index.html`
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/index.css`
- `frontend/src/vite-env.d.ts`
- `frontend/tailwind.config.ts`
- `frontend/postcss.config.js`
- `frontend/eslint.config.js`
- `frontend/.prettierrc`
- `frontend/src/components/.gitkeep`
- `frontend/src/stores/.gitkeep`
- `frontend/src/hooks/.gitkeep`
- `frontend/src/api/.gitkeep`

**Infra:**
- `docker/docker-compose.yml`
- `.github/workflows/ci.yml`
- `.gitignore`

**Sprint 2:**
- `backend/app/connectors/bybit.py` — BybitConnector (ccxt.pro)
- `backend/app/services/market_data.py` — MarketDataService (watch loop + upsert + Redis pub/sub)
- `backend/app/api/candles.py` — REST endpoint histórico de candles
- `backend/alembic/versions/108f2e33f9b1_candles_hypertable.py` — hypertable migration
- `backend/tests/test_market_data.py` — 4 testes unitários
- `backend/tests/__init__.py` — package init
- `backend/app/main.py` — MODIFICADO (lifespan + candles router)

**Sprint 3:**
- `backend/app/ws/candles.py` — WebSocket gateway (Redis Pub/Sub → cliente)
- `frontend/src/api/candles.ts` — API client REST
- `frontend/src/stores/chartStore.ts` — Zustand store (symbol + timeframe)
- `frontend/src/hooks/useCandles.ts` — TanStack Query hook para histórico
- `frontend/src/hooks/useCandleStream.ts` — WebSocket hook com auto-reconnect
- `frontend/src/components/Chart.tsx` — Componente chart (Lightweight Charts v4)
- `frontend/src/components/LiveIndicator.tsx` — Indicador LIVE pulsante
- `frontend/src/components/TimeframeSelector.tsx` — Seletor de timeframe
- `frontend/src/components/SymbolSelector.tsx` — Seletor de símbolo
- `frontend/src/App.tsx` — MODIFICADO (layout com header + chart)
- `backend/app/main.py` — MODIFICADO (adicionado ws_candles_router)
- `backend/app/api/candles.py` — MODIFICADO (fix route order)
- `frontend/tsconfig.node.json` — MODIFICADO (composite + noEmit fix)

**Sprint 4:**
- `backend/app/indicators/builtins.py` — 9 built-in indicators (EMA, SMA, RSI, MACD, Bollinger, ATR, Volume, Stochastic, VWAP)
- `backend/app/indicators/custom.py` — 4 custom price-action plugins (MSS, FVG, CHoCH, Fibonacci)
- `backend/app/indicators/registry.py` — Auto-discovery registry (get, list, compute)
- `backend/app/api/indicators.py` — REST API: list, compute, chart CRUD
- `backend/app/models/chart_indicator.py` — ChartIndicator model (persisted chart instances)
- `backend/alembic/versions/2b7cd0156ca6_add_chart_indicators_table.py` — Migration
- `frontend/src/api/indicators.ts` — API client (fetch, compute, CRUD)
- `frontend/src/stores/indicatorStore.ts` — Zustand store (available, instances, data, panel)
- `frontend/src/components/IndicatorPanel.tsx` — Indicator panel UI (browser, config, active list)
- `backend/app/indicators/__init__.py` — MODIFICADO (re-exports from registry)
- `backend/app/models/__init__.py` — MODIFICADO (added ChartIndicator)
- `backend/app/main.py` — MODIFICADO (adicionado indicators_router)
- `frontend/src/components/Chart.tsx` — MODIFICADO (indicator series rendering: overlay/pane/markers)
- `frontend/src/App.tsx` — MODIFICADO (Indicators button + panel sidebar)

</details>

---

## Próximos Passos

1. **Iniciar Sprint 5:** Construtor de Estratégias + State Machine Engine
2. UI para definir passos da state machine
3. Endpoints CRUD de estratégias
4. Motor `StateEngine` central

### Comandos para retomar o ambiente

```bash
# 1. Subir infra
cd docker && docker compose up -d

# 2. Backend
cd backend && uv sync
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 3. Frontend
cd frontend && node node_modules\vite\bin\vite.js --host 127.0.0.1 --port 5173
```

---

*Este documento deve ser atualizado a cada tarefa concluída e a cada sprint finalizado.*
