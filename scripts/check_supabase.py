"""Health check somente leitura para as tabelas do Supabase."""

from __future__ import annotations

import sys

import httpx

from src.config import load_project_env, load_supabase_config


TABLES = (
    "marketplaces",
    "sources",
    "products",
    "offers",
    "captured_messages",
    "content_items",
    "publications",
)


def main() -> int:
    load_project_env()
    config = load_supabase_config()

    if not config.enabled:
        print("Supabase health check ignorado: SUPABASE_ENABLED está false.")
        return 2

    headers = {
        "apikey": config.service_role_key,
        "Authorization": f"Bearer {config.service_role_key}",
        "Accept": "application/json",
    }

    try:
        with httpx.Client(headers=headers, timeout=10.0) as client:
            for table in TABLES:
                response = client.get(
                    f"{config.url.rstrip('/')}/rest/v1/{table}",
                    params={"select": "id", "limit": "1"},
                )
                if response.status_code not in {200, 206}:
                    print(
                        f"Supabase health check falhou na tabela {table} "
                        f"(HTTP {response.status_code})."
                    )
                    return 1
                print(f"OK: {table}")
    except httpx.HTTPError as exc:
        print(
            "Supabase health check falhou durante a conexão "
            f"({type(exc).__name__})."
        )
        return 1

    print("Supabase health check concluído com sucesso.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
