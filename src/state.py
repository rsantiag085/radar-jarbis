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

import sqlite3
from pathlib import Path

# Caminho do banco de dados local (fora do src/ para não versionar acidentalmente)
DB_PATH = Path(__file__).parent.parent / "config" / "state.db"

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
                posted_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        _conn.commit()
    return _conn


# ------------------------------------------------------------
# Interface pública
# ------------------------------------------------------------

def already_posted(msg_id: str) -> bool:
    """Verifica se a mensagem já foi postada no canal de saída.

    Operação de leitura — não abre transação explícita.

    Args:
        msg_id: Identificador único no formato '{chat_id}:{message_id}'.

    Returns:
        True se já foi postada, False caso contrário.
    """
    conn = _get_conn()
    row = conn.execute(
        "SELECT 1 FROM posted_messages WHERE msg_id = ?", (msg_id,)
    ).fetchone()
    return row is not None


def mark_posted(msg_id: str) -> None:
    """Registra a mensagem como postada para evitar duplicidade.

    Usa `with conn:` para gerenciar a transação (commit/rollback).
    A conexão singleton NÃO é fechada ao sair do bloco with.

    Args:
        msg_id: Identificador único no formato '{chat_id}:{message_id}'.
    """
    conn = _get_conn()
    with conn:  # commit no __exit__ normal; rollback em exceção
        conn.execute(
            "INSERT OR IGNORE INTO posted_messages (msg_id) VALUES (?)", (msg_id,)
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
