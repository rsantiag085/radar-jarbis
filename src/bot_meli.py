"""
Wrapper de compatibilidade para `src.bot_meli`.

O RadarJarbis agora opera de forma unificada em `src.bot` (processando ofertas
da Amazon e do Mercado Livre no mesmo processo e expondo as portas 8000 e 8001).
Este módulo é mantido por retrocompatibilidade e delega a execução para `src.bot`.
"""

import asyncio
from .bot import (
    MELI_ERRORS_TOTAL,
    MELI_MESSAGES_RECEIVED,
    MELI_OFFERS_FILTERED,
    MELI_OFFERS_PUBLISHED,
    MELI_PROCESSING_LATENCY,
    MELI_RECONNECT_ATTEMPTS,
    _process_meli_pipeline,
    _safe_send,
    bot_client,
    handle_new_offer,
    main,
    process_message_object,
    user_client,
)

__all__ = [
    "MELI_ERRORS_TOTAL",
    "MELI_MESSAGES_RECEIVED",
    "MELI_OFFERS_FILTERED",
    "MELI_OFFERS_PUBLISHED",
    "MELI_PROCESSING_LATENCY",
    "MELI_RECONNECT_ATTEMPTS",
    "_process_meli_pipeline",
    "_safe_send",
    "bot_client",
    "handle_new_offer",
    "main",
    "process_message_object",
    "user_client",
]

if __name__ == "__main__":
    asyncio.run(main())
