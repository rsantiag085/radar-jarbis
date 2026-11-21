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
        "notebook", "laptop", "monitor", "odyssey", "qhd", "180hz", "144hz", "240hz",
        "teclado", "mouse", "bateria portátil", "powerbank", "power bank",
        "cadeira gamer", "cadeira gaming", "cadeira de escritório", "cadeira de escritorio",
        "cadeira ergonômica", "cadeira ergonomica", "periférico",
        "headset", "headset gamer", "headphone", "fone de ouvido", "fone gamer",
        "fones bluetooth", "fone bluetooth", "fones sem fio", "fone sem fio",
        "redragon", "zeus lite", "havit", "h2232d",
        "webcam", "ssd", "hd externo", "pendrive",
        "hub usb", "placa de vídeo", "processador", "memória ram", "memoria ram",
        "memória ddr4", "memoria ddr4", "memória ddr5", "memoria ddr5", "ddr4", "ddr5",
        "memória para notebook", "memoria para notebook", "memória notebook", "memoria notebook",
        "memória para desktop", "memoria para desktop", "memória desktop", "memoria desktop",
        "memória para pc", "memoria para pc", "memória pc", "memoria pc",
        "sodimm", "so-dimm", "dimm", "fonte",
        "gabinete", "cooler", "mousepad", "suporte", "carregador",
        "iphone", "smartphone", "celular", "galaxy", "moto g", "motorola", "xiaomi", "redmi", "poco",
        "tablet", "galaxy tab", "ipad",
        "playstation", "ps5", "xbox", "dualsense", "controle sem fio",
        "grand theft auto", "gta 6", "gta vi",
        "caixa de som", "boombox", "soundbar", "jbl", "aiwa",
        "drone", "dji",
    ],
    "pessoal": [
        "tênis", "tenis", "sneaker", "relógio", "relogio", "smartwatch",
    ],
    "smart_home": [
        "smart tv", "tv 4k", "televisão", "televisao", "robô aspirador",
        "robo aspirador", "aspirador robô", "aspirador robot",
        "aspirador de pó", "aspirador de po", "aspirador vertical",
        "fechadura eletrônica", "fechadura eletronica", "fechadura digital",
        "lâmpada inteligente", "lampada inteligente", "tomada inteligente",
        "câmera de segurança", "camera de segurança", "câmera segurança", "camera seguranca",
        "câmera inteligente", "camera inteligente", "câmera bullet", "camera bullet",
        "hikvision", "intelbras", "mercusys",
        "campainha inteligente", "campainha sem fio", "alexa", "echo dot",
        "google home", "google nest", "chromecast", "fire tv stick", "apple tv",
        "ventilador de mesa", "ventilador de parede", "ventilador de coluna", "ventilador",
        "mop", "esfregão", "esfregao", "balde", "vassoura",
        "organizador", "varal", "travesseiro", "travesseiros", "espelho",
    ],
    "casa_cozinha": [
        "fogão", "fogao", "cooktop", "liquidificador", "liquidificadores",
        "panela", "panelas", "frigideira", "frigideiras", "jogo de panelas",
        "jogo de panela", "panela de pressão", "panela de pressao",
        "air fryer", "airfryer", "fritadeira",
        "sanduicheira", "grill", "mixer", "churrasqueira elétrica", "churrasqueira eletrica",
        "purificador de água", "purificador de agua", "purificador água", "purificador agua",
        "balança de cozinha", "balanca de cozinha",
        "copo térmico", "copo termico", "stanley", "quencher",
        "potes de vidro", "potes herméticos", "potes hermeticos", "pote hermético",
    ],
    "beleza": [
        "perfume", "eau de toilette", "eau de parfum", "edp", "edt",
        "colônia", "colonia", "cologne", "floratta", "natura homem", "ilía", "ilia",
        "o boticário", "oboticário", "boticario", "eudora",
        "body splash", "body spray", "creme", "sérum", "serum", "sérum facial",
        "serum facial", "hidratante", "hidrante", "protetor solar", "base", "batom", "máscara",
        "mascara facial", "esfoliante", "shampoo", "condicionador", "finalizador",
        "leave-in", "leave in", "óleo capilar", "oleo capilar", "reconstrutor capilar",
        "tratamento capilar", "kérastase", "kerastase", "l'oréal", "loreal", "truss",
        "lola cosmetics", "koleston", "cicaplast", "la roche-posay", "la roche posay",
        "principia", "gel de limpeza facial", "epidrat", "mantecorp", "cerave", "vichy",
        "desodorante", "antitranspirante", "sabonete", "eucerin", "anti-idade",
        "antiidade", "epigenetic", "gel higienizante", "giovanna baby",
        "pasta de dente", "creme dental", "oral-b", "oral b", "enxaguante bucal",
        "listerine", "colgate plax", "gillette", "mach3", "oneblade", "aparelho de barbear",
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
        "café", "cafe", "melitta", "dolce gusto", "achocolatado", "kopenhagen",
        "azeite", "azeite de oliva", "pepino", "pepinos em conserva", "hemmer",
        "pasta de amendoim", "brigadeiro", "flormel",
        "desinfetante", "lysoform", "limpador", "veja limpador", "limpador perfumado",
        "detergente", "finish", "lava louças", "lava-louças", "harpic", "papel higiênico", "papel higienico",
    ],
    "vestuario": [
        "cueca", "cuecas", "samba canção", "samba cancao", "meia", "meias",
        "roupa", "roupas", "vestuário", "vestuario",
        "camiseta", "camisetas", "camisa", "camisas", "calça", "calca", "calças", "calcas",
        "bermuda", "bermudas", "vestido", "vestidos", "blusa", "blusas", "jaqueta", "jaquetas",
        "moletom", "moletons", "itens esportivos para treino",
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
    "geladeira", "microondas", "micro-ondas", "batedeira", "chaleira", "cafeteira",  # eletrodomésticos restantes
    "cerveja", "cervejas", "chope", "chopp", "baden baden", "heineken",
    "stella artois", "budweiser", "corona", "eisenbahn", "amstel", "skol",
    "brahma", "bohemia", "itaipava", "devassa",
    "iphone 17", "iph\u2060one 17", "bundle nintendo",
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

def _normalize_text(text: str) -> str:
    """Remove caracteres invisíveis (zero-width spaces/joiners) e converte para lowercase."""
    return re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", text).lower()


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
    text_lower = _normalize_text(text)

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
        
    text_lower = _normalize_text(text)
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
        "perfume", "eau de toilette", "eau de parfum", "edp", "edt",
        "colônia", "colonia", "cologne", "body splash", "body spray",
        "floratta", "natura homem", "ilía", "ilia"
    ],
    "relogio": ["relógio", "relogio", "smartwatch"],

    # Tecnologia & Informática
    "smartphone": ["iphone", "smartphone", "celular", "galaxy", "moto g", "motorola", "xiaomi", "redmi", "poco"],
    "tablet": ["tablet", "galaxy tab", "ipad"],
    "games": ["playstation", "ps5", "xbox", "dualsense", "controle sem fio", "grand theft auto", "gta 6", "gta vi"],
    "audio": ["caixa de som", "boombox", "soundbar", "jbl", "aiwa"],
    "drone": ["drone", "dji"],
    "notebook": ["notebook", "laptop"],
    "monitor": ["monitor", "odyssey", "180hz", "144hz", "240hz"],
    "teclado": ["teclado"],
    "mouse": ["mouse", "mousepad"],
    "fone": [
        "fone de ouvido", "fone gamer", "fones bluetooth", "fone bluetooth",
        "fones sem fio", "fone sem fio", "headset", "headset gamer",
        "headphone", "earbud", "airpod", "zeus lite", "h2232d"
    ],
    "armazenamento": ["ssd", "hd externo", "pendrive"],
    "memoria_ram": [
        "memória ram", "memoria ram", "memória ddr4", "memoria ddr4",
        "memória ddr5", "memoria ddr5", "ddr4", "ddr5",
        "memória para notebook", "memoria para notebook", "sodimm", "so-dimm", "dimm"
    ],
    "hardware": ["placa de vídeo", "processador", "fonte", "gabinete", "cooler"],
    "cadeira_gamer": [
        "cadeira gamer", "cadeira gaming", "cadeira de escritório",
        "cadeira de escritorio", "cadeira ergonômica", "cadeira ergonomica"
    ],

    # Vestuário & Moda
    "camiseta": ["camiseta", "camisetas", "camisa", "camisas"],
    "cueca": ["cueca", "cuecas", "samba canção", "samba cancao"],
    "meia": ["meia", "meias"],
    "calca": ["calça", "calca", "calças", "calcas", "legging"],
    "casaco": ["jaqueta", "jaquetas", "moletom", "moletons", "corta vento"],
    "bermuda": ["bermuda", "bermudas", "shorts"],
    "vestido": ["vestido", "vestidos", "blusa", "blusas"],

    # Smart Home / Casa
    "smart_tv": ["smart tv", "tv 4k", "televisão", "televisao", "chromecast", "fire tv stick", "apple tv"],
    "aspirador": [
        "robô aspirador", "robo aspirador", "aspirador robô", "aspirador robot",
        "aspirador de pó", "aspirador de po", "aspirador vertical"
    ],
    "camera_seguranca": [
        "câmera de segurança", "camera de segurança", "câmera segurança", "camera seguranca",
        "câmera inteligente", "camera inteligente", "câmera bullet", "camera bullet",
        "hikvision", "intelbras", "mercusys"
    ],
    "fechadura": ["fechadura eletrônica", "fechadura eletronica", "fechadura digital", "campainha sem fio", "campainha inteligente"],
    "ventilador": ["ventilador de mesa", "ventilador de parede", "ventilador de coluna", "ventilador"],
    "mop_limpeza": ["mop", "esfregão", "esfregao", "balde", "vassoura"],
    "organizacao": ["organizador", "varal", "travesseiro", "travesseiros", "espelho"],

    # Casa e Cozinha
    "airfryer": ["air fryer", "airfryer", "fritadeira"],
    "eletroportateis_cozinha": [
        "sanduicheira", "grill", "mixer", "churrasqueira elétrica", "churrasqueira eletrica",
        "purificador de água", "purificador de agua", "purificador água", "purificador agua",
        "balança de cozinha", "balanca de cozinha"
    ],
    "copo_termico": ["copo térmico", "copo termico", "stanley", "quencher"],
    "potes_cozinha": ["potes de vidro", "potes herméticos", "potes hermeticos", "pote hermético"],
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
        "hidratante", "hidrante", "protetor solar", "base", "batom", "máscara",
        "mascara facial", "esfoliante", "eucerin", "anti-idade", "antiidade", "epigenetic",
        "cicaplast", "la roche-posay", "la roche posay", "principia", "gel de limpeza facial",
        "epidrat", "mantecorp", "cerave", "vichy"
    ],
    "cabelo": [
        "shampoo", "condicionador", "finalizador", "leave-in", "leave in",
        "óleo capilar", "oleo capilar", "reconstrutor capilar", "tratamento capilar",
        "kérastase", "kerastase", "l'oréal", "loreal", "truss", "lola cosmetics", "koleston"
    ],
    "higiene": [
        "desodorante", "antitranspirante", "sabonete", "gel higienizante", "giovanna baby",
        "pasta de dente", "creme dental", "oral-b", "oral b", "enxaguante bucal",
        "listerine", "colgate plax", "gillette", "mach3", "oneblade", "aparelho de barbear"
    ],

    # Supermercado
    "cafe": ["café", "cafe", "melitta", "dolce gusto", "achocolatado", "kopenhagen"],
    "mercearia": ["azeite", "azeite de oliva", "pepino", "pepinos em conserva", "hemmer", "pasta de amendoim", "brigadeiro", "flormel"],
    "limpeza_supermercado": [
        "desinfetante", "lysoform", "limpador", "veja limpador", "limpador perfumado",
        "detergente", "finish", "lava louças", "lava-louças", "harpic", "papel higiênico", "papel higienico"
    ],
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
    text_lower = _normalize_text(text)
    for subtype, keywords in SUBTYPE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return subtype
    return None
