# Changelog - RadarJarbis

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

## 📌 Onde Paramos? (Última atualização: 2026-07-02)

### ✅ Concluído nesta sessão:
- **Inclusão de Ventilador de Mesa**: Adicionado suporte para ofertas de "ventilador de mesa" (independente de marca) no filtro de relevância e na classificação de categorias (vinculada à categoria `smart_home` de itens de casa). Atualizado o arquivo de contexto de negócio ([CONTEXT.md](file:///home/robsonsanoliveira/radar-jarbis/config/context/CONTEXT.md)) e a suíte de testes unitários para validar a detecção do produto e sua correta categorização e aprovação.
- **Limpeza de URLs Curtas Expandidas**: Corrigido o vazamento de parâmetros de rastreamento da Amazon (como `crid`, `dib`, `qid`, etc.) em links que passavam pelo resolvedor de encurtadores (`expandir_e_converter_link`), garantindo que agora todas as URLs resolvidas sejam limpas da mesma forma que as URLs longas diretas.
- **Logs Estruturados (JSON)**: Implementado o formatador `JsonFormatter` que converte todas as saídas de logs padrão do bot e das bibliotecas (`telethon`, `httpx`, `telegram`) para JSON estruturado, facilitando a coleta automática por indexadores (como Loki ou Datadog).
- **Métricas Prometheus (Sinais de Ouro)**: Adicionado o exportador Prometheus na porta `8000` (`METRICS_PORT`), instrumentando métricas de Latência (tempo de conversão/pipeline), Tráfego (mensagens recebidas/publicadas/filtradas), Erros (falhas de conexão, rate limits da API, mídias falhas) e Saturação (reconexões do loop e paralelismo em memória).
- **Deploy**: Reiniciado o serviço `radar-jarbis.service` no systemd com sucesso, com validação de funcionamento das métricas em tempo real e formato JSON nos logs.

### 🚀 Próximos Passos recomendados:
- **Painel de Visualização**: Configurar o Prometheus/Grafana para consumir as métricas na porta `8000` exposta pelo bot.
- **Coletores de Log**: Integrar as ferramentas de log (como Promtail + Loki) para arquivar e ler os logs em JSON estruturado de `/var/log/syslog`.
- **Monitoramento contínuo**: Acompanhar o comportamento do bot em produção com novas ofertas recebidas em tempo real para validar eventuais falhas nos resolvedores de encurtadores adicionais.

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