# Documento de Requisitos — Sistema de Trade de Criptomoedas

> **Versão:** 1.0  
> **Data:** 2026-04-03  
> **Status:** Aprovado para uso no plano de ação  
> **Origem:** Consolidado a partir do brainstorm `brainstorm/01-arquitetura-e-ferramentas.md`

---

## 1. Escopo do Produto

Sistema desktop-web single-user de trade de criptomoedas com suporte a CEX (exchange centralizada), com gráfico ao vivo, boleta de ordens, construtor de estratégias multi-timeframe, automação, backtest, replay de mercado e notificações via Telegram. Suporte a DeFi (Solana/Orca) está previsto para fase futura.

### 1.1 Premissas gerais

- **Single-user:** sem multi-tenant, sem gerenciamento de usuários
- **Sem autenticação:** acesso local via `localhost`; nenhuma credencial de login
- **Deploy local:** Docker Compose apenas para infraestrutura (banco + Redis); API e frontend rodam nativamente
- **Multiplataforma:** funciona em Windows, Linux e macOS sem alterações
- **Fase 1 em paper trading:** nenhuma ordem real é enviada na fase 1; Bybit Testnet simula execução com dados reais de mercado

---

## 2. Módulos e Requisitos Funcionais

---

### 2.1 Gráfico de Candlesticks em Tempo Real

#### Requisitos

| ID | Requisito |
|----|-----------|
| GR-01 | O sistema deve exibir gráfico de candlesticks (OHLCV) em tempo real para qualquer par suportado pela Bybit |
| GR-02 | O gráfico deve suportar múltiplos timeframes: 1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 12H, 1D, 1W |
| GR-03 | O candle em formação deve ser atualizado tick a tick via WebSocket (ccxt.pro `watch_ohlcv`) |
| GR-04 | O gráfico deve suportar sobreposição de indicadores na área do preço (ex: EMA, Bollinger Bands) |
| GR-05 | O gráfico deve suportar painéis separados para indicadores de oscilador (ex: RSI, MACD, Volume) |
| GR-06 | O gráfico deve exibir marcadores visuais nos candles onde sinais de entrada foram disparados |
| GR-07 | O gráfico deve exibir os níveis de entrada, stop e target das posições abertas como linhas horizontais |
| GR-08 | O usuário deve poder navegar no histórico (scroll, zoom) sem perder o feed ao vivo |
| GR-09 | O gráfico deve distinguir visualmente o modo ao vivo do modo replay (indicador de status visível) |
| GR-10 | O gráfico deve suportar tema escuro como padrão |

#### Critérios de aceite

- Candle ao vivo atualiza em menos de 500ms após cada tick da Bybit
- Trocar de timeframe não interrompe o feed; o novo TF carrega histórico do banco e reconecta o WebSocket
- Marcadores de sinal são persistidos e reexibidos ao recarregar o chart

---

### 2.2 Boleta de Ordens — CEX (Bybit)

#### Requisitos

