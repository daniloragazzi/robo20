# Brainstorm — Arquitetura e Ferramentas do Sistema de Trade de Criptomoedas

> **Status:** Em discussão — v2  
> **Data:** 2026-04-03  
> **Objetivo:** Explorar e discutir a arquitetura ideal e as ferramentas de desenvolvimento antes de formalizar o projeto.  
> **Changelog v2:** Adicionadas seções de discussão sobre Docker, Python vs .NET e ajuste de arquitetura para automação de estratégias.

---

## 1. Visão Geral do Produto

Sistema web de trade de criptomoedas com as seguintes capacidades principais:

| Módulo | Descrição |
|--------|-----------|
| **Chart em tempo real** | Gráfico de candlesticks conectado a feeds de mercado ao vivo |
| **Boleta de ordens** | Ticket de entrada Long/Short com suporte a múltiplos tipos de ordem |
| **Replay de mercado** | Reprodução histórica de dados para teste manual de estratégias |
| **Backtest** | Execução automatizada de estratégias sobre dados históricos com relatório de performance |
| **Indicadores** | Biblioteca extensível de indicadores técnicos (built-in via pandas-ta + customizados via plugin); cada instância tem configuração própria de parâmetros, timeframe e alerta Telegram |
| **Construtor de estratégias** | Interface visual para combinar indicadores em estratégias sequenciais multi-timeframe com definição de condições de entrada encadeadas (máquina de estados) |
| **Sinais de entrada** | Motor de alertas/sinais com base nos indicadores e estratégias configurados; portável entre live, replay e backtest sem alteração |
| **CEX trading** | Trades em exchanges centralizadas (Bybit e outras via CCXT) |
| **DeFi / DEX trading** | Trades on-chain em DEX (GMX, Uniswap, dYdX) com execução via carteira |
| **Oráculos on-chain** | Leitura de preços Chainlink/Pyth para estratégias e indicadores DeFi |
| **Notificações Telegram** | Envio de sinais, alertas de indicadores, confirmações de ordem e mensagens de estratégia via bot Telegram |
| **Multiplataforma** | Funciona em Windows, Linux e macOS sem alterações |

---

## 2. Arquitetura Proposta

### 2.1 Visão Macro — Arquitetura em Camadas Modulares

```
┌──────────────────────────────────────────────────────────────┐
│                      FRONTEND (SPA)                          │
│   React + TypeScript · TradingView Lightweight Charts        │
│   Chart · Boleta CEX · Boleta DeFi · Replay · Backtest       │
└──────────────────────────┬───────────────────────────────────┘
                           │ REST + WebSocket
┌──────────────────────────▼───────────────────────────────────┐
│                    API GATEWAY / BFF                         │
│                FastAPI (Python) — REST + WS                  │
└────┬──────────┬──────────┬──────────────────┬────────────────┘
     │          │          │                  │
┌────▼────┐ ┌───▼─────┐ ┌──▼────────┐  ┌─────▼───────────┐
│ Market  │ │ REPLAY  │ │  Order /  │  │    Backtest /   │
│ Data    │ │ Service │ │  Position │  │    Indicator    │
│ Service │ │         │ │  Service  │  │    Service      │
└────┬────┘ └───┬─────┘ └──┬────────┘  └─────┬───────────┘
     │  live    │  replay   │  ordens          │
     │  stream  │  stream   │                  │
     ▼          ▼           │                  │
  [Redis Stream: candles + eventos do sistema] │
  (candles · sinais · ordens · execuções · alertas)
                  │          │                 │
       ┌──────────▼──────────▼─────────────────┴──────────┐
       │                STRATEGY RUNNER                   │
       │        (processo dedicado — asyncio loop)        │
       │   1. Consome Redis Stream (live OU replay)       │
       │   2. Calcula indicadores (pandas-ta)             │
       │   3. Avalia condições de entrada/saída           │
       │   4. Publica eventos → Redis Pub/Sub             │
       │      (sinal · ordem · alerta · status)          │
       │   5. Gerencia posição aberta                     │
       │   6. Fase 2+: estratégias multi-exchange         │
       └────────────────────────┬──────────────────────────┘
                                │
               [Redis Pub/Sub — tópico: events]
                     ┌──────────┘
                     │
       ┌─────────────▼────────────────────────────────────┐
       │           NOTIFICATION SERVICE                   │
       │   Subscreve todos os eventos do Redis bus        │
       ├──────────────────────┬───────────────────────────┤
       │  Telegram Bot        │  WebSocket → Frontend UI  │
       │  (python-telegram-   │  (notificações em tempo   │
       │   bot / aiogram)     │   real na interface)      │
       │                      │                           │
       │  Mensagens enviadas: │                           │
       │  · Sinal disparado   │                           │
       │  · Ordem enviada     │                           │
       │  · Ordem preenchida  │                           │
       │  · Ordem cancelada   │                           │
       │  · Stop atingido     │                           │
       │  · Estratégia ON/OFF │                           │
       │  · Erro crítico      │                           │
       │  · Resumo de PnL     │                           │
       └──────────────────────┴───────────────────────────┘
                  │                           │
┌─────────────────▼───────────────────────────▼────────────────┐
│                       CAMADA DE DADOS                        │
│   TimescaleDB (OHLCV + trades) · Redis (cache/streams/bus)   │
│   PostgreSQL (ordens, estratégias, runner state, backtests)  │
└──────────┬─────────────────────────┬─────────────────────────┘
           │                         │
┌──────────▼──────────────┐  ┌───────▼─────────────────────────┐
│  CEX CONNECTOR          │  │  BLOCKCHAIN CONNECTOR (DeFi)    │
│  CCXT + ccxt.pro        │  │  Interface multi-chain unificada│
├─────────────────────────┤  ├─────────────────────────────────┤
│  FASE 1 (atual)         │  │  FASE 1 — Solana (prioritário)  │
│  · Bybit Testnet        │  │  · solders + solana-py          │
│  · REST + WebSocket     │  │  · Orca Whirlpools (DEX)        │
├─────────────────────────┤  │  · Pyth Network (oráculo)       │
│  FASE 2 — multi-CEX     │  │  · Helius RPC                   │
│  · Binance              │  ├─────────────────────────────────┤
│  · OKX                  │  │  FASE 2+ — EVM (expansão)       │
│  · Kraken               │  │  · web3.py                      │
│  · outras via CCXT      │  │  · Chainlink oracles            │
├─────────────────────────┤  │  · GMX / Uniswap / dYdX         │
│  FASE 3 — arbitragem    │  │  · Arbitrum / Base / Ethereum   │
│  · estratégias CEX-CEX  │  └─────────────────────────────────┘
│  · estratégias CEX-DEX  │
│  · feed unificado multi │
└─────────────────────────┘
```

