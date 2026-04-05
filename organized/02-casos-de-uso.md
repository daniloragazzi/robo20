# Casos de Uso — Sistema de Trade de Criptomoedas

> **Versão:** 1.0  
> **Data:** 2026-04-03  
> **Status:** Aprovado  
> **Depende de:** `01-requisitos.md`  
> **Atores primários:** Trader (único usuário local do sistema)

---

## Índice

1. [UC-01 — Configurar indicador no gráfico com sinal Telegram](#uc-01)
2. [UC-02 — Criar estratégia multi-timeframe no construtor](#uc-02)
3. [UC-03 — Validar estratégia no replay de mercado](#uc-03)
4. [UC-04 — Executar backtest e interpretar resultado](#uc-04)
5. [UC-05 — Ativar estratégia no mercado ao vivo](#uc-05)
6. [UC-06 — Enviar ordem manual na boleta CEX](#uc-06)
7. [UC-07 — Executar swap na Orca via boleta DeFi](#uc-07) *(Fase Futura)*
8. [UC-08 — Usar AI Strategy Builder para criar estratégia (Fase 2)](#uc-08)

---

## UC-01 — Configurar indicador no gráfico com sinal Telegram {#uc-01}

### Contexto

O trader quer monitorar o RSI de 14 períodos no timeframe 1H enquanto observa o gráfico em 5m do par BTC/USDT, e deseja receber uma notificação no Telegram sempre que o RSI entrar em zona de sobrevendido (< 30).

### Atores

- Trader

### Pré-condições

- Sistema rodando, Market Data Service conectado à Bybit
- Bot Telegram configurado (variável `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` no `.env`)
- Gráfico BTC/USDT 5m aberto

### Fluxo principal

1. Trader clica em "Adicionar Indicador" no painel do gráfico
2. Sistema exibe a biblioteca de indicadores categorizada (Trend, Oscillators, Volume, Price Action)
3. Trader seleciona RSI na categoria Oscillators
4. Sistema abre o painel de configuração do RSI com campos:
   - Período: `14` (padrão)
   - Nível sobrecomprado: `70`
   - Nível sobrevendido: `30`
   - Timeframe: `1H` ← trader **altera** de `5m` para `1H`
   - Checkbox "Enviar sinal para o Telegram": trader **marca**
   - Label: trader preenche `RSI-1H Oversold`
5. Trader confirma clicando em "Salvar"
6. Sistema persiste a configuração no PostgreSQL
7. Market Data Service abre o feed WebSocket de BTC/USDT 1H (se ainda não estiver aberto)
8. RSI-1H aparece no painel inferior do gráfico calculado sobre candles 1H
9. Na próxima vez que o RSI-1H cruzar abaixo de 30:
   - Sistema publica evento `indicator.signal` no Redis Pub/Sub
   - Notification Service recebe o evento
   - Mensagem enviada ao Telegram: *"🔔 RSI-1H Oversold — BTC/USDT | RSI(14)[1H] = 28.3 | Preço: $42.150 | Condição: Sobrevendido (< 30)"*
   - Marcador visual é exibido no candle correspondente no gráfico
10. Evento aparece também no feed de notificações da UI

### Fluxos alternativos

**4a.** Trader não altera o timeframe — indicador usa o mesmo TF do chart (5m). O Market Data Service não precisa abrir novo feed.

**9a.** Bot Telegram offline ou timeout: Notification Service loga o erro, descarta a notificação do Telegram, mas continua exibindo o evento na UI. O Strategy Runner não é afetado.

### Pós-condições

- Configuração do RSI-1H salva e restaurada ao reiniciar o sistema
- Feed de BTC/USDT 1H permanece ativo enquanto essa instância do RSI existir

---

## UC-02 — Criar estratégia multi-timeframe no construtor {#uc-02}

### Contexto

O trader quer criar uma estratégia de entrada long baseada em três condições sequenciais usando price action e RSI: primeiro o RSI 1H precisa estar sobrevendido; depois, no 5m, precisa aparecer um MSS bullish; finalmente, o preço deve retrair a pelo menos 61.8% de Fibonacci para confirmar entrada.

### Atores

- Trader

### Pré-condições

- Sistema rodando
- Par de interesse visível no gráfico

### Fluxo principal

1. Trader acessa o menu "Estratégias" → "Criar nova estratégia"
2. Sistema abre o Construtor de Estratégias com tela em branco
3. Trader define o nome: `RSI-MSS-Fibonacci Long`
4. Trader adiciona os indicadores necessários:
   - RSI com parâmetros: período 14, TF 1H, label `RSI-1H`
   - MSS com parâmetros: TF 5m, label `MSS-5m`
   - Fibonacci Retracement com parâmetros: nível de entrada 61.8%, TF 5m, label `Fib-5m`
5. Trader define a máquina de estados com 3 passos sequenciais:
   - **Passo 1 (AGUARDANDO_RSI):** condição = `RSI-1H < 30` → ao atingir, avança para Passo 2
   - **Passo 2 (AGUARDANDO_MSS):** condição = `MSS-5m == BULLISH` → ao atingir, salva contexto (fundo e topo do MSS), avança para Passo 3
   - **Passo 3 (AGUARDANDO_FIBONACCI):** condição = `Fib-5m atingiu 61.8% do contexto salvo` → ao atingir, dispara sinal de entrada
6. Trader define a gestão de risco:
   - Stop loss: abaixo do fundo do MSS salvo no contexto (referência ao contexto da state machine)
   - Take profit: 2:1 risco/retorno calculado dinamicamente
   - Tamanho de posição: 2% do saldo disponível
7. Trader seleciona modo de execução: `SEMI_AUTO`
8. Trader habilita notificação Telegram para: sinal disparado, ordem enviada/preenchida
9. Trader clica em "Salvar estratégia"
10. Sistema valida a configuração (todos os passos referenciam indicadores cadastrados, gestão de risco definida)
11. Sistema persiste a estratégia no PostgreSQL e exibe resumo em linguagem natural:
    > *"Se RSI(14)[1H] < 30, aguardar MSS bullish[5m], aguardar retração a 61.8% de Fibonacci[5m]. Entrada long com stop abaixo do fundo do MSS, alvo 2:1, tamanho 2% do saldo. Modo: aguardar confirmação manual."*

### Fluxos alternativos

**6a.** Trader define stop loss como valor fixo em vez de referência ao contexto: aceito, persiste como `STOP_FIXO` com o valor informado.

**10a.** Validação falha (ex: Passo 2 referencia um indicador que não foi adicionado): sistema exibe mensagem de erro específica e mantém o construtor aberto para correção.

### Pós-condições

- Estratégia salva e disponível na lista "Minhas Estratégias"
- Estratégia pronta para ser usada em replay, backtest ou ao vivo

---

## UC-03 — Validar estratégia no replay de mercado {#uc-03}

### Contexto

Antes de colocar a estratégia RSI-MSS-Fibonacci em live, o trader quer testar manualmente no replay de março de 2024 para observar visualmente como ela se comporta candle a candle.

### Atores

- Trader

### Pré-condições

- Estratégia `RSI-MSS-Fibonacci Long` criada (UC-02)
- Histórico de BTC/USDT (1H e 5m) de março de 2024 disponível no TimescaleDB

### Fluxo principal

1. Trader acessa o painel de Replay: seleciona símbolo `BTC/USDT`, início `01/03/2024`, fim `31/03/2024`
2. Trader seleciona TF principal `5m`
3. Trader vincula a estratégia `RSI-MSS-Fibonacci Long` ao replay
4. Trader define velocidade `5×` e pressiona Play
5. Replay Service inicia publicação de candles históricos no Redis Stream (mesmo canal do live)
6. Gráfico exibe candles se formando progressivamente; RSI 1H e MSS 5m são calculados em tempo real sobre os candles do replay
7. Quando ocorre o Passo 1 (RSI-1H < 30):
   - Estado da estratégia muda para `AGUARDANDO_MSS`
   - Marcador azul aparece no candle no gráfico
   - Evento exibido na UI (sem Telegram durante replay, a menos que configurado)
8. Quando ocorre o Passo 2 (MSS bullish 5m):
   - Estado muda para `AGUARDANDO_FIBONACCI`
   - Contexto (fundo/topo MSS) salvo; linha de referência desenhada no chart
9. Quando ocorre o Passo 3 (retração 61.8%):
   - Sinal de entrada disparado
   - Como modo é `SEMI_AUTO`: painel aparece na UI: *"Sinal detectado — entrar long BTC/USDT a $41.820? [Confirmar] [Rejeitar]"*
   - Ordem paper trade enviada após confirmação
10. Trader pausa o replay para examinar o setup com calma; retoma depois
11. Trader encerra o replay; estado da estratégia é resetado para o estado anterior ao início

### Fluxos alternativos

**4a.** Velocidade alterada para 50× no meio do replay: Replay Service ajusta o intervalo de publicação sem perda de candles.

**9a.** Trader rejeita a entrada no popup: ordem não é criada; estratégia reseta para Passo 1 (aguardando próxima oportunidade).

### Pós-condições

- Nenhuma ordem real ou testnet foi enviada
- Histórico de sinais do replay pode ser revisado no log de eventos

---

## UC-04 — Executar backtest e interpretar resultado {#uc-04}

### Contexto

Após validar visualmente no replay, o trader quer rodar um backtest automático de 2 anos da estratégia RSI-MSS-Fibonacci para ver estatísticas objetivas de performance.

### Atores

- Trader, Celery Worker (ator de sistema)

### Pré-condições

- Estratégia `RSI-MSS-Fibonacci Long` criada
- Histórico de 2 anos de BTC/USDT (1H e 5m) disponível no TimescaleDB

### Fluxo principal

1. Trader acessa "Backtests" → "Novo backtest"
2. Trader configura:
   - Estratégia: `RSI-MSS-Fibonacci Long`
   - Período: `01/01/2022 a 31/12/2023`
   - Capital inicial: `$10.000`
   - Slippage por trade: `0.05%`
   - Taxas: `0.06% maker / 0.10% taker`
3. Trader clica em "Executar"
4. Sistema cria job no Celery; UI exibe barra de progresso
5. Celery Worker carrega todos os candles do período (1H e 5m) do TimescaleDB em memória
6. Motor de backtest executa a state machine evento-a-evento sobre cada candle de 5m (consumindo 1H como TF secundário), simulando ordens com slippage e taxas
7. Ao concluir, Worker persiste resultado no PostgreSQL e publica evento `backtest.completed` no Redis
8. Notification Service recebe o evento e exibe alerta na UI: *"Backtest RSI-MSS-Fibonacci Long concluído ✓"*
9. Trader acessa o dashboard com o resultado:
   - Métricas: 47 trades, win rate 62%, PnL total +$3.840 (+38.4%), drawdown máximo -12%, Sharpe 1.42
   - Equity curve exibida como gráfico de linha
   - Tabela de trades com: data entrada, preço entrada, data saída, preço saída, PnL, duração, passo que gerou a entrada

### Fluxos alternativos

**6a.** TimescaleDB não tem dados suficientes para o período: sistema exibe aviso com o intervalo disponível e oferece ajustar o período ou baixar mais dados.

**9a.** Resultado ruim (ex: win rate < 30%): sem diferença de comportamento; todos os resultados são apresentados da mesma forma.

### Pós-condições

- Resultado do backtest persistido; pode ser revisitado sem executar novamente
- Trader pode decidir ajustar a estratégia e reexecutar o backtest (nova entrada na tabela de backtest)

---

## UC-05 — Ativar estratégia no mercado ao vivo {#uc-05}

### Contexto

Satisfeito com o resultado do backtest e com os testes no replay, o trader ativa a estratégia em modo automático completo na Bybit Testnet.

### Atores

- Trader, Strategy Runner (ator de sistema)

### Pré-condições

- Estratégia `RSI-MSS-Fibonacci Long` criada e testada
- Market Data Service com feed BTC/USDT 1H e 5m ativo
- Bybit Testnet configurada com saldo de paper money
- Modo de execução da estratégia: `TOTALMENTE_AUTO`

### Fluxo principal

1. Trader acessa "Estratégias" → seleciona `RSI-MSS-Fibonacci Long` → clica em "Ativar"
2. Sistema confirma: *"Ativar RSI-MSS-Fibonacci Long em modo TOTALMENTE_AUTO na Bybit Testnet? [Confirmar]"*
3. Trader confirma
4. Strategy Runner registra a estratégia como ativa; estado inicial = `AGUARDANDO_RSI`; estado persistido no PostgreSQL
5. Strategy Runner assina os Redis Streams `candles:BTC/USDT:1H` e `candles:BTC/USDT:5M`
6. Cada candle recebido é avaliado pela state machine:
   - RSI-1H calculado sobre o buffer de candles 1H
   - Se RSI-1H < 30 → estado → `AGUARDANDO_MSS`
7. Quando MSS bullish 5m detectado → estado → `AGUARDANDO_FIBONACCI`, contexto salvo
8. Quando retração 61.8% detectada → sinal disparado → state machine solicita ao Order Service envio de ordem Market Long
9. Order Service envia ordem via CEX Connector (Bybit Testnet) e publica resultado no bus
10. Notification Service despacha para Telegram: *"⚡ Ordem executada — Long BTC/USDT | Entrada: $42.310 | Stop: $41.900 | Alvo: $43.130 | Tamanho: 0.024 BTC"*
11. Posição aparece na boleta CEX com status "Aberta"
12. Quando stop ou target é atingido → Order Service fecha a posição → evento publicado → Telegram notificado
13. Estado da estratégia retorna para `AGUARDANDO_RSI` para aguardar próxima oportunidade

### Fluxos alternativos

**8a.** Bybit Testnet retorna erro (rate limit, símbolo inativo): CEX Connector aplica retry exponencial; se persistir, publica evento `order.error`; Notification Service notifica Telegram com a falha; estado da estratégia volta para `AGUARDANDO_RSI`.

**Reinicialização do sistema no meio do Passo 2 (AGUARDANDO_FIBONACCI):** Ao reiniciar, Strategy Runner lê o estado persistido no PostgreSQL, restaura contexto (fundo/topo do MSS) e retoma no Passo 3 sem requerer nova detecção do MSS.

### Pós-condições

- Trade registrado no histórico de ordens (PostgreSQL) com todos os detalhes
- Estratégia continua ativa aguardando próxima oportunidade até o trader desativar manualmente

---

## UC-06 — Enviar ordem manual na boleta CEX {#uc-06}

### Contexto

O trader viu uma oportunidade spot no gráfico e quer enviar uma ordem Limit Long diretamente pela boleta, sem passar por nenhuma estratégia automatizada.

### Atores

- Trader

### Pré-condições

- Bybit Testnet configurada
- Gráfico BTC/USDT aberto

### Fluxo principal

1. Trader acessa a boleta CEX (painel lateral direito)
2. Seleciona: direção `Long`, tipo `Limit`
3. Preenche:
   - Preço: `$41.500`
   - Quantidade: `0.01 BTC` (~$415)
   - Stop loss: `$41.100`
   - Take profit: `$42.300`
4. Sistema calcula e exibe: preço de liquidação estimado (para futuros com alavancagem), risco total ($4), relação risco/retorno (2:0)
5. Trader confirma; Order Service envia para Bybit Testnet via CCXT
6. Ordem aparece na lista de ordens abertas com status `PENDING`
7. Quando o preço atinge $41.500, a ordem é preenchida → status muda para `FILLED` via WebSocket
8. Notification Service notifica UI e Telegram: *"✅ Ordem preenchida — Limit Long BTC/USDT a $41.500"*

### Pós-condições

- Ordem registrada no histórico
- Posição apareee no painel de posições abertas

---

## UC-07 — Executar swap na Orca via boleta DeFi *(Fase Futura)* {#uc-07}

> **Fora do escopo da Fase 1.** Este caso de uso será detalhado quando o módulo DeFi for implementado. A interação envolve boleta de swap na Orca Whirlpools (Solana), Blockchain Connector (`solders` + `solana-py`), carteira via configuração segura, slippage máximo configurável e confirmação on-chain via Helius RPC.

---

## UC-08 — Usar AI Strategy Builder para criar estratégia (Fase 2) {#uc-08}

### Contexto

*(Fase 2 — não implementado na Fase 1)*

O trader não quer configurar a state machine manualmente. Ele descreve a estratégia em linguagem natural e o LLM gera a configuração completa para revisão.

### Atores

- Trader, LLM (GPT-4o mini / Gemini Flash 2.0)

### Pré-condições

- Chave de API do provedor LLM configurada no `.env`
- Biblioteca de indicadores disponível (para o LLM mapear corretamente)

### Fluxo principal

1. Trader acessa o Construtor de Estratégias → aba "AI Strategy Builder"
2. Trader digita no campo de texto:
   > *"Quero entrar long no BTC quando o RSI de 14 períodos no 1H estiver abaixo de 30, depois esperar um MSS bullish no 5 minutos, e só entrar quando o preço retrair para 61.8% de fibonacci. Stop abaixo do fundo do MSS, take profit 2:1."*
3. Trader clica em "Gerar estratégia"
4. Sistema faz uma chamada única (não streaming) ao LLM com o prompt do usuário + schema JSON da configuração de estratégia
5. LLM retorna JSON estruturado com toda a configuração preenchida
6. Sistema valida o JSON gerado contra o schema esperado
7. Sistema pre-preenche o Construtor de Estratégias com a configuração gerada
8. Trader revisa todos os campos, ajusta se necessário, e salva

### Critério-chave

- O LLM é chamado **uma única vez** ao criar a estratégia; nunca em tempo real durante execução
- O trader sempre revisa e confirma antes de salvar — o LLM não aciona execuções diretamente

### Pós-condições

- Estratégia salva é idêntica a uma estratégia criada manualmente; o fato de ter sido gerada por IA não é distinguível na execução

---

## Matriz de Rastreabilidade — Casos de Uso × Requisitos

| Caso de Uso | Requisitos cobertos |
|-------------|---------------------|
| UC-01 Configurar indicador | IN-01 a IN-10, GR-04, GR-05, GR-06, NT-01 a NT-08, MD-01 a MD-05 |
| UC-02 Criar estratégia | CS-01 a CS-11 |
| UC-03 Validar em replay | RP-01 a RP-10, SR-11 |
| UC-04 Executar backtest | BT-01 a BT-10 |
| UC-05 Ativar em live | SR-01 a SR-11, CC-01 a CC-06, NT-01 a NT-10 |
| UC-06 Ordem manual CEX | BO-01 a BO-16, CC-01 a CC-06 |
| UC-07 Swap DeFi | *Fase Futura — BD-xx e BC-xx a detalhar* |
| UC-08 AI Strategy Builder | CS-11 |

---

*Documento oficial — alterações devem ser versionadas com data e descrição da mudança no topo deste arquivo.*
