"""
Motor de conversão de URLs e formatação de copywriting para Mercado Livre no RadarJarbis.
"""

import re
import urllib.parse
import logging
from . import converters, meli, settings

logger = logging.getLogger("radardojarbis.converters_meli")

# Gatilhos mentais para Mercado Livre
_MELI_TRIGGERS = [
    "🔥 OFERTA MERCADO LIVRE 🔥",
    "⚡ CORRE ANTES QUE ACABE",
    "💥 SUPER OFERTA DO DIA",
]


def _format_meli_post(
    product_name: str,
    price: str,
    url: str,
    installments: str = "",
    coupon: str = "",
    teaser: str = "",
) -> str:
    """Formata a mensagem em HTML para publicação no Telegram."""
    import random
    trigger = random.choice(_MELI_TRIGGERS)
    teaser_block = f"✨ <i>{teaser}</i>\n\n" if teaser else ""
    product_block = f"📦 <b>{product_name}</b>" if product_name else "📦 <b>Oferta no Mercado Livre</b>"
    
    clean_price = price.replace("R$", "").strip() if price else ""
    price_line = f"\n💰 Por apenas <b>R$ {clean_price}</b>" if clean_price else ""
    installments_line = f"\n💳 <i>{installments}</i>" if installments else ""
    coupon_line = f"\n🎟️ Cupom: <b>{coupon}</b>" if coupon else ""
    link_line = f"\n\n🛒 <b>Compre aqui:</b>\n🔗 {url}"

    return (
        f"{trigger}\n\n"
        f"{teaser_block}"
        f"{product_block}"
        f"{price_line}"
        f"{installments_line}"
        f"{coupon_line}"
        f"{link_line}"
    )


async def extract_meli_link_and_convert(
    text: str,
    cookies_str: str = "",
    user_id: str = "",
    affiliate_tag: str = "",
) -> tuple[str, str]:
    """Extrai o link do Mercado Livre do texto, remove qualquer rastreamento do concorrente
    e converte para link de afiliado oficial meli.la do usuário.

    Returns:
        tuple (affiliate_url, item_id)
    """
    effective_user_id = user_id or getattr(settings, "MELI_USER_ID", "111993671")
    effective_tag = affiliate_tag or getattr(settings, "MELI_AFFILIATE_TAG", "noradardojarbis")

    for match in converters._URL_PATTERN.finditer(text):
        raw_url = match.group(0)

        # Resolve links encurtados, páginas sociais ou links diretos
        item_id, clean_url = await meli.resolve_and_extract_meli_item(raw_url)
        if not item_id:
            continue

        # 1. Se temos cookies configurados, tenta gerar o link oficial meli.la
        if cookies_str:
            short_url = await meli.generate_meli_affiliate_link(
                item_id=item_id,
                cookies_str=cookies_str,
                user_id=effective_user_id,
                permalink=clean_url or f"https://www.mercadolivre.com.br/p/{item_id}",
            )
            if short_url:
                return short_url, item_id
            logger.warning(
                f"Não foi possível gerar meli.la para {item_id}. Usando link limpo do produto."
            )

        # 2. Fallback seguro: Link limpo canônico do produto (sem parâmetros de concorrentes)
        safe_url = clean_url or f"https://www.mercadolivre.com.br/p/{item_id}"
        if effective_tag:
            # Anexa a tag configurada do usuário se não houver meli.la
            delimiter = "&" if "?" in safe_url else "?"
            safe_url = f"{safe_url}{delimiter}matt_word={effective_tag}"

        return safe_url, item_id

    return "", ""


async def process_async(
    text: str,
    cookies_str: str = "",
    user_id: str = "",
    affiliate_tag: str = "",
) -> str | None:
    """Pipeline completo assíncrono para Mercado Livre."""
    affiliate_url, item_id = await extract_meli_link_and_convert(
        text,
        cookies_str=cookies_str,
        user_id=user_id,
        affiliate_tag=affiliate_tag,
    )
    if not affiliate_url:
        return None

    product_name = converters._extract_product_name(text)
    price = converters._extract_price(text)
    installments = converters._extract_installments(text)
    coupon = converters._extract_coupon(text)
    teaser = converters._extract_teaser(text, product_name)

    return _format_meli_post(
        product_name=product_name,
        price=price,
        url=affiliate_url,
        installments=installments,
        coupon=coupon,
        teaser=teaser,
    )
