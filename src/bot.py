"""
Orquestrador principal do RadarJarbis — Arquitetura Dual-Client.

- Telethon TelegramClient : lê mensagens dos canais master via MTProto (conta comum).
- python-telegram-bot Bot  : despacha ofertas formatadas para @noradardojarbis via bot token.

Resiliência de rede (camada de código):
    - Reconexão interna do Telethon : 10 tentativas, delay=2s (~20s de janela total).
    - Retry loop externo em main()  : backoff exponencial, máx. _MAX_RECONNECT_ATTEMPTS.
    - FloodWaitError                : espera o cooldown indicado e RETENTA — não encerra.
    - UnauthorizedError/AuthKeyError: encerramento limpo com instrução de recovery.

Gestão de recursos:
    - async with Bot(...): garante bot_client.shutdown() → httpx.AsyncClient.aclose().
    - state.close()      : fecha a conexão SQLite singleton no bloco finally principal.
"""

import asyncio
import io
import json
import logging
import time

import prometheus_client
from telethon import TelegramClient, events
from telethon.errors import AuthKeyError, FloodWaitError, UnauthorizedError
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import RetryAfter, TelegramError

from . import converters, filters, settings, state

# ------------------------------------------------------------
# Logging Estruturado (JSON)
# ------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        
        # Copia campos extras adicionados dinamicamente ao LogRecord
        for key, val in record.__dict__.items():
            if key not in {
                "args", "asctime", "created", "exc_info", "exc_text", "filename",
                "funcName", "levelname", "levelno", "lineno", "module",
                "msecs", "msg", "name", "pathname", "process", "processName",
                "relativeCreated", "stack_info", "thread", "threadName"
            }:
                log_record[key] = val
        return json.dumps(log_record)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter(datefmt="%Y-%m-%d %H:%M:%S"))

logging.basicConfig(
    level=logging.INFO,
    handlers=[handler]
)
logger = logging.getLogger("radardojarbis")

# ------------------------------------------------------------
# Métricas Prometheus (Sinais de Ouro)
# ------------------------------------------------------------

MESSAGES_RECEIVED = prometheus_client.Counter(
    "radar_messages_received_total",
    "Total de mensagens recebidas dos canais master para processamento"
)
OFFERS_PUBLISHED = prometheus_client.Counter(
    "radar_offers_published_total",
    "Total de ofertas publicadas com sucesso no canal de destino"
)
OFFERS_FILTERED = prometheus_client.Counter(
    "radar_offers_filtered_total",
    "Total de ofertas filtradas e nao publicadas",
    ["reason"]
)
PROCESSING_LATENCY = prometheus_client.Histogram(
    "radar_message_processing_duration_seconds",
    "Tempo total de processamento de uma mensagem (incluindo rate limit)",
    buckets=[0.5, 1.0, 2.0, 4.0, 8.0, 15.0, 30.0, 60.0]
)
ERRORS_TOTAL = prometheus_client.Counter(
    "radar_errors_total",
    "Total de erros e excecoes capturados",
    ["type"]
)
PROCESSING_CONCURRENCY = prometheus_client.Gauge(
    "radar_processing_concurrency",
    "Quantidade de mensagens sendo processadas concorrentemente em memoria"
)
RECONNECT_ATTEMPTS = prometheus_client.Gauge(
    "radar_reconnect_attempts",
    "Contador de tentativas sucessivas de reconexao do loop externo"
)

# ------------------------------------------------------------
# Constantes de reconexão externa (loop em main())
# ------------------------------------------------------------

_MAX_RECONNECT_ATTEMPTS = 5
_RECONNECT_BASE_DELAY   = 10    # segundos — base do backoff exponencial
_RECONNECT_MAX_DELAY    = 300   # 5 minutos — teto do backoff

# ------------------------------------------------------------
# Instância do cliente MTProto (Telethon)
#
# connection_retries=10 : dobra a janela de reconexão interna (~20s vs. ~5s padrão)
# retry_delay=2         : mais tempo entre tentativas internas (era 1s)
# auto_reconnect=True   : explicitado para clareza (já é o padrão)
# ------------------------------------------------------------

user_client = TelegramClient(
    str(settings.SESSION_PATH),
    settings.TELEGRAM_API_ID,
    settings.TELEGRAM_API_HASH,
    connection_retries=10,
    retry_delay=2,
    auto_reconnect=True,
)