> **Replay Service:** lê candles históricos do TimescaleDB e publica no **mesmo Redis Stream** do Market Data Service. O Strategy Runner e o Frontend consomem desse stream sem saber se os dados são ao vivo ou replay — velocidade controlada pelo Replay Service (1×, 5×, 50×, pause, seek). Toda estratégia testada em replay se comporta identicamente em produção.

> **Notification Service:** desacoplado via Redis Pub/Sub — nenhum outro serviço chama o Telegram diretamente. Qualquer módulo (Strategy Runner, Order Service, Backtest) simplesmente publica um evento no bus; o Notification Service decide o que enviar e para onde (Telegram, UI, ou ambos).

> **Multi-exchange e arbitragem:** a fase 2 expande para múltiplas exchanges via CCXT (+100 suportadas). Na fase 3, o Strategy Runner ganha estratégias multi-exchange para arbitragem CEX-CEX e CEX-DEX.

### 2.2 Padrão Arquitetural

**Monólito Modular com fronteiras bem definidas** — abordagem recomendada para a fase inicial.

- Cada módulo (market data, orders, strategy, backtest) vive como um pacote Python independente dentro do mesmo repositório (monorepo).
- A comunicação interna usa interfaces bem definidas (não chamadas diretas entre módulos de negócio).
- Quando o projeto crescer, cada módulo pode ser extraído como microsserviço sem reescrita.
- Um **Message Bus interno** (usando Redis Pub/Sub ou um simples event emitter assíncrono) desacopla os módulos desde o início.

> **Por que não microsserviços desde o início?**  
> Microsserviços trazem overhead de infra (k8s, service mesh, distributed tracing) que atrasa o desenvolvimento das features reais. O monólito modular oferece os mesmos benefícios de organização com 10x menos complexidade operacional.

---

## 3. Stack Tecnológica Sugerida

### 3.1 Frontend

| Tecnologia | Papel | Justificativa |
|-----------|-------|---------------|
| **React 18 + TypeScript** | Framework principal da SPA | Ecossistema maduro, tipagem forte essencial para domínio financeiro |
| **Vite** | Build/bundler | Extremamente rápido em dev; substituto moderno do CRA |
| **TradingView Lightweight Charts v4** | Renderização dos candles | Biblioteca oficial da TradingView, open-source, altíssima performance no canvas, suporte nativo a OHLCV e indicadores sobrepostos |
| **Zustand** | State management | Mais simples que Redux; ideal para estado de chart, posições e book |
| **React Query (TanStack Query)** | Cache de dados REST | Gerencia loading/error/cache de endpoints automaticamente |
| **TailwindCSS + shadcn/ui** | UI/Estilo | Produtividade alta, componentes acessíveis e customizáveis |
| **Socket.IO client / native WS** | Tempo real | Candles ao vivo, book de ordens, PnL |

### 3.2 Backend (API + Serviços)

| Tecnologia | Papel | Justificativa |
|-----------|-------|---------------|
| **Python 3.12** | Linguagem principal | Ecossistema dominante em finanças quantitativas e análise de dados |
| **FastAPI** | Framework HTTP + WebSocket | Altíssima performance (ASGI), tipagem com Pydantic, documentação Swagger automática |
| **Pydantic v2** | Validação / domínio | Modelos de ordens, candles e estratégias com validação nativa |
| **SQLAlchemy 2 (async)** | ORM | Async nativo, suporte pleno ao TimescaleDB |
| **Alembic** | Migrations | Controle de versão do schema do banco |
| **Celery + Redis** | Filas de tarefas assíncronas | Backtests e cálculo de indicadores em background sem bloquear API |
| **APScheduler** | Scheduler | Coleta periódica de candles históricos, sinais agendados |
| **aiogram 3** | Bot Telegram | Framework async moderno para bots Telegram em Python; suporte total a asyncio; ideal para integração com FastAPI e o event loop do Strategy Runner |