| ID | Requisito |
|----|-----------|
| BO-01 | A boleta deve suportar os tipos de ordem: Market, Limit, Stop Market, Stop Limit, Trailing Stop e OCO (One Cancels Other) |
| BO-02 | A boleta deve suportar direções Long (compra) e Short (venda a descoberto / futuros perpétuos) |
| BO-03 | A boleta deve permitir configurar tamanho da posição em quantidade de ativo, valor em USDT ou percentual do saldo disponível |
| BO-04 | A boleta deve permitir configurar alavancagem para futuros perpétuos |
| BO-05 | A boleta deve exibir o preço de liquidação estimado antes da confirmação da ordem |
| BO-06 | A boleta deve exibir o campo de stop loss e take profit opcionais para todas as ordens |
| BO-11 | A boleta deve suportar saídas parciais da posição: o usuário deve poder fechar uma fração da posição aberta (ex: 25%, 50%, quantidade fixa) sem fechar a posição inteira |
| BO-12 | A boleta deve permitir configurar múltiplos alvos de saída parcial (ex: fechar 50% no alvo 1 e os 50% restantes no alvo 2), com preços e percentuais configuráveis individualmente |
| BO-13 | Ao executar uma saída parcial, o sistema deve atualizar o tamanho da posição aberta, o PnL realizado parcial e o PnL aberto remanescente em tempo real na UI |
| BO-07 | Na fase 1, todas as ordens devem ser direcionadas à Bybit Testnet; nenhuma ordem real é enviada |
| BO-08 | O resultado de cada ordem (enviada, preenchida, cancelada, rejeitada) deve ser publicado no bus de eventos para notificação |
| BO-09 | O histórico de ordens enviadas deve ser persistido no banco (PostgreSQL) com status atualizado em tempo real |
| BO-10 | A boleta deve exibir o saldo disponível atualizado (paper ou real, dependendo da fase) |
| BO-14 | Enquanto o usuário preenche a boleta (antes de confirmar), o gráfico deve exibir linhas horizontais de pré-visualização indicando os preços configurados: entrada (linha azul), stop loss (linha vermelha) e cada alvo de take profit / saída parcial (linhas verdes); as linhas devem desaparecer ao cancelar a boleta |
| BO-15 | O usuário deve poder arrastar as linhas de pré-visualização diretamente no gráfico para reposicionar os preços; ao soltar, o campo correspondente na boleta deve atualizar automaticamente com o novo valor |
| BO-16 | Ordens já enviadas e ainda abertas (Limit, Stop, TP, SL) devem ser exibidas como linhas arrastáveis no gráfico; ao arrastar e soltar, o sistema deve executar automaticamente a modificação da ordem na exchange (cancel + replace ou API de edição, conforme suporte da Bybit) |

#### Critérios de aceite

- Ordem Market é confirmada em menos de 2s após envio à Bybit Testnet
- Status da ordem atualiza na UI via WebSocket sem necessidade de refresh
- OCO cancela a segunda ordem automaticamente quando a primeira é executada
- Fechar 50% de uma posição Long de 0.1 BTC resulta em posição remanescente de 0.05 BTC, PnL parcial realizado registrado e PnL aberto recalculado
- Configurar dois alvos parciais (50% no alvo 1 e 50% no alvo 2) cria duas ordens Limit independentes; o cancelamento de uma não afeta a outra
- Ao abrir a boleta Limit Long e preencher preço $41.500, stop $41.100 e TP $42.300, três linhas (azul, vermelha, verde) aparecem imediatamente no gráfico nos níveis corretos antes de qualquer confirmação
- Arrastar a linha de stop loss de $41.100 para $41.000 no gráfico atualiza o campo "Stop Loss" da boleta para $41.000 sem nenhuma interação com o formulário
- Arrastar a linha de uma ordem Limit já aberta de $41.500 para $41.800 cancela a ordem anterior e cria nova ordem Limit a $41.800; a linha no gráfico se move para a posição final somente após confirmação da exchange

---

### 2.3 Boleta de Ordens — DeFi *(Fase Futura)*

> **Fora do escopo da Fase 1.** O suporte a DeFi (Boleta de swap na Orca Whirlpools / Solana, Blockchain Connector, carteira Solana) está documentado como requisito futuro na seção 4 e será detalhado quando a CEX estiver totalmente implantada e estável.

---

### 2.4 Indicadores Técnicos

#### Requisitos

