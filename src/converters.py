"""
Motor de conversão de URLs e formatação de copywriting do RadarJarbis.

Responsabilidades:
- Detectar e converter URLs Amazon para incluir a tag de afiliado.
- Formatar o post final com gatilhos mentais (GEMINI.md).
"""

import json
import re
import random
import urllib.parse
import httpx
from . import settings

# ------------------------------------------------------------
# Constantes
# ------------------------------------------------------------

AFFILIATE_TAG = settings.AMAZON_AFFILIATE_TAG

# Domínios Amazon reconhecidos para injeção de tag
# Sufixos avaliados contra o netloc real da URL (evita falsos positivos
# por substring, ex.: 'a.co' dentro de 'magazineluiza.com.br').
_AMAZON_DOMAINS = (
    "amazon.com.br",
    "amzn.to",
    "a.co",
    "amazon.com",
)

# Páginas intermediárias ("bridge pages") que exibem um botão apontando para a loja final
_BRIDGE_DOMAINS = (
    "divulgadorinteligente.com",
)

# Domínios ignorados ao procurar links externos de compra em tags <a> de bridge pages
_BRIDGE_IGNORED_DOMAINS = (
    "divulgadorinteligente.com",
    "whatsapp.com",
    "instagram.com",
    "tiktok.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "threads.net",
    "pinterest.com",
    "t.me",
    "telegram.me",
    "googletagmanager.com",
    "google-analytics.com",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
)

# Padrão para capturar URLs (http e https)
_URL_PATTERN = re.compile(r"https?://[^\s\)\]>\"']+")

# Gatilhos mentais (GEMINI.md §2)
if settings.PRIME_DAY_MODE:
    _TRIGGERS = [
        "🔥 OFERTA PRIME DAY 🔥",
    ]
else:
    _TRIGGERS = [
        "⚠️ MENOR PREÇO HISTÓRICO",
        "⚡ CORRE ANTES QUE ACABE",
        "📉 BUG DE PREÇO",
    ]

# Padrões para extração de preço e nome do produto
_POR_PRICE_PATTERN = re.compile(
    r"\bpor\s*(?:apenas\s*)?(?:R\$\s*)?(\d{1,6}(?:\.\d{3})*(?:,\d{2})?)\b",
    re.IGNORECASE
)
_RS_PRICE_PATTERN = re.compile(
    r"R\$\s*(\d{1,6}(?:\.\d{3})*(?:,\d{2})?)",
    re.IGNORECASE
)
_DE_PRICE_PATTERN = re.compile(
    r"\bde\s*(?:R\$\s*)?(\d{1,6}(?:\.\d{3})*(?:,\d{2})?)\b",
    re.IGNORECASE
)
_GENERIC_PRICE_PATTERN = re.compile(
    r"\b\d{1,6}(?:\.\d{3})*,\d{2}\b"
)
_PRODUCT_EMOJIS = {char for char in "💻📺📱🎧🛒🎮🔊🔌💡🧴👟👕🎒⌨️🖱️⌚💳🖥️📽️📸⚙️📦🗝️🧸🛍" if char != "\ufe0f"}

_PRODUCT_KEYWORDS = [
    "notebook", "laptop", "smart tv", "tv", "monitor", "gabinete", "ssd", "teclado", "mouse", "headset",
    "headset gamer", "headphone", "fone", "fone de ouvido", "fone gamer", "zeus lite", "h2232d",
    "smartphone", "celular", "iphone", "galaxy", "philco", "lenovo", "dell", "samsung", "aoc",
    "lg", "tcl", "multilaser", "positivo", "gree", "consul", "brastemp", "electrolux", "midea",
    "ar condicionado", "geladeira", "fogão", "microondas", "fritadeira", "airfryer", "panela", "cafeteira",
    "liquidificador", "batedeira", "aspirador", "ferro", "chuveiro", "ventilador de mesa", "ventilador", "aquecedor", "climatizador",
    "purificador", "filtro", "torneira", "lâmpada", "tomada", "interruptor", "roteador", "modem", "repetidor",
    "câmera", "fechadura", "sensor", "alarme", "interfone", "campainha", "projetor", "caixa de som", "soundbar",
    "home theater", "receiver", "amplificador", "microfone", "estabilizador", "nobreak", "filtro de linha",
    "adaptador", "cabo", "carregador", "bateria", "power bank", "memória", "ram", "cooler", "ventoinha",
    "placa de vídeo", "gpu", "processador", "cpu", "placa-mãe", "fonte", "hd", "pendrive", "cartão de memória",
    "console", "playstation", "xbox", "nintendo", "switch", "kindle", "echo", "alexa",
    # Novas categorias adicionadas (Beleza, Saúde, Pessoal/Esportes)
    "creme", "sérum", "serum", "hidratante", "protetor solar", "base", "batom", "rímel", "rimel",
    "máscara", "mascara facial", "esfoliante", "vitamina", "suplemento", "whey protein", "whey",
    "creatina", "colágeno", "colageno", "ômega", "omega 3", "probiótico", "probiotico", "shampoo",
    "condicionador", "finalizador", "desodorante", "antitranspirante", "sabonete", "proteína",
    "tênis", "tenis", "sneaker", "perfume", "eau de toilette", "eau de parfum", "colônia", "cologne",
    "relógio", "relogio", "smartwatch", "body splash", "body spray", "leave-in", "cabelo",
    "eucerin", "anti-idade", "antiidade", "epigenetic", "sérum facial", "serum facial"
]

