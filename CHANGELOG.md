# Changelog - RadarJarbis

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

## 📌 Onde Paramos? (Última atualização: 2026-07-09)

### ✅ Concluído nesta sessão:
- **Expansão de Nichos de Garimpo**:
  - Adicionada a categoria **Supermercado (Alimentos e Bebidas)** (ex: batatas fritas Pringles, chocolates, snacks).
  - Adicionada a categoria **Vestuário (Roupas e Acessórios)** (ex: kit de cuecas boxer Reebok), removendo as antigas exclusões de roupas.
  - Expandida a categoria **Casa (Smart Home e Utilidades)** para incluir utilidades domésticas e ferramentas de limpeza manual (ex: mops, baldes, esfregões).
- **Adequação de Filtros e Motor de Relevância**: Atualizado `filters.py` com novas keywords estruturadas e remoção de restrições obsoletas de vestuário na lista `_EXCLUDED_KEYWORDS`.
- **Suíte de Testes e Validação**: Adicionados testes em `test_converters_filters.py` para as novas categorias e ajustados os casos de testes legados de bloqueio de vestuário para garantir integridade e 100% de cobertura.
- **Deploy e Estabilidade**: Serviço systemd `radar-jarbis` reiniciado e validado.

### 🚀 Próximos Passos recomendados:
- **Acompanhar o Tráfego do Canal**: Monitorar se as novas categorias (Supermercado, Vestuário e Utilidades Domésticas) estão fluindo de forma limpa e com as formatações corretas de preços.
- **Deduplicação de ASIN**: Validar se a regra de ASIN + preço atua corretamente nas novas categorias.

---

## [0.3.1] - 2026-07-09

### Adicionado
- **Nicho de Supermercado**: Mapeamento de keywords (`pringles`, `batata frita`, `salgadinho`, `chocolate`, `biscoito`, etc.) na categoria `supermercado`.
- **Nicho de Vestuário**: Mapeamento de keywords (`cueca`, `meia`, `roupa`, `camiseta`, `calça`, `bermuda`, etc.) na categoria `vestuario`.
- **Nicho de Casa/Utilidades**: Expansão do mapeamento de keywords na categoria `smart_home` (`mop`, `esfregão`, `balde`, `vassoura`, `organizador`, `varal`, etc.).
- **Novos Testes Unitários**: Testes cobrindo a relevância e classificação destas novas categorias em `test_converters_filters.py`.