| ID | Requisito |
|----|-----------|
| IN-01 | O sistema deve disponibilizar uma biblioteca de indicadores built-in baseada no pandas-ta (RSI, EMA, SMA, MACD, Bollinger Bands, ATR, VWAP, Stochastic, Volume, entre outros) |
| IN-02 | O sistema deve suportar indicadores customizados (price action) via sistema de plugins: MSS, FVG, Fibonacci Retracement, CHoCH e outros implementados pelo usuário |
| IN-03 | Ao adicionar um indicador ao gráfico, o sistema deve abrir um painel de configuração com os parâmetros específicos do indicador |
| IN-04 | O painel de configuração deve permitir definir o timeframe do indicador de forma independente do timeframe do gráfico principal (multi-timeframe) |
| IN-05 | O painel de configuração deve incluir um checkbox "Enviar sinal para o Telegram" por instância do indicador |
| IN-06 | O painel de configuração deve permitir definir um label customizado para identificar a instância do indicador |
| IN-07 | Cada instância de indicador deve ter sua configuração persistida no banco (PostgreSQL) e restaurada ao recarregar o sistema |
| IN-08 | O sistema de plugins deve seguir a interface `IndicatorPlugin` — qualquer indicador novo que implemente essa interface é automaticamente detectado pelo sistema |
| IN-09 | O indicador Fibonacci Retracement deve permitir configurar o nível exato de sinal (ex: 70.5%, 61.8%, 78.6%) |
| IN-10 | O indicador MSS deve detectar quebra de estrutura bullish e bearish e emitir sinal com direção |

#### Critérios de aceite

- Adicionar o RSI ao gráfico abre o painel com campos: período (padrão 14), nível sobrecomprado (padrão 70), nível sobrevendido (padrão 30), timeframe, checkbox Telegram, label
- Um indicador em timeframe diferente do chart (ex: RSI 1H em chart 5m) calcula corretamente usando candles do TF configurado
- Um plugin customizado colocado na pasta de plugins é reconhecido pelo sistema sem reinicialização

---

### 2.5 Construtor de Estratégias

#### Requisitos

| ID | Requisito |
|----|-----------|
| CS-01 | O sistema deve disponibilizar um Construtor de Estratégias — interface visual para combinar indicadores em estratégias complexas |
| CS-02 | O construtor deve permitir adicionar quantos indicadores forem necessários; cada um com configuração independente (tipo, parâmetros, timeframe, label) |
| CS-03 | O construtor deve permitir definir condições de entrada **sequenciais** (máquina de estados) — não apenas condições simultâneas (AND simples) |
| CS-04 | Cada passo da sequência deve referenciar o sinal de um indicador específico (ex: passo 1 = RSI[1H] < 30; passo 2 = MSS[5m] bullish) |
| CS-05 | A estratégia deve ter um nome definido pelo usuário e ser salva no banco para reutilização futura |
| CS-06 | O construtor deve permitir definir gestão de risco: stop loss, take profit, saídas parciais e tamanho de posição (%, valor fixo ou baseado em ATR) |
| CS-07 | O construtor deve permitir selecionar o modo de execução: `SINAL_APENAS`, `SEMI_AUTO` (aguarda confirmação manual) ou `TOTALMENTE_AUTO` |
| CS-08 | O construtor deve permitir configurar se a estratégia envia notificação Telegram ao disparar sinal e ao executar ordem |
| CS-09 | Uma estratégia salva deve poder ser carregada, editada e salva novamente sem criar duplicata (salvar como nova versão ou sobrescrever) |
| CS-10 | O construtor deve exibir um resumo da lógica da estratégia em linguagem natural ("Se RSI[1H] < 30, aguardar MSS[5m] bullish, ...") |
| CS-11 | O sistema deve disponibilizar um **AI Strategy Builder** (Fase 2): campo de texto onde o usuário descreve a estratégia em linguagem natural, e o LLM gera a configuração completa para revisão |
| CS-12 | O construtor deve permitir configurar múltiplos alvos de saída parcial, cada um com preço (valor fixo, percentual de ganho ou múltiplo de risco como 1R, 2R, 3R) e percentual da posição a fechar naquele alvo (ex: 50% no alvo 1 a 1R, 50% no alvo 2 a 2R) |
| CS-13 | O Strategy Runner deve executar cada saída parcial automaticamente ao atingir o alvo correspondente, sem cancelar as saídas restantes; o resumo em linguagem natural deve listar todos os alvos configurados |

