# Plano de Ação — Sistema de Trade de Criptomoedas

> **Versão:** 1.0  
> **Data:** 2026-04-03  
> **Status:** Aprovado  
> **Depende de:** `01-requisitos.md`, `02-casos-de-uso.md`, `03-arquitetura.md`

---

## Metodologia

O desenvolvimento é organizado em **Sprints de 1 semana**, agrupados em milestones que entregam valor funcional incremental. Cada sprint tem um objetivo claro e tarefas rastreáveis no documento `05-tracking.md`.

**Princípios:**

1. **Infraestrutura antes da feature** — banco, Redis e serviços base antes de qualquer UI
2. **Contratos antes das implementações** — definir interfaces (`IndicatorPlugin`, `ExchangeConnector`) antes de implementar
3. **Core antes de optional** — State Machine + Strategy Runner + Market Data antes de Telegram e Backtest
4. **Testabilidade** — testes unitários obrigatórios para o motor de backtest e a state machine engine

---

## Fase 1 — Core (Estimativa: ~10 semanas)

### Milestones da Fase 1

| # | Milestone | Objetivo | Sprints |
|---|-----------|----------|---------|
| M1 | Setup & Infra | Ambiente pronto, banco criado, pipeline CI | 1 |
| M2 | Market Data + Chart ao vivo | Ver candles BTC ao vivo no frontend | 2–3 |
| M3 | Indicadores | RSI e EMA no chart, calculados corretamente | 4 |
| M4 | State Machine + Strategy Builder | Criar e salvar estratégia RSI-MSS-Fibonacci | 5 |
| M5 | Strategy Runner ao vivo | Estratégia disparando sinais em live | 6 |
| M6 | Boleta CEX + Ordens Manuais | Enviar ordem na Bybit Testnet pela UI | 7 |
| M7 | Replay | Validar estratégia em dados históricos | 8 |
| M8 | Backtest | Métricas de performance sobre histórico | 9 |
| M9 | Notificações Telegram | Sinais e ordens chegando no Telegram | 10 |

---

### Sprint 1 — Setup & Infraestrutura

**Objetivo:** Repositório configurado, ambiente de desenvolvimento rodando, banco criado com schema inicial.

| # | Tarefa | Tipo | Detalhes |
|---|--------|------|----------|
| 1.1 | Criar estrutura de diretórios do projeto | Setup | `backend/`, `frontend/`, `docker/`, conforme `03-arquitetura.md` seção 5 |
| 1.2 | Criar `docker-compose.yml` | Infra | TimescaleDB 2.x + Redis 7 + pgAdmin (opcional) |
| 1.3 | Configurar projeto Python com `pyproject.toml` | Setup | uv + FastAPI + SQLAlchemy 2 async + Pydantic v2 + Alembic |
| 1.4 | Criar modelos SQLAlchemy + primeira migração Alembic | Backend | Tabelas: `candles`, `strategies`, `strategy_indicators`, `strategy_steps`, `strategy_executions`, `orders`, `positions` |
| 1.5 | Criar entrypoint FastAPI mínimo | Backend | `GET /health` retorna 200; CORS liberado para localhost:5173 |
| 1.6 | Configurar projeto frontend | Frontend | `npm create vite@latest` com React + TypeScript; instalar TailwindCSS + shadcn/ui |
| 1.7 | Configurar linting e formatação | Setup | `ruff` + `mypy` para Python; `eslint` + `prettier` para TS |
| 1.8 | Configurar CI básico (GitHub Actions) | CI | lint + type check + `pytest` em push para `main` |
| 1.9 | Criar arquivo `.env.example` | Docs | Todas as variáveis necessárias, sem valores reais |

**Critério de conclusão:** `docker compose up -d` levanta banco e Redis; `uvicorn` inicia sem erro; `npm run dev` abre SPA em branco; CI passa.

---

### Sprint 2 — Market Data Service

**Objetivo:** Candles de BTC/USDT 5m chegando no Redis Stream via ccxt.pro.

