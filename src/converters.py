"""
Motor de conversão de URLs e formatação de copywriting do RadarJarbis.

Responsabilidades:
- Detectar e converter URLs Amazon para incluir a tag de afiliado.
- Formatar o post final com gatilhos mentais (GEMINI.md).
"""

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

# Padrão para capturar URLs (http e https)
_URL_PATTERN = re.compile(r"https?://[^\s\)\]>\"']+")

# Gatilhos mentais (GEMINI.md §2)
_TRIGGERS = [
    "🔥 OFERTA PRIME DAY 🔥",
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
_PRODUCT_EMOJIS = set("💻📺📱🎧🛒🎮🔊🔌💡🧴👟👕🎒⌨️🖱️⌚💳🖥️📽️📸⚙️📦🗝️🧸")

_PRODUCT_KEYWORDS = [
    "notebook", "laptop", "smart tv", "tv", "monitor", "gabinete", "ssd", "teclado", "mouse", "headset",
    "fone", "smartphone", "celular", "iphone", "galaxy", "philco", "lenovo", "dell", "samsung", "aoc",
    "lg", "tcl", "multilaser", "positivo", "gree", "consul", "brastemp", "electrolux", "midea",
    "ar condicionado", "geladeira", "fogão", "microondas", "fritadeira", "airfryer", "panela", "cafeteira",
    "liquidificador", "batedeira", "aspirador", "ferro", "chuveiro", "ventilador de mesa", "ventilador", "aquecedor", "climatizador",
    "purificador", "filtro", "torneira", "lâmpada", "tomada", "interruptor", "roteador", "modem", "repetidor",
    "câmera", "fechadura", "sensor", "alarme", "interfone", "campainha", "projetor", "caixa de som", "soundbar",
    "home theater", "receiver", "amplificador", "microfone", "estabilizador", "nobreak", "filtro de linha",
    "adaptador", "cabo", "carregador", "bateria", "power bank", "memória", "ram", "cooler", "ventoinha",
    "placa de vídeo", "gpu", "processador", "cpu", "placa-mãe", "fonte", "hd", "pendrive", "cartão de memória",
    "console", "playstation", "xbox", "nintendo", "switch", "kindle", "echo", "alexa"
]

_PRODUCT_BRANDS = [
    "lenovo", "dell", "samsung", "aoc", "philco", "lg", "sony", "panasonic", "pioneer", "multilaser",
    "positivo", "asus", "acer", "hp", "apple", "xiaomi", "redmi", "poco", "realme", "motorola", "nokia",
    "huawei", "oppo", "vivo", "oneplus", "google", "amazon", "alexa", "echo", "kindle", "fire tv", "roku",
    "chromecast", "intel", "amd", "nvidia", "geforce", "radeon", "kingston", "sandisk", "wd", "western digital",
    "seagate", "toshiba", "corsair", "hyperx", "razer", "logitech", "redragon", "t-dagger", "havit", "edifier",
    "jbl", "sony", "bose", "sennheiser", "audio-technica", "shure", "behringer", "focusrite", "epson", "canon",
    "nikon", "gopro", "dji"
]
_INSTALLMENT_PATTERN = re.compile(
    r"\b(?:em\s+até|em|até)\s+\d{1,2}\s*x(?:\s+sem\s+juros)?",
    re.IGNORECASE
)
_PRIME_PATTERN = re.compile(
    r"\b(?:exclusiv[ao]?\s+)?membros\s+(?:Amazon\s+)?prime\b|\bexclusiv[ao]?\s+prime\b",
    re.IGNORECASE
)
_COUPON_PATTERN = re.compile(
    r"\b(?:CUPOM|Cupom|cupom|🎟️?|use\s+o\s+cupom|cumpom)[:\s-]*\**([A-Z0-9]{3,20}(?:\s*[\++-]\s*[A-Z0-9]{3,20})*)\**"
)
_TEASER_EXCLUDE_PATTERN = re.compile(
    r"R\$\s*\d|\b(?:cupom|use|cumpom|notificações|grupo|canal|whatsapp|t\.me)\b|https?://",
    re.IGNORECASE
)


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


async def expandir_e_converter_link(url_encurtada: str, sua_tag: str = "noradardojarb-20") -> str:
    """Segue os redirecionamentos de links encurtados e injeta a tag de afiliado."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        # Método GET com Stream para passar pelas barreiras de segurança da Amazon/Encurtador
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            async with client.stream("GET", url_encurtada, headers=headers) as response:
                url_final = str(response.url)
                
        if not _is_amazon_url(url_final):
            return url_final
            
        # Reaproveita a limpeza de lixo e a injeção da tag na URL expandida
        return _inject_affiliate_tag(url_final, tag=sua_tag)
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


def _extract_installments(text: str) -> str:
    """Extrai informações de parcelamento (ex: 'em até 10x sem juros')."""
    match = _INSTALLMENT_PATTERN.search(text)
    return match.group(0).strip() if match else ""


def _extract_coupon(text: str) -> str:
    """Extrai o código do cupom se estiver presente na mensagem original."""
    match = _COUPON_PATTERN.search(text)
    return match.group(1).strip() if match else ""


def _check_prime(text: str) -> bool:
    """Verifica se a oferta é exclusiva para membros Prime."""
    return bool(_PRIME_PATTERN.search(text))


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
            
            if clean_flat == product_name:
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
            
        score = 0
        clean_lower = clean.lower()
        
        # Filtros negativos fortes
        if any(p in clean_lower for p in ["r$", "por", "de", "pix", "ou", "10x", "12x", "cupom", "use", "http", "🔗", "link"]):
            score -= 50
        if any(p in clean_lower for p in ["notificações", "perder nada", "grupo", "canal", "t.me", "whatsapp"]):
            score -= 50
            
        # Emojis de produto
        if any(char in _PRODUCT_EMOJIS for char in clean):
            score += 20
            
        # Negrito
        if ("**" in clean) or ("__" in clean):
            score += 15
            
        # Palavras-chave de produtos
        if any(kw in clean_lower for kw in _PRODUCT_KEYWORDS):
            score += 30
            
        # Marcas
        if any(brand in clean_lower for brand in _PRODUCT_BRANDS):
            score += 15
            
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
    
    return clean_winner[:80]


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

def _format_post(product_name: str, price: str, url: str, installments: str = "", coupon: str = "", has_prime: bool = False, teaser: str = "") -> str:
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

    Returns:
        String formatada em HTML para postagem.
    """
    trigger = random.choice(_TRIGGERS)
    teaser_block = f"✨ <i>{teaser}</i>\n\n" if teaser else ""
    price_suffix = f" {installments}" if installments else ""
    price_block = f"\n💰 <b>{price}</b>{price_suffix}" if price else ""
    coupon_block = f"\n🎟️ Cupom: <b>{coupon}</b>" if coupon else ""
    prime_block = f"\n\n👑 <i>Exclusivo Membros Prime</i>" if has_prime else ""
    url_block = f"\n\n🔗 {url}" if url else ""

    return (
        f"{trigger}\n\n"
        f"{teaser_block}"
        f"🛒 <b>{product_name}</b>"
        f"{price_block}"
        f"{coupon_block}"
        f"{url_block}"
        f"{prime_block}"
    )


# ------------------------------------------------------------
# Interface pública
# ------------------------------------------------------------

def process(text: str) -> str | None:
    """Pipeline completo de conversão e formatação de uma oferta.

    Etapas:
    1. Extrai nome do produto, preço e URL Amazon do texto bruto.
    2. Injeta tag de afiliado na URL.
    3. Formata o post com gatilho mental e estrutura HTML.

    Args:
        text: Texto bruto da mensagem aprovada pelo filters.py.

    Returns:
        Post formatado em HTML pronto para postagem no canal de saída, ou None se nenhuma URL Amazon for localizada.
    """
    product_name = _extract_product_name(text)
    price = _extract_price(text)
    installments = _extract_installments(text)
    coupon = _extract_coupon(text)
    has_prime = _check_prime(text)
    teaser = _extract_teaser(text, product_name)
    url = _extract_first_amazon_url(text)

    if not url:
        return None

    return _format_post(product_name, price, url, installments, coupon, has_prime, teaser)


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
    product_name = _extract_product_name(text)
    price = _extract_price(text)
    installments = _extract_installments(text)
    coupon = _extract_coupon(text)
    has_prime = _check_prime(text)
    teaser = _extract_teaser(text, product_name)
    url = await _extract_first_amazon_url_async(text)

    if not url:
        return None

    return _format_post(product_name, price, url, installments, coupon, has_prime, teaser)