# bot_client é gerenciado como async context manager dentro de main().
# Esta variável de módulo é preenchida antes do loop de eventos iniciar,
# garantindo que o handler já tenha acesso ao cliente ao receber mensagens.
bot_client: Bot | None = None


# ------------------------------------------------------------
# Rate limit e postagem segura
# ------------------------------------------------------------

async def _safe_send(text: str, photo_bytes: bytes | None = None, max_retries: int = 3) -> None:
    """Despacha o post (com imagem se houver) para o canal de saída com retry automático.

    Captura RetryAfter (bot API) e faz backoff respeitando o cooldown
    indicado pela API do Telegram.

    Args:
        text: Post formatado em HTML pronto para postagem.
        photo_bytes: Conteúdo binário da foto do anúncio original (opcional).
        max_retries: Número máximo de tentativas antes de descartar.
    """
    for attempt in range(1, max_retries + 1):
        try:
            if photo_bytes and len(text) <= 1024:
                # Se houver foto e o texto couber na legenda do Telegram (limite de 1024 caracteres)
                await bot_client.send_photo(
                    chat_id=settings.OUTPUT_CHANNEL_ID,
                    photo=io.BytesIO(photo_bytes),
                    caption=text,
                    parse_mode=ParseMode.HTML,
                )
            else:
                # Se não houver foto, ou se o texto for maior que o limite da legenda do Telegram,
                # envia a imagem de forma avulsa primeiro e depois despacha o texto completo.
                if photo_bytes:
                    try:
                        await bot_client.send_photo(
                            chat_id=settings.OUTPUT_CHANNEL_ID,
                            photo=io.BytesIO(photo_bytes),
                        )
                    except Exception as pe:
                        logger.error(f"Erro ao despachar foto avulsa: {pe}")
                        ERRORS_TOTAL.labels(type="media_dispatch").inc()

                await bot_client.send_message(
                    chat_id=settings.OUTPUT_CHANNEL_ID,
                    text=text,
                    parse_mode=ParseMode.HTML,
                )
            logger.info("Post despachado com sucesso.")
            OFFERS_PUBLISHED.inc()
            return
        except RetryAfter as e:
            wait = e.retry_after + 1
            logger.warning(
                f"Rate limit (RetryAfter). Aguardando {wait}s "
                f"(tentativa {attempt}/{max_retries})."
            )
            ERRORS_TOTAL.labels(type="telegram_api_retry_after").inc()
            await asyncio.sleep(wait)
        except TelegramError as e:
            logger.error(
                f"Erro na Bot API: {e}. "
                f"Tentativa {attempt}/{max_retries}."
            )
            ERRORS_TOTAL.labels(type="telegram_api_error").inc()
            await asyncio.sleep(5)

    logger.critical("Máximo de tentativas atingido. Mensagem descartada.")
    ERRORS_TOTAL.labels(type="message_discarded").inc()


# ------------------------------------------------------------
# ------------------------------------------------------------
# In-memory safety lock to prevent concurrent duplicate processing
# ------------------------------------------------------------
_processing_msg_ids = set()


