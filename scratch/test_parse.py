import sys
sys.path.insert(0, '/home/robsonsanoliveira/radar-jarbis')

import src.converters as converters

text = """😉 VAI DEIXAR SEU CABELO PERFEITO!

👱🏻‍♀️ Eudora Siàge Cica Therapy Leave-in 100ml

🔥 por R$ 30 na Amazon

🛒 https://amzn.to/4f1NziF

🚛 Frete grátis | Amazon Prime

🔐 Site Confiável: Amazon

📱 Link para entrar no grupo
🔐 reduza.com.br/whatsapp"""

product_name = converters._extract_product_name(text)
teaser = converters._extract_teaser(text, product_name)
price = converters._extract_price(text)
installments = converters._extract_installments(text)
coupon = converters._extract_coupon(text)
has_prime = converters._check_prime(text)

print(f"Product Name: {product_name!r}")
print(f"Teaser: {teaser!r}")
print(f"Price: {price!r}")
print(f"Installments: {installments!r}")
print(f"Coupon: {coupon!r}")
print(f"Has Prime: {has_prime!r}")