### 3.3 Exchange / Dados de Mercado — CEX

| Tecnologia | Papel | Justificativa |
|-----------|-------|---------------|
| **CCXT v4+ (Python)** | Conectividade multi-exchange CEX | Suporte a +100 exchanges, API unificada para spot, futuros e opções; REST + WS |
| **ccxt.pro** (incluso no v4) | WebSocket unificado | `watch_ohlcv()`, `watch_orders()`, `watch_positions()` — dados ao vivo sem polling; gatilho do Strategy Runner |
| **Bybit Testnet** | Ambiente paper trading | Exchange real com dados reais, sem dinheiro real — ideal para fase 1 |

### 3.3b Exchange / Dados de Mercado — DeFi (DEX + Oráculos)

> **Decisão registrada (2026-04-03):** DeFi prioritário em **Solana + Orca**. Outras redes/DEX entram em fases subsequentes. A arquitetura deve ser desenhada para suportar múltiplas redes desde o início (abstração multi-chain).

> ⚠️ **Solana ≠ EVM:** Solana usa uma arquitetura completamente diferente das redes EVM (Ethereum, Arbitrum, Base). Isso significa que `web3.py` **não se aplica** à Solana — a biblioteca e o modelo de programação são distintos.

| Tecnologia | Papel | Justificativa |
|-----------|-------|---------------|
| **solders** (Python) | Biblioteca core Solana | Bindings Python de alta performance para o SDK Rust da Solana — operações de carteira, transações, assinatura |
| **solana-py** (Python) | Cliente RPC Solana | Comunicação com nós Solana (mainnet, devnet) — consultas de conta, envio de transações, subscrição de eventos via WebSocket |
| **Orca Whirlpools** | DEX primária — Solana | AMM de liquidez concentrada (similar ao Uniswap v3); maior volume em Solana; integração via instrução de programa on-chain |
| **Pyth Network** | Oráculo de preço — Solana | Oráculo nativo da Solana com atualizações em ~400ms; suporta BTC, ETH, SOL, e centenas de ativos; SDK Python disponível |
| **Solana RPC** (Helius / QuickNode / próprio) | Provider de nó | Acesso à rede Solana; nós públicos têm rate limit severo — recomendado provider dedicado (Helius tem plano gratuito generoso) |
| **web3.py** *(fase 2+)* | Interação EVM (Ethereum, Arbitrum, Base) | Entra quando expandir para redes EVM; Solana não usa esta lib |
| **Blockchain Connector (abstração própria)** | Camada multi-chain | Interface unificada para CEX e múltiplas redes — isola o resto do sistema das diferenças entre Solana, EVM, etc. (ver seção 5.4) |

> **Segurança — chave privada Solana:** diferente de uma API key de exchange (que pode ser revogada a qualquer momento), a chave privada da carteira Solana **não pode ser revogada**. Comprometê-la significa perda permanente dos fundos. Armazenamento obrigatório em variável de ambiente local, nunca no banco, nunca no código. Detalhar política de segurança nos documentos formais.

### 3.4 Banco de Dados

| Tecnologia | Papel | Justificativa |
|-----------|-------|---------------|
| **TimescaleDB** (extensão PostgreSQL) | Armazenamento de séries temporais (OHLCV, ticks) | Compressão automática, queries time-series otimizadas, 100% compatível com SQL padrão |
| **PostgreSQL 16** | Dados relacionais (usuários, ordens, estratégias, backtest results) | Confiabilidade comprovada, transações ACID |
| **Redis 7** | Cache + Pub/Sub + filas Celery | Candles recentes em memória, streaming de eventos entre serviços, sessões |

### 3.5 Motor de Backtest / Estratégias

| Tecnologia | Papel | Justificativa |
|-----------|-------|---------------|
| **Pandas + NumPy** | Manipulação de séries de preço | Padrão de mercado para dados tabulares |
| **pandas-ta** | Indicadores técnicos built-in | +130 indicadores clássicos (RSI, EMA, MACD, Bollinger, etc.) encapsulados como plugins |
| **TA-Lib** (opcional) | Indicadores técnicos alternativos | Alta performance C; usar quando pandas-ta for lento em backtests longos |
| **Sistema de plugins próprio** | Indicadores customizados (MSS, FVG, Fibonacci, CHoCH, etc.) | pandas-ta não cobre price action; qualquer indicador novo implementa a interface `IndicatorPlugin` — ver seção 5.4.2 |
| **Motor próprio de backtest** | Engine de simulação evento-a-evento | Necessário para suportar máquinas de estado sequenciais (ver seção 5.5.3) e estratégias multi-TF; frameworks externos (backtrader, vectorbt) não suportam bem esses dois requisitos |
| **Vectorbt** (avaliação futura) | Backtests vetorizados ultra-rápidos | Pode acelerar runs de estratégias simples (sem state machine); avaliar integração na fase 2 |

### 3.6 Infraestrutura & DevOps

| Tecnologia | Papel | Justificativa |
|-----------|-------|---------------|
| **Docker Compose** | **Apenas infra** (TimescaleDB + Redis) | TimescaleDB no Windows é trabalhoso de instalar manualmente; Docker resolve em segundos sem poluir o sistema |
| **GitHub Actions** | CI/CD | Lint, testes, build automático |
| **pytest + pytest-asyncio** | Testes backend | Cobertura de serviços async do FastAPI |
| **Vitest + React Testing Library** | Testes frontend | Integrado ao Vite, rápido |

