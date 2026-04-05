# Arquitetura Técnica — Sistema de Trade de Criptomoedas

> **Versão:** 1.0  
> **Data:** 2026-04-03  
> **Status:** Aprovado  
> **Depende de:** `01-requisitos.md`

---

## 1. Visão Geral

O sistema é composto por serviços independentes que se comunicam via Redis Pub/Sub e Redis Streams. Cada serviço tem responsabilidade bem delimitada. A separação por processo garante que uma falha isolada (ex: Notification Service) não afete os módulos críticos (Strategy Runner, Order Service).

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                            FRONTEND  (React + Vite)                               │
│   Chart (TV Lightweight)  │  Boleta CEX  │  Construtor Estratégias      │
│   Dashboard Backtest      │  Replay Controls              │  Notificações UI        │
└─────────────────────────────────┬─────────────────────────────────────────────────┘
                                  │ REST + WebSocket (FastAPI)
┌─────────────────────────────────▼─────────────────────────────────────────────────┐
│                            BACKEND  (FastAPI / ASGI)                              │
│   REST API  ──  WebSocket Gateway  ──  Schemas Pydantic v2                        │
└──────┬────────────┬──────────────┬──────────────┬──────────────┬──────────────────┘
       │            │              │              │              │
       ▼            ▼              ▼              ▼              ▼
┌──────────┐ ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
│  Market  │ │  Order/  │  │ Strategy │  │ Backtest │  │ Notification │
│   Data   │ │ Position │  │  Runner  │  │ Service  │  │   Service    │
│ Service  │ │ Service  │  │(asyncio) │  │ (Celery) │  │ (aiogram3)   │
└────┬─────┘ └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘
     │            │              │              │               │
     ▼            ▼              ▼              ▼               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         REDIS 7                                         │
│  Streams: candles:{symbol}:{tf}       Pub/Sub: events.*                 │
│  Keys: strategy_state:*, positions:*                                    │
└──────────────┬──────────────────────────────────────────────────────────┘
               │
     ┌─────────┴───────────┐
     │                     │
     ▼                     ▼
┌───────────┐       ┌─────────────────┐
│TimescaleDB│       │  PostgreSQL 16  │
│  OHLCV    │       │ orders,strats,  │
│  candles  │       │ backtest,state  │
└───────────┘       └─────────────────┘

┌──────────────────┝
│  CEX Connector   │
│  (CCXT/ccxt.pro) │
│  Bybit Testnet   │
└──────────────────┘

*Blockchain Connector (DeFi/Solana) — Fase Futura*

┌───────────────────────────────────┐
│         Replay Service            │
│  Lê TimescaleDB → publica no      │
│  mesmo Stream candles:{s}:{tf}    │
└───────────────────────────────────┘
```

---

## 2. Camadas e Responsabilidades

### 2.1 Frontend

| Componente | Biblioteca / Tecnologia | Responsabilidade |
|-----------|------------------------|-----------------|
| Gráfico de candlesticks | TradingView Lightweight Charts v4 | Renderizar candles OHLCV, indicadores sobrepostos, marcadores de sinal, linhas de posição |
| UI shell | React 18 + TypeScript + Vite | SPA com roteamento, layout, temas |
| Estado global | Zustand | Carregar/persistir estado de UI (par selecionado, TF ativo, indicadores do chart) |
| Dados remotos | TanStack Query v5 | Cache e sincronização de dados REST (backtest, histórico de ordens, estratégias) |
| Estilos | TailwindCSS + shadcn/ui | Componentes de UI, tema escuro |
| Dados ao vivo | WebSocket nativo (browser) | Receber candles, eventos de sinal, atualizações de status de ordem em tempo real |

O frontend **nunca** acessa Redis, banco de dados ou exchanges diretamente. Toda comunicação passa pela API FastAPI.

### 2.2 API Gateway (FastAPI)

- **REST endpoints:** CRUD de estratégias, indicadores, configurações; disparo de backtests; consulta de ordens, posições, histórico de candles
- **WebSocket gateway:** Canal bidirecional entre frontend e backend. Broadcasts de candles ao vivo, eventos de estratégia, notificações
- **Autenticação:** Nenhuma. FastAPI escuta em `127.0.0.1` apenas
- **Validação:** Pydantic v2 para todos os schemas de entrada e saída

### 2.3 Market Data Service

**Responsabilidade única:** manter feeds de candles vivos e publicar/persistir dados.

```
ccxt.pro watch_ohlcv()
        │
        ▼
   candle fechado
        │
  ┌─────┴──────┐
  │            │
  ▼            ▼
