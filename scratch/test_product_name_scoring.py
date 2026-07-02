import re

_PRODUCT_EMOJIS = set("💻📺📱🎧🛒🎮🔊🔌💡🧴👟👕🎒⌨️🖱️⌚💳🖥️📽️📸⚙️📦🗝️🧸")

_KEYWORDS = [
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

_BRANDS = [
    "lenovo", "dell", "samsung", "aoc", "philco", "lg", "sony", "panasonic", "pioneer", "multilaser",
    "positivo", "asus", "acer", "hp", "apple", "xiaomi", "redmi", "poco", "realme", "motorola", "nokia",
    "huawei", "oppo", "vivo", "oneplus", "google", "amazon", "alexa", "echo", "kindle", "fire tv", "roku",
    "chromecast", "intel", "amd", "nvidia", "geforce", "radeon", "kingston", "sandisk", "wd", "western digital",
    "seagate", "toshiba", "corsair", "hyperx", "razer", "logitech", "redragon", "t-dagger", "havit", "edifier",
    "jbl", "sony", "bose", "sennheiser", "audio-technica", "shure", "behringer", "focusrite", "epson", "canon",
    "nikon", "gopro", "dji"
]

def _extract_product_name(text: str) -> str:
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
        if any(kw in clean_lower for kw in _KEYWORDS):
            score += 30
            
        # Marcas
        if any(brand in clean_lower for brand in _BRANDS):
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
    # Remove emojis do começo da string
    clean_winner = re.sub(r"^[^\w\s]+", "", clean_winner).strip()
    
    return clean_winner[:80]

# Testes
test_cases = [
    # Case 1: AOC Monitor
    """Para sua Sindrome de Pro Player

🔥Monitor Gamer AOC Destiny 24,5 Polegadas, 240Hz

💵R$ 899
🎟Cupom: `VAIPROGOL` ou BOLAROLANDO
🔗
https://link.amazon/B0a5e17nA""",

    # Case 2: Smart TV
    """CABE EM QUALQUER CANTIN DA CASA

📺 **Smart TV 32" Philco Roku TV**

🔥 ~~DE 999,99~~ | **POR 699,90 no Pix ou 742 até 12x**
🎟 CUPOM: **VAIPROGOL**

🔗 https://amzn.divulgador.link/mxJsK2J3""",

    # Case 3: Lenovo Notebook
    """TROCAR TEU NOTE QUE TA CAPENGA JÁ

💻 **Notebook Lenovo Ideapad Slim 3, Intel Core i5-13420h 8GB RAM, 512GB SSD, W11**

🔥 ~~DE 3.999~~ | **POR 3.229,05 no Pix ou 3.419 até 10x**""",

    # Case 4: Simples
    "🔥 SSD Samsung 1TB — por apenas R$ 379,90 no Pix!"
]

for i, t in enumerate(test_cases, 1):
    print(f"CASE {i}:")
    print(f"WINNER: {_extract_product_name(t)}")
    print("-" * 40)