> **Decisão sobre Docker:** A API Python e o frontend rodam **fora do container** durante o desenvolvimento (hot-reload nativo, debugger integrado ao VS Code, sem overhead de build de imagem). O Docker fica restrito ao `timescaledb` e `redis` no `docker-compose.yml`. Isso captura ~90% do benefício (ambiente de infra reproduzível) com zero custo de produtividade no dia-a-dia.

---

## 4. Discussão: Python vs. Plataforma Microsoft (.NET / C#)

| Critério | Python + FastAPI | .NET 8 / C# + ASP.NET Core |
|---|---|---|
| **Ecossistema quant/finanças** | ✅ Dominante — pandas, numpy, pandas-ta, TA-Lib, vectorbt | ❌ Escasso — Accord.NET limitado; quants usam Python por padrão |
| **CCXT (exchange connector)** | ✅ Biblioteca principal é Python | ❌ Sem port C# oficial maduro |
| **Performance HTTP** | ✅ FastAPI (ASGI async) comparável ao .NET em benchmarks reais | ✅ Leve vantagem bruta — irrelevante para single-user local |
| **Processamento numérico (backtest)** | ✅ NumPy opera em C internamente — altíssima performance vetorizada | ❌ Reimplementar pipelines vetorizados em C# é custoso e lento |
| **Tipagem / segurança** | ✅ Python 3.12 + Pydantic v2 + mypy cobre o domínio bem | ✅ Tipagem estática nativa, vantagem em compilação |
| **Automação de estratégias** | ✅ Scripts Python são cidadãos de primeira classe | ✅ Funciona, mas sem ecossistema quant de suporte |
| **Velocidade de prototipação** | ✅ Muito alta para este domínio | ⚠️ Mais verboso; overhead de compilação |
| **Ecosystem Windows** | ⚠️ Funciona bem, mas historicamente mais fluido em Linux | ✅ Microsoft nativo, excelente tooling no Windows |

**Conclusão:** A escolha por Python **não é só pela quantidade de bibliotecas** — é porque o ecossistema inteiro de dados financeiros e quant vive em Python. Qualquer pesquisa acadêmica de estratégia, qualquer indicador avançado, o próprio CCXT: tudo nasce em Python. Usar .NET exigiria bridges ou reimplementações, aumentando custo e reduzindo qualidade. **Para um sistema de trading, Python é a escolha racionalmente correta, não apenas conveniente.**

---

## 5. Decisões de Design Importantes

### 5.1 Replay de Mercado

O replay reproduz dados históricos no frontend como se fossem dados ao vivo. A arquitetura proposta:

```
[TimescaleDB: histórico OHLCV]
        │
        ▼
[Replay Service (Python)]  — controla velocidade (1x, 5x, 50x), pausa, seek
        │  WebSocket
        ▼
[Frontend: Chart]  — recebe candles como se fosse feed real
```

- O frontend **não precisa saber** se está em modo live ou replay; o mesmo componente de chart é usado.
- O Replay Service emula o comportamento do Market Data Service.

### 5.2 Motor de Estratégias + Sinais + Automação

**Modelo de uma estratégia:**
```
Estratégia = {
    indicadores configurados (cada um com TF, parâmetros e toggle Telegram próprios),
    condições de entrada sequenciais (máquina de estados — ver seção 5.5.3),
    gestão de risco (stop, target, tamanho de posição),
    modo: SINAL_APENAS | SEMI_AUTO | TOTALMENTE_AUTO
}
```

**Por que o Strategy Runner precisa ser processo dedicado (e não parte da API):**
- A API HTTP é stateless e orientada a request/response — não tem loop contínuo
- O runner precisa de **estado persistente entre candles** (posição aberta, último valor do indicador, contexto)
- Se a API reiniciar, o runner **não pode perder** o estado de uma estratégia ativa com posição aberta
- Permite rodar múltiplas estratégias em paralelo, cada uma isolada

**Fluxo completo de execução automática:**
```
[Bybit WS] → candle fechado
     │
     ▼
[Redis Stream: candles:{symbol}:{timeframe}]
     │
     ▼
[Strategy Runner — asyncio loop por estratégia ativa]
     ├─ Carrega estado (PostgreSQL)
     ├─ Calcula indicadores (pandas-ta)
     ├─ Avalia regras de entrada/saída
     └─ SE condição TRUE:
            ├─ SINAL_APENAS  → evento → Frontend (alerta no chart)
            ├─ SEMI_AUTO     → ordem pendente → Frontend (confirmação manual)
            └─ TOTALMENTE_AUTO → ordem → Order Service → Bybit Testnet
```

**Estado persistente do runner (PostgreSQL):**
```sql
strategy_runner_state (
    strategy_id UUID,
    is_active BOOLEAN,
    current_position  -- LONG | SHORT | NONE
    entry_price NUMERIC,
    current_stop NUMERIC,
    current_target NUMERIC,
    last_candle_ts TIMESTAMPTZ,
    last_indicator_values JSONB   -- ex: {"ema9": 42100.5, "rsi14": 28.3}
)
```

