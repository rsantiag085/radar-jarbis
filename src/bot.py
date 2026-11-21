"""
Orquestrador principal unificado do RadarJarbis (Amazon + Mercado Livre) — Arquitetura Dual-Client.

- Telethon TelegramClient : lê mensagens dos canais master via MTProto (conta comum).
- python-telegram-bot Bot  : despacha ofertas formatadas para OUTPUT_CHANNEL_ID via bot token.
- Roteamento Inteligente   : identifica se a oferta é da Amazon ou do Mercado Livre e aplica
                             o pipeline correspondente com deduplicação SQLite e cooldown de variedade.
- Observabilidade Dupla    : expõe métricas Prometheus e JSON nas portas 8000 (Amazon) e 8001 (Meli),
                             além de spans OpenTelemetry para ClickHouse / Zabbix 8.
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
from telegram.error import RetryAfter, TelegramError, TimedOut
from telegram.request import HTTPXRequest

from . import converters, converters_meli, filters, meli, metrics, settings, state, telemetry

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
# Métricas Prometheus — Amazon (Porta 8000)
# ------------------------------------------------------------

MESSAGES_RECEIVED = prometheus_client.Counter(
    "radar_messages_received_total",
    "Total de mensagens recebidas dos canais master para processamento Amazon"
)
OFFERS_PUBLISHED = prometheus_client.Counter(
    "radar_offers_published_total",
    "Total de ofertas Amazon publicadas com sucesso no canal de destino"
)
OFFERS_FILTERED = prometheus_client.Counter(
    "radar_offers_filtered_total",
    "Total de ofertas Amazon filtradas e nao publicadas",
    ["reason"]
)
PROCESSING_LATENCY = prometheus_client.Histogram(
    "radar_message_processing_duration_seconds",
    "Tempo total de processamento de uma mensagem Amazon (incluindo rate limit)",
    buckets=[0.5, 1.0, 2.0, 4.0, 8.0, 15.0, 30.0, 60.0]
)
ERRORS_TOTAL = prometheus_client.Counter(
    "radar_errors_total",
    "Total de erros e excecoes capturados (Amazon)",
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
# Métricas Prometheus — Mercado Livre (Porta 8001)
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
MELI_ERRORS_TOTAL = prometheus_client.Counter(
    "meli_errors_total",
    "Total de erros e excecoes capturados no fluxo Meli",
    ["type"]
)
MELI_RECONNECT_ATTEMPTS = prometheus_client.Gauge(
    "meli_reconnect_attempts",
    "Contador de tentativas sucessivas de reconexao do loop Meli"
)

# ------------------------------------------------------------
# Constantes de reconexão externa (loop em main())
# ------------------------------------------------------------

_MAX_RECONNECT_ATTEMPTS = 5
_RECONNECT_BASE_DELAY = 10    # segundos — base do backoff exponencial
_RECONNECT_MAX_DELAY = 300    # 5 minutos — teto do backoff

# ------------------------------------------------------------
# Instância do cliente MTProto (Telethon)
# ------------------------------------------------------------

user_client = TelegramClient(
    str(settings.SESSION_PATH),
    settings.TELEGRAM_API_ID,
    settings.TELEGRAM_API_HASH,
    connection_retries=10,
    retry_delay=2,
    auto_reconnect=True,
)

bot_client: Bot | None = None

# Locks em memória para evitar processamento concorrente duplicado
_processing_msg_ids: set[str] = set()
_processing_asins: set[str] = set()
_processing_items: set[str] = set()


# ------------------------------------------------------------
# Detecção de Plataforma
# ------------------------------------------------------------

def detect_platform(text: str) -> str:
    """Identifica a plataforma principal da mensagem ('meli', 'amazon' ou 'unknown').

    Inspeciona as URLs presentes no texto:
    - Domínios Mercado Livre (mercadolivre.com.br, meli.la, etc.) -> 'meli'
    - Domínios Amazon (amazon.com.br, amzn.to, a.co, etc.) -> 'amazon'
    - Links encurtados genéricos -> 'unknown' (testará Amazon primeiro e Meli como fallback)
    - Sem nenhuma URL -> 'none'
    """
    urls = converters._URL_PATTERN.findall(text)
    if not urls:
        return "none"

    for url in urls:
        if meli.is_meli_url(url) or meli.extract_meli_item_id(url):
            return "meli"
        if converters._is_amazon_url(url):
            return "amazon"

    return "unknown"


# ------------------------------------------------------------
# Rate limit e postagem segura
# ------------------------------------------------------------

async def _safe_send(
    text: str,
    photo_bytes: bytes | None = None,
    max_retries: int = 3,
    platform: str = "amazon",
) -> bool:
    """Despacha o post (com imagem se houver) para o canal de saída com retry automático.

    Captura RetryAfter (bot API) e faz backoff respeitando o cooldown
    indicado pela API do Telegram.

    Returns:
        True se a mensagem foi enviada (ou em caso de timeout ambíguo onde não reenviamos),
        False se todas as tentativas falharem.
    """
    pub_counter = MELI_OFFERS_PUBLISHED if platform == "meli" else OFFERS_PUBLISHED
    err_counter = MELI_ERRORS_TOTAL if platform == "meli" else ERRORS_TOTAL

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
                        logger.error(f"Erro ao despachar foto avulsa ({platform}): {pe}")
                        err_counter.labels(type="media_dispatch").inc()

                await bot_client.send_message(
                    chat_id=settings.OUTPUT_CHANNEL_ID,
                    text=text,
                    parse_mode=ParseMode.HTML,
                )
            logger.info(f"Post ({platform}) despachado com sucesso.")
            pub_counter.inc()
            return True
        except RetryAfter as e:
            wait = e.retry_after + 1
            logger.warning(
                f"Rate limit (RetryAfter - {platform}). Aguardando {wait}s "
                f"(tentativa {attempt}/{max_retries})."
            )
            err_counter.labels(type="telegram_api_retry_after").inc()
            await asyncio.sleep(wait)
        except TimedOut as e:
            # Timeout é ambíguo: o Telegram pode ter entregue a mensagem mesmo sem responder a tempo.
            # Reenviar causaria posts duplicados no canal, então NÃO retentamos.
            logger.warning(
                f"Timeout na Bot API ({platform}: {e}); entrega incerta — sem reenvio para evitar duplicidade."
            )
            err_counter.labels(type="telegram_api_timeout").inc()
            return True
        except TelegramError as e:
            logger.error(
                f"Erro na Bot API ({platform}): {e}. "
                f"Tentativa {attempt}/{max_retries}."
            )
            err_counter.labels(type="telegram_api_error").inc()
            await asyncio.sleep(5)

    logger.critical(f"Máximo de tentativas atingido ({platform}). Mensagem descartada.")
    err_counter.labels(type="message_discarded").inc()
    if platform == "meli":
        MELI_OFFERS_FILTERED.labels(reason="max_retries").inc()
    return False


# ------------------------------------------------------------
# Verificação de Cooldown de Variedade (Categoria / Subtipo)
# ------------------------------------------------------------

def _check_variety_cooldown(
    msg_id: str,
    category: str | None,
    subtype: str | None,
    filtered_counter: prometheus_client.Counter,
    span,
) -> bool:
    """Verifica se o canal está em cooldown global (7-19 min) ou se a categoria/subtipo está em cooldown (62 min).

    Returns:
        True se estiver bloqueado por cooldown, False se puder prosseguir.
    """
    if not getattr(settings, "ENABLE_COOLDOWN", False):
        return False

    min_post_cd = getattr(settings, "POST_COOLDOWN_MIN_MINUTES", 7)
    max_post_cd = getattr(settings, "POST_COOLDOWN_MAX_MINUTES", 19)
    cat_minutes = getattr(settings, "CATEGORY_COOLDOWN_MINUTES", 62)
    sub_minutes = getattr(settings, "SUBTYPE_COOLDOWN_MINUTES", 62)

    if max_post_cd > 0 and state.is_global_in_cooldown():
        logger.info(
            f"[{msg_id}] Descartado: Canal em cooldown global entre postagens ({min_post_cd}-{max_post_cd} min)."
        )
        filtered_counter.labels(reason="global_cooldown").inc()
        span.set_attribute("filter.reason", "global_cooldown")
        span.log(f"[{msg_id}] Canal em cooldown global ({min_post_cd}-{max_post_cd} min).", severity="INFO")
        span.end(status_code="STATUS_CODE_UNSET", status_message="Filtered: global_cooldown")
        return True

    if subtype and state.is_subtype_in_cooldown(subtype, minutes=sub_minutes):
        logger.info(f"[{msg_id}] Descartado: Subtipo '{subtype}' em cooldown ({sub_minutes} min).")
        filtered_counter.labels(reason="subtype_cooldown").inc()
        span.set_attribute("filter.reason", "subtype_cooldown")
        span.log(f"[{msg_id}] Subtipo '{subtype}' em cooldown.", severity="INFO")
        span.end(status_code="STATUS_CODE_UNSET", status_message="Filtered: subtype_cooldown")
        return True

    if category and state.is_category_in_cooldown(category, minutes=cat_minutes):
        logger.info(f"[{msg_id}] Descartado: Categoria '{category}' em cooldown ({cat_minutes} min).")
        filtered_counter.labels(reason="category_cooldown").inc()
        span.set_attribute("filter.reason", "category_cooldown")
        span.log(f"[{msg_id}] Categoria '{category}' em cooldown.", severity="INFO")
        span.end(status_code="STATUS_CODE_UNSET", status_message="Filtered: category_cooldown")
        return True

    return False


# ------------------------------------------------------------
# Pipeline Amazon
# ------------------------------------------------------------

async def _process_amazon_pipeline(
    effective_chat_id: int | str,
    message,
    text: str,
    allow_fallback_to_meli: bool = False,
) -> bool:
    """Processa uma mensagem no fluxo da Amazon.

    Returns:
        True se a mensagem era da Amazon (ou foi tratada definitivamente),
        False se `allow_fallback_to_meli=True` e nenhuma URL Amazon foi encontrada.
    """
    msg_id = f"amazon:{effective_chat_id}:{message.id}"
    if msg_id in _processing_msg_ids:
        return True
    _processing_msg_ids.add(msg_id)
    PROCESSING_CONCURRENCY.set(len(_processing_msg_ids))

    MESSAGES_RECEIVED.inc()
    start_time = time.perf_counter()
    reserved_asin: str | None = None
    span = telemetry.start_span(
        service_name="radar-jarbis-amazon",
        span_name="process_amazon_offer",
        attributes={"chat_id": str(effective_chat_id), "msg_id": str(msg_id)},
    )

    try:
        if not filters.is_relevant(text):
            logger.debug(f"[{msg_id}] Reprovado pelo filtro de relevância.")
            OFFERS_FILTERED.labels(reason="irrelevance").inc()
            span.set_attribute("filter.reason", "irrelevance")
            span.log(f"[{msg_id}] Reprovado pelo filtro de relevância.", severity="DEBUG")
            span.end(status_code="STATUS_CODE_UNSET", status_message="Filtered: irrelevance")
            return True

        if state.already_posted(msg_id):
            logger.debug(f"[{msg_id}] Já postado anteriormente (por msg_id). Ignorando.")
            OFFERS_FILTERED.labels(reason="duplicate").inc()
            span.set_attribute("filter.reason", "duplicate")
            span.log(f"[{msg_id}] Já postado anteriormente (por msg_id).", severity="DEBUG")
            span.end(status_code="STATUS_CODE_UNSET", status_message="Filtered: duplicate")
            return True

        category = filters.get_category(text)
        subtype = filters.get_subtype(text)
        logger.info(f"[{msg_id}] Aprovado — categoria: {category} (subtipo: {subtype}). Processando Amazon...")
        span.set_attribute("offer.category", category or "")
        if subtype:
            span.set_attribute("offer.subtype", subtype)
        span.log(f"[{msg_id}] Aprovado — categoria: {category}. Convertendo links...", severity="INFO")

        formatted = await converters.process_async(text)
        if not formatted:
            if allow_fallback_to_meli:
                span.set_attribute("filter.reason", "fallback_to_meli")
                span.end(status_code="STATUS_CODE_UNSET", status_message="Fallback to Meli")
                return False

            logger.info(f"[{msg_id}] Descartado: nenhuma URL Amazon localizada/convertida.")
            OFFERS_FILTERED.labels(reason="no_amazon_url").inc()
            state.mark_posted(msg_id)
            span.set_attribute("filter.reason", "no_amazon_url")
            span.log(f"[{msg_id}] Descartado: nenhuma URL Amazon localizada/convertida.", severity="INFO")
            span.end(status_code="STATUS_CODE_UNSET", status_message="Filtered: no_amazon_url")
            return True

        asin = converters.extract_asin(formatted) or converters.extract_asin(text)
        price = converters.extract_price(text)
        if asin:
            span.set_attribute("offer.asin", asin)
        if price:
            span.set_attribute("offer.price", str(price))

        if asin and asin in _processing_asins:
            logger.info(f"[{msg_id}] Descartado: ASIN {asin} já está em processamento por outra mensagem.")
            OFFERS_FILTERED.labels(reason="duplicate_asin").inc()
            state.mark_posted(msg_id, asin=asin, price=price)
            span.set_attribute("filter.reason", "duplicate_asin_concurrent")
            span.log(f"[{msg_id}] Descartado: ASIN {asin} em processamento concorrente.", severity="INFO")
            span.end(status_code="STATUS_CODE_UNSET", status_message="Filtered: duplicate_asin_concurrent")
            return True
        if asin:
            _processing_asins.add(asin)
            reserved_asin = asin

        if asin and state.asin_already_posted(asin, price=price, within_hours=settings.DEDUPLICATION_WINDOW_HOURS):
            logger.info(
                f"[{msg_id}] Descartado: Produto (ASIN: {asin}) já postado "
                f"recentemente (limite de 48h para queda de preço >=10% ou 25 dias caso contrário) com o preço ({price})."
            )
            OFFERS_FILTERED.labels(reason="duplicate_asin").inc()
            state.mark_posted(msg_id, asin=asin, price=price)
            span.set_attribute("filter.reason", "duplicate_asin_recent")
            span.log(f"[{msg_id}] Descartado: ASIN {asin} já postado recentemente com preço ({price}).", severity="INFO")
            span.end(status_code="STATUS_CODE_UNSET", status_message="Filtered: duplicate_asin_recent")
            return True

        if _check_variety_cooldown(msg_id, category, subtype, OFFERS_FILTERED, span):
            state.mark_posted(msg_id, asin=asin, price=price)
            return True

        photo_bytes = None
        if message.photo:
            try:
                photo_bytes = await user_client.download_media(message, file=bytes)
                logger.info(f"[{msg_id}] Imagem da oferta baixada com sucesso (~{len(photo_bytes)} bytes).")
                span.log(f"[{msg_id}] Imagem baixada ({len(photo_bytes)} bytes).", severity="DEBUG")
            except Exception as e:
                warning_msg = f"[{msg_id}] Não foi possível baixar a imagem: {e}. Enviando apenas texto."
                logger.warning(warning_msg)
                ERRORS_TOTAL.labels(type="media_download").inc()
                span.log(warning_msg, severity="WARNING")

        await asyncio.sleep(settings.RATE_LIMIT_DELAY)
        await _safe_send(formatted, photo_bytes=photo_bytes, platform="amazon")

        state.mark_posted(msg_id, asin=asin, price=price)
        if getattr(settings, "ENABLE_COOLDOWN", False):
            next_cd = state.record_cooldown(
                category=category,
                subtype=subtype,
                min_global_minutes=getattr(settings, "POST_COOLDOWN_MIN_MINUTES", 7),
                max_global_minutes=getattr(settings, "POST_COOLDOWN_MAX_MINUTES", 19),
            )
            logger.info(f"[{msg_id}] Cooldown registrado (próximo post liberado em {next_cd} min; categoria '{category}' por {getattr(settings, 'CATEGORY_COOLDOWN_MINUTES', 62)} min).")
        span.log(f"[{msg_id}] Oferta Amazon despachada com sucesso: ASIN={asin}", severity="INFO")
        span.end(status_code="STATUS_CODE_OK", status_message="Published")
        return True
    except Exception as e:
        span.set_status("STATUS_CODE_ERROR", str(e))
        span.log(f"[{msg_id}] Exceção inesperada: {e}", severity="ERROR")
        span.end()
        raise
    finally:
        span.end()
        if reserved_asin:
            _processing_asins.discard(reserved_asin)
        _processing_msg_ids.discard(msg_id)
        PROCESSING_CONCURRENCY.set(len(_processing_msg_ids))
        PROCESSING_LATENCY.observe(time.perf_counter() - start_time)


# ------------------------------------------------------------
# Pipeline Mercado Livre
# ------------------------------------------------------------

async def _process_meli_pipeline(
    effective_chat_id: int | str,
    message,
    text: str,
) -> None:
    """Processa uma mensagem no fluxo do Mercado Livre."""
    msg_id = f"meli:{effective_chat_id}:{message.id}"
    if msg_id in _processing_msg_ids:
        return
    _processing_msg_ids.add(msg_id)
    PROCESSING_CONCURRENCY.set(len(_processing_msg_ids))

    MELI_MESSAGES_RECEIVED.inc()
    start_time = time.perf_counter()
    reserved_item: str | None = None
    span = telemetry.start_span(
        service_name="radar-jarbis-meli",
        span_name="process_meli_offer",
        attributes={"chat_id": str(effective_chat_id), "msg_id": str(msg_id)},
    )

    try:
        if not filters.is_relevant(text):
            logger.debug(f"[{msg_id}] Reprovado pelo filtro de relevância.")
            MELI_OFFERS_FILTERED.labels(reason="irrelevance").inc()
            span.set_attribute("filter.reason", "irrelevance")
            span.log(f"[{msg_id}] Reprovado pelo filtro de relevância.", severity="DEBUG")
            span.end(status_code="STATUS_CODE_UNSET", status_message="Filtered: irrelevance")
            return

        if state.already_posted(msg_id):
            logger.debug(f"[{msg_id}] Já postado anteriormente. Ignorando.")
            MELI_OFFERS_FILTERED.labels(reason="duplicate_msg").inc()
            span.set_attribute("filter.reason", "duplicate_msg")
            span.log(f"[{msg_id}] Já postado anteriormente.", severity="DEBUG")
            span.end(status_code="STATUS_CODE_UNSET", status_message="Filtered: duplicate_msg")
            return

        category = filters.get_category(text)
        subtype = filters.get_subtype(text)
        logger.info(f"[{msg_id}] Aprovado — categoria: {category} (subtipo: {subtype}). Processando Mercado Livre...")
        span.set_attribute("offer.category", category or "")
        if subtype:
            span.set_attribute("offer.subtype", subtype)
        span.log(f"[{msg_id}] Aprovado — categoria: {category}. Convertendo link Meli...", severity="INFO")

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
            span.set_attribute("filter.reason", "no_meli_url")
            span.log(f"[{msg_id}] Descartado: nenhuma URL Mercado Livre localizada/convertida.", severity="INFO")
            span.end(status_code="STATUS_CODE_UNSET", status_message="Filtered: no_meli_url")
            return

        product_name = converters._extract_product_name(text)
        price = converters._extract_price(text)
        installments = converters._extract_installments(text)
        coupon = converters._extract_coupon(text)
        teaser = converters._extract_teaser(text, product_name)

        if item_id:
            span.set_attribute("offer.item_id", item_id)
        if price:
            span.set_attribute("offer.price", str(price))

        if item_id and item_id in _processing_items:
            logger.info(f"[{msg_id}] Descartado: Item Meli ({item_id}) já está em processamento por outra mensagem.")
            MELI_OFFERS_FILTERED.labels(reason="duplicate_item").inc()
            state.mark_posted(msg_id, asin=item_id, price=price)
            span.set_attribute("filter.reason", "duplicate_item_concurrent")
            span.log(f"[{msg_id}] Descartado: Item Meli ({item_id}) em processamento concorrente.", severity="INFO")
            span.end(status_code="STATUS_CODE_UNSET", status_message="Filtered: duplicate_item_concurrent")
            return
        if item_id:
            _processing_items.add(item_id)
            reserved_item = item_id

        if item_id and state.asin_already_posted(item_id, price=price, within_hours=settings.DEDUPLICATION_WINDOW_HOURS):
            logger.info(
                f"[{msg_id}] Descartado: Produto Meli ({item_id}) já postado "
                f"recentemente (limite de 48h para queda de preço >=10% ou 25 dias caso contrário) com preço ({price})."
            )
            MELI_OFFERS_FILTERED.labels(reason="duplicate_item").inc()
            state.mark_posted(msg_id, asin=item_id, price=price)
            span.set_attribute("filter.reason", "duplicate_item_recent")
            span.log(f"[{msg_id}] Descartado: Item Meli ({item_id}) já postado recentemente com preço ({price}).", severity="INFO")
            span.end(status_code="STATUS_CODE_UNSET", status_message="Filtered: duplicate_item_recent")
            return

        if _check_variety_cooldown(msg_id, category, subtype, MELI_OFFERS_FILTERED, span):
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
                span.log(f"[{msg_id}] Imagem baixada ({len(photo_bytes)} bytes).", severity="DEBUG")
            except Exception as e:
                logger.warning(f"[{msg_id}] Não foi possível baixar imagem: {e}. Enviando texto.")
                MELI_ERRORS_TOTAL.labels(type="media_download").inc()
                span.log(f"[{msg_id}] Falha ao baixar imagem: {e}", severity="WARNING")

        await asyncio.sleep(settings.RATE_LIMIT_DELAY)
        await _safe_send(formatted, photo_bytes=photo_bytes, platform="meli")

        state.mark_posted(msg_id, asin=item_id, price=price)
        if getattr(settings, "ENABLE_COOLDOWN", False):
            next_cd = state.record_cooldown(
                category=category,
                subtype=subtype,
                min_global_minutes=getattr(settings, "POST_COOLDOWN_MIN_MINUTES", 7),
                max_global_minutes=getattr(settings, "POST_COOLDOWN_MAX_MINUTES", 19),
            )
            logger.info(f"[{msg_id}] Cooldown registrado (próximo post liberado em {next_cd} min; categoria '{category}' por {getattr(settings, 'CATEGORY_COOLDOWN_MINUTES', 62)} min).")
        span.log(f"[{msg_id}] Oferta Meli despachada com sucesso: item_id={item_id}", severity="INFO")
        span.end(status_code="STATUS_CODE_OK", status_message="Published")

    except Exception as e:
        span.set_status("STATUS_CODE_ERROR", str(e))
        span.log(f"[{msg_id}] Exceção inesperada: {e}", severity="ERROR")
        span.end()
        raise
    finally:
        span.end()
        if reserved_item:
            _processing_items.discard(reserved_item)
        _processing_msg_ids.discard(msg_id)
        PROCESSING_CONCURRENCY.set(len(_processing_msg_ids))
        MELI_PROCESSING_LATENCY.observe(time.perf_counter() - start_time)


# ------------------------------------------------------------
# Roteador Principal de Mensagens
# ------------------------------------------------------------

async def process_message_object(chat_id: int | str, message) -> None:
    """Roteia uma mensagem de canal master para o pipeline Amazon ou Mercado Livre."""
    text: str = message.text or ""
    if not text:
        return

    effective_chat_id = getattr(message, "chat_id", None) or chat_id
    platform = detect_platform(text)

    if platform == "meli":
        await _process_meli_pipeline(effective_chat_id, message, text)
    elif platform == "amazon":
        await _process_amazon_pipeline(effective_chat_id, message, text, allow_fallback_to_meli=False)
    elif platform == "unknown":
        # Link encurtado genérico: tenta resolver como Amazon primeiro; se não for, tenta Meli
        handled = await _process_amazon_pipeline(effective_chat_id, message, text, allow_fallback_to_meli=True)
        if not handled:
            await _process_meli_pipeline(effective_chat_id, message, text)
    else:
        # Sem URL alguma: executa pelo pipeline Amazon padrão para contabilizar filtro (irrelevance / no_amazon_url)
        await _process_amazon_pipeline(effective_chat_id, message, text, allow_fallback_to_meli=False)


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

def get_amazon_metrics_payload() -> dict:
    """Gera o payload JSON de métricas da Amazon (Porta 8000)."""
    latency_stats = metrics.extract_histogram_stats(PROCESSING_LATENCY)
    return {
        "messages_received": metrics.extract_counter_value(MESSAGES_RECEIVED),
        "offers_published": metrics.extract_counter_value(OFFERS_PUBLISHED),
        "offers_filtered": metrics.extract_counter_value(OFFERS_FILTERED),
        "offers_filtered_by_reason": metrics.extract_labeled_counter_values(OFFERS_FILTERED),
        "processing_latency_avg_seconds": latency_stats["avg_seconds"],
        "processing_latency": latency_stats,
        "errors_total": metrics.extract_counter_value(ERRORS_TOTAL),
        "errors_by_type": metrics.extract_labeled_counter_values(ERRORS_TOTAL),
        "reconnect_attempts": metrics.extract_counter_value(RECONNECT_ATTEMPTS),
        "memory_rss_bytes": metrics.get_process_memory_rss_bytes(),
    }


def get_meli_metrics_payload() -> dict:
    """Gera o payload JSON de métricas do Mercado Livre (Porta 8001)."""
    latency_stats = metrics.extract_histogram_stats(MELI_PROCESSING_LATENCY)
    return {
        "messages_received": metrics.extract_counter_value(MELI_MESSAGES_RECEIVED),
        "offers_published": metrics.extract_counter_value(MELI_OFFERS_PUBLISHED),
        "offers_filtered": metrics.extract_counter_value(MELI_OFFERS_FILTERED),
        "offers_filtered_by_reason": metrics.extract_labeled_counter_values(MELI_OFFERS_FILTERED),
        "processing_latency_avg_seconds": latency_stats["avg_seconds"],
        "processing_latency": latency_stats,
        "errors_total": metrics.extract_counter_value(MELI_ERRORS_TOTAL),
        "errors_by_type": metrics.extract_labeled_counter_values(MELI_ERRORS_TOTAL),
        "reconnect_attempts": metrics.extract_counter_value(MELI_RECONNECT_ATTEMPTS),
        "memory_rss_bytes": metrics.get_process_memory_rss_bytes(),
    }


async def main() -> None:
    """Inicializa os clientes e mantém o loop ativo com reconexão automática."""
    global bot_client

    logger.info("RadarJarbis Unificado (Amazon + Mercado Livre) iniciando...")
    logger.info(f"Monitorando {len(settings.SOURCE_CHANNEL_IDS)} canal(is) master.")
    logger.info(f"Canal de saída: {settings.OUTPUT_CHANNEL_ID}")
    if not settings.MELI_COOKIES:
        logger.warning(
            "MELI_COOKIES não está configurado no .env! O bot sanitizará links de concorrentes, "
            "mas para gerar os links curtos meli.la oficiais da sua conta de afiliado, defina MELI_COOKIES."
        )

    # Inicializa o servidor de métricas da Amazon (Porta 8000)
    try:
        metrics.start_metrics_server(settings.METRICS_PORT, json_provider=get_amazon_metrics_payload)
        logger.info(f"Servidor de métricas Amazon ativo na porta {settings.METRICS_PORT} (/metrics e /metrics.json).")
    except Exception as e:
        logger.error(f"Erro ao inicializar o servidor de métricas Amazon: {e}")

    # Inicializa o servidor de métricas do Mercado Livre (Porta 8001)
    try:
        meli_metrics_port = getattr(settings, "METRICS_PORT_MELI", 8001)
        if meli_metrics_port != settings.METRICS_PORT:
            metrics.start_metrics_server(meli_metrics_port, json_provider=get_meli_metrics_payload)
            logger.info(f"Servidor de métricas Mercado Livre ativo na porta {meli_metrics_port} (/metrics e /metrics.json).")
    except Exception as e:
        logger.error(f"Erro ao inicializar o servidor de métricas Mercado Livre: {e}")

    attempt = 0

    async with Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        request=HTTPXRequest(connect_timeout=10.0, read_timeout=30.0, write_timeout=30.0, pool_timeout=10.0),
    ) as bot:
        bot_client = bot

        while attempt < _MAX_RECONNECT_ATTEMPTS:
            RECONNECT_ATTEMPTS.set(attempt)
            MELI_RECONNECT_ATTEMPTS.set(attempt)
            try:
                await user_client.start()
                logger.info(
                    "User client autenticado. Aguardando mensagens em tempo real... "
                    f"(ciclo {attempt + 1}/{_MAX_RECONNECT_ATTEMPTS})"
                )
                attempt = 0
                RECONNECT_ATTEMPTS.set(attempt)
                MELI_RECONNECT_ATTEMPTS.set(attempt)

                await user_client.run_until_disconnected()

            except FloodWaitError as e:
                wait = e.seconds + 5
                logger.warning(
                    f"FloodWaitError: aguardando {wait}s antes de retentar conexão."
                )
                ERRORS_TOTAL.labels(type="telethon_flood").inc()
                await asyncio.sleep(wait)

            except (UnauthorizedError, AuthKeyError) as e:
                logger.critical(
                    f"Erro de autenticação irrecuperável ({type(e).__name__}): {e}. "
                    "Delete config/session.session e reautentique o client."
                )
                ERRORS_TOTAL.labels(type="auth_error").inc()
                break

            except (OSError, ConnectionError) as e:
                attempt += 1
                RECONNECT_ATTEMPTS.set(attempt)
                MELI_RECONNECT_ATTEMPTS.set(attempt)
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
                attempt += 1
                RECONNECT_ATTEMPTS.set(attempt)
                MELI_RECONNECT_ATTEMPTS.set(attempt)
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
                if user_client.is_connected():
                    await user_client.disconnect()
                    logger.info("User client (MTProto) desconectado.")

    state.close()
    logger.info("RadarJarbis encerrado.")


if __name__ == "__main__":
    asyncio.run(main())
