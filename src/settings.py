import os
from pathlib import Path
from dotenv import load_dotenv

# Localiza e carrega o arquivo .env
_env_path = Path(__file__).parent.parent / "config" / ".env"
load_dotenv(dotenv_path=_env_path)

# Caminho do arquivo de sessão Telethon (gerado na 1ª autenticação)
SESSION_PATH: Path = Path(__file__).parent.parent / "config" / "session"

try:
    # Parâmetros obrigatórios de infraestrutura e segurança
    TELEGRAM_API_ID: int = int(os.environ["TELEGRAM_API_ID"])
    TELEGRAM_API_HASH: str = os.environ["TELEGRAM_API_HASH"]
    TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]

    # Canais de fluxo
    SOURCE_CHANNEL_IDS: list[int] = [int(x.strip()) for x in os.environ["SOURCE_CHANNEL_IDS"].split(",")]
    OUTPUT_CHANNEL_ID: str = os.environ["OUTPUT_CHANNEL_ID"]

    # Delays de controle de spam
    RATE_LIMIT_DELAY: float = float(os.getenv("RATE_LIMIT_DELAY", "3.5"))

except KeyError as e:
    raise RuntimeError(
        f"CRITICAL ERROR: A variável de ambiente obrigatória {e} não foi localizada no arquivo config/.env. "
        f"A inicialização do RadarJarbis foi abortada por segurança."
    ) from e