#### Critérios de aceite

- Uma estratégia com 3 indicadores em 2 timeframes diferentes é salva e restaurada corretamente
- O modo SEMI_AUTO exibe um alerta na UI aguardando confirmação antes de enviar a ordem
- Configurar saída parcial de 50% a 1R e 50% a 2R resulta em duas ordens Limit geradas automaticamente após a entrada; a execução da primeira não cancela a segunda
- O resumo em linguagem natural da estratégia lista corretamente todos os alvos: "Fechar 50% a 1R ($42.100), fechar 50% restantes a 2R ($42.700)"
- O AI Strategy Builder (Fase 2) gera uma configuração válida a partir da descrição do exemplo RSI + MSS + Fibonacci

---

### 2.6 Strategy Runner — Execução de Estratégias

#### Requisitos

| ID | Requisito |
|----|-----------|
| SR-01 | O Strategy Runner deve ser um processo dedicado com loop asyncio contínuo, separado da API HTTP |
| SR-02 | O runner deve suportar múltiplas estratégias ativas simultaneamente, cada uma isolada |
| SR-03 | O runner deve implementar a máquina de estados por instância de estratégia — o estado atual (passo ativo, contexto) é persistido no PostgreSQL |
| SR-04 | Se o sistema reiniciar, o runner deve recuperar o estado de todas as estratégias ativas e retomar exatamente de onde parou |
| SR-05 | O runner deve assinar múltiplos streams de candles via Redis (um por timeframe necessário pelas estratégias ativas) |
| SR-06 | O runner deve notificar o Market Data Service sobre quais symbols e timeframes precisam ter feed ativo |
| SR-07 | No modo `SINAL_APENAS`: o runner publica o evento de sinal no Redis bus; nenhuma ordem é enviada |
| SR-08 | No modo `SEMI_AUTO`: o runner publica o evento de sinal e cria uma ordem pendente de confirmação na UI |
| SR-09 | No modo `TOTALMENTE_AUTO`: o runner envia a ordem diretamente para o Order Service sem intervenção humana |
| SR-10 | O runner deve emitir evento no bus para cada transição de estado da estratégia (ex: "passo 1 atingido — aguardando MSS") |
| SR-11 | O runner deve suportar a mesma fonte de candles para modo live (Market Data Service) e modo replay (Replay Service) sem alteração de código |

#### Critérios de aceite

- Estratégia com state machine de 3 passos transita corretamente entre estados ao receber os sinais na ordem certa
- Reinicialização do sistema não perde passo ativo nem contexto (fundo/topo do MSS para o Fibonacci)
- Múltiplas estratégias em símbolos e TFs diferentes rodam simultaneamente sem interferência

---

### 2.7 Replay de Mercado

#### Requisitos

| ID | Requisito |
|----|-----------|
| RP-01 | O sistema deve permitir selecionar qualquer período histórico disponível no banco para reprodução |
| RP-02 | O Replay Service deve publicar candles históricos no mesmo Redis Stream utilizado pelos dados ao vivo |
| RP-03 | O Frontend e o Strategy Runner devem receber os candles de replay **da mesma forma** que os candles ao vivo — sem código condicional |
| RP-04 | O replay deve suportar controle de velocidade: 1×, 5×, 10×, 50×, 100× |
| RP-05 | O replay deve suportar pausa e retomada |
| RP-06 | O replay deve suportar seek (pular para um candle/data específica) |
| RP-07 | Durante o replay, o gráfico deve exibir os candles sendo formados progressivamente, como se fossem dados ao vivo |
| RP-08 | O Strategy Runner deve poder ser ativado durante um replay — permitindo testar a estratégia manualmente enquanto os candles se formam |
| RP-09 | As ordens geradas durante o replay são simuladas (paper trading); nenhuma ordem real é enviada |
| RP-10 | O estado da estratégia deve ser resetado ao iniciar um replay; ao encerrar o replay, o estado live anterior é restaurado |