### 5.3 Boleta de Ordens — CEX e DeFi
- **Market** — execução imediata ao preço de mercado
- **Limit** — execução ao preço especificado
- **Stop Market** — ativação por stop + execução a mercado
- **Stop Limit** — ativação por stop + execução a preço limite
- **Trailing Stop** — stop dinâmico que acompanha o preço
- **OCO (One Cancels Other)** — Target + Stop simultâneos

Direções: **Long** (compra) e **Short** (venda a descoberto / futuros)

**DeFi (Orca/Solana):** a boleta DeFi tem comportamento diferente — não há conceito de "ordem limit" on-chain da mesma forma; uma swap na Orca é uma transação atômica com slippage configurado. A UI precisará de um modo específico para DeFi.

### 5.4 Indicadores — Configuração por Instância e Sistema de Plugins

#### 5.4.1 Painel de configuração ao adicionar indicador ao chart

Ao arrastar/clicar para adicionar um indicador no gráfico, o sistema abre um **modal de configuração** com:

- **Parâmetros específicos do indicador** (ex: RSI → período, nível sobrecomprado, nível sobrevendido)
- **Timeframe do indicador** — por padrão herdado do chart; pode ser sobrescrito (ex: RSI em 1H com chart em 5m)
- **Checkbox: enviar sinal para Telegram** — toggle por instância do indicador
- **Nome/label customizado** — para identificar na UI e na mensagem do Telegram

Exemplo de configuração persistida (PostgreSQL):
```json
{
  "indicator_instance_id": "rsi-btcusdt-1h-01",
  "type": "RSI",
  "symbol": "BTCUSDT",
  "timeframe": "1h",
  "params": {
    "period": 14,
    "overbought": 70,
    "oversold": 30
  },
  "telegram_signal": true,
  "label": "RSI 14 — 1H"
}
```

#### 5.4.2 Biblioteca de indicadores: built-in + plugins customizados

O pandas-ta cobre centenas de indicadores clássicos (RSI, EMA, MACD, Bollinger, etc.), mas **não cobre indicadores de price action** como MSS (Market Structure Shift), FVG (Fair Value Gap), Fibonacci com níveis customizados, etc. O sistema precisa de um **sistema de plugins**:

```python
# Interface que todo indicador (built-in ou customizado) deve implementar
class IndicatorPlugin(Protocol):
    name: str                          # ex: "MSS", "RSI", "FIB_RETRACEMENT"
    default_params: dict               # parâmetros e valores padrão
    config_schema: dict                # schema para gerar o painel de config na UI

    def calculate(self, candles: pd.DataFrame, params: dict) -> IndicatorResult:
        # Retorna valores calculados + lista de sinais disparados
        ...
```

**Indicadores built-in** (via pandas-ta, encapsulados no plugin):
RSI · EMA · SMA · MACD · Bollinger Bands · ATR · Volume · VWAP · Stochastic · etc.

**Indicadores customizados** (implementação própria):
- **MSS** (Market Structure Shift) — detecta quebra de estrutura de alta/baixa
- **FVG** (Fair Value Gap) — identifica gaps de valor justo no orderflow
- **Fibonacci Retracement** — calcula níveis de retração com sinal configurável (ex: disparar no nível 70.5%)
- **CHoCH** (Change of Character) — variante do MSS
- Qualquer outro que o usuário implemente seguindo a interface `IndicatorPlugin`

### 5.5 Construtor de Estratégias — Multi-Indicador e Multi-Timeframe

#### 5.5.1 Visão geral do construtor

O construtor é uma interface visual (no frontend) que permite:
1. **Adicionar indicadores** — cada um com suas configurações independentes (parâmetros + TF próprio)
2. **Definir condições de entrada** — relações entre os sinais dos indicadores
3. **Definir gestão de risco** — stop, target, tamanho de posição
4. **Salvar a estratégia** com nome para reutilização
5. **Selecionar modo de execução**: SINAL_APENAS | SEMI_AUTO | TOTALMENTE_AUTO

#### 5.5.2 Exemplo concreto — Estratégia RSI + MSS + Fibonacci

A estratégia descrita pelo usuário usa **3 indicadores em 2 timeframes diferentes** com uma **condição sequencial** (não simultânea):

```
Estratégia: "RSI Oversold + MSS Confirmation + Fib Entry"

Indicadores configurados:
  [1] RSI
      · timeframe: 1H
      · período: 14
      · sinal: RSI < 30 (sobrevenda)

  [2] MSS (Market Structure Shift)
      · timeframe: 5m
      · sinal: MSS de alta detectado (quebra de estrutura bullish)

  [3] Fibonacci Retracement
      · timeframe: 5m
      · referência: fundo → topo do movimento que gerou o MSS
      · sinal: preço retorna ao nível 70.5%

Condição de entrada (sequencial — máquina de estados):
  PASSO 1: aguardar RSI[1H] < 30
  PASSO 2: (após passo 1 ativo) aguardar MSS[5m] bullish
  PASSO 3: (após passo 2) aguardar preço tocar Fib[5m] @ 70.5%
  → ENTRADA: Long no toque do Fib 70.5%

Gestão de risco:
  · Stop: abaixo do fundo do MSS (5m)
  · Target: estrutura anterior (configurável)
  · Tamanho: % do capital configurável
```

#### 5.5.3 Modelo de máquina de estados — por que é necessário

Uma condição "todas verdadeiras ao mesmo tempo" (AND simples) **não resolve** estratégias sequenciais como a acima. O RSI 1H pode estar em sobrevenda por horas — o sistema precisa **recordar** que o passo 1 foi atingido e então monitorar o passo 2.

