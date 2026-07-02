import re

_PRODUCT_EMOJIS = set("💻📺📱🎧🛒🎮🔊🔌💡🧴👟👕🎒⌨️🖱️⌚💳🖥️📽️📸⚙️📦🗝️🧸")

_PRODUCT_KEYWORDS = [
    "notebook", "laptop", "smart tv", "tv", "monitor", "gabinete", "ssd", "teclado", "mouse", "headset",
    "fone", "smartphone", "celular", "iphone", "galaxy", "philco", "lenovo", "dell", "samsung", "aoc",
    "lg", "tcl", "multilaser", "positivo", "gree", "consul", "brastemp", "electrolux", "midea"
]

_PRODUCT_BRANDS = [
    "lenovo", "dell", "samsung", "aoc", "philco", "lg", "sony", "panasonic", "pioneer", "multilaser",
    "positivo", "asus", "acer", "hp", "apple", "xiaomi", "redmi", "poco", "realme", "motorola"
]

_TEASER_EXCLUDE_PATTERN = re.compile(
    r"R\$\s*\d|\b(?:cupom|use|cumpom|notificações|grupo|canal|whatsapp|t\.me)\b|https?://",
    re.IGNORECASE
)

def _extract_product_name(text: str) -> str:
    lines = text.splitlines()
    scored_lines = []
    
    for line in lines:
        clean = line.strip()
        if not clean:
            continue
            
        score = 0
        clean_lower = clean.lower()
        
        if any(p in clean_lower for p in ["r$", "por", "de", "pix", "ou", "10x", "12x", "cupom", "use", "http", "🔗", "link"]):
            score -= 50
        if any(p in clean_lower for p in ["notificações", "perder nada", "grupo", "canal", "t.me", "whatsapp"]):
            score -= 50
            
        if any(char in _PRODUCT_EMOJIS for char in clean):
            score += 20
            
        if ("**" in clean) or ("__" in clean):
            score += 15
            
        if any(kw in clean_lower for kw in _PRODUCT_KEYWORDS):
            score += 30
            
        if any(brand in clean_lower for brand in _PRODUCT_BRANDS):
            score += 15
            
        if 15 <= len(clean) <= 100:
            score += 10
        elif len(clean) < 8 or len(clean) > 130:
            score -= 30
            
        scored_lines.append((score, clean))
        
    if not scored_lines:
        return "Oferta imperdível"
        
    scored_lines.sort(key=lambda x: x[0], reverse=True)
    winner = scored_lines[0][1]
    
    clean_winner = winner.replace("**", "").replace("__", "").replace("*", "").strip()
    clean_winner = re.sub(r"^[^\w\s]+", "", clean_winner).strip()
    
    return clean_winner[:80]

def _extract_teaser(text: str, product_name: str) -> str:
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

# Testes
test_cases = [
    """Para sua Sindrome de Pro Player

🔥Monitor Gamer AOC Destiny 24,5 Polegadas, 240Hz

💵R$ 899""",

    """CABE EM QUALQUER CANTIN DA CASA

📺 **Smart TV 32" Philco Roku TV**

🔥 ~~DE 999,99~~ | POR 699,90""",

    "🔥 SSD Samsung 1TB — por apenas R$ 379,90 no Pix!"
]

for i, t in enumerate(test_cases, 1):
    pn = _extract_product_name(t)
    tz = _extract_teaser(t, pn)
    print(f"CASE {i}:")
    print(f"PRODUCT NAME: {pn}")
    print(f"TEASER:       {tz}")
    print("-" * 40)
