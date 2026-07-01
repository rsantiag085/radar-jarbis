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

# ------------------------------------------------------------
# Constantes
# ------------------------------------------------------------

AFFILIATE_TAG = "noradardojarb-20"

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
    "⚠️ MENOR PREÇO HISTÓRICO",
    "⚡ CORRE ANTES QUE ACABE",
    "📉 BUG DE PREÇO",
]

# Padrões para extração de preço e nome do produto
_PRICE_PATTERN = re.compile(
    r"R\$\s*[\d.,]+", re.IGNORECASE
)
_PRODUCT_NAME_PATTERN = re.compile(
    r"(?:🛒|produto:|oferta:|✅)?\s*(.{10,80}?)(?:\n|R\$|por apenas|de|Link)",
    re.IGNORECASE,
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


def _inject_affiliate_tag(url: str) -> str:
    """Injeta o parâmetro 'tag=noradardojarb-20' em uma URL Amazon.

    Substitui tag existente se houver, ou adiciona ao query string.

    Args:
        url: URL bruta do canal master.

    Returns:
        URL com tag de afiliado injetada.
    """
    if not _is_amazon_url(url):
        return url  # URLs não-Amazon são mantidas sem alteração

    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    params["tag"] = [AFFILIATE_TAG]  # substitui tag existente ou adiciona nova
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
                
        parsed_url = urllib.parse.urlparse(url_final)
        if 'amazon.com.br' not in parsed_url.netloc:
            return url_final
            
        query_params = urllib.parse.parse_qs(parsed_url.query)
        query_params['tag'] = [sua_tag]
        query_params.pop('ascsubtag', None)
        
        new_query = urllib.parse.urlencode(query_params, doseq=True)
        return urllib.parse.urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            parsed_url.params,
            new_query,
            parsed_url.fragment
        ))
    except Exception as e:
        print(f"Erro de SRE ao expandir link {url_encurtada}: {e}")
        return url_encurtada


# ------------------------------------------------------------
# Extração de dados da oferta
# ------------------------------------------------------------

def _extract_price(text: str) -> str:
    """Extrai o primeiro preço encontrado no texto."""
    match = _PRICE_PATTERN.search(text)
    return match.group(0).strip() if match else ""


def _extract_product_name(text: str) -> str:
    """Tenta extrair o nome do produto do texto bruto."""
    match = _PRODUCT_NAME_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    # Fallback: usa a primeira linha não vazia como nome
    for line in text.splitlines():
        clean = line.strip().lstrip("🛒✅⚡⚠️📉🔥💰").strip()
        if len(clean) > 10:
            return clean[:80]
    return "Oferta imperdível"


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

def _format_post(product_name: str, price: str, url: str) -> str:
    """Monta o bloco de texto final para postagem no canal.

    Formato HTML compatível com Telegram (ParseMode.HTML).

    Args:
        product_name: Nome/descrição do produto.
        price: Preço formatado (ex: 'R$ 299,90').
        url: URL afiliada Amazon.

    Returns:
        String formatada em HTML para postagem.
    """
    trigger = random.choice(_TRIGGERS)
    price_block = f"\n💰 <b>{price}</b>" if price else ""
    url_block = f"\n\n🔗 {url}" if url else ""

    return (
        f"{trigger}\n\n"
        f"🛒 <b>{product_name}</b>"
        f"{price_block}"
        f"{url_block}\n\n"
        f"<i>Links qualificados de associado.</i>"
    )


# ------------------------------------------------------------
# Interface pública
# ------------------------------------------------------------

def process(text: str) -> str:
    """Pipeline completo de conversão e formatação de uma oferta.

    Etapas:
    1. Extrai nome do produto, preço e URL Amazon do texto bruto.
    2. Injeta tag de afiliado na URL.
    3. Formata o post com gatilho mental e estrutura HTML.

    Args:
        text: Texto bruto da mensagem aprovada pelo filters.py.

    Returns:
        Post formatado em HTML pronto para postagem no canal de saída.
    """
    product_name = _extract_product_name(text)
    price = _extract_price(text)
    url = _extract_first_amazon_url(text)

    return _format_post(product_name, price, url)