| # | Tarefa | Tipo | Detalhes |
|---|--------|------|----------|
| 2.1 | Implementar `BybitConnector` com ccxt.pro | Backend | `watch_ohlcv()` para `BTC/USDT` em `5m`; publicar candle fechado no Redis Stream |
| 2.2 | Implementar `Market Data Service` base | Backend | Loop asyncio; gerenciar conexões WebSocket; publicar no Stream `candles:BTC/USDT:5m` |
| 2.3 | Persistir candles no TimescaleDB | Backend | A cada candle fechado, upsert na tabela `candles`; usar SQLAlchemy async |
| 2.4 | Endpoint REST para histórico de candles | Backend | `GET /api/candles/{symbol}/{timeframe}?limit=500` — lê do TimescaleDB |
| 2.5 | Reconexão automática | Backend | Detectar queda do WebSocket; preencher gap via `fetch_ohlcv` REST antes de retomar Stream |
| 2.6 | Testes unitários Market Data | Tests | Mock do ccxt.pro; testar publicação correta no Redis; testar reconexão |

**Critério de conclusão:** Redis Stream `candles:BTC/USDT:5m` recebe candles a cada abertura de novo candle; TimescaleDB acumula histórico.

---

### Sprint 3 — Gráfico ao Vivo no Frontend

**Objetivo:** Ver candlesticks BTC/USDT 5m ao vivo na UI com scroll de histórico.

| # | Tarefa | Tipo | Detalhes |
|---|--------|------|----------|
| 3.1 | Implementar WebSocket Gateway na API | Backend | Endpoint `/ws/candles/{symbol}/{timeframe}`; assinar Redis Stream e fazer forward para frontend |
| 3.2 | Criar componente Chart | Frontend | TradingView Lightweight Charts v4; chart tipo `candlestick` |
| 3.3 | Carregar histórico inicial | Frontend | `GET /api/candles/...` ao montar o componente; preencher chart com histórico |
| 3.4 | Conectar WebSocket ao vivo | Frontend | Receber candles em tempo real e atualizar o candle em formação |
| 3.5 | Seletor de timeframe | Frontend | Dropdown com todos os TFs; trocar TF fecha WebSocket atual e abre novo |
| 3.6 | Seletor de símbolo | Frontend | Input de busca; suportar qualquer par da Bybit |
| 3.7 | Indicador de status ao vivo | Frontend | Ponto verde "LIVE" visível no chart; ausente em outros modos |

**Critério de conclusão:** UC-01 passo 1–2 completo — usuário vê chart ao vivo e consegue trocar TF e símbolo.

---

### Sprint 4 — Indicadores Técnicos

**Objetivo:** Adicionar RSI e EMA ao chart; pipeline de cálculo de indicadores funcionando.

| # | Tarefa | Tipo | Detalhes |
|---|--------|------|----------|
| 4.1 | Definir `IndicatorPlugin` Protocol | Backend | Interface conforme `03-arquitetura.md` seção 7.1 |
| 4.2 | Implementar built-ins: RSI, EMA, SMA | Backend | Wrappers `pandas-ta` implementando `IndicatorPlugin` |
| 4.3 | Implementar built-ins: MACD, Bollinger Bands, ATR, Volume | Backend | Mesma abordagem |
| 4.4 | Implementar `MSS` plugin | Backend | Market Structure Shift — detectar HH/HL e LH/LL; emitir BULLISH/BEARISH |
| 4.5 | Implementar `FVG` plugin | Backend | Fair Value Gap — detectar gap de 3 candles; marcar zona no chart |
| 4.6 | Implementar `Fibonacci Retracement` plugin | Backend | Detectar retração dado swing high/low no contexto; verificar nível configurável |
| 4.7 | Implementar `CHoCH` plugin | Backend | Change of Character — inversão de estrutura |
| 4.8 | Endpoint para listar indicadores disponíveis | Backend | `GET /api/indicators` — retorna lista com nome, schema de parâmetros |
| 4.9 | Endpoint para salvar instância de indicador | Backend | `POST /api/chart/indicators` — persiste no PostgreSQL |
| 4.10 | UI: biblioteca de indicadores + painel de configuração | Frontend | Modal com lista categorizada; formulário dinâmico baseado no `params_schema` |
| 4.11 | UI: renderizar indicador no chart | Frontend | RSI em painel separado; EMA sobreposto; cores configuráveis |
| 4.12 | Suporte a indicador em TF diferente do chart | Frontend + Backend | Chart em 5m, RSI calculado sobre candles 1H; Market Data Service abre feed 1H automaticamente |
| 4.13 | Testes unitários de indicadores | Tests | Testar cálculo MSS, FVG e Fibonacci com fixtures de candles conhecidos |

