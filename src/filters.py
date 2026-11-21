"""
Motor de filtragem de ofertas do RadarJarbis.

Avalia mensagens recebidas dos canais master e decide se pertencem
a uma das 6 categorias permitidas definidas em config/context/CONTEXT.md.
"""

import re
from . import settings


# ------------------------------------------------------------
# Categorias e Keywords (baseadas estritamente no CONTEXT.md)
# ------------------------------------------------------------

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "tecnologia": [
        "notebook", "laptop", "monitor", "teclado", "mouse", "bateria portátil",
        "powerbank", "power bank", "cadeira gamer", "cadeira gaming", "periférico",
        "headset", "headset gamer", "headphone", "fone de ouvido", "fone gamer",
        "redragon", "zeus lite", "havit", "h2232d",
        "webcam", "ssd", "hd externo", "pendrive",
        "hub usb", "placa de vídeo", "processador", "memória ram", "memoria ram",
        "memória ddr4", "memoria ddr4", "memória ddr5", "memoria ddr5", "ddr4", "ddr5",
        "memória para notebook", "memoria para notebook", "memória notebook", "memoria notebook",
        "memória para desktop", "memoria para desktop", "memória desktop", "memoria desktop",
        "memória para pc", "memoria para pc", "memória pc", "memoria pc",
        "sodimm", "so-dimm", "dimm", "fonte",
        "gabinete", "cooler", "mousepad", "suporte", "carregador",
    ],
    "pessoal": [
        "tênis", "tenis", "sneaker", "relógio", "relogio", "smartwatch",
    ],
    "smart_home": [
        "smart tv", "tv 4k", "televisão", "televisao", "robô aspirador",
        "robo aspirador", "aspirador robô", "aspirador robot", "fechadura eletrônica",
        "fechadura eletronica", "fechadura digital", "lâmpada inteligente",
        "lampada inteligente", "tomada inteligente", "câmera de segurança",
        "camera de segurança", "campainha inteligente", "alexa", "echo dot",
        "google home", "google nest", "chromecast", "fire tv stick", "apple tv",
        "ventilador de mesa", "mop", "esfregão", "esfregao", "balde", "vassoura",
        "organizador", "varal",
    ],
    "casa_cozinha": [
        "fogão", "fogao", "cooktop", "liquidificador", "liquidificadores",
        "panela", "panelas", "frigideira", "frigideiras", "jogo de panelas",
        "jogo de panela", "panela de pressão", "panela de pressao",
    ],
    "beleza": [
        "perfume", "eau de toilette", "eau de parfum", "colônia", "colonia", "cologne",
        "body splash", "body spray", "creme", "sérum", "serum", "sérum facial",
        "serum facial", "hidratante", "protetor solar", "base", "batom", "máscara",
        "mascara facial", "esfoliante", "shampoo", "condicionador", "finalizador",
        "desodorante", "antitranspirante", "sabonete", "eucerin", "anti-idade",
        "antiidade", "epigenetic",
    ],
    "saude": [
        "vitamina", "suplemento", "whey protein", "whey", "creatina", "colágeno",
        "colageno", "ômega", "omega 3", "probiótico", "probiotico", "proteína",
        "proteina", "pré-treino", "pre-treino", "glutamina", "multivitamínico",
        "multivitaminico",
    ],
    "supermercado": [
        "pringles", "batata frita", "batata frita pringles", "salgadinho", "chocolate",
        "biscoito", "bolacha", "snack", "petisco", "bebida", "refrigerante",
        "ketchup", "maionese", "mostarda", "heinz",
    ],
    "vestuario": [
        "cueca", "cuecas", "meia", "meias", "roupa", "roupas", "vestuário", "vestuario",
        "camiseta", "camisetas", "camisa", "camisas", "calça", "calca", "calças", "calcas",
        "bermuda", "bermudas", "vestido", "vestidos", "blusa", "blusas", "jaqueta", "jaquetas",
        "moletom", "moletons",
    ],
    "livros": [
        "livro", "livros", "ebook", "e-book", "box de livros", "kindle",
        "leitura", "literatura", "graphic novel", "mangá", "manga", "hq", "quadrinhos",
    ],
    "bebe_infantil": [
        "fralda", "fraldas", "lenço umedecido", "lenços umedecidos", "lenco umedecido", "lencos umedecidos",
        "bebê", "bebe", "mamadeira", "mamadeiras", "chupeta", "chupetas",
        "carrinho de bebê", "carrinho de bebe", "berço", "berco", "cadeirinha",
        "pomada de assadura", "pomada para assadura", "huggies", "pampers",
    ],
}

