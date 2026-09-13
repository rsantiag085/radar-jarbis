"""
Gerenciador de estado persistente do RadarJarbis.

Usa uma conexão SQLite **singleton** para todo o ciclo de vida do processo,
eliminando o overhead de abrir/fechar file descriptors a cada mensagem.

Configuração:
    - PRAGMA journal_mode=WAL  : leituras não bloqueiam escritas (seguro para
                                 cron externo de purge sem parar o bot).
    - PRAGMA synchronous=NORMAL: balanço entre durabilidade e performance;
                                 aceitável pois o bot pode re-processar
                                 mensagens não registradas ao reiniciar
                                 (INSERT OR IGNORE garante idempotência).

Ciclo de vida:
    _get_conn()  — cria a conexão singleton na primeira chamada.
    close()      — deve ser chamado no bloco finally de main() para encerrar
                   a conexão de forma limpa antes do processo sair.

Nota sobre transações:
    O padrão `with conn:` do sqlite3 gerencia APENAS commit/rollback da
    transação; ele NÃO fecha a conexão. Com o singleton isso é exatamente
    o que queremos — a conexão permanece viva entre chamadas.
"""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Caminho do banco de dados local (fora do src/ para não versionar acidentalmente)
_custom_db = os.getenv("STATE_DB_PATH")
DB_PATH = Path(_custom_db) if _custom_db else Path(__file__).parent.parent / "config" / "state.db"

# Conexão singleton — None até a primeira chamada a _get_conn()
_conn: sqlite3.Connection | None = None


# ------------------------------------------------------------
# Gerenciamento interno da conexão
# ------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    """Retorna a conexão singleton, criando-a e inicializando o schema se necessário.

    check_same_thread=False é seguro aqui porque o bot opera em asyncio
    single-threaded; a flag é necessária apenas para os testes de threading.
    """
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS posted_messages (
                msg_id    TEXT PRIMARY KEY,
                posted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                asin      TEXT,
                price     TEXT
            )
        """)
        # Adicionar coluna asin caso ela não exista em um banco pré-existente
        try:
            _conn.execute("ALTER TABLE posted_messages ADD COLUMN asin TEXT")
        except sqlite3.OperationalError:
            # Coluna já existe
            pass

        # Adicionar coluna price caso ela não exista em um banco pré-existente
        try:
            _conn.execute("ALTER TABLE posted_messages ADD COLUMN price TEXT")
        except sqlite3.OperationalError:
            # Coluna já existe
            pass

        # Adicionar índice na coluna asin para buscas rápidas
        _conn.execute("CREATE INDEX IF NOT EXISTS idx_posted_messages_asin ON posted_messages(asin)")
        _conn.commit()
    return _conn


# ------------------------------------------------------------
# Interface pública
# ------------------------------------------------------------

def already_posted(msg_id: str) -> bool:
    """Verifica se a mensagem já foi postada no canal de saída.

    Operação de leitura — não abre transação explícita.
    Suporta busca com prefixo de plataforma (ex: 'amazon:...' ou 'meli:...')
    com fallback para o formato legado sem prefixo.

    Args:
        msg_id: Identificador único no formato '{platform}:{chat_id}:{message_id}'
                ou formato legado '{chat_id}:{message_id}'.

    Returns:
        True se já foi postada, False caso contrário.
    """
    conn = _get_conn()
    if ":" in msg_id:
        parts = msg_id.split(":", 1)
        if parts[0] in ("amazon", "meli"):
            legacy_id = parts[1]
            row = conn.execute(
                "SELECT 1 FROM posted_messages WHERE msg_id = ? OR msg_id = ?",
                (msg_id, legacy_id),
            ).fetchone()
            return row is not None

    row = conn.execute(
        "SELECT 1 FROM posted_messages WHERE msg_id = ?", (msg_id,)
    ).fetchone()
    return row is not None


