"""
Orquestrador dedicado do RadarJarbis para ofertas do Mercado Livre.

- Telethon TelegramClient : lê mensagens dos canais master via MTProto.
- python-telegram-bot Bot  : despacha ofertas formatadas para o canal configurado (ex: @mypromotest).
- src/converters_meli.py   : converte URLs e gera links meli.la de afiliado.
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

from . import converters, converters_meli, filters, meli, settings, state

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
logger = logging.getLogger("radardojarbis.meli_bot")

# ------------------------------------------------------------
# Métricas Prometheus
# ------------------------------------------------------------

MELI_MESSAGES_RECEIVED = prometheus_client.Counter(
    "meli_messages_received_total",
    "Total de mensagens recebidas para processamento Meli"
)
MELI_OFFERS_PUBLISHED = prometheus_client.Counter(
    "meli_offers_published_total",
    "Total de ofertas Meli publicadas com sucesso"
)
MELI_OFFERS_FILTERED = prometheus_client.Counter(
    "meli_offers_filtered_total",
    "Total de ofertas Meli filtradas e nao publicadas",
    ["reason"]
)
MELI_PROCESSING_LATENCY = prometheus_client.Histogram(
    "meli_message_processing_duration_seconds",
    "Tempo total de processamento de uma mensagem Meli",
    buckets=[0.5, 1.0, 2.0, 4.0, 8.0, 15.0, 30.0, 60.0]
)

_MAX_RECONNECT_ATTEMPTS = 5
_RECONNECT_BASE_DELAY = 10
_RECONNECT_MAX_DELAY = 300

user_client = TelegramClient(
    str(settings.SESSION_PATH),
    settings.TELEGRAM_API_ID,
    settings.TELEGRAM_API_HASH,
    connection_retries=10,
    retry_delay=2,
    auto_reconnect=True,
)

bot_client: Bot | None = None
_processing_msg_ids = set()


async def _safe_send(text: str, photo_bytes: bytes | None = None, max_retries: int = 3) -> None:
    """Despacha o post formatado do Mercado Livre com retry automático."""
    for attempt in range(1, max_retries + 1):
        try:
            if photo_bytes and len(text) <= 1024:
                await bot_client.send_photo(
                    chat_id=settings.OUTPUT_CHANNEL_ID,
                    photo=io.BytesIO(photo_bytes),
                    caption=text,
                    parse_mode=ParseMode.HTML,
                )
            else:
                if photo_bytes:
                    try:
                        await bot_client.send_photo(
                            chat_id=settings.OUTPUT_CHANNEL_ID,
                            photo=io.BytesIO(photo_bytes),
                        )
                    except Exception as pe:
                        logger.error(f"Erro ao despachar foto avulsa: {pe}")

                await bot_client.send_message(
                    chat_id=settings.OUTPUT_CHANNEL_ID,
                    text=text,
                    parse_mode=ParseMode.HTML,
                )
            logger.info("Post Mercado Livre despachado com sucesso.")
            MELI_OFFERS_PUBLISHED.inc()
            return
        except RetryAfter as e:
            wait = e.retry_after + 1
            logger.warning(f"Rate limit (RetryAfter). Aguardando {wait}s.")
            await asyncio.sleep(wait)
        except TelegramError as e:
            logger.error(f"Erro na Bot API: {e}. Tentativa {attempt}/{max_retries}.")
            await asyncio.sleep(5)

    logger.critical("Máximo de tentativas atingido. Mensagem Meli descartada.")
    MELI_OFFERS_FILTERED.labels(reason="max_retries").inc()


async def process_message_object(chat_id: int | str, message) -> None:
    """Pipeline de processamento para Mercado Livre."""
    text: str = message.text or ""
    if not text:
        return

    effective_chat_id = getattr(message, "chat_id", None) or chat_id
    message_id = message.id
    msg_id = f"meli:{effective_chat_id}:{message_id}"

    if msg_id in _processing_msg_ids:
        return
    _processing_msg_ids.add(msg_id)

    MELI_MESSAGES_RECEIVED.inc()
    start_time = time.perf_counter()

    try:
        # Filtro de relevância de conteúdo
        if not filters.is_relevant(text):
            logger.debug(f"[{msg_id}] Reprovado pelo filtro de relevância.")
            MELI_OFFERS_FILTERED.labels(reason="irrelevance").inc()
            return

        # Deduplicação no banco de dados local
        if state.already_posted(msg_id):
            logger.debug(f"[{msg_id}] Já postado anteriormente. Ignorando.")
            MELI_OFFERS_FILTERED.labels(reason="duplicate_msg").inc()
            return

        category = filters.get_category(text)
        logger.info(f"[{msg_id}] Aprovado — categoria: {category}. Processando Mercado Livre...")

        affiliate_url, item_id = await converters_meli.extract_meli_link_and_convert(
            text,
            cookies_str=settings.MELI_COOKIES,
            user_id=settings.MELI_USER_ID,
            affiliate_tag=settings.MELI_AFFILIATE_TAG,
        )
        if not affiliate_url:
            logger.info(f"[{msg_id}] Descartado: nenhuma URL Mercado Livre localizada/convertida.")
            MELI_OFFERS_FILTERED.labels(reason="no_meli_url").inc()
            state.mark_posted(msg_id)
            return

        product_name = converters._extract_product_name(text)
        price = converters._extract_price(text)
        installments = converters._extract_installments(text)
        coupon = converters._extract_coupon(text)
        teaser = converters._extract_teaser(text, product_name)

        if item_id and state.asin_already_posted(item_id, price=price, within_hours=settings.DEDUPLICATION_WINDOW_HOURS):
            logger.info(f"[{msg_id}] Descartado: Produto Meli ({item_id}) já postado recentemente com preço ({price}).")
            MELI_OFFERS_FILTERED.labels(reason="duplicate_item").inc()
            state.mark_posted(msg_id, asin=item_id, price=price)
            return

        formatted = converters_meli._format_meli_post(
            product_name=product_name,
            price=price,
            url=affiliate_url,
            installments=installments,
            coupon=coupon,
            teaser=teaser,
        )

        photo_bytes = None
        if message.photo:
            try:
                photo_bytes = await user_client.download_media(message, file=bytes)
                logger.info(f"[{msg_id}] Imagem da oferta baixada com sucesso (~{len(photo_bytes)} bytes).")
            except Exception as e:
                logger.warning(f"[{msg_id}] Não foi possível baixar imagem: {e}. Enviando texto.")

        await asyncio.sleep(settings.RATE_LIMIT_DELAY)
        await _safe_send(formatted, photo_bytes=photo_bytes)
        state.mark_posted(msg_id, asin=item_id, price=price)

    finally:
        _processing_msg_ids.discard(msg_id)
        MELI_PROCESSING_LATENCY.observe(time.perf_counter() - start_time)


@user_client.on(events.NewMessage(chats=settings.SOURCE_CHANNEL_IDS))
async def handle_new_offer(event) -> None:
    """Handler de novas mensagens em tempo real."""
    await process_message_object(event.chat_id, event.message)


async def main() -> None:
    """Inicializa o bot do Mercado Livre."""
    global bot_client

    logger.info("RadarJarbis Mercado Livre iniciando...")
    logger.info(f"Monitorando {len(settings.SOURCE_CHANNEL_IDS)} canal(is) master.")
    logger.info(f"Canal de saída: {settings.OUTPUT_CHANNEL_ID}")
    if not settings.MELI_COOKIES:
        logger.warning(
            "MELI_COOKIES não está configurado no .env! O bot sanitizará links de concorrentes, "
            "mas para gerar os links curtos meli.la oficiais da sua conta de afiliado, defina MELI_COOKIES."
        )

    try:
        meli_metrics_port = getattr(settings, "METRICS_PORT_MELI", 8001)
        prometheus_client.start_http_server(meli_metrics_port)
        logger.info(f"Métricas Prometheus do Mercado Livre ativas na porta {meli_metrics_port}.")
    except Exception as e:
        logger.error(f"Erro ao inicializar Prometheus metrics do Mercado Livre: {e}")

    attempt = 0
    async with Bot(token=settings.TELEGRAM_BOT_TOKEN) as bot:
        bot_client = bot

        while attempt < _MAX_RECONNECT_ATTEMPTS:
            try:
                await user_client.start()
                logger.info("Telethon conectado com sucesso!")

                # Processa as 5 mensagens mais recentes de cada canal ao iniciar
                for chat in settings.SOURCE_CHANNEL_IDS:
                    try:
                        messages = await user_client.get_messages(chat, limit=5)
                        for msg in reversed(messages):
                            if msg and msg.text:
                                await process_message_object(msg.chat_id, msg)
                    except Exception as e:
                        logger.error(f"Erro ao carregar mensagens recentes do canal {chat}: {e}")

                attempt = 0
                await user_client.run_until_disconnected()

            except (UnauthorizedError, AuthKeyError) as e:
                logger.critical(f"Erro de autenticação MTProto: {e}")
                break
            except FloodWaitError as e:
                logger.warning(f"FloodWait: aguardando {e.seconds}s...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                attempt += 1
                delay = min(_RECONNECT_BASE_DELAY * (2 ** (attempt - 1)), _RECONNECT_MAX_DELAY)
                logger.error(f"Erro no loop principal: {e}. Reconectando em {delay}s...")
                await asyncio.sleep(delay)
            finally:
                if user_client.is_connected():
                    await user_client.disconnect()

    state.close()
    logger.info("RadarJarbis Mercado Livre encerrado.")


if __name__ == "__main__":
    asyncio.run(main())
