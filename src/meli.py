"""
Módulo de integração e geração de links de afiliados do Mercado Livre para o RadarJarbis.
"""

import json
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

_BRIDGE_DOMAINS = (
    "divulgadorinteligente.com",
)

_NEXT_DATA_PATTERN = re.compile(
    r'<script[^>]*id=[\"\']__NEXT_DATA__[\"\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)

_META_IMAGE_PATTERNS = (
    re.compile(
        r'<meta[^>]+(?:property|name)=[\"\'](?:og:image|twitter:image)[\"\'][^>]+content=[\"\'](https?://[^\"\']+)[\"\']',
        re.IGNORECASE,
    ),
    re.compile(
        r'<meta[^>]+content=[\"\'](https?://[^\"\']+)[\"\'][^>]+(?:property|name)=[\"\'](?:og:image|twitter:image)[\"\']',
        re.IGNORECASE,
    ),
)

_ITEM_ID_PATTERN = re.compile(r"(MLB[U]?[0-9]{8,14}|MLB-[0-9]{8,14})", re.IGNORECASE)

_IMAGE_URL_CACHE: dict[str, str] = {}
_IMAGE_URL_CACHE_MAX = 128


def _cache_image_url(key_url: str, image_url: str | None) -> None:
    if not key_url or not image_url:
        return
    if len(_IMAGE_URL_CACHE) >= _IMAGE_URL_CACHE_MAX:
        _IMAGE_URL_CACHE.pop(next(iter(_IMAGE_URL_CACHE)), None)
    _IMAGE_URL_CACHE[key_url] = image_url


def get_cached_image_url(*urls: str) -> str | None:
    """Retorna a URL limpa da imagem oficial previamente extraída durante a resolução do Meli."""
    for u in urls:
        if u and u in _IMAGE_URL_CACHE:
            return _IMAGE_URL_CACHE[u]
    return None


def _extract_clean_image_from_html(html: str) -> str | None:
    """Extrai a URL da imagem oficial do produto (mlstatic.com) de bridge pages ou páginas do Meli."""
    if not html:
        return None

    next_match = _NEXT_DATA_PATTERN.search(html)
    if next_match:
        try:
            data = json.loads(next_match.group(1))
            product = ((data.get("props") or {}).get("pageProps") or {}).get("product") or {}
            orig_img = (product.get("originalValues") or {}).get("image")
            if isinstance(orig_img, str) and orig_img.strip().startswith("http"):
                return orig_img.strip()
            is_custom = bool((product.get("metadata") or {}).get("is_custom_image"))
            prod_img = product.get("image")
            if not is_custom and isinstance(prod_img, str) and prod_img.strip().startswith("http"):
                return prod_img.strip()
        except Exception:
            pass

    for pattern in _META_IMAGE_PATTERNS:
        m = pattern.search(html)
        if m:
            cand = m.group(1).replace("&amp;", "&").strip()
            if "mlstatic.com" in cand or not _is_bridge_url(cand):
                return cand

    return None


def _is_bridge_url(url: str) -> bool:
    """Verifica se a URL pertence a uma página intermediária (ex: divulgadorinteligente.com)."""
    try:
        netloc = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return False
    return any(netloc == d or netloc.endswith("." + d) for d in _BRIDGE_DOMAINS)


def _extract_meli_candidate_from_bridge_html(html: str) -> str | None:
    """Extrai a URL do Mercado Livre (original ou botão meli.la) de páginas intermediárias."""
    if not html:
        return None

    next_match = _NEXT_DATA_PATTERN.search(html)
    if next_match:
        try:
            data = json.loads(next_match.group(1))
            product = ((data.get("props") or {}).get("pageProps") or {}).get("product") or {}
            orig_url = (product.get("originalValues") or {}).get("url")
            if isinstance(orig_url, str) and (is_meli_url(orig_url) or extract_meli_item_id(orig_url)):
                return orig_url.strip()
            btn_link = product.get("link")
            if isinstance(btn_link, str) and (is_meli_url(btn_link) or extract_meli_item_id(btn_link)):
                return btn_link.strip()
        except Exception:
            pass

    for href in re.findall(r'<a\b[^>]*\bhref=[\"\'](https?://[^\"\'\s<>]+)[\"\']', html, re.IGNORECASE):
        clean_href = href.replace("&amp;", "&")
        if is_meli_url(clean_href) or extract_meli_item_id(clean_href):
            return clean_href

    return None


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


async def resolve_and_extract_meli_item(
    url: str,
    timeout: float = 12.0,
    _depth: int = 0,
) -> tuple[str | None, str | None]:
    """Resolve qualquer formato de link do Mercado Livre (meli.la, sec, encurtadores externos, bridge pages, etc.)
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

    # 2. Segue redirecionamentos para resolver links encurtados ou páginas sociais / intermediárias
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=timeout) as client:
        try:
            resp = await client.get(url)
            final_url = str(resp.url)
            extracted_img = _extract_clean_image_from_html(resp.text)
            if extracted_img:
                _cache_image_url(url, extracted_img)
                _cache_image_url(final_url, extracted_img)

            # Verifica se a URL de destino final já é a página do produto
            final_match = _ITEM_ID_PATTERN.search(final_url)
            if final_match and ("/p/" in final_url or "/up/" in final_url or "produto.mercadolivre" in final_url):
                item_id = final_match.group(1).upper().replace("-", "")
                clean_url = final_url.split("?")[0].split("#")[0]
                return item_id, clean_url

            # Se caiu em página intermediária (ex: divulgadorinteligente.com), extrai o link do Meli da página
            if _depth < 2 and (_is_bridge_url(url) or _is_bridge_url(final_url)):
                meli_candidate = _extract_meli_candidate_from_bridge_html(resp.text)
                if meli_candidate:
                    cand_match = _ITEM_ID_PATTERN.search(meli_candidate)
                    if cand_match and ("/p/" in meli_candidate or "/up/" in meli_candidate or "produto.mercadolivre" in meli_candidate):
                        item_id = cand_match.group(1).upper().replace("-", "")
                        clean_url = meli_candidate.split("?")[0].split("#")[0]
                        return item_id, clean_url
                    return await resolve_and_extract_meli_item(meli_candidate, timeout=timeout, _depth=_depth + 1)

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
    user_id: str = "",
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