async def process_message_object(chat_id: int | str, message) -> None:
    """Processa uma mensagem específica de um canal master.

    Pipeline:
        1. Valida se há texto.
        2. Evita concorrência na mesma mensagem (lock em memória).
        3. Filtra por categoria e desconto mínimo (filters.py).
        4. Verifica deduplicação no banco SQLite (state.py).
        5. Converte URLs e formata copywriting (converters.py).
        6. Aplica delay de rate limit.
        7. Despacha via bot token (_safe_send).
        8. Registra como postada no banco SQLite (state.py).
    """
    text: str = message.text or ""
    if not text:
        return

    effective_chat_id = getattr(message, "chat_id", None) or chat_id
    message_id = message.id
    msg_id = f"amazon:{effective_chat_id}:{message_id}"

    # Lock preventivo para evitar concorrência entre carga histórica e eventos em tempo real
    if msg_id in _processing_msg_ids:
        return
    _processing_msg_ids.add(msg_id)
    PROCESSING_CONCURRENCY.set(len(_processing_msg_ids))

    MESSAGES_RECEIVED.inc()
    start_time = time.perf_counter()

    try:
        # Filtro de categoria e desconto
        if not filters.is_relevant(text):
            logger.debug(f"[{msg_id}] Reprovado pelo filtro de relevância.")
            OFFERS_FILTERED.labels(reason="irrelevance").inc()
            return

        # Deduplicação no banco de dados
        if state.already_posted(msg_id):
            logger.debug(f"[{msg_id}] Já postado anteriormente (por msg_id). Ignorando.")
            OFFERS_FILTERED.labels(reason="duplicate").inc()
            return

        # Conversão e formatação
        category = filters.get_category(text)
        logger.info(f"[{msg_id}] Aprovado — categoria: {category}. Processando...")

        formatted = await converters.process_async(text)
        if not formatted:
            logger.info(f"[{msg_id}] Descartado: nenhuma URL Amazon localizada/convertida.")
            OFFERS_FILTERED.labels(reason="no_amazon_url").inc()
            # Marca como processado no banco para evitar reprocessamento futuro
            state.mark_posted(msg_id)
            return

        # Deduplicação por ASIN (mesmo produto de afiliado diferente)
        asin = converters.extract_asin(formatted)
        price = converters.extract_price(text)
        if asin and state.asin_already_posted(asin, price=price, within_hours=settings.DEDUPLICATION_WINDOW_HOURS):
            logger.info(
                f"[{msg_id}] Descartado: Produto (ASIN: {asin}) já postado "
                f"recentemente (limite de 48h para queda de preço >=10% ou 8 dias caso contrário) com o preço ({price})."
            )
            OFFERS_FILTERED.labels(reason="duplicate_asin").inc()
            # Marca o ID da mensagem para evitar reprocessá-la
            state.mark_posted(msg_id, asin=asin, price=price)
            return

        # Tenta baixar a foto original do anúncio (se houver)
        photo_bytes = None
        if message.photo:
            try:
                photo_bytes = await user_client.download_media(message, file=bytes)
                logger.info(f"[{msg_id}] Imagem da oferta baixada com sucesso (~{len(photo_bytes)} bytes).")
            except Exception as e:
                warning_msg = f"[{msg_id}] Não foi possível baixar a imagem: {e}. Enviando apenas texto."
                logger.warning(warning_msg)
                ERRORS_TOTAL.labels(type="media_download").inc()

        # Rate limit antes da postagem (GUARDRAILS.md §3)
        await asyncio.sleep(settings.RATE_LIMIT_DELAY)

        # Despacho
        await _safe_send(formatted, photo_bytes=photo_bytes)

        # Marca como postada
        state.mark_posted(msg_id, asin=asin, price=price)
    finally:
        _processing_msg_ids.discard(msg_id)
        PROCESSING_CONCURRENCY.set(len(_processing_msg_ids))
        PROCESSING_LATENCY.observe(time.perf_counter() - start_time)


# ------------------------------------------------------------
# Handler de novas mensagens em tempo real (Telethon)
# ------------------------------------------------------------

@user_client.on(events.NewMessage(chats=settings.SOURCE_CHANNEL_IDS))
async def handle_new_offer(event) -> None:
    """Processa cada nova mensagem recebida em tempo real dos canais master."""
    await process_message_object(event.chat_id, event.message)


# ------------------------------------------------------------
# Ponto de entrada
# ------------------------------------------------------------

