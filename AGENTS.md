# AGENTS.md — RadarJarbis

## Objetivo

Ecossistema Python de automação para canais de afiliados do Telegram (Amazon e Mercado Livre) que lê ofertas de canais e grupos de origem (masters), filtra produtos por nicho/desconto, reformula mensagens com gatilhos de conversão, injeta as tags de afiliados do operador e publica no canal de destino.

## Arquitetura do Sistema

O projeto adota uma **Arquitetura Dual-Client Assíncrona**:
- **Telethon (MTProto)**: Executa com uma conta de usuário do Telegram para ler `SOURCE_CHANNEL_IDS` em tempo real (`events.NewMessage`) e recupera as 10 mensagens mais recentes ao iniciar ou reconectar.
- **python-telegram-bot (Bot API)**: Utilizado exclusivamente para despachar as ofertas filtradas e formatadas para `OUTPUT_CHANNEL_ID` via token de bot (`TELEGRAM_BOT_TOKEN`).
- **Dois Bots Independentes no Mesmo Repositório**:
  1. **Bot Amazon** (`src.bot`): Processa links da Amazon (`amzn.to`, `amazon.com.br`, `a.co`), extrai preços, parcelamento, selo Prime e cupons via `src/converters.py` e `src/filters.py`. Porta de métricas padrão: `8000`.
  2. **Bot Mercado Livre** (`src.bot_meli`): Processa URLs do Mercado Livre, resolve links encurtados/sociais, gera links `meli.la` e formata mensagens via `src/converters_meli.py` e `src/meli.py`. Porta de métricas padrão: `8001`.
- **Persistência e Deduplicação**:
  - SQLite local em modo WAL (`config/state.db` ou `config/state_meli.db`) gerenciado por `src/state.py`.
  - Deduplicação dinâmica por ASIN / Item ID (janela de 48h para queda de preço >= 10% ou 8 dias para o mesmo preço).
  - Mídia (fotos/vídeos) é manipulada puramente em memória (`io.BytesIO`) e nunca persistida em banco.
- **Métricas e Observabilidade**:
  - Módulo `src/metrics.py` expõe endpoints `/metrics` (Prometheus) e `/metrics.json` (Zabbix/HTTP Agent).

## Estrutura de Arquivos

- `src/bot.py`: Ponto de entrada do Bot Amazon.
- `src/bot_meli.py`: Ponto de entrada do Bot Mercado Livre.
- `src/settings.py`: Carregador centralizado de variáveis de ambiente (`.env` ou `config/.env`).
- `src/filters.py`: Regras de inclusão/exclusão por nicho e validações de desconto.
- `src/converters.py`: Parser de links Amazon, extração de preços, títulos, cupons e HTML final.
- `src/converters_meli.py`: Parser de links Mercado Livre e copywriting formatado.
- `src/meli.py`: Integração HTTP para resolução de produtos e geração de links de afiliados `meli.la`.
- `src/state.py`: Camada de persistência e deduplicação SQLite (thread-safe com locks).
- `src/metrics.py`: Servidor HTTP dual de métricas em background.
- `config/.env.example`: Modelo de configuração com placeholders genéricos.
- `docs/SETUP_GUIDE.md`: Guia de instalação e configuração passo a passo para terceiros.
- `docs/ZABBIX_MONITORING.md`: Guia de integração e monitoramento Zabbix.
- `radar-jarbis.service.example`: Modelo de serviço systemd para o bot Amazon.
- `radar-jarbis-meli.service.example`: Modelo de serviço systemd para o bot Mercado Livre.
- `tests/`: Suite de testes automatizados (`unittest`).

## Comandos de Desenvolvimento e Validação

Execute a partir da raiz do repositório:

```bash
# Instalar dependências
.venv/bin/pip install -r requirements.txt

# Executar Bot Amazon localmente
.venv/bin/python -m src.bot

# Executar Bot Mercado Livre localmente
SESSION_NAME=session_meli .venv/bin/python -m src.bot_meli

# Executar suite completa de testes
.venv/bin/python -m unittest discover -s tests -v

# Validar sintaxe Python
.venv/bin/python -m compileall -q src tests
```

## Restrições e Segurança (Hard Rules)

1. **Zero Hardcoding de Segredos**: Nunca registrar, exibir ou comitar tokens, senhas, hashes, chaves, sessões Telethon (`*.session`) ou arquivos `.env`.
2. **Preservação de Fallbacks e SQLite**: Nunca remover ou alterar o banco SQLite de deduplicação sem validação e testes automatizados.
3. **Anonimato e Neutralidade**: O projeto é genérico e desacoplado de dados pessoais do autor (nomes, caminhos absolutos locais ou credenciais fixas).
4. **Resiliência e Recursos**: Preservar compatibilidade com ambientes enxutos (VM de 1 vCPU / 1 GB RAM); evitar dependências pesadas e loops bloqueantes no event loop do asyncio.
5. **Critério de Conclusão**: Uma alteração só é considerada concluída quando a sintaxe foi verificada (`compileall`), os testes unitários passaram e nenhum dado sensível foi incluído no diff.
