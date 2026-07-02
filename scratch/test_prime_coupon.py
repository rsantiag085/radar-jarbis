import re

_PRIME_PATTERN = re.compile(
    r"\b(?:exclusiva?\s+)?membros\s+(?:Amazon\s+)?prime\b|\bexclusiva?\s+prime\b",
    re.IGNORECASE
)

# Regex sensível a maiúsculas para o código do cupom, mas insensível para o prefixo
_COUPON_PATTERN = re.compile(
    r"\b(?:CUPOM|Cupom|cupom|🎟️?|use\s+o\s+cupom|cumpom)[:\s-]*\**([A-Z0-9]{3,20}(?:\s*[\++-]\s*[A-Z0-9]{3,20})*)\**"
)

def _has_prime(text: str) -> bool:
    return bool(_PRIME_PATTERN.search(text))

def _extract_coupon(text: str) -> str:
    match = _COUPON_PATTERN.search(text)
    if match:
        coupon = match.group(1).strip()
        return coupon
    return ""

# Testes
test_cases = [
    "🔥 ~~DE 3.999~~ | **POR 3.229,05 no Pix**\n🎟 CUPOM: **POUPEAGORA + NOTE300**\n🔹 Oferta exclusiva membros Amazon Prime",
    "Use o cupom: NOTE100 para ganhar desconto!",
    "SSD Kingston por R$ 199\nCupom: SSD50\nExclusivo Prime",
    "Sem cupom e sem prime apenas preço normal",
    "🎟️ cupom: cupom inválido com letras minúsculas", # Não deve capturar
    "Cupom: MAIS100", # Deve capturar
]

for t in test_cases:
    print(f"INPUT:\n{t}")
    print(f"HAS PRIME: {_has_prime(t)}")
    print(f"COUPON:    {_extract_coupon(t)}")
    print("-" * 40)
