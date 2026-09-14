import os
from pathlib import Path

from .config import load_project_env, load_supabase_config

# Mantém a precedência existente: .env da raiz e config/.env como fallback.
load_project_env()

# Configuração centralizada da integração, desabilitada por padrão.
SUPABASE = load_supabase_config()
SUPABASE_URL: str | None = SUPABASE.url
SUPABASE_SERVICE_ROLE_KEY: str | None = SUPABASE.service_role_key
SUPABASE_ENABLED: bool = SUPABASE.enabled
SUPABASE_REQUIRED: bool = SUPABASE.required

# Caminho do arquivo de sessão Telethon (permite customizar por variável de ambiente para instâncias paralelas)
_session_name = os.getenv("SESSION_NAME", "session")
SESSION_PATH: Path = Path(os.getenv("SESSION_PATH", str(Path(__file__).parent.parent / "config" / _session_name)))

# Configurações do Mercado Livre
MELI_COOKIES: str = os.getenv("MELI_COOKIES", "")
MELI_USER_ID: str = os.getenv("MELI_USER_ID", "111993671")
MELI_AFFILIATE_TAG: str = os.getenv("MELI_AFFILIATE_TAG", "noradardojarbis")

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

    # Portas de métricas do Prometheus
    METRICS_PORT: int = int(os.getenv("METRICS_PORT", "8000"))
    METRICS_PORT_MELI: int = int(os.getenv("METRICS_PORT_MELI", os.getenv("MELI_METRICS_PORT", "8001")))

    # Habilita ou desabilita publicação de cupons gerais da Amazon
    ENABLE_COUPONS: bool = os.getenv("ENABLE_COUPONS", "false").lower() == "true"

    # Habilita ou desabilita o modo Prime Day para formatação de posts
    PRIME_DAY_MODE: bool = os.getenv("PRIME_DAY_MODE", "false").lower() == "true"

except KeyError as e:
    raise RuntimeError(
        f"CRITICAL ERROR: A variável de ambiente obrigatória {e} não foi localizada no arquivo config/.env. "
        f"A inicialização do RadarJarbis foi abortada por segurança."
    ) from e