**Critério de conclusão:** UC-01 completo — RSI 1H aparece no chart 5m; painel de configuração com todos os campos; configuração persiste após reload.

---

### Sprint 5 — Construtor de Estratégias + State Machine Engine

**Objetivo:** Criar e salvar estratégia RSI-MSS-Fibonacci com state machine de 3 passos.

| # | Tarefa | Tipo | Detalhes |
|---|--------|------|----------|
| 5.1 | Implementar `StateEngine` — motor central | Backend | Carregar definição de estratégia; avaliar condição do passo atual; transicionar estado; retornar evento |
| 5.2 | Testes unitários do `StateEngine` | Tests | Fixtures de sequência de candles; verificar transição de estado em cada passo; testar reset |
| 5.3 | Endpoints CRUD de estratégias | Backend | `POST /api/strategies`, `GET`, `PUT`, `DELETE`; serializar/deserializar state machine completa |
| 5.4 | UI: Construtor de Estratégias — tela base | Frontend | Layout com seção de indicadores, seção de passos sequenciais, seção de gestão de risco |
| 5.5 | UI: adicionar indicadores à estratégia | Frontend | Selecionar da biblioteca + configurar parâmetros inline |
| 5.6 | UI: definir passos da state machine | Frontend | Selecionar indicador, operador e valor por passo; reordenar passos por drag-and-drop |
| 5.7 | UI: configurar gestão de risco | Frontend | Stop loss (fixo, ATR, referência a contexto), take profit, tamanho de posição |
| 5.8 | UI: selecionar modo de execução | Frontend | Radio button: SINAL_APENAS / SEMI_AUTO / TOTALMENTE_AUTO |
| 5.9 | UI: resumo em linguagem natural | Frontend | Gerar texto descritivo da lógica da estratégia para revisão |
| 5.10 | Salvar e listar estratégias | Frontend | `POST` e `GET` da API; lista "Minhas Estratégias" |

**Critério de conclusão:** UC-02 completo — estratégia RSI-MSS-Fibonacci de 3 passos salva, listada e recarregada corretamente.

---

### Sprint 6 — Strategy Runner ao vivo

**Objetivo:** Strategy Runner executando estratégia em live, emitindo eventos de sinal.

| # | Tarefa | Tipo | Detalhes |
|---|--------|------|----------|
| 6.1 | Implementar Strategy Runner — loop asyncio | Backend | Carregar execuções ativas do PostgreSQL na inicialização; task por execução |
| 6.2 | Subscrição dinâmica a Redis Streams | Backend | Runner identifica TFs necessários e abre consumers para cada stream |
| 6.3 | Integrar `StateEngine` no Runner | Backend | A cada candle recebido, chamar `engine.evaluate(candle, state)` |
| 6.4 | Persistir transições de estado | Backend | Salvar `current_state` e `context` em `strategy_executions` a cada transição |
| 6.5 | Publicar eventos de sinal | Backend | `events.strategy.signal` e `events.strategy.transition` no Redis Pub/Sub |
| 6.6 | Endpoints para ativar/pausar/desativar estratégia | Backend | `POST /api/strategies/{id}/activate`, `/pause`, `/deactivate` |
| 6.7 | UI: painel de estratégias ativas | Frontend | Lista de execuções com estado atual (AGUARDANDO_RSI, etc.) |
| 6.8 | UI: feed de eventos em tempo real | Frontend | WebSocket para receber `events.*` e exibir na UI como notificações / log de atividade |
| 6.9 | Marcador visual no chart para sinais | Frontend | Ao receber `events.strategy.signal`, adicionar marcador no candle correto |
| 6.10 | Teste de integração Strategy Runner | Tests | Runner + StateEngine + Redis mock; verificar sequência completa de 3 estados |

**Critério de conclusão:** UC-05 parcial — estratégia dispara evento de sinal na UI; marcador aparece no chart; estado atualizado no painel.

---

### Sprint 7 — Boleta CEX e Execução de Ordens

**Objetivo:** Enviar e gerenciar ordens na Bybit Testnet; Strategy Runner em modo AUTO executa ordens.

