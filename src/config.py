"""Carregamento centralizado de ambiente e configurações externas."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).parent.parent


def load_project_env() -> Path:
    """Carrega o .env da raiz ou, como fallback, config/.env."""
    root_env = PROJECT_ROOT / ".env"
    config_env = PROJECT_ROOT / "config" / ".env"
    if root_env.exists():
        env_path = root_env
    elif config_env.exists():
        env_path = config_env
    else:
        env_path = root_env
    load_dotenv(dotenv_path=env_path)
    return env_path


def _get_bool(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name, "").strip().lower()
    if not raw_value:
        return default
    if raw_value in {"true", "1", "yes", "on"}:
        return True
    if raw_value in {"false", "0", "no", "off"}:
        return False
    raise RuntimeError(
        f"Configuração inválida: {name} deve ser true ou false."
    )


@dataclass(frozen=True)
class SupabaseConfig:
    """Configuração do Supabase sem representação textual das credenciais."""

    enabled: bool = False
    required: bool = False
    url: str | None = field(default=None, repr=False)
    service_role_key: str | None = field(default=None, repr=False)

    @classmethod
    def from_env(cls) -> "SupabaseConfig":
        enabled = _get_bool("SUPABASE_ENABLED", default=False)
        required = _get_bool("SUPABASE_REQUIRED", default=False)
        url = os.getenv("SUPABASE_URL", "").strip() or None
        service_role_key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or None
        )

        config = cls(
            enabled=enabled,
            required=required,
            url=url,
            service_role_key=service_role_key,
        )
        config.validate()
        return config

    def validate(self) -> None:
        """Valida credenciais somente quando a integração está habilitada."""
        if not self.enabled:
            return

        missing = []
        if not self.url:
            missing.append("SUPABASE_URL")
        if not self.service_role_key:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        if missing:
            raise RuntimeError(
                "Configuração do Supabase incompleta. Variáveis ausentes: "
                + ", ".join(missing)
            )

        parsed_url = urlparse(self.url)
        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
            or parsed_url.username
            or parsed_url.password
        ):
            raise RuntimeError(
                "Configuração inválida: SUPABASE_URL deve ser uma URL HTTP(S) "
                "sem credenciais embutidas."
            )


def load_supabase_config() -> SupabaseConfig:
    """Cria a configuração do Supabase a partir do ambiente atual."""
    return SupabaseConfig.from_env()
