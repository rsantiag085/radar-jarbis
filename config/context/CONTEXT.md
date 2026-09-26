# Contexto de Negócio — RadarJarbis

## Visão Geral do Projeto
O **RadarJarbis** é uma operação automatizada de canais de ofertas de afiliados (Amazon e Mercado Livre) no Telegram, focada em captação de ofertas com alta conversão, filtragem inteligente de nichos e monetização através de links de afiliados.

## Parâmetros de Operação
- **Canal Oficial de Saída:** Definido via `OUTPUT_CHANNEL_ID` (Telegram)
- **ID de Associado Amazon:** Definido via `AMAZON_AFFILIATE_TAG`
- **ID de Afiliado Mercado Livre:** Definido via `MELI_AFFILIATE_TAG` / `MELI_USER_ID`

## Nichos de Atuação (Foco de Garimpo e Filtragem)
Para manter a relevância comercial e evitar ruído no canal de saída, o sistema filtra as seguintes categorias:
1. **Itens de Tecnologia:** Notebooks, monitores, teclados, mouses, baterias portáteis, cadeiras gamer, memórias RAM (desktop e notebook - DDR4, DDR5, SODIMM) e periféricos em geral.
2. **Itens Pessoais:** Tênis, perfumes, relógios e body sprays.
3. **Itens para Casa (Smart Home e Utilidades):** Smart TVs, robôs aspiradores, fechaduras eletrônicas, dispositivos inteligentes, ventilador de mesa, e itens de limpeza/utilidades domésticas (mops, baldes, organizadores, etc.).
4. **Casa e Cozinha:** Fogões, cooktops, liquidificadores, panelas, frigideiras e jogos de panelas. *(NOTA: Geladeiras, micro-ondas e bebidas alcoólicas são ativamente excluídos)*.
5. **Beleza e Saúde:** Produtos de cuidados pessoais, cosméticos e suplementação voltados ao bem-estar.
6. **Supermercado (Alimentos e Bebidas):** Itens de supermercado, como batata frita, salgadinhos, chocolates, biscoitos, petiscos, refrigerantes/bebidas, além de condimentos e molhos. *(Cervejas e bebidas alcoólicas são excluídas)*.
7. **Vestuário (Roupas e Acessórios):** Camisetas, camisas, calças, bermudas, cuecas, meias, casacos, jaquetas, vestidos, blusas e roupas em geral.
8. **Livros e Leitura:** Livros físicos, boxes, e-books e Kindle.
9. **Bebê e Infantil:** Fraldas, lenços umedecidos, mamadeiras, chupetas, carrinhos de bebê e itens de puericultura.
10. **Cupons Gerais Amazon / Mercado Livre:** Cupons de desconto progressivo aplicáveis a produtos dos nichos selecionados.