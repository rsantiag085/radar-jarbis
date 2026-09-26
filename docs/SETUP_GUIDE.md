# Guia Completo de Instalação e Configuração para Terceiros

Este guia detalha o passo a passo para configurar e executar os bots de afiliados da **Amazon** e do **Mercado Livre** do **RadarJarbis** na sua própria infraestrutura e com suas próprias contas.

---

## 📑 Índice
1. [Visão Geral e Requisitos](#-visão-geral-e-requisitos)
2. [Passo 1: Obter Credenciais do Telegram](#-passo-1-obter-credenciais-do-telegram)
3. [Passo 2: Configurar o Canal de Destino e IDs dos Canais de Origem](#-passo-2-configurar-o-canal-de-destino-e-ids-dos-canais-de-origem)
4. [Passo 3: Configurar Afiliados (Amazon e Mercado Livre)](#-passo-3-configurar-afiliados-amazon-e-mercado-livre)
5. [Passo 4: Configuração das Variáveis de Ambiente (.env)](#-passo-4-configuração-das-variáveis-de-ambiente-env)
6. [Passo 5: Primeira Execução e Autenticação MTProto](#-passo-5-primeira-execução-e-autenticação-mtproto)
7. [Passo 6: Execução em Produção via Systemd](#-passo-6-execução-em-produção-via-systemd)
8. [Passo 7: Monitoramento e Métricas (Opcional)](#-passo-7-monitoramento-e-métricas-opcional)
9. [Segurança e Boas Práticas](#-segurança-e-boas-práticas)

---

## 📌 Visão Geral e Requisitos

O RadarJarbis opera em **Arquitetura Dual-Client**:
1. **Telethon (MTProto)**: Lê mensagens dos canais de ofertas monitorados através de uma conta de usuário do Telegram.
2. **python-telegram-bot (Bot API)**: Publica as ofertas formatadas com sua tag de afiliado diretamente no seu canal de saída.

### Requisitos Mínimos:
- **Sistema Operacional**: Linux (Ubuntu 22.04/24.04, Debian 12 ou qualquer distribuição moderna) ou macOS.
- **Python**: Versão 3.11, 3.12 ou 3.13.
- **Hardware**: Qualquer VPS/VM simples (ex: 1 vCPU, 1 GB de RAM como `e2-micro` na GCP ou `t4g.nano` na AWS).

---

## 🔑 Passo 1: Obter Credenciais do Telegram

### 1.1. Obter API_ID e API_HASH (Telethon - Leitura)
1. Acesse [https://my.telegram.org](https://my.telegram.org) e faça login com o número de telefone da conta do Telegram que será usada para ler os canais.
2. Clique em **API development tools**.
3. Crie uma aplicação (se ainda não tiver uma). Escolha qualquer nome de aplicativo (ex: `RadarReader`).
4. Copie o **App api_id** (número inteiro) e o **App api_hash** (string alfanumérica).

> ⚠️ **Dica de Segurança**: É altamente recomendado utilizar um chip/número secundário dedicado apenas para a automação de leitura, evitando riscos na sua conta pessoal.

### 1.2. Criar o Bot Oficial do Telegram (Bot API - Publicação)
1. No Telegram, abra a conversa com o [@BotFather](https://t.me/BotFather).
2. Envie o comando `/newbot`.
3. Escolha um nome e um username para o seu bot (ex: `MeuRadarOfertasBot`).
4. O BotFather fornecerá um **HTTP API Token** (formato: `1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ`).

---

## 📢 Passo 2: Configurar o Canal de Destino e IDs dos Canais de Origem

### 2.1. Canal de Saída (`OUTPUT_CHANNEL_ID`)
1. Crie seu canal de ofertas no Telegram (pode ser público ou privado).
2. Adicione o bot criado no BotFather como **Administrador** do canal com permissão para **Postar Mensagens** (*Post Messages*).
3. Se o canal for público: use o username com `@` (ex: `@meucanaldeofertas`).
4. Se o canal for privado: use o ID numérico do canal (ex: `-1001234567890`).

### 2.2. Canais de Entrada (`SOURCE_CHANNEL_IDS`)
1. Certifique-se de que a conta de usuário (do Telethon) entrou em todos os canais de ofertas que você deseja monitorar.
2. Defina os canais no `.env` separados por vírgula. Podem ser usernames (ex: `@canal1, @canal2`) ou IDs numéricos (ex: `-1001111111111, -1002222222222`).

---

## 🛒 Passo 3: Configurar Afiliados (Amazon e Mercado Livre)

### 3.1. Amazon Associados
1. Acesse o [Portal de Associados da Amazon](https://associados.amazon.com.br).
2. Copie a sua **Tag de Associado** (ex: `seunome-20`).
3. O bot da Amazon (`src.bot`) substituirá automaticamente qualquer link da Amazon encontrado pelas ofertas com a sua tag.

### 3.2. Mercado Livre Afiliados
1. Acesse a central de afiliados do Mercado Livre.
2. Obtenha seu **User ID** (número de usuário da sua conta Mercado Livre) e a sua **Tag de Afiliado**.
3. *(Opcional / Recomendado)* Para encurtamento oficial `meli.la`:
   - Abra o navegador logado no Mercado Livre.
   - Abra as Ferramentas de Desenvolvedor (F12) ➡️ aba **Rede** (Network) ou **Armazenamento** (Storage/Cookies).
   - Copie a string completa do cookie de sessão e configure em `MELI_COOKIES` no `.env`.
   - Caso `MELI_COOKIES` não seja informado, o bot usará o redirecionamento com parâmetros de rastreamento.

---

## ⚙️ Passo 4: Configuração das Variáveis de Ambiente (.env)

1. Clone o repositório no seu servidor ou máquina local:
   ```bash
   git clone https://github.com/SEU_USUARIO/radar-jarbis.git
   cd radar-jarbis
   ```

2. Crie e ative o ambiente virtual Python:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. Crie o arquivo `.env` a partir do template:
   ```bash
   cp config/.env.example .env
   ```

4. Edite o `.env` com suas credenciais:
   ```ini
   # MTProto (Conta de leitura Telethon)
   TELEGRAM_API_ID=12345678
   TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890abcdef12

   # Bot API (Envio de mensagens)
   TELEGRAM_BOT_TOKEN=1234567890:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

   # Canais
   SOURCE_CHANNEL_IDS=-1001234567890, @canalorigem
   OUTPUT_CHANNEL_ID=@meucanaldeofertas

   # Afiliados Amazon
   AMAZON_AFFILIATE_TAG=seunome-20
   ENABLE_COUPONS=false
   PRIME_DAY_MODE=false

   # Afiliados Mercado Livre
   MELI_USER_ID=12345678
   MELI_AFFILIATE_TAG=suatagmeli
   MELI_COOKIES=

   # Portas de Métricas (caso use monitoramento)
   METRICS_PORT=8000
   METRICS_PORT_MELI=8001
   ```

---

## 🚀 Passo 5: Primeira Execução e Autenticação MTProto

Na primeira vez em que você executar o bot, o Telethon solicitará a autenticação da conta de usuário no terminal:

### Para o Bot da Amazon:
```bash
.venv/bin/python -m src.bot
```
- Digite o **número de telefone** (formato internacional, ex: `+5511999999999`).
- Digite o **código de confirmação** recebido no aplicativo do Telegram.
- Se houver senha de duas etapas (2FA), digite a senha.
- Será criado o arquivo `config/session.session`. Nas próximas execuções, o login será automático.

### Para o Bot do Mercado Livre:
```bash
SESSION_NAME=session_meli .venv/bin/python -m src.bot_meli
```
- Você pode reutilizar a mesma sessão ou autenticar uma sessão dedicada `session_meli.session`.

---

## 🛡️ Passo 6: Execução em Produção via Systemd

Para manter os bots rodando 24/7 em um servidor Linux de forma resiliente e com reinício automático:

### 6.1. Configurar o Serviço do Bot Amazon
1. Copie o arquivo de exemplo:
   ```bash
   cp radar-jarbis.service.example radar-jarbis.service
   ```
2. Edite `radar-jarbis.service` ajustando `User`, `Group`, `WorkingDirectory` e `ExecStart` com os caminhos reais da sua VM.
3. Instale o serviço:
   ```bash
   sudo cp radar-jarbis.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now radar-jarbis.service
   ```

### 6.2. Configurar o Serviço do Bot Mercado Livre
1. Copie o arquivo de exemplo:
   ```bash
   cp radar-jarbis-meli.service.example radar-jarbis-meli.service
   ```
2. Edite `radar-jarbis-meli.service` ajustando os caminhos da sua VM.
3. Instale o serviço:
   ```bash
   sudo cp radar-jarbis-meli.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now radar-jarbis-meli.service
   ```

### 6.3. Comandos Úteis do Systemd
```bash
# Ver status em tempo real
sudo systemctl status radar-jarbis.service
sudo systemctl status radar-jarbis-meli.service

# Ver logs do bot
sudo journalctl -u radar-jarbis.service -f -n 50
sudo journalctl -u radar-jarbis-meli.service -f -n 50

# Reiniciar serviço (ex: após mudar o .env)
sudo systemctl restart radar-jarbis.service
```

---

## 📊 Passo 7: Monitoramento e Métricas (Opcional)

Cada bot possui um servidor HTTP de métricas embutido:
- **Bot Amazon**: `http://localhost:8000/metrics` e `http://localhost:8000/metrics.json`
- **Bot Mercado Livre**: `http://localhost:8001/metrics` e `http://localhost:8001/metrics.json`

Consulte a documentação dedicada em [`docs/ZABBIX_MONITORING.md`](ZABBIX_MONITORING.md) para importar o template pronto no Zabbix ou Grafana.

---

## 🔒 Segurança e Boas Práticas

1. **Permissões de Arquivos no Servidor**:
   Restrinja a leitura de arquivos com credenciais:
   ```bash
   chmod 600 .env config/.env config/*.session config/*.db
   ```
2. **Nunca versionar segredos**:
   O `.gitignore` já vem pré-configurado para ignorar `.env`, arquivos `*.session`, `*.db` e arquivos `.service` locais. Nunca force o commit desses arquivos (`git add -f`).
3. **Firewall (UFW)**:
   Se as portas de métricas (8000/8001) estiverem ativas, não as exponha publicamente para a internet. Permita acesso apenas pelo IP do seu servidor de monitoramento:
   ```bash
   sudo ufw allow from <IP_DO_ZABBIX> to any port 8000 proto tcp
   sudo ufw allow from <IP_DO_ZABBIX> to any port 8001 proto tcp
   ```
4. **Rate Limit e Anti-Spam**:
   Mantenha `RATE_LIMIT_DELAY=3.5` ou superior para evitar que o Telegram limite temporariamente sua conta (FloodWait).
