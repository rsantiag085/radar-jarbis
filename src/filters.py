"""
Motor de filtragem de ofertas do RadarJarbis.

Avalia mensagens recebidas dos canais master e decide se pertencem
a uma das 4 categorias permitidas definidas em config/context/CONTEXT.md.
"""

import re

# ------------------------------------------------------------
# Categorias e Keywords (baseadas estritamente no CONTEXT.md)
# ------------------------------------------------------------

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "tecnologia": [
        "notebook", "laptop", "monitor", "teclado", "mouse", "bateria portátil",
        "powerbank", "power bank", "cadeira gamer", "cadeira gaming", "periférico",
        "headset", "fone de ouvido", "webcam", "ssd", "hd externo", "pendrive",
        "hub usb", "placa de vídeo", "processador", "memória ram", "fonte",
        "gabinete", "cooler", "mousepad", "suporte", "carregador",
    ],
    "pessoal": [
        "tênis", "tenis", "sneaker", "perfume", "eau de toilette", "eau de parfum",
        "colônia", "cologne", "relógio", "relogio", "smartwatch", "body splash",
        "body spray",
        # EXCLUÍDO: roupas, vestuário, camiseta, calça, bermuda (CONTEXT.md Fase 1)
    ],
    "smart_home": [
        "smart tv", "tv 4k", "televisão", "televisao", "robô aspirador",
        "robo aspirador", "aspirador robô", "aspirador robot", "fechadura eletrônica",
        "fechadura eletronica", "fechadura digital", "lâmpada inteligente",
        "lampada inteligente", "tomada inteligente", "câmera de segurança",
        "camera de segurança", "campainha inteligente", "alexa", "echo dot",
        "google home", "google nest", "chromecast", "fire tv stick", "apple tv",
        "ventilador de mesa",
        # EXCLUÍDO: eletrodomésticos, utensílios de cozinha (CONTEXT.md Fase 1)
    ],
    "beleza_saude": [
        "creme", "sérum", "serum", "hidratante", "protetor solar", "base", "batom",
        "máscara", "mascara facial", "esfoliante", "vitamina", "suplemento",
        "whey protein", "whey", "creatina", "colágeno", "colageno", "ômega",
        "omega 3", "probiótico", "probiotico", "shampoo", "condicionador",
        "finalizador", "desodorante", "antitranspirante", "sabonete", "proteína",
    ],
}

# Palavras que indicam categorias EXCLUÍDAS nesta fase (bloqueio explícito)
_EXCLUDED_KEYWORDS: list[str] = [
    "camiseta", "camisa", "calça", "calca", "bermuda", "vestido", "blusa",
    "jaqueta", "moletom", "cueca", "meia", "roupa", "vestuário",  # vestuário
    "geladeira", "fogão", "fogao", "microondas", "liquidificador", "batedeira",
    "panela", "frigideira", "chaleira", "cafeteira",  # eletrodomésticos/cozinha
]

# Padrão para detectar percentual de desconto mencionado no texto
_DISCOUNT_PATTERN = re.compile(r"(\d+)\s*%\s*(?:off|desc(?:onto)?|de desconto)", re.IGNORECASE)


# ------------------------------------------------------------
# Interface pública
# ------------------------------------------------------------

def is_relevant(text: str) -> bool:
    """Decide se uma mensagem deve ser processada e postada.

    Critérios de aprovação (todos devem ser atendidos):
    1. Pertence a pelo menos uma categoria permitida do CONTEXT.md.
    2. Não contém keywords de categorias EXCLUÍDAS na Fase 1.
    3. Se mencionar desconto explícito, este deve ser >= 10% (GEMINI.md §3).

    Args:
        text: Texto bruto da mensagem recebida do canal master.

    Returns:
        True se a mensagem deve ser postada, False caso contrário.
    """
    text_lower = text.lower()

    # 1. Verificar bloqueio por categoria excluída
    if any(kw in text_lower for kw in _EXCLUDED_KEYWORDS):
        return False

    # 2. Verificar se pertence a pelo menos uma categoria permitida
    matched = any(
        kw in text_lower
        for keywords in CATEGORY_KEYWORDS.values()
        for kw in keywords
    )
    if not matched:
        return False

    # 3. Verificar desconto mínimo de 10% (somente se desconto for mencionado)
    discount_match = _DISCOUNT_PATTERN.search(text)
    if discount_match:
        discount = int(discount_match.group(1))
        if discount < 10:
            return False

    return True


def get_category(text: str) -> str | None:
    """Retorna o nome da categoria identificada (primeira correspondência).

    Útil para logging e futuros filtros por categoria específica.

    Args:
        text: Texto bruto da mensagem.

    Returns:
        Nome da categoria ou None se nenhuma for identificada.
    """
    text_lower = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return category
    return None