_PRODUCT_BRANDS = [
    "lenovo", "dell", "samsung", "aoc", "philco", "lg", "sony", "panasonic", "pioneer", "multilaser",
    "positivo", "asus", "acer", "hp", "apple", "xiaomi", "redmi", "poco", "realme", "motorola", "nokia",
    "huawei", "oppo", "vivo", "oneplus", "google", "amazon", "alexa", "echo", "kindle", "fire tv", "roku",
    "chromecast", "intel", "amd", "nvidia", "geforce", "radeon", "kingston", "sandisk", "wd", "western digital",
    "seagate", "toshiba", "corsair", "hyperx", "razer", "logitech", "redragon", "t-dagger", "havit", "edifier",
    "jbl", "sony", "bose", "sennheiser", "audio-technica", "shure", "behringer", "focusrite", "epson", "canon",
    "nikon", "gopro", "dji",
    # Beleza / Skincare / Saúde / Suplementos
    "eudora", "siàge", "siage", "oboticário", "o boticário", "boticario", "natura", "growth",
    "max titanium", "la roche-posay", "la roche posay", "la roche", "cerave", "vichy", "neutrogena",
    "l'oréal", "loreal", "nivea", "pantene", "dove", "eucerin",
    # Esportes / Moda
    "nike", "adidas", "puma", "olympikus", "mizuno", "asics", "under armour",
    # Eletrodomésticos / Casa
    "arno", "mondial", "philco", "britânia", "britania", "cadence", "oster"
]
_INSTALLMENT_PATTERN = re.compile(
    r"\b(?:em\s+até|em|até)\s+\d{1,2}\s*x(?:\s+sem\s+juros)?",
    re.IGNORECASE
)
_PRIME_PATTERN = re.compile(
    r"\b(?:exclusiv[ao]?\s+)?membros\s+(?:Amazon\s+)?prime\b|\bexclusiv[ao]?\s+prime\b",
    re.IGNORECASE
)
_SUBSCRIBE_AND_SAVE_PATTERN = re.compile(
    r"\bprograme\s+(?:e|&)\s+poupe\b",
    re.IGNORECASE
)
_COUPON_PATTERN = re.compile(
    r"\b(?:CUPOM|Cupom|cupom|🎟️?|use\s+o\s+cupom|cumpom)[:\s-]*\**([A-Z0-9]{3,20}(?:\s*[\++-]\s*[A-Z0-9]{3,20})*)\**"
)
_TEASER_EXCLUDE_PATTERN = re.compile(
    r"R\$\s*\d|\b(?:cupom|use|cumpom|notificações|grupo|canal|whatsapp|t\.me)\b|https?://",
    re.IGNORECASE
)

_MEASUREMENT_PATTERN = re.compile(
    r"\b\d+\s*(?:ml|l|g|kg|gb|tb|mb|hz|w|v|cm|mm|in|mah|k|hz|fps|%)\b|\b\d+ª?\s*(?:geração|geracao|geracao)\b|\b\d+(?:[\'\"]|polegadas)\b",
    re.IGNORECASE
)

_FALSE_COUPONS = {
    "AMAZON", "CUPOM", "DESCONTO", "OFF", "FRETE", "PRIME", 
    "GANHE", "COMPRAS", "ACIMA", "VALIDO", "VÁLIDO",
    "PARA", "ALGUNS", "PRODUTOS", "FAÇA", "TESTE", "EXCLUSIVO",
    "MEMBROS", "HOJE", "AGORA", "OUTROS", "APENAS", "POR", "DE", 
    "PIX", "OU", "USE", "LINK", "COMO", "ESTE", "AQUI", "DIAS",
    "MUITO", "MAIS", "TUDO", "TODO", "TODOS", "SECTOR", "LIVROS",
    "EBOOKS", "E-BOOKS", "SETOR", "LEITURA"
}

def matches_word_boundary(word, text):
    pattern = r'\b' + re.escape(word) + r'\b'
    return bool(re.search(pattern, text, re.IGNORECASE))

def _has_negative_word(clean_lower: str) -> bool:
    for p in ["r$", "pix", "10x", "12x", "cupom", "http", "🔗", "link"]:
        if p in clean_lower:
            return True
    if re.search(r'\bde\s*(?:r\$\s*)?\d', clean_lower):
        return True
    if re.search(r'\bpor\s*(?:apenas\s*)?(?:r\$\s*)?\d', clean_lower):
        return True
    if matches_word_boundary("ou", clean_lower):
        return True
    if matches_word_boundary("use", clean_lower):
        return True
    return False



# ------------------------------------------------------------
# Conversão de URLs
# ------------------------------------------------------------