#### Critérios de aceite

- Selecionar um período no passado e pressionar Play exibe os candles sendo formados progressivamente no gráfico
- Mudar a velocidade de 1× para 50× não causa perda de candles nem dessincronia entre chart e Strategy Runner
- Uma estratégia ativada durante replay dispara sinais exatamente nos mesmos candles que dispararia em live

---

### 2.8 Backtest de Estratégias

#### Requisitos

| ID | Requisito |
|----|-----------|
| BT-01 | O sistema deve permitir selecionar uma estratégia salva e executar backtest sobre um período histórico definido |
| BT-02 | O backtest deve ler candles diretamente do TimescaleDB sem passar pelo Redis Stream (execução em lote, mais rápida que o replay) |
| BT-03 | O motor de backtest deve usar o mesmo engine de máquina de estados do Strategy Runner — garantindo que o comportamento seja idêntico ao live |
| BT-04 | O backtest deve simular slippage e taxas de execução configuráveis |
| BT-05 | O resultado do backtest deve incluir: total de trades, win rate, PnL total, PnL médio por trade, maior ganho, maior perda, drawdown máximo, Sharpe ratio |
| BT-06 | O resultado deve ser persistido no banco e exibido em um dashboard de backtest |
| BT-07 | O dashboard deve exibir o gráfico de equity curve (evolução do capital ao longo do backtest) |
| BT-08 | O dashboard deve exibir a lista de todos os trades com entrada, saída, PnL, duração e qual passo da state machine gerou a entrada |
| BT-09 | O backtest deve suportar estratégias multi-timeframe (o engine carrega todos os TFs necessários do banco) |
| BT-10 | O backtest deve ser executado em background (Celery) sem bloquear a API; o usuário recebe notificação quando concluído |

#### Critérios de aceite

- Backtest de 1 ano em 1H conclui em menos de 60 segundos
- O mesmo sinal disparado em live (dado histórico) é disparado identicamente no backtest
- Equity curve exibe cada trade como ponto na curva com tooltip de detalhes

---

### 2.9 Market Data Service

#### Requisitos

| ID | Requisito |
|----|-----------|
| MD-01 | O Market Data Service deve manter conexões WebSocket ativas com a Bybit via ccxt.pro para todos os símbolos e timeframes solicitados |
| MD-02 | O serviço deve publicar cada candle fechado no Redis Stream `candles:{symbol}:{timeframe}` |
| MD-03 | O serviço deve persistir cada candle fechado no TimescaleDB para uso em backtest e replay |
| MD-04 | O serviço deve gerenciar dinamicamente quais feeds manter abertos — baseado nos indicadores e estratégias ativas no momento |
| MD-05 | Se a conexão WebSocket cair, o serviço deve reconectar automaticamente e preencher os candles perdidos via REST |
| MD-06 | O serviço deve suportar coleta de histórico retroativo: ao adicionar um novo símbolo/TF, baixar o histórico disponível do banco para o TimescaleDB |

#### Critérios de aceite

- Ao adicionar um indicador RSI em 1H num chart que estava só com 5m, o serviço abre automaticamente o feed de 1H
- Queda e reconexão WebSocket não perde dados; candles perdidos são preenchidos via REST antes de publicar no Redis

---

### 2.10 Notification Service — Telegram e UI

#### Requisitos