Redis Stream  TimescaleDB
candles:{s}:{tf}  (hypertable)
```

- Gerencia dinamicamente quais feeds abrir/fechar com base nas estratégias e indicadores ativos
- Em caso de queda do WebSocket: reconecta e preenche gap via REST (`fetch_ohlcv`)
- Processo separado da API; comunica necessidade de feeds via tabela `active_feeds` no PostgreSQL ou via Redis key

### 2.4 Strategy Runner

**Responsabilidade única:** executar a lógica de estratégias ativas evento a evento.

```
Redis Stream candles:{symbol}:{tf}
        │
        ▼
  Avaliação da State Machine (por estratégia)
        │
  ┌─────┴──────────────────────┐
  │                            │
  ▼                            ▼
Publicar evento             Order Service
events.signal             (modo AUTO)
        │
        ▼
Atualizar estado
PostgreSQL strategy_executions
```

- Loop asyncio dedicado; nunca bloqueia I/O
- Estado de cada estratégia ativa persistido no PostgreSQL a cada transição
- Suporta múltiplas estratégias simultaneamente em tasks asyncio separadas
- Agnóstico à fonte dos candles (live ou replay — mesmo Redis Stream)

**Estrutura da State Machine por estratégia:**

```python
# Identificador do estado
state: str  # ex: "AGUARDANDO_RSI" | "AGUARDANDO_MSS" | "AGUARDANDO_FIBONACCI"
context: dict  # ex: {"msss_low": 41900, "msss_high": 42500}
step_index: int
last_transition: datetime
```

### 2.5 Order / Position Service

- Recebe comandos do Strategy Runner (ordens automáticas) e da API (ordens manuais via boleta)
- Delega execução para o CEX Connector
- Persiste todas as ordens e posições no PostgreSQL
- Assina respostas de execução das exchanges e publica eventos no bus
- Calcula e mantém P&L aberto em tempo real

### 2.6 Backtest Service (Celery Worker)

- Carrega todos os candles do período em memória (TimescaleDB, leitura em lote)
- Reutiliza a **mesma** state machine engine do Strategy Runner
- Simula slippage: preço de preenchimento = preço de fechamento do candle + spread configurado
- Simula taxas: deduzidas do PnL simulado
- Persiste resultado completo no PostgreSQL (tabela `backtest_runs` + `backtest_trades`)
- Não usa Redis Streams — tudo em memória durante a execução

### 2.7 Replay Service

- Lê candles históricos do TimescaleDB em ordem cronológica
- Publica no mesmo Redis Stream (`candles:{symbol}:{tf}`) usado pelo Market Data Service
- Controla o ritmo de publicação baseado na velocidade selecionada (1×, 5×, 50×, etc.)
- Suporta pausa (parar de publicar) e seek (pular para um timestamp)
- A API expõe endpoints REST para controlar o Replay Service (play, pause, seek, stop)

### 2.8 Notification Service

- Subscreve **todos** os tópicos de `events.*` no Redis Pub/Sub
- Mantém tabela de roteamento por tipo de evento × canal de destino (configurado pelo usuário)
- Dois canais: Telegram (aiogram 3 bot) e UI WebSocket (via FastAPI broadcast)
- Falhas em qualquer canal são logadas e descartadas sem propagar exceção

**Tópicos de eventos (Redis Pub/Sub):**

| Tópico | Payload |
|--------|---------|
| `events.indicator.signal` | symbol, indicator, condition, price, label |
| `events.strategy.transition` | strategy_id, from_state, to_state, context |
| `events.strategy.signal` | strategy_id, symbol, direction, price, stop, target |
| `events.order.sent` | order_id, symbol, type, side, qty, price |
| `events.order.filled` | order_id, fill_price, fill_qty, pnl |
| `events.order.cancelled` | order_id, reason |
| `events.order.error` | order_id, error_message |
| `events.position.closed` | position_id, pnl, duration |
| `events.backtest.completed` | backtest_id, strategy_name, summary |
| `events.system.error` | service, error_message, severity |

### 2.9 CEX Connector

```
Order/Position Service
        │
        ▼