def _is_amazon_url(url: str) -> bool:
    """Verifica se a URL pertence a um domínio Amazon reconhecido.

    Usa urllib.parse.urlparse para extrair o netloc real e comparar
    como sufixo de domínio, evitando falsos positivos por substring
    (ex.: 'a.co' dentro de 'magazineluiza.com.br').
    """
    try:
        netloc = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return False
    return any(
        netloc == domain or netloc.endswith("." + domain)
        for domain in _AMAZON_DOMAINS
    )


# Padrão para capturar o ASIN da Amazon em diferentes formatos de URLs
_ASIN_PATTERN = re.compile(r"/(?:dp|gp/product|gp/aw/d|product|d)/([A-Z0-9]{10})\b", re.IGNORECASE)


def extract_asin(url_or_text: str) -> str | None:
    """Extrai o ASIN (Amazon Standard Identification Number) de uma URL ou de um texto contendo uma URL da Amazon.

    Args:
        url_or_text: URL ou texto de post contendo links.

    Returns:
        O ASIN em letras maiúsculas ou None se não for encontrado.
    """
    if not url_or_text:
        return None

    # Tenta encontrar URLs no texto recebido
    urls = _URL_PATTERN.findall(url_or_text)
    amazon_urls = [u for u in urls if _is_amazon_url(u)]

    # Se não achou URL da Amazon via regex mas a própria string original pode ser a URL, usamos ela
    urls_to_check = amazon_urls if amazon_urls else [url_or_text]

    for url in urls_to_check:
        # 1. Tentar encontrar via padrão no path da URL
        match = _ASIN_PATTERN.search(url)
        if match:
            return match.group(1).upper()

        # 2. Como fallback, tentar encontrar nos parâmetros da URL (ex: ?asin=...)
        try:
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            for k, v in params.items():
                if k.lower() == "asin" and v:
                    candidate = v[0].strip()
                    if len(candidate) == 10 and candidate.isalnum():
                        return candidate.upper()
        except Exception:
            pass

    return None



_JUNK_PARAMS = {
    "crid", "dib", "dib_tag", "qid", "sprefix", "sr", "ufe",
    "ascsubtag", "btn_ref", "linkcode", "linkid", "keywords"
}


def _inject_affiliate_tag(url: str, tag: str | None = None) -> str:
    """Injeta o parâmetro de tag de afiliado em uma URL Amazon e remove parâmetros inúteis de rastreamento.

    Substitui tag existente se houver, ou adiciona ao query string.

    Args:
        url: URL bruta do canal master.
        tag: Tag específica de afiliado (opcional, usa a global por padrão).

    Returns:
        URL limpa com tag de afiliado injetada.
    """
    if not _is_amazon_url(url):
        return url  # URLs não-Amazon são mantidas sem alteração

    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    params["tag"] = [tag if tag is not None else AFFILIATE_TAG]  # substitui tag existente ou adiciona nova
    
    # Remove parâmetros de rastreamento desnecessários da Amazon que aumentam o link de forma excessiva
    for key in list(params.keys()):
        if key.lower() in _JUNK_PARAMS:
            params.pop(key, None)
            
    new_query = urllib.parse.urlencode(params, doseq=True)
    return urllib.parse.urlunparse(parsed._replace(query=new_query))


