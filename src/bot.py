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
import logging

from telethon import TelegramClient, events
from telethon.errors import AuthKeyError, FloodWaitError, UnauthorizedError
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import RetryAfter, TelegramError

from . import converters, filters, settings, state

# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("radardojarbis")

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

async def _safe_send(text: str, max_retries: int = 3) -> None:
    """Despacha o post para o canal de saída com retry automático.

    Captura RetryAfter (bot API) e faz backoff respeitando o cooldown
    indicado pela API do Telegram.

    Args:
        text: Post formatado em HTML pronto para postagem.
        max_retries: Número máximo de tentativas antes de descartar.
    """
    for attempt in range(1, max_retries + 1):
        try:
            await bot_client.send_message(
                chat_id=settings.OUTPUT_CHANNEL_ID,
                text=text,
                parse_mode=ParseMode.HTML,
            )
            logger.info("Post despachado com sucesso.")
            return
        except RetryAfter as e:
            wait = e.retry_after + 1
            logger.warning(
                f"Rate limit (RetryAfter). Aguardando {wait}s "
                f"(tentativa {attempt}/{max_retries})."
            )
            await asyncio.sleep(wait)
        except TelegramError as e:
            logger.error(
                f"Erro na Bot API: {e}. "
                f"Tentativa {attempt}/{max_retries}."
            )
            await asyncio.sleep(5)

    logger.critical("Máximo de tentativas atingido. Mensagem descartada.")


# ------------------------------------------------------------
# Handler de novas mensagens (Telethon)
# ------------------------------------------------------------

@user_client.on(events.NewMessage(chats=settings.SOURCE_CHANNEL_IDS))
async def handle_new_offer(event) -> None:
    """Processa cada nova mensagem recebida dos canais master.

    Pipeline:
        1. Valida se há texto.
        2. Filtra por categoria e desconto mínimo (filters.py).
        3. Verifica deduplicação (state.py).
        4. Converte URLs e formata copywriting (converters.py).
        5. Aplica delay de rate limit.
        6. Despacha via bot token (_safe_send).
        7. Registra como postada (state.py).
    """
    text: str = event.message.text or ""
    if not text:
        return

    chat_id = event.chat_id
    message_id = event.message.id
    msg_id = f"{chat_id}:{message_id}"

    # Filtro de categoria e desconto
    if not filters.is_relevant(text):
        logger.debug(f"[{msg_id}] Reprovado pelo filtro de relevância.")
        return

    # Deduplicação
    if state.already_posted(msg_id):
        logger.debug(f"[{msg_id}] Já postado anteriormente. Ignorando.")
        return

    # Conversão e formatação
    category = filters.get_category(text)
    logger.info(f"[{msg_id}] Aprovado — categoria: {category}. Processando...")

    formatted = converters.process(text)

    # Rate limit antes da postagem (GUARDRAILS.md §3)
    await asyncio.sleep(settings.RATE_LIMIT_DELAY)

    # Despacho
    await _safe_send(formatted)

    # Marca como postada
    state.mark_posted(msg_id)


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

    attempt = 0

    # async with garante bot_client.initialize() na entrada e
    # bot_client.shutdown() → httpx.AsyncClient.aclose() na saída.
    async with Bot(token=settings.TELEGRAM_BOT_TOKEN) as bot:
        bot_client = bot  # disponibiliza para _safe_send e handle_new_offer

        while attempt < _MAX_RECONNECT_ATTEMPTS:
            try:
                # start() autentica interativamente na 1ª execução (telefone + OTP).
                # Nas seguintes, usa o arquivo config/session.session.
                await user_client.start()
                logger.info(
                    "User client autenticado. Aguardando mensagens... "
                    f"(ciclo {attempt + 1}/{_MAX_RECONNECT_ATTEMPTS})"
                )
                attempt = 0  # reseta contador após conexão bem-sucedida

                await user_client.run_until_disconnected()

            except FloodWaitError as e:
                # FloodWait não é falha de rede — não incrementa attempt.
                # Espera o cooldown e RETENTA a conexão.
                wait = e.seconds + 5
                logger.warning(
                    f"FloodWaitError: aguardando {wait}s antes de retentar conexão."
                )
                await asyncio.sleep(wait)

            except (UnauthorizedError, AuthKeyError) as e:
                # Sessão inválida ou chave corrompida — não adianta retentar.
                logger.critical(
                    f"Erro de autenticação irrecuperável ({type(e).__name__}): {e}. "
                    "Delete config/session.session e reautentique o client."
                )
                break  # sai do loop — intervenção manual necessária

            except (OSError, ConnectionError) as e:
                # Queda de rede após esgotamento das retentativas internas do Telethon.
                attempt += 1
                delay = min(
                    _RECONNECT_BASE_DELAY * (2 ** (attempt - 1)),
                    _RECONNECT_MAX_DELAY,
                )
                logger.error(
                    f"Erro de rede ({type(e).__name__}): {e}. "
                    f"Tentativa {attempt}/{_MAX_RECONNECT_ATTEMPTS}. "
                    f"Aguardando {delay}s antes de reconectar..."
                )
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
                logger.exception(
                    f"Exceção inesperada ({type(e).__name__}) — "
                    f"tentativa {attempt}/{_MAX_RECONNECT_ATTEMPTS}: {e}"
                )
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