| ID | Requisito |
|----|-----------|
| NT-01 | O Notification Service deve subscrever todos os eventos do Redis Pub/Sub e despachar notificações |
| NT-02 | Deve suportar dois canais de saída: **Telegram** (via bot aiogram 3) e **UI** (via WebSocket para o frontend) |
| NT-03 | Nenhum outro módulo deve chamar o Telegram diretamente; toda notificação passa pelo bus de eventos |
| NT-04 | As configurações do bot Telegram (`TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`) devem ser armazenadas em uma tabela `notification_settings` no PostgreSQL e gerenciadas exclusivamente pela tela de configurações do frontend; nunca em variáveis de ambiente |
| NT-05 | Os seguintes eventos devem gerar notificação: sinal disparado, ordem enviada, ordem preenchida, ordem cancelada, stop atingido, target atingido, estratégia ativada, estratégia pausada, erro crítico, resumo diário de PnL |
| NT-06 | O usuário deve poder configurar quais eventos são enviados ao Telegram (toggle por tipo de evento); eventos críticos (stop atingido, erro) são sempre enviados |
| NT-07 | A mensagem de sinal disparado deve incluir: símbolo, estratégia/indicador, condição que ativou, preço atual, sugestão de entrada/stop/target |
| NT-08 | A mensagem de ordem preenchida deve incluir: símbolo, tipo, preço de execução, PnL aberto |
| NT-09 | O resumo diário deve ser enviado automaticamente em horário configurável e incluir: nº de trades, win rate, PnL total do dia |
| NT-10 | Erros de envio ao Telegram (bot inativo, timeout) não devem travar outros serviços; o erro é logado e a notificação é descartada |
| NT-11 | O frontend deve disponibilizar uma tela de **Configurações de Notificações** onde o usuário pode: inserir/atualizar o Bot Token e o Chat ID do Telegram; testar a conexão com o bot (envio de mensagem de teste); habilitar/desabilitar o Telegram globalmente; e configurar os toggles por tipo de evento e o horário do resumo diário |

#### Critérios de aceite

- Sinal disparado gera mensagem no Telegram em menos de 3 segundos
- Desabilitar "Sinal de indicador" nas configurações para o Telegram não afeta as notificações na UI
- Falha no Telegram não propaga exceção para o Strategy Runner
- Após inserir Bot Token e Chat ID válidos na tela de configurações e clicar em "Testar", uma mensagem de teste chega no Telegram em menos de 5 segundos
- Alterar o Bot Token na tela de configurações é refletido imediatamente no Notification Service sem reinicialização do sistema
---

### 2.11 CEX Connector (Bybit — Fase 1)

#### Requisitos

| ID | Requisito |
|----|-----------|
| CC-01 | O conector deve usar CCXT + ccxt.pro como camada de abstração |
| CC-02 | Na Fase 1, conectar exclusivamente à Bybit Testnet; chaves de API configuradas via `.env` |
| CC-03 | O conector deve suportar: busca de saldo, envio de todos os tipos de ordem suportados (BO-01), cancelamento, consulta de status e consulta de posições abertas |
| CC-04 | O conector deve implementar a interface `ExchangeConnector` — garantindo que adicionar outras exchanges na Fase 2 não altere os módulos consumidores |
| CC-05 | O conector deve tratar rate limits da exchange com retry exponencial |
| CC-06 | Todas as credenciais de API (key, secret) devem ser carregadas de variáveis de ambiente; nunca hardcoded ou armazenadas no banco |

---

### 2.12 Blockchain Connector *(Fase Futura)*

> **Fora do escopo da Fase 1.** O Blockchain Connector (Solana + Orca + Pyth + Helius) será detalhado em fase posterior, após a conclusão completa do módulo CEX.

---

## 3. Requisitos Não-Funcionais

### 3.1 Performance

| ID | Requisito |
|----|-----------|
| PF-01 | Latência entre o fechamento de um candle na exchange e a avaliação da estratégia pelo runner: < 500ms |
| PF-02 | Backtest de 1 ano em timeframe 1H deve concluir em menos de 60 segundos |
| PF-03 | O frontend deve manter 60fps de renderização do chart com até 5 indicadores sobrepostos ativos |
| PF-04 | O sistema deve suportar pelo menos 5 estratégias ativas simultaneamente sem degradação perceptível |