def convert_urls(text: str) -> str:
    """Substitui todas as URLs Amazon brutas por URLs com tag de afiliado.

    Args:
        text: Texto bruto da mensagem.

    Returns:
        Texto com todas as URLs Amazon convertidas.
    """
    return _URL_PATTERN.sub(
        lambda m: _inject_affiliate_tag(m.group(0)),
        text,
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

_AMAZON_PRODUCT_IMAGE_PATTERNS = (
    re.compile(r'data-old-hires=[\"\'](https?://m\.media-amazon\.com/images/I/[^\"\']+)[\"\']', re.IGNORECASE),
    re.compile(r'"hiRes"\s*:\s*"(https?://m\.media-amazon\.com/images/I/[^"]+)"', re.IGNORECASE),
    re.compile(r'<img[^>]+id=[\"\']landingImage[\"\'][^>]+src=[\"\'](https?://m\.media-amazon\.com/images/I/[^\"\']+)[\"\']', re.IGNORECASE),
)

# Cache leve em memória (URL intermediária -> URL limpa da imagem oficial do produto)
_BRIDGE_IMAGE_CACHE: dict[str, str] = {}
_BRIDGE_IMAGE_CACHE_MAX = 128


def _is_bridge_url(url: str) -> bool:
    """Verifica se a URL pertence a uma página intermediária reconhecida (ex.: divulgadorinteligente.com)."""
    try:
        netloc = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return False
    return any(
        netloc == domain or netloc.endswith("." + domain)
        for domain in _BRIDGE_DOMAINS
    )


def has_bridge_url(text: str) -> bool:
    """Retorna True se o texto contiver alguma URL de página intermediária (ex.: divulgadorinteligente.com)."""
    if not text:
        return False
    return any(_is_bridge_url(m.group(0)) for m in _URL_PATTERN.finditer(text))


def cache_bridge_image_url(source_url: str, image_url: str | None) -> None:
    """Armazena em cache limitado a imagem limpa associada a uma URL de bridge."""
    if not source_url or not image_url:
        return
    if len(_BRIDGE_IMAGE_CACHE) >= _BRIDGE_IMAGE_CACHE_MAX:
        oldest_key = next(iter(_BRIDGE_IMAGE_CACHE))
        _BRIDGE_IMAGE_CACHE.pop(oldest_key, None)
    _BRIDGE_IMAGE_CACHE[source_url] = image_url


def extract_bridge_image_url(html: str) -> str | None:
    """Extrai a URL da imagem oficial limpa do produto (sem moldura do divulgador) do HTML da bridge page."""
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
            candidate = m.group(1).replace("&amp;", "&").strip()
            if not _is_bridge_url(candidate):
                return candidate

    return None


def extract_store_product_image_url(html: str) -> str | None:
    """Extrai a URL da imagem oficial diretamente do HTML da loja (Amazon / Mercado Livre)."""
    if not html:
        return None

    for pattern in _AMAZON_PRODUCT_IMAGE_PATTERNS:
        m = pattern.search(html)
        if m:
            return m.group(1).replace("&amp;", "&").strip()

    for pattern in _META_IMAGE_PATTERNS:
        m = pattern.search(html)
        if m:
            candidate = m.group(1).replace("&amp;", "&").strip()
            if not _is_bridge_url(candidate):
                return candidate

    return None


async def fetch_clean_product_image(
    text: str,
    fallback_product_url: str = "",
    pre_resolved_image_url: str | None = None,
) -> bytes | None:
    """Baixa em memória os bytes da imagem oficial limpa do produto (Amazon CDN / Meli CDN),
    ignorando imagens customizadas/molduras de canais terceiros.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }

    image_url = pre_resolved_image_url

    async with httpx.AsyncClient(follow_redirects=True, timeout=10.0, headers=headers) as client:
        # 1. Procura imagem limpa nas bridge URLs presentes no texto (usando cache se já expandido)
        if not image_url and text:
            for m in _URL_PATTERN.finditer(text):
                u = m.group(0)
                if not _is_bridge_url(u):
                    continue
                cached = _BRIDGE_IMAGE_CACHE.get(u)
                if cached:
                    image_url = cached
                    break
                try:
                    resp = await client.get(u)
                    extracted = extract_bridge_image_url(resp.text)
                    if extracted:
                        cache_bridge_image_url(u, extracted)
                        image_url = extracted
                        break
                except Exception:
                    continue

        # 2. Fallback: tenta extrair og:image / landingImage diretamente da página da loja
        if not image_url and fallback_product_url and fallback_product_url.startswith("http"):
            try:
                resp = await client.get(fallback_product_url)
                image_url = extract_store_product_image_url(resp.text)
            except Exception:
                image_url = None

        if not image_url:
            return None

        # 3. Faz o download em memória dos bytes da imagem limpa
        try:
            img_resp = await client.get(image_url)
            content_type = img_resp.headers.get("content-type", "").lower()
            if img_resp.status_code == 200 and img_resp.content and (
                content_type.startswith("image/") or len(img_resp.content) > 512
            ):
                return img_resp.content
        except Exception:
            return None

    return None


def extract_bridge_destination_url(html: str) -> tuple[str | None, str | None]:
    """Extrai (original_url, button_link) do HTML de páginas intermediárias como divulgadorinteligente.com."""
    if not html:
        return None, None

    next_match = _NEXT_DATA_PATTERN.search(html)
    if next_match:
        try:
            data = json.loads(next_match.group(1))
            product = ((data.get("props") or {}).get("pageProps") or {}).get("product") or {}
            orig_url = (product.get("originalValues") or {}).get("url")
            btn_link = product.get("link")
            clean_orig = (
                orig_url.strip()
                if isinstance(orig_url, str) and orig_url.strip().startswith("http")
                else None
            )
            clean_btn = (
                btn_link.strip()
                if isinstance(btn_link, str) and btn_link.strip().startswith("http")
                else None
            )
            if clean_orig or clean_btn:
                return clean_orig, clean_btn
        except Exception:
            pass

    for href in re.findall(r'<a\b[^>]*\bhref=[\"\'](https?://[^\"\'\s<>]+)[\"\']', html, re.IGNORECASE):
        clean_href = href.replace("&amp;", "&").strip()
        try:
            netloc = urllib.parse.urlparse(clean_href).netloc.lower()
        except Exception:
            continue
        if any(netloc == d or netloc.endswith("." + d) for d in _BRIDGE_IGNORED_DOMAINS):
            continue
        return None, clean_href

    return None, None


async def expandir_e_converter_link(url_encurtada: str, sua_tag: str | None = None) -> str:
    """Segue os redirecionamentos de links encurtados (incluindo páginas intermediárias) e injeta a tag de afiliado."""
    effective_tag = sua_tag or AFFILIATE_TAG
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        # Método GET com Stream para passar pelas barreiras de segurança da Amazon/Encurtador
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            async with client.stream("GET", url_encurtada, headers=headers) as response:
                url_final = str(response.url)
                bridge_html = ""
                if not _is_amazon_url(url_final) and _is_bridge_url(url_final):
                    raw_bytes = await response.aread()
                    bridge_html = raw_bytes.decode("utf-8", errors="ignore")

            if bridge_html:
                cache_bridge_image_url(url_encurtada, extract_bridge_image_url(bridge_html))
                orig_url, btn_link = extract_bridge_destination_url(bridge_html)
                if orig_url and _is_amazon_url(orig_url):
                    try:
                        orig_netloc = urllib.parse.urlparse(orig_url).netloc.lower()
                    except Exception:
                        orig_netloc = ""
                    if "amazon.com.br" in orig_netloc or "amazon.com" in orig_netloc:
                        return _inject_affiliate_tag(orig_url, tag=effective_tag)

                candidate = btn_link or orig_url
                if candidate:
                    try:
                        cand_netloc = urllib.parse.urlparse(candidate).netloc.lower()
                    except Exception:
                        cand_netloc = ""

                    if "amazon.com.br" in cand_netloc or "amazon.com" in cand_netloc:
                        return _inject_affiliate_tag(candidate, tag=effective_tag)

                    if not any(
                        cand_netloc == d or cand_netloc.endswith("." + d)
                        for d in ("mercadolivre.com.br", "mercadolivre.com", "mercadolibre.com", "meli.la")
                    ):
                        async with client.stream("GET", candidate, headers=headers) as btn_resp:
                            url_final = str(btn_resp.url)
                    else:
                        url_final = candidate

        if not _is_amazon_url(url_final):
            return url_final

        # Reaproveita a limpeza de lixo e a injeção da tag na URL expandida
        return _inject_affiliate_tag(url_final, tag=effective_tag)
    except Exception as e:
        print(f"Erro de SRE ao expandir link {url_encurtada}: {e}")
        return url_encurtada


# ------------------------------------------------------------
# Extração de dados da oferta
# ------------------------------------------------------------

def _extract_price(text: str) -> str:
    """Extrai a melhor estimativa de preço promocional ou preço padrão no texto."""
    # 1. Procura primeiro por indicações de preço promocional ("por R$ X" ou "por X")
    por_match = _POR_PRICE_PATTERN.search(text)
    if por_match:
        price_val = por_match.group(1).strip()
        if price_val.isdigit() and len(price_val) <= 2:
            pass
        else:
            return f"R$ {price_val}"

    # 2. Procura por qualquer padrão contendo "R$"
    rs_match = _RS_PRICE_PATTERN.search(text)
    if rs_match:
        return f"R$ {rs_match.group(1).strip()}"

    # 3. Procura por padrão com "de X"
    de_match = _DE_PRICE_PATTERN.search(text)
    if de_match:
        price_val = de_match.group(1).strip()
        if not (price_val.isdigit() and len(price_val) <= 2):
            return f"R$ {price_val}"

    # 4. Procura por um número genérico formatado como decimal BR (ex: 3.229,05)
    generic_match = _GENERIC_PRICE_PATTERN.search(text)
    if generic_match:
        return f"R$ {generic_match.group(0).strip()}"

    return ""


# Alias público para extração de preço
extract_price = _extract_price



def _extract_installments(text: str) -> str:
    """Extrai informações de parcelamento (ex: 'em até 10x sem juros')."""
    match = _INSTALLMENT_PATTERN.search(text)
    return match.group(0).strip() if match else ""


def _extract_coupon(text: str) -> str:
    """Extrai o código do cupom se estiver presente na mensagem original."""
    text_no_urls = re.sub(r"https?://[^\s]+", "", text)
    
    colon_patterns = [
        re.compile(r"(?i:cupom|code|código|codigo)[:\s-]+\**([a-zA-Z0-9]{3,20}(?:\s*[\++-]\s*[a-zA-Z0-9]{3,20})*)\**"),
        re.compile(r"(?:🎟️|🏷️|🎟|🏷)[:\s-]*\**([a-zA-Z0-9]{3,20}(?:\s*[\++-]\s*[a-zA-Z0-9]{3,20})*)\**"),
    ]
    
    for pattern in colon_patterns:
        matches = pattern.findall(text_no_urls)
        for match in matches:
            clean_match = match.strip().upper()
            if clean_match not in _FALSE_COUPONS:
                return clean_match
                
    candidates = re.findall(r"\b[A-Z0-9]{3,20}(?:\s*[\++-]\s*[A-Z0-9]{3,20})*\b", text_no_urls)
    best_candidate = None
    for cand in candidates:
        cand_upper = cand.upper()
        if cand_upper in _FALSE_COUPONS:
            continue
            
        for line in text_no_urls.splitlines():
            if cand in line:
                line_lower = line.lower()
                if any(ind in line_lower for ind in ["cupom", "🎟️", "🏷️", "code", "código", "codigo"]):
                    return cand_upper
        if not best_candidate:
            best_candidate = cand_upper
            
    matches = _COUPON_PATTERN.findall(text_no_urls)
    for match in matches:
        clean_match = match.strip().upper()
        if clean_match not in _FALSE_COUPONS:
            return clean_match
            
    return ""


def _check_prime(text: str) -> bool:
    """Verifica se a oferta é exclusiva para membros Prime."""
    return bool(_PRIME_PATTERN.search(text))


def _check_subscribe_and_save(text: str) -> bool:
    """Verifica se a oferta menciona a modalidade 'Programe e Poupe'."""
    return bool(_SUBSCRIBE_AND_SAVE_PATTERN.search(text))


def _extract_teaser(text: str, product_name: str) -> str:
    """Extrai a primeira linha não vazia do texto original como teaser/chamada,
    desde que ela não seja idêntica ao nome do produto extraído.
    """
    for line in text.splitlines():
        clean = line.strip()
        if clean:
            # Simplifica a comparação
            clean_flat = clean.replace("**", "").replace("__", "").replace("*", "").strip()
            clean_flat = re.sub(r"^[^\w\s]+", "", clean_flat).strip()
            
            if clean_flat == product_name or (
                product_name and len(product_name) >= 40 and clean_flat.startswith(product_name)
            ):
                return ""
            if _TEASER_EXCLUDE_PATTERN.search(clean):
                continue
                
            clean_display = clean.replace("**", "").replace("__", "").replace("*", "").strip()
            # Remove emojis e decorações no início
            clean_display = re.sub(r"^[^\w\s]+", "", clean_display).strip()
            return clean_display
            
    return ""


def _extract_product_name(text: str) -> str:
    """Tenta extrair o nome do produto do texto bruto avaliando e pontuando cada linha."""
    lines = text.splitlines()
    scored_lines = []
    
    for line in lines:
        clean = line.strip()
        if not clean:
            continue
            
        # Remove URLs e marcações de links markdown da linha candidata
        line_no_url = _URL_PATTERN.sub("", clean)
        line_no_url = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line_no_url)
        line_no_url = line_no_url.replace("()", "").strip()
        
        # Ignora linhas que ficaram vazias ou muito curtas após a remoção de URLs
        if len(line_no_url) < 3:
            continue
            
        score = 0
        clean_lower = clean.lower()
        
        # Filtros negativos fortes
        if _has_negative_word(clean_lower):
            score -= 50
            
        if any(p in clean_lower for p in ["notificações", "perder nada", "grupo", "canal", "t.me", "whatsapp", "site confiável", "site seguro", "confiável", "confiavel", "seguro", "site:", "link para", "entrar no grupo", "entrar no canal", "reduza.com", "divulgadorinteligente"]):
            score -= 100

        # Termos típicos de frete, venda e promoção que não fazem parte do nome do produto
        if any(p in clean_lower for p in ["vendido", "enviado", "frete", "entregue", "compre", "clique", "grátis", "gratis"]):
            score -= 80
            
        # Emojis de produto
        if any(char in _PRODUCT_EMOJIS for char in clean):
            score += 20
            
        # Negrito
        if ("**" in clean) or ("__" in clean):
            score += 15
            
        # Palavras-chave de produtos
        if any(matches_word_boundary(kw, clean_lower) for kw in _PRODUCT_KEYWORDS):
            score += 30
            
        # Marcas
        if any(matches_word_boundary(brand, clean_lower) for brand in _PRODUCT_BRANDS):
            score += 15

        # Medidas/Unidades (indica forte característica de especificação de produto)
        if _MEASUREMENT_PATTERN.search(clean_lower):
            score += 25
            
        # Comprimento ideal
        if 15 <= len(clean) <= 100:
            score += 10
        elif len(clean) < 8 or len(clean) > 130:
            score -= 30
            
        scored_lines.append((score, clean))
        
    if not scored_lines:
        return "Oferta imperdível"
        
    # Ordena pelo score decrescente
    scored_lines.sort(key=lambda x: x[0], reverse=True)
    
    # Pega o vencedor e limpa marcações/emojis do início para o post final
    winner = scored_lines[0][1]
    
    # Remove marcações de negrito do markdown original e emojis do início
    clean_winner = winner.replace("**", "").replace("__", "").replace("*", "").strip()
    # Remove emojis e caracteres especiais do começo da string
    clean_winner = re.sub(r"^[^\w\s]+", "", clean_winner).strip()
    
    # Remove preço do final se existir (ex: - R$ 50, por R$ 26, R$ 1.299,90)
    clean_winner = re.sub(
        r"\s*[-–—]?\s*(?:por|de)?\s*R\$\s*\d+(?:\.\d{3})*(?:,\d{2})?\s*$",
        "",
        clean_winner,
        flags=re.IGNORECASE
    )
    # Trunca para o limite de tamanho do Telegram
    truncated = clean_winner[:80].strip()
    # Limpa hífens, barras, vírgulas, pontos ou espaços sobressalentes no final do texto truncado
    truncated = re.sub(r"\s*[-–—/,\.]\s*$", "", truncated).strip()
    
    return truncated


def _extract_first_amazon_url(text: str) -> str:
    """Retorna a primeira URL Amazon convertida encontrada no texto."""
    for match in _URL_PATTERN.finditer(text):
        url = match.group(0)
        if _is_amazon_url(url):
            return _inject_affiliate_tag(url)
    return ""


# ------------------------------------------------------------
# Formatação do post final
# ------------------------------------------------------------

def _format_post(product_name: str, price: str, url: str, installments: str = "", coupon: str = "", has_prime: bool = False, teaser: str = "", has_subscribe_and_save: bool = False) -> str:
    """Monta o bloco de texto final para postagem no canal.

    Formato HTML compatível com Telegram (ParseMode.HTML).

    Args:
        product_name: Nome/descrição do produto.
        price: Preço formatado (ex: 'R$ 299,90').
        url: URL afiliada Amazon.
        installments: Informações de parcelamento (ex: 'em até 10x').
        coupon: Código do cupom (ex: 'POUPEAGORA').
        has_prime: True se for oferta exclusiva Prime.
        teaser: Texto opcional de chamada/engajamento.
        has_subscribe_and_save: True se for preço com Programe e Poupe.

    Returns:
        String formatada em HTML para postagem.
    """
    # Título: Nome do produto
    post = f"🛒 <b>{product_name}</b>\n\n"

    # Breve descrição de até 10 palavras
    if teaser:
        words = teaser.split()
        if len(words) > 10:
            truncated_teaser = " ".join(words[:10]) + "..."
        else:
            truncated_teaser = teaser
        post += f"✨ <i>{truncated_teaser}</i>\n\n"

    # Valor (com parcelamento)
    if price:
        price_suffix = f" {installments}" if installments else ""
        post += f"💰 Por <b>{price}</b>{price_suffix}\n"

    # Cupom (caso tenha)
    if coupon:
        post += f"🎟️ Cupom: <b>{coupon}</b>\n"

    # Selo Prime
    if has_prime:
        post += f"👑 <i>Exclusivo Membros Prime</i>\n"

    # Selo Programe e Poupe
    if has_subscribe_and_save:
        post += f"🔄 <i>Valor com Programe e Poupe</i>\n"

    # Link de afiliado
    if url:
        post += f"\n🔗 {url}"

    return post.strip()


# ------------------------------------------------------------
# Detecção e formatação de Cupons Gerais
# ------------------------------------------------------------

def _is_coupon_announcement(text: str) -> bool:
    """Verifica se a mensagem é um anúncio de cupom geral (não atrelado a um único produto)."""
    if not settings.ENABLE_COUPONS:
        return False
    text_lower = text.lower()
    has_coupon = "cupom" in text_lower or "cupons" in text_lower
    if not has_coupon:
        return False
        
    general_indicators = [
        "cupom amazon", "cupons amazon", "chegou mais um cupom", 
        "cupom exclusivo", "compras acima de", "válido para alguns produtos"
    ]
    if any(ind in text_lower for ind in general_indicators):
        return True
        
    # Verifica o score máximo das linhas de produto
    max_score = -999
    lines = text.splitlines()
    for line in lines:
        clean = line.strip()
        if not clean:
            continue
        score = 0
        clean_lower = clean.lower()
        if _has_negative_word(clean_lower):
            score -= 50
        if any(char in _PRODUCT_EMOJIS for char in clean):
            score += 20
        if any(matches_word_boundary(kw, clean_lower) for kw in _PRODUCT_KEYWORDS):
            score += 30
        if any(matches_word_boundary(brand, clean_lower) for brand in _PRODUCT_BRANDS):
            score += 15
        if 15 <= len(clean) <= 100:
            score += 10
        elif len(clean) < 8 or len(clean) > 130:
            score -= 30
        max_score = max(max_score, score)
        
    return max_score < 35


def _extract_coupon_benefit(text: str) -> str:
    """Extrai a principal descrição de benefício do cupom (ex: Ganhe R$ 100 OFF)."""
    lines = text.splitlines()
    benefit_patterns = [
        re.compile(r"ganhe\s+.*?(?:off|desconto|r\$)", re.IGNORECASE),
        re.compile(r"\b\d+%\s+(?:off|desconto|desc)\b", re.IGNORECASE),
        re.compile(r"\br\$\s*\d+\s*(?:off|desconto|desc)\b", re.IGNORECASE),
        re.compile(r"desconto\s+de\s+.*?", re.IGNORECASE),
        re.compile(r"compras\s+acima\s+de\s+.*?", re.IGNORECASE),
    ]
    for line in lines:
        clean = line.strip()
        if not clean:
            continue
        clean_lower = clean.lower()
        if "http" in clean_lower or "cupom:" in clean_lower or "cupom :" in clean_lower:
            continue
        for pattern in benefit_patterns:
            if pattern.search(clean):
                clean_display = clean.replace("**", "").replace("__", "").replace("*", "").strip()
                clean_display = re.sub(r"^[^\w\s]+", "", clean_display).strip()
                return clean_display
    for line in lines:
        clean = line.strip()
        if not clean:
            continue
        clean_lower = clean.lower()
        if "http" in clean_lower or "cupom:" in clean_lower or "cupom :" in clean_lower or "exclusivo" in clean_lower:
            continue
        clean_display = clean.replace("**", "").replace("__", "").replace("*", "").strip()
        clean_display = re.sub(r"^[^\w\s]+", "", clean_display).strip()
        if len(clean_display) > 10:
            return clean_display
    return "Cupom Especial Amazon"


def _format_coupon_post(benefit: str, url: str, coupon: str, has_prime: bool, teaser: str, has_subscribe_and_save: bool = False) -> str:
    """Formata o post especial para anúncio de cupons gerais."""
    trigger = "🔥 CUPOM AMAZON 🔥"
    teaser_block = f"✨ <i>{teaser}</i>\n\n" if teaser else ""
    benefit_block = f"🛒 <b>{benefit}</b>"
    coupon_block = f"\n🎟️ Cupom: <b>{coupon}</b>" if coupon else ""
    prime_block = f"\n\n👑 <i>Exclusivo Membros Prime</i>" if has_prime else ""
    sns_block = f"\n\n🔄 <i>Valor com Programe e Poupe</i>" if has_subscribe_and_save else ""
    url_block = f"\n\n🔗 {url}" if url else ""
    return (
        f"{trigger}\n\n"
        f"{teaser_block}"
        f"{benefit_block}"
        f"{coupon_block}"
        f"{url_block}"
        f"{prime_block}"
        f"{sns_block}"
    )


# ------------------------------------------------------------
# Interface pública
# ------------------------------------------------------------

def process(text: str) -> str | None:
    """Pipeline completo de conversão e formatação de uma oferta.

    Etapas:
    1. Extrai nome do produto/benefício, preço e URL Amazon do texto bruto.
    2. Injeta tag de afiliado na URL.
    3. Formata o post com gatilho mental e estrutura HTML.

    Args:
        text: Texto bruto da mensagem aprovada pelo filters.py.

    Returns:
        Post formatado em HTML pronto para postagem no canal de saída, ou None se nenhuma URL Amazon for localizada.
    """
    url = _extract_first_amazon_url(text)
    if not url:
        return None

    has_subscribe_and_save = _check_subscribe_and_save(text)

    if _is_coupon_announcement(text):
        coupon = _extract_coupon(text)
        benefit = _extract_coupon_benefit(text)
        has_prime = _check_prime(text)
        teaser = _extract_teaser(text, benefit)
        return _format_coupon_post(benefit, url, coupon, has_prime, teaser, has_subscribe_and_save)

    product_name = _extract_product_name(text)
    price = _extract_price(text)
    installments = _extract_installments(text)
    coupon = _extract_coupon(text)
    has_prime = _check_prime(text)
    teaser = _extract_teaser(text, product_name)

    return _format_post(product_name, price, url, installments, coupon, has_prime, teaser, has_subscribe_and_save)


async def _extract_first_amazon_url_async(text: str) -> str:
    """Retorna a primeira URL Amazon convertida encontrada no texto, expandindo encurtadores se necessário."""
    for match in _URL_PATTERN.finditer(text):
        url = match.group(0)
        
        try:
            parsed = urllib.parse.urlparse(url)
            netloc = parsed.netloc.lower()
        except Exception:
            continue
        
        # Se já for uma URL longa direta da Amazon, injeta e retorna imediatamente (rápido, sem HTTP request)
        if "amazon.com.br" in netloc or "amazon.com" in netloc:
            return _inject_affiliate_tag(url)
            
        # Caso contrário, pode ser um encurtador ou link intermediário. Tentamos expandir.
        try:
            resolved = await expandir_e_converter_link(url, AFFILIATE_TAG)
            if "amazon.com.br" in resolved or "amazon.com" in resolved:
                return resolved
        except Exception as e:
            # Em caso de erro de conexão/resolução, ignoramos e tentamos o próximo link
            continue
            
    return ""


async def process_async(text: str) -> str | None:
    """Pipeline completo de conversão e formatação de uma oferta de forma assíncrona.

    Diferente de process(), resolve links encurtados (como amzn.to) de forma real
    fazendo chamadas HTTP para seguir redirecionamentos e injetar a tag na URL final.

    Returns:
        Post formatado em HTML pronto para postagem no canal de saída, ou None se nenhuma URL Amazon for localizada.
    """
    url = await _extract_first_amazon_url_async(text)
    if not url:
        return None

    has_subscribe_and_save = _check_subscribe_and_save(text)

    if _is_coupon_announcement(text):
        coupon = _extract_coupon(text)
        benefit = _extract_coupon_benefit(text)
        has_prime = _check_prime(text)
        teaser = _extract_teaser(text, benefit)
        return _format_coupon_post(benefit, url, coupon, has_prime, teaser, has_subscribe_and_save)

    product_name = _extract_product_name(text)
    price = _extract_price(text)
    installments = _extract_installments(text)
    coupon = _extract_coupon(text)
    has_prime = _check_prime(text)
    teaser = _extract_teaser(text, product_name)

    return _format_post(product_name, price, url, installments, coupon, has_prime, teaser, has_subscribe_and_save)

