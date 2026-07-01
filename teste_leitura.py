import os
import re
from pathlib import Path
from telethon import TelegramClient, events
from dotenv import load_dotenv

# Importa a sua função de conversão do pacote src, renomeando para manter compatibilidade com sua chamada
from src.converters import convert_urls as converter_link_amazon 

# Carrega as credenciais do seu arquivo .env local
_env_path = Path(__file__).parent / "config" / ".env"
load_dotenv(dotenv_path=_env_path)

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")

if not API_ID or not API_HASH:
    raise RuntimeError(
        "CRITICAL ERROR: As variáveis de ambiente TELEGRAM_API_ID e/ou TELEGRAM_API_HASH "
        "não foram localizadas no arquivo config/.env ou no sistema."
    )

try:
    API_ID = int(API_ID)
except (TypeError, ValueError):
    raise RuntimeError(
        f"CRITICAL ERROR: A variável TELEGRAM_API_ID ({API_ID}) não é um número inteiro válido."
    )

CANAL_ORIGEM = 'gugaaprova' 

# Inicializa o cliente do Telegram reutilizando a sessão configurada
_session_path = Path(__file__).parent / "config" / "session"
client = TelegramClient(str(_session_path), API_ID, API_HASH)

print("⚡ Inicializando o Radar com Conversor de Links...")

@client.on(events.NewMessage(chats=CANAL_ORIGEM))
async def msg_handler(event):
    texto_original = event.text
    print("\n📥 [NOVA MENSAGEM DETECTADA]")
    
    # Expressão regular simples para identificar se há links na mensagem
    links = re.findall(r'(https?://[^\s]+)', texto_original)
    
    if links:
        print(f"🔗 Links originais encontrados: {links}")
        
        # Passa o texto completo ou os links para o seu módulo tratar
        # Aqui assumimos que sua função recebe o texto e devolve o texto convertido
        texto_convertido = converter_link_amazon(texto_original)
        
        print("\n🚀 [RESULTADO DA CONVERSÃO DO JARBIS]:")
        print(texto_convertido)
        print("-" * 50)
    else:
        print("ℹ️ Mensagem sem links. Ignorando...")

async def main():
    print(f"📡 Monitor rodando localmente no canal: @{CANAL_ORIGEM}...")

with client:
    client.loop.run_until_complete(main())
    client.run_until_disconnected()