# Segurança, Guardrails e Proteção de Dados Sensíveis

## 1. Proteção de Dados e Informações Sensíveis (Hard Rule)
- **Zero Hardcoding:** É terminantemente proibido escrever Tokens do Telegram, chaves de API da Amazon, IDs de afiliados (ex: `AMAZON_AFFILIATE_TAG`) ou credenciais de instâncias do Google Cloud diretamente no código-fonte. Tudo deve ser consumido via variáveis de ambiente (`.env`).
- **Anonimato do Operador:** O sistema é uma entidade puramente automatizada ("Faceless"). Nenhuma resposta, metadado, log ou descrição de canal deve fazer alusão à identidade, nome, profissão ou localização do seu criador.

## 2. Prevenção de Bloqueios (Políticas da Amazon)
- **Política Antifraude:** O robô nunca deve incentivar compras do operador, de familiares diretos ou dispositivos na mesma rede local Wi-Fi utilizando o ID de afiliado cadastrado.
- **Transparência:** A exibição da indicação de associado ("Links qualificados de associado") no rodapé dos posts foi removida sob demanda explícita do operador para otimização de copywriting.

## 3. Estabilidade do Sistema
- **Limitação de Rate Limit:** Implementar um espaçamento (sleep/delay) de segurança entre as requisições de leitura e os disparos no canal de saída para evitar banimentos por SPAM na API do Telegram.
- **Barreira Antiduplicação (ASIN + Preço):** O robô não deve publicar anúncios idênticos do mesmo produto. A repetição do mesmo produto (ASIN) na janela ativa de deduplicação (padrão 24 horas) é bloqueada, exceto se houver alteração de preço (quedas ou reajustes).
- **Controle de Nichos e Cupons:** Cupons gerais que mencionem produtos de categorias excluídas (ex: vestuário, eletrodomésticos grandes) ou fora de nicho (ex: livros, pet shop, automotivo, brinquedos, fraldas) devem ser ativamente bloqueados no filtro de relevância para manter a integridade comercial do canal.