# Palavras que indicam categorias EXCLUÍDAS nesta fase (bloqueio explícito)
_EXCLUDED_KEYWORDS: list[str] = [
    "geladeira", "microondas", "batedeira", "chaleira", "cafeteira",  # eletrodomésticos restantes
    "cerveja", "cervejas", "chope", "chopp", "baden baden", "heineken",
    "stella artois", "budweiser", "corona", "eisenbahn", "amstel", "skol",
    "brahma", "bohemia", "itaipava", "devassa"
]

# Palavras que indicam categorias/produtos fora do nosso nicho (bloqueio específico para cupons gerais)
_NON_NICHE_KEYWORDS: list[str] = [
    "ração", "racao", "pet", "gato", "cachorro", "cão", "animal",
    "pneu", "automotivo", "carro", "moto",
    "brinquedo", "brinquedos", "papelaria",
    "copo", "prato", "talher",
    "ferramenta", "furadeira", "parafusadeira"
]

# Padrão para detectar percentual de desconto mencionado no texto
_DISCOUNT_PATTERN = re.compile(r"(\d+)\s*%\s*(?:off|desc(?:onto)?|de desconto)", re.IGNORECASE)


# ------------------------------------------------------------
# Helpers internos
# ------------------------------------------------------------

def _is_general_coupon_announcement(text: str) -> bool:
    """Verifica se a mensagem é um anúncio de cupom geral (não atrelado a um único produto/categoria fora de nicho)."""
    if not settings.ENABLE_COUPONS:
        return False
    text_lower = text.lower()
    has_coupon = "cupom" in text_lower or "cupons" in text_lower
    if not has_coupon:
        return False
        
    general_indicators = [
        "ganhe r$", "off nas compras acima", "compras acima de", 
        "nas compras acima", "cupom de frete", "desconto nas compras", 
        "cupom de r$", "cupom de desconto na amazon", "cupom amazon",
        "chegou mais um cupom"
    ]
    has_general_indicator = any(ind in text_lower for ind in general_indicators)
    if not has_general_indicator:
        return False
        
    # Bloqueia se o anúncio for específico de produtos fora do nosso nicho
    for kw in _NON_NICHE_KEYWORDS:
        # Usa limite de palavra (\b) para evitar falsos positivos
        if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
            return False
            
    return True


# ------------------------------------------------------------
# Interface pública
# ------------------------------------------------------------