### 3.2 Segurança

| ID | Requisito |
|----|-----------|
| SE-01 | Chaves de API da exchange devem ser armazenadas exclusivamente em variáveis de ambiente (.env local) |
| SE-02 | O arquivo `.env` deve estar no `.gitignore`; nunca deve ser commitado no repositório |
| SE-03 | A API FastAPI deve escutar apenas em `localhost` (127.0.0.1) por padrão |
| SE-04 | O banco de dados PostgreSQL deve aceitar conexões apenas de localhost |
| SE-05 | Logs do sistema não devem conter chaves privadas, tokens de API ou tokens do Telegram em nenhum nível de verbosidade |

### 3.3 Confiabilidade

| ID | Requisito |
|----|-----------|
| CF-01 | O Strategy Runner deve recuperar seu estado completo após reinicialização do processo em menos de 5 segundos |
| CF-02 | O Market Data Service deve reconectar WebSockets automaticamente em caso de queda, sem intervenção manual |
| CF-03 | Falha no Notification Service (Telegram offline, etc.) não deve afetar o funcionamento do Strategy Runner, Order Service ou Market Data Service |
| CF-04 | O sistema deve registrar logs estruturados para todos os eventos críticos (ordens, erros, transições de estado de estratégia) |

### 3.4 Manutenibilidade

| ID | Requisito |
|----|-----------|
| MT-01 | Cada módulo (Market Data, Order, Strategy, Backtest, Notification, CEX Connector) deve ter interface bem definida e ser substituível independentemente; a interface `BlockchainConnector` será definida na fase DeFi |
| MT-02 | Adicionar um novo indicador via plugin não deve exigir alteração em nenhum arquivo existente |
| MT-03 | Migrar da Bybit Testnet para a Bybit real deve exigir apenas troca de credenciais no `.env` |
| MT-04 | O sistema deve ter cobertura de testes unitários nos módulos de cálculo de indicadores e no motor de backtest |

---

## 4. Fora do Escopo — Fase 1

Os itens abaixo são reconhecidos como requisitos futuros mas **não fazem parte da Fase 1**:

| Item | Fase prevista |
|------|--------------|
| Execução de ordens reais (Bybit real) | Fase 2 |
| Multi-exchange CEX (Binance, OKX, Kraken) | Fase 2 |
| AI Strategy Builder (LLM) | Fase 2 |
| Classificador de regime de mercado (LLM) | Fase 2 |
| **Boleta DeFi — Orca / Solana** | **Fase DeFi** |
| **Blockchain Connector (solders + solana-py)** | **Fase DeFi** |
| **Carteira Solana + Pyth + Helius RPC** | **Fase DeFi** |
| Redes EVM (Arbitrum, Base, Ethereum) | Fase DeFi+ |
| Estratégias de arbitragem multi-exchange | Fase 3 |
| Market making | Fase 3 |
| Explicação de sinais por IA | Fase 3 |
| TradingView Webhook | Plus |
| Autenticação / login | Não previsto |
| App mobile nativo | Não previsto |

---

## 5. Restrições e Decisões Técnicas (resumo)

| Decisão | Valor |
|---------|-------|
| Linguagem backend | Python 3.12 |
| Framework API | FastAPI (ASGI async) |
| Framework frontend | React 18 + TypeScript + Vite |
| Biblioteca de chart | TradingView Lightweight Charts v4 |
| CEX connector | CCXT + ccxt.pro |
| Banco de séries temporais | TimescaleDB |
| Banco relacional | PostgreSQL 16 |
| Cache / event bus | Redis 7 |
| Indicadores built-in | pandas-ta |
| Notificações Telegram | aiogram 3 |
| Docker | Apenas para TimescaleDB + Redis |
| Blockchain connector | Fase DeFi (a definir) |

---

*Documento oficial — alterações devem ser versionadas com data e descrição da mudança no topo deste arquivo.*
