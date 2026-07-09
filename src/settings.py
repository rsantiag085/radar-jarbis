import os
from pathlib import Path
from dotenv import load_dotenv

# Localiza e carrega o arquivo .env (prioriza o da raiz se existir, depois na pasta config)
_root_env = Path(__file__).parent.parent / ".env"
_config_env = Path(__file__).parent.parent / "config" / ".env"

if _root_env.exists():
    _env_path = _root_env
elif _config_env.exists():
    _env_path = _config_env
else:
    _env_path = _root_env  # fallback padrão

load_dotenv(dotenv_path=_env_path)

# Caminho do arquivo de sessão Telethon (gerado na 1ª autenticação)
SESSION_PATH: Path = Path(__file__).parent.parent / "config" / "session"

try:
    # Parâmetros obrigatórios de infraestrutura e segurança
    TELEGRAM_API_ID: int = int(os.environ["TELEGRAM_API_ID"])
    TELEGRAM_API_HASH: str = os.environ["TELEGRAM_API_HASH"]
    TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]

    # Canais de fluxo (suporta IDs numéricos ou usernames como @canal)
    SOURCE_CHANNEL_IDS: list[int | str] = []
    for x in os.environ["SOURCE_CHANNEL_IDS"].split(","):
        clean_x = x.strip()
        if not clean_x:
            continue
        try:
            SOURCE_CHANNEL_IDS.append(int(clean_x))
        except ValueError:
            SOURCE_CHANNEL_IDS.append(clean_x)

    OUTPUT_CHANNEL_ID: str = os.environ["OUTPUT_CHANNEL_ID"]
    
    # Tag de afiliado Amazon (opcional, com fallback)
    AMAZON_AFFILIATE_TAG: str = os.getenv("AMAZON_AFFILIATE_TAG", "noradardojarb-20")

    # Delays de controle de spam
    RATE_LIMIT_DELAY: float = float(os.getenv("RATE_LIMIT_DELAY", "3.5"))

    # Janela de deduplicação de anúncios idênticos (em horas)
    DEDUPLICATION_WINDOW_HOURS: int = int(os.getenv("DEDUPLICATION_WINDOW_HOURS", "24"))

    # Porta de métricas do Prometheus
    METRICS_PORT: int = int(os.getenv("METRICS_PORT", "8000"))

    # Habilita ou desabilita publicação de cupons gerais da Amazon
    ENABLE_COUPONS: bool = os.getenv("ENABLE_COUPONS", "false").lower() == "true"

    # Habilita ou desabilita o modo Prime Day para formatação de posts
    PRIME_DAY_MODE: bool = os.getenv("PRIME_DAY_MODE", "false").lower() == "true"

except KeyError as e:
    raise RuntimeError(
        f"CRITICAL ERROR: A variável de ambiente obrigatória {e} não foi localizada no arquivo config/.env. "
        f"A inicialização do RadarJarbis foi abortada por segurança."
    ) from e