```
Estado da instância da estratégia:

IDLE
  │ RSI[1H] < 30
  ▼
AGUARDANDO_MSS          ← RSI confirmou, monitorando 5m
  │ MSS bullish[5m] detectado
  ▼
AGUARDANDO_FIBONACCI    ← grava fundo e topo do movimento MSS
  │ preço toca Fib 70.5%
  ▼
ENTRADA_SINALIZADA      → emite sinal / envia ordem
  │ ordem enviada
  ▼
EM_POSICAO              ← gerencia stop/target
  │ stop ou target atingido
  ▼
IDLE                    ← reset, aguarda próxima oportunidade
```

Cada instância de estratégia ativa mantém **seu estado atual** persistido no PostgreSQL — se o sistema reiniciar, o estado é recuperado e a estratégia continua exatamente de onde parou.

#### 5.5.4 Portabilidade da estratégia — live, replay e backtest

A **mesma definição de estratégia** (JSON salvo no banco) roda nos três modos sem alteração de código:

| Modo | Fonte de candles | Ordens | Diferença |
|------|-----------------|--------|-----------|
| **Live** | Redis Stream (Market Data Service) | Reais (ou paper) | Estado persiste continuamente |
| **Replay** | Redis Stream (Replay Service) | Simuladas | Velocidade controlada; estado reseta ao iniciar |
| **Backtest** | Leitura direta do TimescaleDB (sem stream) | Simuladas | Execução vetorizada/loop; mais rápido que replay |

O Strategy Runner recebe como parâmetro a **fonte de dados** — o código da estratégia e da máquina de estados é idêntico nos três casos.

### 5.6 Multi-Timeframe — Implicação Arquitetural no Strategy Runner

Estratégias multi-TF (como a do exemplo acima) exigem que o Strategy Runner **assine múltiplos streams de candles simultaneamente**:

```python
# Strategy Runner — subscrições MTF para uma estratégia
async def run_strategy(strategy: Strategy):
    # Assina todos os TFs necessários pelos indicadores da estratégia
    subscriptions = {
        "1h": redis.subscribe("candles:BTCUSDT:1h"),
        "5m": redis.subscribe("candles:BTCUSDT:5m"),
    }

    # Mantém buffers separados por TF
    buffers = {"1h": CandleBuffer(), "5m": CandleBuffer()}

    async for tf, candle in merge_streams(subscriptions):
        buffers[tf].update(candle)

        # Cada indicador processa apenas seu TF
        rsi_signal    = rsi_indicator.evaluate(buffers["1h"])    # RSI só olha 1H
        mss_signal    = mss_indicator.evaluate(buffers["5m"])    # MSS só olha 5m
        fib_signal    = fib_indicator.evaluate(buffers["5m"])    # Fib só olha 5m

        # Máquina de estados avalia os sinais
        state_machine.advance(rsi_signal, mss_signal, fib_signal)
```

**Consequência na camada de dados:** o Market Data Service precisa manter feeds ativos para **todos os TFs solicitados** pelas estratégias e indicadores ativos — não apenas o TF principal do chart. O Market Data Service consulta o banco de estratégias ativas para saber quais streams manter abertos.

### 5.7 Notification Service — Telegram

O Notification Service é um processo leve que **escuta o Redis Pub/Sub** e despacha mensagens para os canais configurados. Nenhum outro módulo importa ou chama o Telegram diretamente — tudo passa pelo bus.

**Tipos de mensagem e exemplos de formato:**

```
🟢 SINAL LONG — BTCUSDT 1h
Estratégia: EMA Cross + RSI
Condição: EMA9 cruzou EMA21 ↑ · RSI = 34
Preço atual: $83.420
Sugestão: entrada $83.420 · stop $82.100 · alvo $85.800

──────────────────────────────
✅ ORDEM ENVIADA — BTCUSDT
Tipo: Limit Long · $83.400
Qtd: 0.05 BTC · Alavancagem: 5×
Exchange: Bybit Testnet

──────────────────────────────
🔔 ORDEM PREENCHIDA — BTCUSDT
Preço exec: $83.398
PnL aberto: +$12.40 (+0.30%)

──────────────────────────────
🔴 STOP ATINGIDO — BTCUSDT
Saída: $82.105
PnL realizado: -$64.75 (-0.78%)
Duração: 2h 14min

──────────────────────────────
📊 RESUMO DIÁRIO — 2026-04-03
Trades: 4 · Wins: 3 · Losses: 1
PnL: +$187.30 · Win rate: 75%
```

**Arquitetura do Notification Service:**
```python
# Subscreve o Redis Pub/Sub e redireciona para os canais ativos
class NotificationService:
    async def run(self):
        async for event in redis.subscribe("events"):
            msg = self.format(event)          # formata para Telegram
            await self.telegram.send(msg)     # envia via aiogram
            await self.websocket.broadcast(msg)  # envia para UI simultaneamente
```

**Configuração por tipo de evento (usuário define o que quer receber):**

| Evento | Telegram | UI |
|--------|----------|----|
| Sinal de indicador | ✅ configurável | ✅ sempre |
| Ordem enviada | ✅ configurável | ✅ sempre |
| Ordem preenchida | ✅ configurável | ✅ sempre |
| Stop/Target atingido | ✅ sempre | ✅ sempre |
| Estratégia ON/OFF | ✅ configurável | ✅ sempre |
| Erro crítico | ✅ sempre | ✅ sempre |
| Resumo diário de PnL | ✅ configurável (horário) | ✅ dashboard |

