# Relatório Comparativo de Anúncios — 20/11/2026

Comparativo e consolidação das ofertas coletadas entre 00:00:00 e 23:59:59 (Horário Oficial de Brasília — UTC-3) dos três canais master:
- **Guga Aprova** (`https://t.me/gugaaprova`)
- **La Casa de Promos** (`https://t.me/lacasadepromos`)
- **Grupo de Promoções / Reduza** (`https://t.me/grupo_promocoes`)

Planilha consolidada multi-aba disponível em: [`docs/anuncios_canais_2026_11_20.xlsx`](file:///home/robson/projetos/radar-jarbis/docs/anuncios_canais_2026_11_20.xlsx)

---

## 1. Estrutura das Abas da Planilha Excel

O arquivo [`docs/anuncios_canais_2026_11_20.xlsx`](file:///home/robson/projetos/radar-jarbis/docs/anuncios_canais_2026_11_20.xlsx) contém 4 abas estruturadas:

1. **`Resumo Geral`**: Tabela comparativa com volume total e aprovados por categoria nos 3 canais e status no nosso bot.
2. **`Guga Aprova`**: 269 anúncios cronológicos do grupo Guga.
3. **`La Casa de Promos`**: 123 anúncios cronológicos do grupo La Casa de Promos.
4. **`Grupo Promocoes`**: 97 anúncios cronológicos do grupo Reduza / Grupo Promoções.

Arquivos CSV individuais para integração contínua:
- [`docs/anuncios_gugaaprova_2026_11_20.csv`](file:///home/robson/projetos/radar-jarbis/docs/anuncios_gugaaprova_2026_11_20.csv)
- [`docs/anuncios_lacasadepromos_2026_11_20.csv`](file:///home/robson/projetos/radar-jarbis/docs/anuncios_lacasadepromos_2026_11_20.csv)
- [`docs/anuncios_grupo_promocoes_2026_11_20.csv`](file:///home/robson/projetos/radar-jarbis/docs/anuncios_grupo_promocoes_2026_11_20.csv)

---

## 2. Quadro Comparativo Consolidado por Categoria

| Categoria | Guga Total (Aprov.) | La Casa Total (Aprov.) | Grupo Promo Total (Aprov.) | Total Consolidado | Presente no Nosso Bot? |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Beleza (Skincare/Cabelo/Perfumes)** | 50 (50) | 30 (30) | 13 (13) | **93** | ✅ **SIM** |
| **Tecnologia (Smartphones/Consoles/Fones)** | 25 (25) | 22 (18) | 13 (12) | **60** | ✅ **SIM** *(Exclui iPhone 17)* |
| **Smart Home (Lâmpadas/Tomadas/Alexa/TV)** | 17 (16) | 8 (8) | 10 (10) | **35** | 🟡 *Em Tecnologia/Casa* |
| **Supermercado (Alimentos/Bebidas/Limpeza)** | 6 (5) | 8 (7) | 5 (5) | **19** | ✅ **SIM** |
| **Vestuário & Calçados (Moda)** | 14 (14) | 1 (1) | 3 (3) | **18** | ❌ Não prioritário |
| **Saúde & Suplementação (Creatina/Whey/Oral)**| 9 (9) | 6 (6) | 2 (2) | **17** | ✅ **SIM** |
| **Casa & Cozinha (Eletroportáteis/Airfryer)** | 5 (5) | 8 (8) | 4 (4) | **17** | ✅ **SIM** |
| **Bebê & Infantil (Fraldas/Lenços)** | 2 (2) | 3 (3) | 0 (0) | **5** | ✅ **SIM** |
| **Pessoal (Acessórios/Mochilas/Tênis)** | 5 (5) | 0 (0) | 1 (1) | **6** | ✅ **SIM** |
| **Livros & Leitura (Físicos/Kindle)** | 4 (4) | 1 (1) | 1 (1) | **6** | ❌ Apenas com cupom |
| **Fora de Nicho / Descartados / Outros** | 132 (0) | 36 (0) | 45 (0) | **213** | ❌ Descartados |
| **TOTAL GERAL** | **269 (135)** | **123 (82)** | **97 (51)** | **489 (268)** | **Aproveitamento: 54,8%** |

---

## 3. Principais Insights do Grupo Promoções (Reduza)

1. **Volume e Horário de Atuação**:
   - Foram **97 anúncios** no dia 20/11, iniciando às `08:25 BRT` e encerrando às `20:19 BRT` (janela ativa de ~12 horas).
2. **Plataformas / Encurtadores**:
   - **Amazon**: 34 ofertas diretas.
   - **Mercado Livre**: 26 ofertas diretas.
   - **Magalu**: 2 ofertas diretas.
   - **Encurtadores Próprios (`reduz.ai` / `reduz.me`)**: 35 ofertas (que redirecionam principalmente para Mercado Livre e Amazon, e que o nosso bot expande e resolve em tempo real).
3. **Presença de Cupons**:
   - **34 anúncios** (35,0%) mencionavam cupons de desconto, especialmente cupons do Mercado Livre e Amazon.
4. **Taxa de Aproveitamento**:
   - **51 ofertas** (52,6%) foram aprovadas pelos filtros do nosso robô.