| # | Tarefa | Tipo | Detalhes |
|---|--------|------|----------|
| 7.1 | Implementar `Order Service` | Backend | Receber comandos de ordem; delegar ao `BybitConnector`; persistir no PostgreSQL |
| 7.2 | `BybitConnector` — métodos de ordem | Backend | `create_order`, `cancel_order`, `fetch_balance`, `fetch_positions` via CCXT |
| 7.3 | `BybitConnector` — watch_orders | Backend | ccxt.pro `watch_orders()`; publicar `events.order.*` ao receber atualizações |
| 7.4 | Integrar Strategy Runner com Order Service | Backend | Modo AUTO: ao disparar sinal, chamar Order Service diretamente |
| 7.5 | Modo SEMI_AUTO — ordem pendente de confirmação | Backend | Criar `pending_orders` no banco; aguardar confirmação da UI |
| 7.6 | Endpoints de ordens | Backend | `POST /api/orders`, `DELETE /api/orders/{id}`, `GET /api/orders`, `POST /api/orders/{id}/confirm` |
| 7.7 | UI: Boleta CEX | Frontend | Formulário com: tipo de ordem, side, price, qty/%, stop, target; preview de liquidação |
| 7.8 | UI: lista de ordens abertas | Frontend | Tabela com status atualizado em tempo real via WebSocket |
| 7.9 | UI: painel de posições abertas | Frontend | Posição, PnL aberto, botão de fechar |
| 7.10 | UI: popup de confirmação SEMI_AUTO | Frontend | Alert modal quando chega `pending_order` via WebSocket |
| 7.11 | UI: saldo disponível | Frontend | Consumir endpoint de saldo; exibir na boleta |

**Critério de conclusão:** UC-06 completo; UC-05 completo — ordem automática enviada pela estratégia, atualiza status na UI.

---

### Sprint 8 — Replay de Mercado

**Objetivo:** Replay funcional; estratégia pode ser testada visualmente sobre dados históricos.

| # | Tarefa | Tipo | Detalhes |
|---|--------|------|----------|
| 8.1 | Implementar `Replay Service` | Backend | Ler candles do TimescaleDB; publicar no Stream `candles:{s}:{tf}` com controle de velocidade |
| 8.2 | Controle de velocidade | Backend | `asyncio.sleep()` proporcional à velocidade configurada (1×, 5×, 50×) |
| 8.3 | Controle de pausa e seek | Backend | Pausar suspende o loop; seek pula o `current_ts` interno para o timestamp solicitado |
| 8.4 | Endpoints de controle do replay | Backend | `POST /api/replay/start`, `/pause`, `/resume`, `/seek`, `/stop` |
| 8.5 | Isolamento de estado durante replay | Backend | Strategy Runner cria instância de estado separada para replay; estado live preservado |
| 8.6 | UI: painel de controles de replay | Frontend | Date range picker, seletor de velocidade, botões Play/Pause/Stop, barra de progresso |
| 8.7 | UI: indicador visual de modo replay | Frontend | Banner amarelo "REPLAY — dd/MM/yyyy" no topo do chart |
| 8.8 | Testes do Replay Service | Tests | Verificar ordem cronológica, velocidade, pausa e seek |

**Critério de conclusão:** UC-03 completo — replay de março 2024 com estratégia activa dispara sinais exatamente onde esperado.

---

### Sprint 9 — Backtest Engine

**Objetivo:** Executar backtest completo de 2 anos; dashboard com métricas e equity curve.

