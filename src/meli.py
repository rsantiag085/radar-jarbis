"""
Módulo de integração e geração de links de afiliados do Mercado Livre para o RadarJarbis.
"""

import re
import urllib.parse
import httpx
import logging

logger = logging.getLogger("radardojarbis.meli")

_MELI_DOMAINS = (
    "mercadolivre.com.br",
    "mercadolivre.com",
    "mercadolibre.com",
    "produto.mercadolivre.com.br",
    "meli.la",
)

_ITEM_ID_PATTERN = re.compile(r"(MLB[U]?[0-9]{8,14}|MLB-[0-9]{8,14})", re.IGNORECASE)


def is_meli_url(url: str) -> bool:
    """Verifica se a URL pertence a um domínio do Mercado Livre."""
    try:
        netloc = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return False
    return any(netloc == domain or netloc.endswith("." + domain) for domain in _MELI_DOMAINS)


def extract_meli_item_id(url_or_text: str) -> str | None:
    """Extrai o ID do item/produto do Mercado Livre (ex: MLB61080793, MLBU4152340456)."""
    if not url_or_text:
        return None
    match = _ITEM_ID_PATTERN.search(url_or_text)
    if match:
        raw_id = match.group(1).upper().replace("-", "")
        return raw_id
    return None


async def resolve_meli_url(url: str, timeout: float = 12.0) -> str:
    """Segue redirecionamentos de links encurtados para encontrar a URL final do Mercado Livre."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9",
    }
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=timeout) as client:
        try:
            resp = await client.get(url)
            return str(resp.url)
        except Exception as e:
            logger.debug(f"Erro ao resolver URL {url}: {e}")
            return url


async def resolve_and_extract_meli_item(url: str, timeout: float = 12.0) -> tuple[str | None, str | None]:
    """Resolve qualquer formato de link do Mercado Livre (meli.la, sec, encurtadores externos, etc.)
    e extrai com segurança o ID do item (MLB/MLBU) e uma URL limpa sem rastreamento de concorrentes.

    Returns:
        tuple: (item_id, clean_product_url) ou (None, None)
    """
    # 1. Se já for um link direto de produto com MLB no path (ex: /p/MLB..., /up/MLBU..., produto.mercadolivre.com.br/MLB-...)
    direct_match = _ITEM_ID_PATTERN.search(url)
    if direct_match and ("/p/" in url or "/up/" in url or "produto.mercadolivre" in url):
        item_id = direct_match.group(1).upper().replace("-", "")
        clean_url = url.split("?")[0].split("#")[0]
        return item_id, clean_url

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9",
    }

    # 2. Segue redirecionamentos para resolver links encurtados ou páginas sociais
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=timeout) as client:
        try:
            resp = await client.get(url)
            final_url = str(resp.url)

            # Verifica se a URL de destino final já é a página do produto
            final_match = _ITEM_ID_PATTERN.search(final_url)
            if final_match and ("/p/" in final_url or "/up/" in final_url or "produto.mercadolivre" in final_url):
                item_id = final_match.group(1).upper().replace("-", "")
                clean_url = final_url.split("?")[0].split("#")[0]
                return item_id, clean_url

            # Se caiu em página social / vitrine de outro afiliado (/social/...) ou página intermediária:
            # Extrai o link do produto em destaque no HTML
            featured_links = re.findall(
                r'href=[\"\'](https?://[^\s\"\'<>]+(?:polycard_client=recommendations_home_affiliate-profile|card-featured)[^\s\"\'<>]+)[\"\']',
                resp.text,
            )
            if not featured_links:
                featured_links = re.findall(
                    r'href=[\"\'](https?://[^\s\"\'<>]+(?:/p/MLB|/up/MLB|produto\.mercadolivre\.com\.br)[^\s\"\'<>]+)[\"\']',
                    resp.text,
                )

            if featured_links:
                first_link = featured_links[0].replace("&amp;", "&")
                html_match = _ITEM_ID_PATTERN.search(first_link)
                if html_match:
                    item_id = html_match.group(1).upper().replace("-", "")
                    clean_url = first_link.split("?")[0].split("#")[0]
                    return item_id, clean_url

            # Fallback adicional: se o ID constar na URL final de qualquer forma
            if final_match:
                item_id = final_match.group(1).upper().replace("-", "")
                return item_id, f"https://www.mercadolivre.com.br/p/{item_id}"

        except Exception as e:
            logger.warning(f"Erro ao resolver e inspecionar URL {url}: {e}")

    return None, None


async def generate_meli_affiliate_link(
    item_id: str,
    cookies_str: str,
    user_id: str = "111993671",
    title: str = "",
    permalink: str = ""
) -> str | None:
    """Gera o link de afiliado oficial meli.la utilizando a sessão autenticada da Barra de Afiliados."""
    if not item_id or not cookies_str:
        return None

    clean_item_id = item_id.replace("-", "").upper()
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:151.0) Gecko/20100101 Firefox/151.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Cookie": cookies_str,
        "Referer": "https://www.mercadolivre.com.br/",
    }

    params = {
        "origin": "vpp",
        "app": "upp",
        "platform": "desktop",
        "user_id": user_id,
        "caller_id": user_id,
        "site_id": "MLB",
        "wid": clean_item_id,
        "vertical": "core",
        "business_unit": "ML",
        "vpp_nav": "true",
        "offer_type": "BEST_PRICE",
        "domain_id": "MLB",
        "picture_height": "1024",
        "picture_width": "1024",
        "title": title or "Oferta",
        "picture_id": "none",
        "permalink": permalink or f"https://www.mercadolivre.com.br/p/{clean_item_id}",
        "category_id": "MLB186662",
        "internal_tags": "is_affiliate",
        "pid": clean_item_id,
        "pid_extended": f"{clean_item_id}_{clean_item_id}",
        "parent_origin": "https://www.mercadolivre.com.br"
    }

    url = f"https://www.mercadolivre.com.br/noindex/share/{clean_item_id}"

    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=10.0) as client:
        try:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                clean_text = resp.text.replace(r"\u002F", "/")
                matches = re.findall(r"https?://meli\.la/[A-Za-z0-9]+", clean_text)
                if matches:
                    return matches[0]
            else:
                logger.warning(f"Falha ao gerar link Meli para {clean_item_id}: HTTP {resp.status_code}")
        except Exception as e:
            logger.error(f"Exceção ao chamar gerador Meli para {clean_item_id}: {e}")

    return None