> **aiogram vs python-telegram-bot:** o `aiogram 3` foi escolhido por ser totalmente async nativo (não cria threads extras), se integra perfeitamente com o `asyncio` já usado em toda a stack Python. O `python-telegram-bot` v20+ também suporta async, mas o aiogram tem uma API mais moderna e ergonômica.

A ambição de suportar múltiplas redes (Solana hoje, EVM amanhã) exige que o resto do sistema **não saiba** com qual rede está falando. Criamos uma interface comum:

```python
# Interface unificada — o Strategy Runner usa isso, não sabe se é Solana ou EVM
class BlockchainConnector(Protocol):
    async def get_price(self, symbol: str) -> Decimal: ...
    async def get_position(self, symbol: str) -> Position: ...
    async def send_swap(self, order: DeFiOrder) -> TxResult: ...
    async def get_balance(self) -> dict[str, Decimal]: ...

# Implementações concretas por rede
class SolanaConnector(BlockchainConnector):   # solders + solana-py + Orca
    ...

class ArbitrumConnector(BlockchainConnector): # web3.py + GMX (fase 2)
    ...
```

**Por que isso importa:** quando implementarmos Arbitrum/GMX na fase 2, o Strategy Runner, o Order Service e o Backtest Engine **não precisam mudar nada** — apenas uma nova implementação do conector é registrada.

**Comparação com CCXT:** é exatamente o mesmo padrão que o CCXT usa para CEX. Estamos replicando essa filosofia para o lado DeFi.

**Dados de preço Pyth na Solana:**
```python
# Pyth publica preços on-chain com ~400ms de atualização
# Ideal como fonte de dados para estratégias DeFi
pyth_price = await solana_connector.get_price("BTC/USD")  # lê do oráculo Pyth
```

---

## 6. Decisões de Arquitetura — Todas Fechadas ✅

### Decisões (2026-04-03)

| Questão | Decisão |
|---------|---------|
| **Usuários** | **Single-user** — uso pessoal/privado, sem multi-tenant |
| **Execução de ordens** | **Paper trading** na fase 1; execução real entra em fase posterior |
| **Exchange CEX primária** | **Bybit** (Spot + Futuros Perpétuos) via CCXT + ccxt.pro |
| **Deploy** | **Local** — Docker Compose apenas para infra (TimescaleDB + Redis) |
| **DeFi — rede prioritária** | **Solana** — arquitetura multi-chain desenhada para expansão futura |
| **DeFi — DEX prioritária** | **Orca Whirlpools** (AMM concentrado nativo da Solana) |
| **DeFi — oráculo** | **Pyth Network** (nativo Solana, ~400ms, SDK Python disponível) |
| **DeFi — expansão** | Fase 2+ adiciona redes EVM (Arbitrum, Base, Ethereum) via `web3.py` |
| **Multiplataforma** | Windows / Linux / macOS — stack toda é cross-platform |
| **Notificações** | **Telegram + UI** — bot via aiogram 3; configurável por tipo de evento |
| **Autenticação** | **Sem autenticação** — acesso local direto (localhost); sistema roda apenas na máquina do usuário |
| **Mobile** | **Web responsiva** — funciona no browser do celular sem app nativo; app nativo fora do escopo |
| **Carteira Solana** | **Carteira única em `.env`** — chave privada nunca entra no banco; configurada uma vez no ambiente local |
| **RPC Solana** | **Helius free tier** (100k req/dia) — suficiente para início; upgrade transparente se necessário |

---

## 7. Roadmap de Fases — Visão Geral

| Fase | Foco | CEX | DeFi | Estratégias / IA |
|------|------|-----|------|-----------------|
| **Fase 1** | Core do sistema | Bybit Testnet (paper trading) | Solana + Orca + Pyth | Indicadores com config por instância · Construtor com state machine MTF · Sinais · Semi-auto · Auto · Portabilidade live/replay/backtest |
| **Fase 2** | Execução real + Multi-CEX + IA | Bybit real + Binance, OKX, Kraken | EVM: Arbitrum, GMX, Uniswap | **AI Strategy Builder** (descreve em linguagem natural → gera config da estratégia) · Classificador de regime de mercado (LLM 4H/1D) · Plugins de indicadores da comunidade |
| **Fase 3** | Arbitragem + Expansão DeFi | Feed unificado multi-CEX | Base, Ethereum mainnet, novas DEX | Arbitragem CEX-CEX · Arbitragem CEX-DEX · Market making · Explicação de sinais por IA ("por que entrou aqui?") |
| **Plus** | Integrações externas | — | — | **TradingView Webhook:** receber alertas da TV via HTTP POST e rotear para execução · **Requer plano TV Pro + URL pública** |

> **Por que documentar as fases agora?** Porque algumas decisões de arquitetura da Fase 1 precisam ser tomadas com a Fase 3 em mente — especialmente a abstração do CEX Connector e do Blockchain Connector. Se não projetarmos as interfaces corretas agora, a expansão futura exigirá reescrita em vez de extensão.

---

## 8. Integração com LLM / IA — Fase 2