def parse_price(p: str | None) -> float | None:
    """Extrai o valor numérico (float) de uma string de preço formatada em Real (BRL)."""
    if not p:
        return None
    p_clean = p.upper().replace("R$", "").replace(" ", "").replace("\xa0", "").strip()
    if "," in p_clean:
        p_clean = p_clean.replace(".", "").replace(",", ".")
    try:
        return float(p_clean)
    except ValueError:
        return None


def asin_already_posted(asin: str, price: str | None = None, within_hours: int = 24) -> bool:
    """Verifica se o ASIN já foi postado no canal dentro da janela de deduplicação.

    A janela é de:
    - 48 horas se houver uma baixa de pelo menos 10% no preço em relação à última postagem.
    - 8 dias (192 horas) caso contrário.

    Args:
        asin: O ASIN do produto Amazon (10 caracteres).
        price: Preço do produto para checagem de variação.
        within_hours: Mantido para compatibilidade de assinatura, mas ignorado em favor das regras dinâmicas.

    Returns:
        True se já foi postado dentro da janela aplicável, False caso contrário.
    """
    if not asin:
        return False
    conn = _get_conn()
    row = conn.execute(
        "SELECT price, posted_at FROM posted_messages "
        "WHERE asin = ? "
        "ORDER BY posted_at DESC LIMIT 1",
        (asin,)
    ).fetchone()

    if row is None:
        return False

    last_price, last_posted_str = row

    # Parse data da última postagem
    try:
        last_posted_dt = datetime.strptime(last_posted_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            last_posted_dt = datetime.fromisoformat(last_posted_str.replace(" ", "T"))
        except ValueError:
            return False

    now_dt = datetime.now(timezone.utc).replace(tzinfo=None)
    elapsed_hours = (now_dt - last_posted_dt).total_seconds() / 3600.0

    # Determina se há uma baixa de 10% ou mais
    has_10_percent_drop = False
    if price is not None and last_price is not None:
        last_price_float = parse_price(last_price)
        current_price_float = parse_price(price)
        if last_price_float is not None and current_price_float is not None and last_price_float > 0:
            # Baixa de 10% ou mais: preço atual deve ser menor ou igual a 90% do preço anterior
            if current_price_float <= last_price_float * 0.90 + 1e-9:
                has_10_percent_drop = True

    # Define o limite de tempo (48h ou 8 dias)
    limit_hours = 48 if has_10_percent_drop else 192  # 8 dias = 192 horas

    return elapsed_hours < limit_hours


def mark_posted(msg_id: str, asin: str | None = None, price: str | None = None) -> None:
    """Registra a mensagem como postada para evitar duplicidade.

    Usa `with conn:` para gerenciar a transação (commit/rollback).
    A conexão singleton NÃO é fechada ao sair do bloco with.

    Args:
        msg_id: Identificador único no formato '{chat_id}:{message_id}'.
        asin: ASIN opcional do produto Amazon.
        price: Preço opcional do produto.
    """
    conn = _get_conn()
    with conn:  # commit no __exit__ normal; rollback em exceção
        conn.execute(
            "INSERT OR IGNORE INTO posted_messages (msg_id, asin, price) VALUES (?, ?, ?)",
            (msg_id, asin, price)
        )


def purge_old_records(days: int = 30) -> int:
    """Remove registros com mais de `days` dias para manter o banco enxuto.

    Deve ser chamado por um job periódico (ex: cron semanal na GCP VM).

    Args:
        days: Quantidade de dias para considerar um registro como expirado.

    Returns:
        Número de registros deletados.
    """
    conn = _get_conn()
    with conn:  # commit no __exit__ normal; rollback em exceção
        cursor = conn.execute(
            "DELETE FROM posted_messages WHERE posted_at < datetime('now', ?)",
            (f"-{days} days",),
        )
    return cursor.rowcount


def close() -> None:
    """Fecha a conexão singleton e reseta o estado interno.

    Deve ser chamado no bloco finally de main() para garantir que o arquivo
    WAL do SQLite seja mesclado e o file descriptor seja liberado de forma
    limpa antes do processo encerrar.

    É idempotente: pode ser chamado mesmo se a conexão já estiver fechada.
    """
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None