ExchangeConnector (interface)
        │
        ▼
BybitConnector(ccxt.pro)
  - create_order()
  - cancel_order()
  - fetch_balance()
  - fetch_positions()
  - watch_orders() → publica events.order.*
```

- Interface `ExchangeConnector` garantida; adicionar Binance na Fase 2 = nova classe, sem alterar consumidores
- Rate limit tratado pelo CCXT internamente + retry exponencial customizado
- Credenciais carregadas de `os.environ` no momento de criação da instância

### 2.10 Blockchain Connector *(Fase Futura)*

> O Blockchain Connector (Solana + Orca + Pyth + Helius) não faz parte da Fase 1. A interface `BlockchainConnector` será definida e implementada quando o módulo DeFi for iniciado, seguindo o mesmo padrão de `ExchangeConnector` (Protocol do Python). O Order Service já será projetado de forma a acomodar o conector no futuro sem refatoração.

---

## 3. Modelo de Dados

### 3.1 TimescaleDB — Série temporal

```sql
-- Hypertable particionada por tempo
CREATE TABLE candles (
    ts          TIMESTAMPTZ   NOT NULL,
    symbol      TEXT          NOT NULL,
    timeframe   TEXT          NOT NULL,   -- '1m', '5m', '1H', etc.
    open        NUMERIC(20,8) NOT NULL,
    high        NUMERIC(20,8) NOT NULL,
    low         NUMERIC(20,8) NOT NULL,
    close       NUMERIC(20,8) NOT NULL,
    volume      NUMERIC(30,8) NOT NULL,
    PRIMARY KEY (ts, symbol, timeframe)
);
SELECT create_hypertable('candles', 'ts', chunk_time_interval => INTERVAL '7 days');
CREATE INDEX ON candles (symbol, timeframe, ts DESC);
```

### 3.2 PostgreSQL — Modelo relacional (principais tabelas)

```
strategies
  id, name, description, mode (SINAL_APENAS|SEMI_AUTO|TOTALMENTE_AUTO),
  risk_config (JSONB), created_at, updated_at

strategy_indicators
  id, strategy_id→strategies, indicator_type, params (JSONB),
  timeframe, label, notify_telegram

strategy_steps
  id, strategy_id→strategies, step_index, indicator_id→strategy_indicators,
  condition_type, condition_value, description

strategy_executions
  id, strategy_id→strategies, symbol, status (ACTIVE|PAUSED|STOPPED),
  current_state, context (JSONB), activated_at, last_transition

orders
  id, strategy_execution_id→strategy_executions (nullable),
  exchange, symbol, side, order_type, qty, price, stop, target,
  status, fill_price, fill_qty, fee, created_at, filled_at

positions
  id, exchange, symbol, side, entry_price, qty, stop, target,
  pnl_open, status (OPEN|CLOSED), opened_at, closed_at

backtest_runs
  id, strategy_id→strategies, period_start, period_end, capital_initial,
  slippage_pct, taker_fee_pct, maker_fee_pct, status, created_at, completed_at,
  summary (JSONB)  -- {total_trades, win_rate, pnl_total, ...}

backtest_trades
  id, backtest_run_id→backtest_runs, entry_ts, entry_price, exit_ts,
  exit_price, side, qty, pnl, fee, duration_sec, triggering_step_index