### 8.1 Decisão de design — onde NÃO usar LLM

LLM **não deve** ser usado como motor de sinal em tempo real (a cada tick ou candle), pelos seguintes motivos:

| Problema | Impacto |
|---|---|
| **Latência** (300ms–2s por chamada) | Inviável em TFs curtos; múltiplos símbolos explodem o tempo de processamento |
| **Custo por chamada de API** | Backtest de 2 anos em 1m ≈ ~1 milhão de chamadas → inviável financeiramente |
| **Não-determinismo** | O mesmo input pode gerar outputs diferentes → quebra reprodutibilidade do backtest |
| **Ausência de memória stateful** | Simular a máquina de estados exigiria enviar histórico completo a cada candle |

### 8.2 AI Strategy Builder — o uso principal (Fase 2)

O usuário descreve a estratégia em **linguagem natural** e o LLM traduz **uma única vez** para a configuração estruturada do sistema. Zero custo em produção, totalmente determinístico após a tradução.

```
[Usuário — AI Mode no construtor de estratégias]

"Comprar quando RSI 14 no 1H estiver abaixo de 30,
 aguardar um MSS bullish no gráfico de 5 minutos,
 após o MSS aguardar o preço retornar ao nível 70.5%
 de Fibonacci do movimento que gerou o MSS."

         ↓  chamada única ao LLM

[LLM gera a configuração da estratégia]

{
  "nome": "RSI Oversold + MSS + Fib Entry",
  "indicadores": [
    {"tipo": "RSI",             "tf": "1h", "params": {"period": 14, "oversold": 30}},
    {"tipo": "MSS",             "tf": "5m"},
    {"tipo": "FIB_RETRACEMENT", "tf": "5m", "params": {"level": 70.5}}
  ],
  "estado_maquina": [
    {"passo": 1, "condicao": "RSI[1h] < 30"},
    {"passo": 2, "condicao": "MSS[5m] = bullish"},
    {"passo": 3, "condicao": "PRECO toca FIB[5m] @ 70.5%"}
  ],
  "modo": "SINAL_APENAS"
}

         ↓  usuário revisa, ajusta parâmetros se quiser, salva
```

**O LLM age como um "compilador de linguagem natural → configuração"** — o sistema executa a configuração gerada com o mesmo engine determinístico de qualquer outra estratégia.

### 8.3 Classificador de Regime de Mercado (Fase 2 — experimental)

Uma chamada por candle fechado em timeframe **alto (4H ou 1D)** — custo e latência irrelevantes:

```python
# 1 chamada a cada 4 horas por símbolo monitorado
contexto = {
    "candles_1d": últimos_30_candles_diários,
    "candles_4h": últimos_50_candles_4h,
    "volume_media": ...,
    "atr_14": ...
}

resposta = llm.classify_regime(contexto)
# → {"regime": "tendência_alta", "volatilidade": "elevada",
#    "confiança": 0.82, "nota": "momentum forte acima da EMA200"}
```

Com base no regime classificado, o sistema pode **habilitar ou desabilitar estratégias automaticamente** — ex: desativar estratégias de reversão em tendências fortes.

### 8.4 Explicação de Sinais Disparados (Fase 3)

Quando um sinal é gerado, o LLM produz uma explicação em linguagem natural para a mensagem do Telegram:

```
🟢 SINAL LONG — BTCUSDT
Estratégia: RSI Oversold + MSS + Fib Entry

📊 Por que entrou aqui:
O RSI(14) no 1H atingiu 26.8 (zona de sobrevenda extrema).
Após 2 candles, detectado MSS bullish no 5m — quebra da
máxima anterior com volume 40% acima da média.
Preço retornou exatamente ao nível 70.5% de Fibonacci
($ 83.240) do movimento de alta de 11:35–11:42.
Configuração de alta probabilidade em confluência de 3 TFs.

Entrada: $83.240 · Stop: $82.850 · Alvo: $84.800
R/R: 1:3.9
```

### 8.5 Stack LLM sugerida

| Tecnologia | Papel | Justificativa |
|---|---|---|
| **OpenAI GPT-4o mini** ou **Google Gemini Flash 2.0** | LLM principal | Baixo custo por token, rápido, boa capacidade de seguir schemas JSON estruturados |
| **LangChain** ou chamada direta via SDK | Orquestração de prompts | LangChain para casos com chains complexas; SDK direto para casos simples como o Strategy Builder |
| **Structured Output / JSON Mode** | Garantia de output válido | Força o LLM a retornar JSON validado pelo schema Pydantic da configuração de estratégia |
| **Modelo local (Ollama + Llama 3)** | Alternativa offline opcional | Para quem não quer depender de API externa; qualidade inferior mas sem custo e sem latência de rede |

---

## 9. Próximos Passos

> ✅ Todas as decisões de arquitetura estão fechadas. O brainstorm está concluído.

1. Criar o documento formal de **Requisitos** (`organized/01-requisitos.md`).
2. Criar o documento de **Arquitetura Oficial** (`organized/02-arquitetura.md`).
3. Criar o **Plano de Ação** com fases e prioridades (`organized/03-plano-de-acao.md`).
4. Criar o **Tracking de Execução** (`organized/04-tracking.md`).

---

*Este documento é parte do processo de brainstorm e está sujeito a alterações. As decisões finais serão consolidadas nos documentos da pasta `organized/`.*