async def main() -> None:
    """Inicializa os clientes e mantém o loop ativo com reconexão automática.

    Fluxo de lifecycle:
        1. `async with Bot(...)` inicializa o httpx.AsyncClient do PTB e garante
           seu encerramento (shutdown/aclose) ao sair do bloco — mesmo em exceção.
        2. O loop while gerencia reconexões externas com backoff exponencial.
        3. O bloco finally interno desconecta o MTProto a cada iteração.
        4. `state.close()` fora do `async with` fecha o SQLite singleton por último.
    """
    global bot_client

    logger.info("RadarJarbis iniciando...")
    logger.info(f"Monitorando {len(settings.SOURCE_CHANNEL_IDS)} canal(is) master.")
    logger.info(f"Canal de saída: {settings.OUTPUT_CHANNEL_ID}")

    # Inicializa o servidor de métricas do Prometheus
    try:
        prometheus_client.start_http_server(settings.METRICS_PORT)
        logger.info(f"Servidor de métricas do Prometheus ativo na porta {settings.METRICS_PORT}.")
    except Exception as e:
        logger.error(f"Erro ao inicializar o servidor de métricas: {e}")

    attempt = 0

    # async with garante bot_client.initialize() na entrada e
    # bot_client.shutdown() → httpx.AsyncClient.aclose() na saída.
    async with Bot(token=settings.TELEGRAM_BOT_TOKEN) as bot:
        bot_client = bot  # disponibiliza para _safe_send e handle_new_offer

        while attempt < _MAX_RECONNECT_ATTEMPTS:
            RECONNECT_ATTEMPTS.set(attempt)
            try:
                # start() autentica interativamente na 1ª execução (telefone + OTP).
                # Nas seguintes, usa o arquivo config/session.session.
                await user_client.start()
                logger.info(
                    "User client autenticado. Processando histórico recente..."
                )

                # Processa as últimas 5 mensagens de cada canal master
                for chat in settings.SOURCE_CHANNEL_IDS:
                    try:
                        messages = await user_client.get_messages(chat, limit=5)
                        # Inverte para processar da mais antiga para a mais recente
                        for msg in reversed(messages):
                            if msg.text:
                                await process_message_object(msg.chat_id, msg)
                    except Exception as e:
                        logger.error(f"Erro ao buscar histórico do canal {chat}: {e}")

                logger.info(
                    "Histórico recente processado. Aguardando mensagens... "
                    f"(ciclo {attempt + 1}/{_MAX_RECONNECT_ATTEMPTS})"
                )
                attempt = 0  # reseta contador após conexão bem-sucedida
                RECONNECT_ATTEMPTS.set(attempt)

                await user_client.run_until_disconnected()

            except FloodWaitError as e:
                # FloodWait não é falha de rede — não incrementa attempt.
                # Espera o cooldown e RETENTA a conexão.
                wait = e.seconds + 5
                logger.warning(
                    f"FloodWaitError: aguardando {wait}s antes de retentar conexão."
                )
                ERRORS_TOTAL.labels(type="telethon_flood").inc()
                await asyncio.sleep(wait)

            except (UnauthorizedError, AuthKeyError) as e:
                # Sessão inválida ou chave corrompida — não adianta retentar.
                logger.critical(
                    f"Erro de autenticação irrecuperável ({type(e).__name__}): {e}. "
                    "Delete config/session.session e reautentique o client."
                )
                ERRORS_TOTAL.labels(type="auth_error").inc()
                break  # sai do loop — intervenção manual necessária

            except (OSError, ConnectionError) as e:
                # Queda de rede após esgotamento das retentativas internas do Telethon.
                attempt += 1
                RECONNECT_ATTEMPTS.set(attempt)
                delay = min(
                    _RECONNECT_BASE_DELAY * (2 ** (attempt - 1)),
                    _RECONNECT_MAX_DELAY,
                )
                logger.error(
                    f"Erro de rede ({type(e).__name__}): {e}. "
                    f"Tentativa {attempt}/{_MAX_RECONNECT_ATTEMPTS}. "
                    f"Aguardando {delay}s antes de reconectar..."
                )
                ERRORS_TOTAL.labels(type="network_error").inc()
                if attempt >= _MAX_RECONNECT_ATTEMPTS:
                    logger.critical(
                        "Máximo de tentativas de reconexão atingido. Encerrando."
                    )
                    break
                await asyncio.sleep(delay)

            except KeyboardInterrupt:
                logger.info("Interrompido pelo operador.")
                break

            except Exception as e:
                # Catch-all: loga e retenta com delay fixo.
                attempt += 1
                RECONNECT_ATTEMPTS.set(attempt)
                logger.exception(
                    f"Exceção inesperada ({type(e).__name__}) — "
                    f"tentativa {attempt}/{_MAX_RECONNECT_ATTEMPTS}: {e}"
                )
                ERRORS_TOTAL.labels(type="unexpected_error").inc()
                if attempt >= _MAX_RECONNECT_ATTEMPTS:
                    logger.critical(
                        "Máximo de tentativas atingido após erro inesperado. Encerrando."
                    )
                    break
                await asyncio.sleep(_RECONNECT_BASE_DELAY)

            finally:
                # Garante desconexão limpa do MTProto a cada iteração do loop,
                # independente do caminho de saída (exceção, break ou loop normal).
                if user_client.is_connected():
                    await user_client.disconnect()
                    logger.info("User client (MTProto) desconectado.")

    # Encerramento final fora do `async with Bot`:
    # executado após bot_client.shutdown() garantir o fechamento do httpx.
    state.close()
    logger.info("RadarJarbis encerrado.")


if __name__ == "__main__":
    asyncio.run(main())
