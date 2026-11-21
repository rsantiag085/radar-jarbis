# Relatório Comparativo de Anúncios — 20/11/2026

Comparativo e consolidação das ofertas coletadas entre 00:00:00 e 23:59:59 (Horário Oficial de Brasília — UTC-3) dos canais master:
- **Guga Aprova** (`https://t.me/gugaaprova`)
- **La Casa de Promos** (`https://t.me/lacasadepromos`)

Planilha consolidada multi-aba disponível em: [`docs/anuncios_canais_2026_11_20.xlsx`](file:///home/robson/projetos/radar-jarbis/docs/anuncios_canais_2026_11_20.xlsx)

---

## 1. Estrutura das Abas da Planilha Excel

O arquivo [`docs/anuncios_canais_2026_11_20.xlsx`](file:///home/robson/projetos/radar-jarbis/docs/anuncios_canais_2026_11_20.xlsx) contém 3 abas estruturadas:

1. **`Resumo Geral`**: Tabela comparativa com o volume total e aprovados por categoria em cada grupo, além do status de ativação no nosso bot.
2. **`Guga Aprova`**: 269 anúncios cronológicos do grupo Guga com colunas de categoria, subtipo, aprovação de filtro, loja, ASIN/MLB, produto, preço, cupom e links.
3. **`La Casa de Promos`**: 123 anúncios cronológicos do grupo La Casa de Promos com as mesmas colunas padronizadas.

Arquivos CSV individuais para integração contínua:
- [`docs/anuncios_gugaaprova_2026_11_20.csv`](file:///home/robson/projetos/radar-jarbis/docs/anuncios_gugaaprova_2026_11_20.csv)
- [`docs/anuncios_lacasadepromos_2026_11_20.csv`](file:///home/robson/projetos/radar-jarbis/docs/anuncios_lacasadepromos_2026_11_20.csv)

---

## 2. Quadro Comparativo Consolidado por Categoria

| Categoria | Guga Aprova (Total) | Guga (Aprovados) | La Casa de Promos (Total) | La Casa (Aprovados) | Total Consolidado | Presente no Nosso Bot? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Beleza (Skincare/Cabelo/Perfumes)** | 50 | 50 | 30 | 30 | **80** | ✅ **SIM** |
| **Tecnologia (Smartphones/Consoles/Fones)** | 25 | 25 | 22 | 18 | **47** | ✅ **SIM** *(Exclui iPhone 17)* |
| **Smart Home (Lâmpadas/Tomadas/Alexa)** | 17 | 16 | 8 | 8 | **25** | 🟡 *Em Tecnologia/Casa* |
| **Saúde & Suplementação (Creatina/Whey/Oral)**| 9 | 9 | 6 | 6 | **15** | ✅ **SIM** |
| **Vestuário & Calçados (Moda)** | 14 | 14 | 1 | 1 | **15** | ❌ Não prioritário |
| **Supermercado (Alimentos/Bebidas/Limpeza)** | 6 | 5 | 8 | 7 | **14** | ✅ **SIM** |
| **Casa & Cozinha (Eletroportáteis/Airfryer)** | 5 | 5 | 8 | 8 | **13** | ✅ **SIM** |
| **Bebê & Infantil (Fraldas/Lenços)** | 2 | 2 | 3 | 3 | **5** | ✅ **SIM** |
| **Livros & Leitura (Físicos/Kindle)** | 4 | 4 | 1 | 1 | **5** | ❌ Apenas com cupom |
| **Pessoal (Acessórios/Mochilas/Tênis)** | 5 | 5 | 0 | 0 | **5** | ✅ **SIM** |
| **Fora de Nicho / Descartados / Outros** | 132 | 0 | 36 | 0 | **168** | ❌ Descartados |
| **TOTAL GERAL** | **269** | **135 (50,2%)** | **123** | **82 (66,7%)** | **392** | **217 Aprovados (55,4%)** |

---

## 3. Principais Insights e Comportamento dos Grupos

1. **La Casa de Promos é Quase 100% Amazon**:
   - Das 123 postagens, **121 foram da Amazon** (98,4%) e **2 da Shopee** (1,6%).
   - Alta taxa de aproveitamento pelo nosso bot: **66,7% dos anúncios** se enquadram diretamente nas nossas categorias de conversão.
2. **Guga Aprova tem Maior Mix de Lojas**:
   - Conta com grande volume de Shopee, Mercado Livre, Magalu e Natura, além da Amazon.
3. **Bloqueio de iPhone 17 em Ação**:
   - No canal *La Casa de Promos*, ofertas de `Apple iPhone 17` e `Apple iPhone 17e` foram publicadas e marcadas como `aprovado_filtro = NAO`, confirmando o isolamento e proteção contra modelos não desejados.
4. **Dominância de Beleza e Tecnologia**:
   - Juntas, as categorias de **Beleza** (80 anúncios) e **Tecnologia** (47 anúncios) somam **127 anúncios** (quase 60% de todas as ofertas válidas dos dois grupos).