```

### 3.3 Redis — Chaves e estruturas

| Chave / Canal | Tipo | Propósito |
|---------------|------|-----------|
| `candles:{SYMBOL}:{TF}` | Stream | Canal principal de candles (live e replay) |
| `strategy_state:{execution_id}` | Hash | Cache de estado rápido (complementa PostgreSQL) |
| `active_feeds` | Set | Conjunto de feeds que Market Data Service deve manter |
| `events.*` | Pub/Sub | Todos os eventos do sistema |
| `replay:control:{session_id}` | Hash | Estado do replay (speed, paused, current_ts) |

---

## 4. Comunicação entre Serviços

```
┌──────────────────────────────────────────────────────────────────┐
│ Protocolo     │ Usado para                                        │
├──────────────────────────────────────────────────────────────────┤
│ Redis Streams │ candles ao vivo e replay (produtor → consumidores)│
│ Redis Pub/Sub │ eventos assíncronos (sinal, ordem, erro, etc.)    │
│ REST (FastAPI)│ operações request/response (CRUD, triggers)       │
│ WebSocket     │ push ao Frontend (candles, notificações, status)  │
│ Celery        │ jobs de backtest em background                    │
│ SQLAlchemy 2  │ leitura/escrita assíncrona no PostgreSQL          │
└──────────────────────────────────────────────────────────────────┘
```

**Regra fundamental:** nenhum serviço chama diretamente outro serviço HTTP interno. A integração entre serviços acontece via Redis (Streams e Pub/Sub). O único canal direto é Strategy Runner → Order Service (chamada direta Python, mesmo processo ou via Redis command channel).

---

## 5. Estrutura de Diretórios do Projeto

```
robo2.0/
├── docker/
│   └── docker-compose.yml          # TimescaleDB + Redis + pgAdmin
├── backend/
│   ├── pyproject.toml              # Dependências Python (uv ou poetry)
│   ├── alembic/                    # Migrações do banco
│   ├── app/
│   │   ├── main.py                 # Entrypoint FastAPI
│   │   ├── api/                    # Routers REST
│   │   ├── ws/                     # WebSocket handlers
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   ├── schemas/                # Pydantic schemas
│   │   ├── services/
│   │   │   ├── market_data.py      # Market Data Service
│   │   │   ├── strategy_runner.py  # Strategy Runner
│   │   │   ├── order_service.py    # Order/Position Service
│   │   │   ├── backtest_service.py # Backtest engine
│   │   │   ├── replay_service.py   # Replay Service
│   │   │   └── notification_service.py
│   │   ├── connectors/
│   │   │   ├── base.py             # ExchangeConnector interface (BlockchainConnector: Fase Futura)
│   │   │   └── bybit.py            # BybitConnector (CCXT)
│   │   ├── indicators/
│   │   │   ├── base.py             # IndicatorPlugin interface/protocol
│   │   │   ├── builtin.py          # Wrappers pandas-ta
│   │   │   └── plugins/            # Diretório de plugins customizados
│   │   │       ├── mss.py          # Market Structure Shift
│   │   │       ├── fvg.py          # Fair Value Gap
│   │   │       ├── fibonacci.py    # Fibonacci Retracement
│   │   │       └── choch.py        # Change of Character
│   │   ├── statemachine/
│   │   │   └── engine.py           # Motor de state machine (compartilhado runner/backtest)
│   │   └── core/
│   │       ├── config.py           # Carregamento de variáveis de ambiente
│   │       ├── database.py         # Conexão SQLAlchemy async
│   │       └── redis.py            # Conexão Redis
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── components/
│   │   │   ├── Chart/              # TradingView Lightweight Charts
│   │   │   ├── OrderForm/          # Boleta CEX
│   │   │   ├── StrategyBuilder/    # Construtor de estratégias
│   │   │   ├── BacktestDashboard/  
│   │   │   └── Notifications/      
│   │   ├── stores/                 # Zustand stores
│   │   ├── hooks/                  # React Query hooks + WebSocket hooks
│   │   └── api/                    # Funções cliente HTTP
├── brainstorm/
│   └── 01-arquitetura-e-ferramentas.md
└── organized/
    ├── 01-requisitos.md
    ├── 02-casos-de-uso.md
    ├── 03-arquitetura.md          ← este arquivo
    ├── 04-plano-de-acao.md
    └── 05-tracking.md