def is_relevant(text: str) -> bool:
    """Decide se uma mensagem deve ser processada e postada.

    Critérios de aprovação:
    1. Não contém keywords de categorias EXCLUÍDAS na Fase 1.
    2. Pertence a pelo menos uma categoria permitida do CONTEXT.md OU é um cupom Amazon geral válido.
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

    # 2. Verificar se é um cupom Amazon geral
    is_gen_coupon = _is_general_coupon_announcement(text)

    # 3. Verificar se pertence a pelo menos uma categoria permitida
    matched_category = any(
        kw in text_lower
        for keywords in CATEGORY_KEYWORDS.values()
        for kw in keywords
    )
    
    if not (is_gen_coupon or matched_category):
        return False

    # 4. Verificar desconto mínimo de 10% (somente se desconto for mencionado)
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
    if _is_general_coupon_announcement(text):
        return "cupons"
        
    text_lower = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return category
    return None


# ------------------------------------------------------------
# Subtipos de Produtos para controle de Cooldown e Variedade
# ------------------------------------------------------------

SUBTYPE_KEYWORDS: dict[str, list[str]] = {
    # Pessoal / Calçados / Acessórios
    "tenis": ["tênis", "tenis", "sneaker"],
    "perfume": [
        "perfume", "eau de toilette", "eau de parfum", "colônia", "colonia",
        "cologne", "body splash", "body spray"
    ],
    "relogio": ["relógio", "relogio", "smartwatch"],

    # Tecnologia & Informática
    "notebook": ["notebook", "laptop"],
    "monitor": ["monitor"],
    "teclado": ["teclado"],
    "mouse": ["mouse", "mousepad"],
    "fone": [
        "fone de ouvido", "fone gamer", "headset", "headset gamer",
        "headphone", "earbud", "airpod", "zeus lite", "h2232d"
    ],
    "armazenamento": ["ssd", "hd externo", "pendrive"],
    "memoria_ram": [
        "memória ram", "memoria ram", "memória ddr4", "memoria ddr4",
        "memória ddr5", "memoria ddr5", "ddr4", "ddr5",
        "memória para notebook", "memoria para notebook", "sodimm", "so-dimm", "dimm"
    ],
    "hardware": ["placa de vídeo", "processador", "fonte", "gabinete", "cooler"],
    "cadeira_gamer": ["cadeira gamer", "cadeira gaming"],

    # Vestuário & Moda
    "camiseta": ["camiseta", "camisetas", "camisa", "camisas"],
    "cueca": ["cueca", "cuecas"],
    "meia": ["meia", "meias"],
    "calca": ["calça", "calca", "calças", "calcas", "legging"],
    "casaco": ["jaqueta", "jaquetas", "moletom", "moletons", "corta vento"],
    "bermuda": ["bermuda", "bermudas", "shorts"],
    "vestido": ["vestido", "vestidos", "blusa", "blusas"],

    # Smart Home / Casa
    "smart_tv": ["smart tv", "tv 4k", "televisão", "televisao", "chromecast", "fire tv stick", "apple tv"],
    "aspirador": ["robô aspirador", "robo aspirador", "aspirador robô", "aspirador robot"],
    "fechadura": ["fechadura eletrônica", "fechadura eletronica", "fechadura digital"],
    "ventilador": ["ventilador de mesa", "ventilador"],
    "mop_limpeza": ["mop", "esfregão", "esfregao", "balde", "vassoura"],
    "organizacao": ["organizador", "varal"],

    # Casa e Cozinha
    "fogao_cooktop": ["fogão", "fogao", "cooktop"],
    "liquidificador": ["liquidificador", "liquidificadores"],
    "panelas": [
        "panela", "panelas", "frigideira", "frigideiras",
        "jogo de panelas", "jogo de panela", "panela de pressão", "panela de pressao"
    ],

    # Beleza & Saúde
    "suplementos": [
        "whey protein", "whey", "creatina", "colágeno", "colageno",
        "ômega", "omega 3", "probiótico", "probiotico", "vitamina", "suplemento", "proteína"
    ],
    "skincare": [
        "creme", "sérum", "serum", "sérum facial", "serum facial",
        "hidratante", "protetor solar", "base", "batom", "máscara",
        "mascara facial", "esfoliante", "eucerin", "anti-idade", "antiidade", "epigenetic"
    ],
    "cabelo": ["shampoo", "condicionador", "finalizador"],
    "higiene": ["desodorante", "antitranspirante", "sabonete"],

    # Supermercado
    "snacks": ["pringles", "batata frita", "salgadinho", "chocolate", "biscoito", "bolacha", "snack", "petisco"],
    "bebidas": ["bebida", "refrigerante"],

    # Livros & Bebê
    "livros": ["livro", "livros", "ebook", "e-book", "box de livros", "kindle", "mangá", "manga", "hq", "quadrinhos"],
    "bebe": ["fralda", "fraldas", "lenço umedecido", "lenços umedecidos", "lenco umedecido", "lencos umedecidos", "mamadeira", "chupeta", "huggies", "pampers"],
}


def get_subtype(text: str) -> str | None:
    """Retorna o subtipo do produto identificado (ex: 'perfume', 'tenis', 'camiseta').

    Útil para cooldown específico de produto e evitar posts repetitivos do mesmo tipo.

    Args:
        text: Texto bruto da mensagem.

    Returns:
        Nome do subtipo ou None se nenhum for identificado.
    """
    text_lower = text.lower()
    for subtype, keywords in SUBTYPE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return subtype
    return None