### Modificado
- **Políticas de Exclusão**: Removidas keywords de vestuário/roupas do filtro `_EXCLUDED_KEYWORDS`.
- **Documentação do Projeto**: Ajustado o [CONTEXT.md](file:///home/robsonsanoliveira/radar-jarbis/config/context/CONTEXT.md) para documentar as novas categorias oficiais.

---

## [0.3.0] - 2026-07-05

### Adicionado
- **Detecção de Cupons Gerais**: Novo fluxo inteligente em `filters.py` e `converters.py` que detecta anúncios gerais de cupons de desconto Amazon e os formata em um template de copywriting limpo e minimalista.
- **Filtro Inteligente de Nicho para Cupons**: Nova validação que restringe os cupons gerais para apenas categorias permitidas, bloqueando ativamente cupons de livros, papelaria, produtos pet, pneus/ferramentas e itens infantis/brinquedos.

### Corrigido
- **Falso Positivo de Pontuação**: Ajustada a verificação das palavras de template promocional (`de`/`por`) nas funções de score de linha para que apenas correspondam a padrões numéricos de preço (ex: "de 299", "por 155"), evitando a penalidade indevida de preposições presentes nos nomes dos produtos.

---

## [0.2.2] - 2026-07-03

### Adicionado
- **Deduplicação Inteligente por ASIN e Preço**: Resolvido o problema de repetição de anúncios idênticos provenientes de diferentes canais master ou com links de afiliados diferentes. O bot extrai o ASIN do produto e, caso ele já tenha sido postado na janela de tempo ativa (padrão 24h), ele só será enviado se o preço do produto for diferente do preço registrado na última postagem.
- **Normalização de Comparação de Preços**: Desenvolvido um método robusto que limpa símbolos de moeda (`R$`), espaços em branco e pontos de milhar (`.`), garantindo comparações corretas de preços mesmo com formatações diferentes.
- **Suíte de Testes Ampliada**: Criados novos testes unitários e de integração validando a extração de ASIN e o fluxo de bloqueio/liberação no pipeline por variação de preço, totalizando **96 testes** funcionais de regressão.

---

## [0.2.1] - 2026-07-02

### Adicionado
- **Logs Estruturados (JSON)**: Implementado o formatador `JsonFormatter` que converte todas as saídas de logs padrão do bot e das bibliotecas para JSON estruturado, facilitando a coleta automática por indexadores (como Loki ou Datadog).
- **Métricas Prometheus (Sinais de Ouro)**: Adicionado o exportador Prometheus na porta `8000` (`METRICS_PORT`), instrumentando métricas de Latência (tempo de conversão/pipeline), Tráfego (mensagens recebidas/publicadas/filtradas), Erros e Saturação.

### Modificado
- **Inclusão de Ventilador de Mesa**: Adicionado suporte para ofertas de "ventilador de mesa" (independente de marca) no filtro de relevância e na classificação de categorias (vinculada à categoria `smart_home` de itens de casa).
- **Limpeza de URLs Curtas Expandidas**: Corrigido o vazamento de parâmetros de rastreamento da Amazon (como `crid`, `dib`, `qid`, etc.) em links que passavam pelo resolvedor de encurtadores (`expandir_e_converter_link`), garantindo que agora todas as URLs resolvidas sejam limpas da mesma forma que as URLs longas diretas.
- **Deploy**: Reiniciado o serviço `radar-jarbis.service` no systemd com sucesso.


---

## [0.2.0] - 2026-07-01

### Adicionado
- Integração de serviço persistente do Linux via **systemd** (`radar-jarbis.service`), permitindo execução em segundo plano com auto-restart em caso de falha.
- Suporte a leitura de `.env` posicionado na raiz do projeto, facilitando a edição rápida.
- Carga histórica de inicialização: o bot agora varre os últimos 10 posts de cada grupo master monitorado para processar ofertas recebidas enquanto esteve offline.
- Controle preventivo de concorrência em memória (`_processing_msg_ids`) para evitar que a carga histórica e os eventos de tempo real tentem postar o mesmo item ao mesmo tempo.
- Variável de ambiente `AMAZON_AFFILIATE_TAG` no `.env` para carregar dinamicamente o ID de afiliado da Amazon sem hardcoding, conforme as diretrizes de segurança.
- Suporte a postagens com imagem: o bot agora detecta, faz o download em memória (RAM, sem uso de disco) da foto original da oferta nos canais master e a despacha como Foto + Legenda no canal de destino.
- Extração de cupons e verificação de exclusividade Prime: o bot agora detecta automaticamente e anexa códigos de cupom de desconto (ex: `POUPEAGORA`) e insere o selo `👑 Exclusivo Membros Prime` no final do post formatado.
- Cópia do texto de chamada (teaser): desenvolvida a extração automática da primeira linha de engajamento da oferta de origem (ex: `Para sua Sindrome de Pro Player`), formatando-a em itálico e com o prefixo `✨` logo acima do nome do produto no canal de saída. Possui proteção contra duplicações para ofertas que iniciam diretamente no nome do produto.

### Modificado
- Suporte a usernames no canal de origem: a variável `SOURCE_CHANNEL_IDS` agora converte IDs numéricos e mantém usernames (como `@canal`) de forma transparente sem quebrar por erro de conversão de tipo.
- Limpeza e filtragem de ofertas sem Amazon link: ofertas contendo apenas links de terceiros (Shopee, Magazine Luiza, Mercado Livre) ou sem link agora são devidamente ignoradas/descartadas para evitar postagens sem link e proteger contra propagação de links com tags de outros afiliados.
- Motor de extração de preços robusto: desenvolvida uma esteira de prioridades de expressões regulares em `converters.py` que prioriza valores promocionais (`por`), aceita preços sem o prefixo explícito `R$` (corrigindo bugs de raspagem de dados) e formata automaticamente o valor final com a moeda brasileira.
- Remoção do rodapé de transparência: O texto `Links qualificados de associado.` foi inteiramente removido do final de todas as mensagens por decisão do operador para ganho estético e de copywriting.
- Integração de parcelamento: o bot agora raspa informações de parcelamento (ex: `até 10x` ou `em até 12x sem juros`) da mensagem original e as formata ao lado do preço final.
- Introdução de ofertas padronizada: removidos os gatilhos mentais rotativos antigos (como `BUG DE PREÇO`, `MENOR PREÇO HISTÓRICO`) e fixada a introdução `🔥 OFERTA PRIME DAY 🔥` no início de todas as postagens.
- Extrator de nomes pontuado: substituído o regex simplista por um motor inteligente de pontuação de linhas em `converters.py` que analisa a presença de emojis de produtos, marcas conhecidas, palavras-chave tecnológicas (evitando capturar frases de chamada como "Para sua Síndrome de Pro Player" ou "CABE EM QUALQUER CANTIN") e limpa automaticamente decorações e marcas de negrito.
- Limpeza de parâmetros de rastreamento (URLs curtas): modificada a função `_inject_affiliate_tag` para expurgar parâmetros de rastreamento inúteis da Amazon (como `crid`, `dib`, `dib_tag`, `qid`, `sprefix`, `sr`, `ufe`, `linkCode`, `linkId`), deixando as URLs finais significativamente mais curtas, limpas e estéticas no canal.

## [0.1.0] - 2026-06-27

### Adicionado
- Estrutura inicial do projeto gerada com foco em segurança.
- Criação dos documentos de contexto (`CONTEXT.md`, `GEMINI.md`, `GUARDRAILS.md`).
- Registro do novo bot exclusivo para a operação de renda extra de afiliados.