```

---

## 6. Decisões Técnicas Críticas

### 6.1 Por que Redis Streams em vez de chamadas diretas entre serviços?

- Desacoplamento: Market Data Service não sabe quem consome seus candles
- Replay gratuito: o Replay Service usa o mesmo canal — nenhum código condicional nos consumidores
- Persistência: Redis Streams têm memória integrada; consumidores perdidos podem recuperar mensagens
- Backpressure: consumidores lentos não bloqueiam o produtor

### 6.2 Por que a State Machine está em um engine compartilhado?

- Strategy Runner (live/replay) e Backtest Service devem produzir **exatamente** os mesmos resultados para o mesmo conjunto de candles
- Um único `engine.py` garante isso; qualquer correção de bug beneficia ambos automaticamente

### 6.3 Por que Backtest usa Celery e não asyncio?

- Backtest é CPU-bound (loop tight sobre centenas de milhares de candles)
- asyncio não paraleliza CPU-bound; Celery com worker separado (processo Python separado) sim
- Mantém a API HTTP responsiva durante execução de backtest longo

### 6.4 Por que TimescaleDB em vez de InfluxDB?

- TimescaleDB é PostgreSQL com extensão de séries temporais: mesma ferramenta para dados relacionais e séries temporais
- SQLAlchemy funciona normalmente; sem necessidade de ORM diferente
- Queries de backtest podem fazer JOINs entre candles e configurações de estratégia

### 6.5 Fluxo de inicialização do Strategy Runner

```
1. Carregar todas as strategy_executions com status=ACTIVE do PostgreSQL
2. Para cada execução: restaurar estado e contexto
3. Registrar necessidade de feeds no set active_feeds do Redis
4. Iniciar task asyncio por execução
5. Subscrever apenas os streams necessários
6. Notificar Market Data Service para garantir feeds abertos
```

---

## 7. Interfaces Contrato

### 7.1 IndicatorPlugin Protocol

```python
from typing import Protocol
import pandas as pd

class IndicatorPlugin(Protocol):
    name: str           # Identificador único: "MSS", "FVG", etc.
    display_name: str   # Nome exibido na UI
    params_schema: dict # JSON Schema dos parâmetros configuráveis

    def calculate(self, candles: pd.DataFrame, params: dict) -> pd.DataFrame:
        """
        Recebe DataFrame com colunas [open, high, low, close, volume, ts].
        Retorna DataFrame com as colunas de sinal adicionadas.
        Ex: coluna 'mss_signal' com valores: 'BULLISH' | 'BEARISH' | None
        """
        ...
```

### 7.2 ExchangeConnector Protocol

```python
from typing import Protocol

class ExchangeConnector(Protocol):
    exchange_id: str  # "bybit", "binance", ...

    async def create_order(self, symbol, side, order_type, qty, price, params) -> dict: ...
    async def cancel_order(self, order_id, symbol) -> dict: ...
    async def fetch_balance(self) -> dict: ...
    async def fetch_positions(self) -> list[dict]: ...
    async def watch_orders(self) -> None: ...  # publica events.order.* no Redis
```

### 7.3 BlockchainConnector Protocol *(Fase Futura)*

> A ser definido quando o módulo DeFi for iniciado. Seguirá o mesmo padrão de `Protocol` do Python com métodos assíncronos: `get_balance`, `get_price`, `execute_swap`, `get_tx_status`. O `chain_id` identificará a rede ("solana", "arbitrum", etc.).

---

## 8. Ambiente de Desenvolvimento

### Pré-requisitos

- Python 3.12+ (recomendado via `pyenv`)
- Node.js 20+ (frontend)
- Docker Desktop (apenas para TimescaleDB + Redis)
- `uv` (gerenciador de pacotes Python rápido) ou `poetry`

### Inicialização

```bash
# 1. Infraestrutura
cd docker && docker compose up -d

# 2. Backend
cd backend
uv sync                      # instala dependências do pyproject.toml
alembic upgrade head         # executa migrações
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 3. Celery worker (terminal separado)
cd backend
uv run celery -A app.celery_app worker --loglevel=info

# 4. Frontend
cd frontend
npm install
npm run dev                  # http://localhost:5173
```

### Variáveis de Ambiente (`.env` na raiz do backend)

```env
# PostgreSQL / TimescaleDB
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/robo

# Redis
REDIS_URL=redis://localhost:6379/0

# Bybit Testnet
BYBIT_API_KEY=...
BYBIT_API_SECRET=...
BYBIT_TESTNET=true

# Ambiente
ENV=development
LOG_LEVEL=INFO
```

> **Nota:** Token e Chat ID do Telegram são configurados pela tela de configurações do frontend (tabela `notification_settings` no PostgreSQL), não via `.env`.

---

*Documento oficial — alterações devem ser versionadas com data e descrição da mudança no topo deste arquivo.*