| # | Tarefa | Tipo | Detalhes |
|---|--------|------|----------|
| 9.1 | Implementar `Backtest Service` como Celery task | Backend | Carregar candles em lote; executar StateEngine em loop tight; coletar trades |
| 9.2 | Simulação de slippage e taxas | Backend | Preço de preenchimento = close + spread; PnL líquido após taxas |
| 9.3 | Calcular métricas de performance | Backend | Win rate, PnL total, drawdown máximo, Sharpe ratio, PnL médio, maior ganho/perda |
| 9.4 | Persistir resultado no PostgreSQL | Backend | Tabelas `backtest_runs` e `backtest_trades` |
| 9.5 | Publicar evento ao concluir | Backend | `events.backtest.completed` no Redis Pub/Sub |
| 9.6 | Endpoints de backtest | Backend | `POST /api/backtests` (inicia), `GET /api/backtests/{id}` (resultado), `GET /api/backtests` (lista) |
| 9.7 | UI: formulário de configuração de backtest | Frontend | Período, capital inicial, slippage, taxas |
| 9.8 | UI: dashboard de resultado | Frontend | Cards de métricas (win rate, PnL, drawdown, Sharpe) |
| 9.9 | UI: equity curve | Frontend | Gráfico de linha; um ponto por trade; tooltip com detalhes |
| 9.10 | UI: tabela de trades | Frontend | Lista paginada com: data, preço entrada/saída, PnL, duração, passo do sinal |
| 9.11 | Testes unitários do mecanismo de backtest | Tests | Verificar métricas corretas sobre sequência de trades conhecida |

**Critério de conclusão:** UC-04 completo — backtest de 2 anos conclui em < 60s; dashboard exibe todas as métricas.

---

### Sprint 10 — Notification Service + Telegram

**Objetivo:** Notificações Telegram e resumo diário funcionando.

| # | Tarefa | Tipo | Detalhes |
|---|--------|------|----------|
| 10.1 | Implementar `Notification Service` | Backend | Subscrever `events.*`; despachar para Telegram e UI WebSocket |
| 10.2 | Integrar aiogram 3 | Backend | Bot com `send_message`; mensagens formatadas por tipo de evento |
| 10.3 | Configuração de notificações por tipo | Backend | Tabela `notification_config` no PostgreSQL; toggles por evento × canal |
| 10.4 | Endpoint + UI para configurar notificações | Frontend | Tela de Configurações: Bot Token, Chat ID, botão de teste, toggles por tipo de evento |
| 10.5 | Resumo diário automatizado | Backend | APScheduler: job diário em horário configurável; calcula PnL do dia; publica evento `daily.summary` |

**Critério de conclusão:** UC-01 passo 9 completo (sinal chega no Telegram); tela de configurações permite configurar e testar o bot sem tocar em arquivos.

---

## Fase 2 — Expansão (início após Fase 1)

| Milestone | Conteúdo |
|-----------|----------|
| M10 | Bybit real (trocar credenciais no `.env`; habilitar envio real de ordens com confirmação dupla) |
| M11 | AI Strategy Builder — integrar LLM (GPT-4o mini ou Gemini Flash 2.0) via Structured Output |
| M12 | Multi-CEX — adicionar Binance como segundo `ExchangeConnector` |
| M13 | Classificador de regime de mercado (LLM) |

## Fase DeFi (início após Fase 2)

| Milestone | Conteúdo |
|-----------|----------|
| MD1 | Blockchain Connector — Solana (solders + solana-py, Orca, Pyth, Helius) |
| MD2 | Boleta DeFi — swap na Orca Whirlpools |
| MD3 | EVM Connector — Arbitrum/Base (web3.py, GMX/Uniswap) |

## Fase 3 — Avançado

| Milestone | Conteúdo |
|-----------|----------|
| M15 | Estratégias de arbitragem cross-exchange |
| M16 | Market making simples |
| M17 | Signal Explainer — LLM explica cada sinal disparado |

## Plus (paralelo / opcional)

| Item | Observação |
|------|------------|
| TradingView Webhook | Receber webhooks de alertas do TradingView Pro+; traduzir para evento interno |

---

## Dependências entre Sprints

```
Sprint 1 (Setup)
    └── Sprint 2 (Market Data)
            └── Sprint 3 (Chart ao vivo)
                    └── Sprint 4 (Indicadores)
                            └── Sprint 5 (Strategy Builder)
                                    └── Sprint 6 (Strategy Runner)
                                            ├── Sprint 7 (Boleta CEX)
                                            │       └── Sprint 8 (Replay)
                                            │               └── Sprint 9 (Backtest)
                                            └── Sprint 10 (Telegram) ← pode ser paralelo ao 7-9
```

Sprint 10 pode ser desenvolvido em paralelo com os sprints 7–9 pela separação clara de responsabilidades (Notification Service é independente da execução de ordens).

---

*Documento oficial — alterações devem ser versionadas com data e descrição da mudança no topo deste arquivo.*
