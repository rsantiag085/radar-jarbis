"""
Suíte de testes de deduplicação do RadarJarbis.

Cobre três níveis:
    1. Unitário  — comportamento isolado de src/state.py
    2. Integração — pipeline completo simulado via mocks (bot.py → state.py)
    3. Concorrência — valida thread-safety do banco SQLite

Todas as suítes usam um banco temporário isolado (in-memory ou tempfile)
para não contaminar config/state.db de produção.
"""

import asyncio
import logging
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Importa o módulo de estado; sobrescreveremos DB_PATH antes de cada teste
# ---------------------------------------------------------------------------
import src.state as state_module

# ---------------------------------------------------------------------------
# Configuração mínima de logging para os testes
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s | %(message)s")


# ===========================================================================
# 1. TESTES UNITÁRIOS — src/state.py
# ===========================================================================

class TestStateDeduplication(unittest.TestCase):
    """Valida o comportamento de already_posted / mark_posted com banco isolado."""

    MSG_ID = "3971790914:11"

    def setUp(self):
        """Cria um banco temporário em disco, fecha o singleton e redireciona DB_PATH."""
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._original_db_path = state_module.DB_PATH
        state_module.DB_PATH = Path(self._tmp.name)
        state_module.close()  # reseta o singleton para usar o novo DB_PATH

    def tearDown(self):
        """Fecha o singleton, restaura DB_PATH e remove o arquivo temporário."""
        state_module.close()  # garante que a conexão seja fechada antes de deletar
        state_module.DB_PATH = self._original_db_path
        Path(self._tmp.name).unlink(missing_ok=True)

    # -----------------------------------------------------------------------

    def test_primeira_vez_nao_postada(self):
        """Mensagem nova deve retornar False em already_posted."""
        resultado = state_module.already_posted(self.MSG_ID)
        self.assertFalse(
            resultado,
            "Mensagem nova não deve constar no banco antes de mark_posted().",
        )

    def test_marca_e_verifica_postada(self):
        """Após mark_posted, already_posted deve retornar True."""
        state_module.mark_posted(self.MSG_ID)
        resultado = state_module.already_posted(self.MSG_ID)
        self.assertTrue(
            resultado,
            "Mensagem deve ser detectada como duplicada após mark_posted().",
        )

    def test_segunda_tentativa_bloqueada(self):
        """
        Simula processamento duplo do msg_id "3971790914:11".

        Primeira passagem  → should_post = True  (not already_posted)
        Segunda passagem   → should_post = False (already_posted)
        """
        # --- 1ª tentativa ---
        primeira = not state_module.already_posted(self.MSG_ID)
        self.assertTrue(primeira, "1ª tentativa deve ser liberada para postagem.")

        state_module.mark_posted(self.MSG_ID)  # simula postagem bem-sucedida

        # --- 2ª tentativa ---
        segunda = not state_module.already_posted(self.MSG_ID)
        self.assertFalse(segunda, "2ª tentativa deve ser BLOQUEADA pelo deduplicador.")

    def test_insert_or_ignore_idempotente(self):
        """mark_posted chamado duas vezes não deve lançar exceção nem duplicar linhas."""
        state_module.mark_posted(self.MSG_ID)
        state_module.mark_posted(self.MSG_ID)  # não deve explodir

        conn = sqlite3.connect(state_module.DB_PATH)
        count = conn.execute(
            "SELECT COUNT(*) FROM posted_messages WHERE msg_id = ?", (self.MSG_ID,)
        ).fetchone()[0]
        conn.close()

        self.assertEqual(count, 1, "Deve haver exatamente 1 registro, mesmo com inserts duplos.")

    def test_platform_prefixes_and_legacy_fallback(self):
        """Valida que prefixos amazon: e meli: são isolados entre si e compatíveis com legados."""
        # 1. Isolamento entre plataformas
        state_module.mark_posted(f"amazon:{self.MSG_ID}")
        self.assertTrue(state_module.already_posted(f"amazon:{self.MSG_ID}"))
        self.assertFalse(state_module.already_posted(f"meli:{self.MSG_ID}"))

        # 2. Fallback para registros legados gravados sem prefixo
        legacy_id = "999999:123"
        state_module.mark_posted(legacy_id)
        self.assertTrue(state_module.already_posted(legacy_id))
        self.assertTrue(state_module.already_posted(f"amazon:{legacy_id}"))
        self.assertTrue(state_module.already_posted(f"meli:{legacy_id}"))

    def test_purge_old_records(self):
        """purge_old_records deve remover apenas registros antigos."""
        state_module.mark_posted(self.MSG_ID)

        # Manipula a data para simular registro com 31 dias
        conn = sqlite3.connect(state_module.DB_PATH)
        conn.execute(
            "UPDATE posted_messages SET posted_at = datetime('now', '-31 days') WHERE msg_id = ?",
            (self.MSG_ID,),
        )
        conn.commit()
        conn.close()

        removidos = state_module.purge_old_records(days=30)
        self.assertEqual(removidos, 1, "Deve ter removido 1 registro antigo.")
        self.assertFalse(state_module.already_posted(self.MSG_ID))

    def test_asin_deduplication(self):
        """Valida se o ASIN é corretamente salvo e dedupado em diferentes janelas com checagem de preço."""
        asin = "B0C3MB3B52"
        price_1 = "R$ 100,00"
        price_drop_9 = "R$ 91,00"   # Queda de 9% (< 10%)
        price_drop_10 = "R$ 90,00"  # Queda de 10% (>= 10%)
        price_drop_15 = "R$ 85,00"  # Queda de 15% (>= 10%)
        price_higher = "R$ 110,00"  # Aumento de preço

        self.assertFalse(state_module.asin_already_posted(asin, price=price_1))

        # Salva postagem com ASIN e preço
        state_module.mark_posted(self.MSG_ID, asin=asin, price=price_1)

        # Mesmo ASIN e mesmo preço deve barrar (True) — pois 0h < 8 dias
        self.assertTrue(state_module.asin_already_posted(asin, price=price_1))
        # Queda de 9% (menos de 10%) deve barrar (True) — pois 0h < 8 dias
        self.assertTrue(state_module.asin_already_posted(asin, price=price_drop_9))
        # Queda de 10% deve barrar (True) — pois 0h < 48h
        self.assertTrue(state_module.asin_already_posted(asin, price=price_drop_10))

        # Altera a data de postagem para 25 horas atrás
        conn = sqlite3.connect(state_module.DB_PATH)
        conn.execute(
            "UPDATE posted_messages SET posted_at = datetime('now', '-25 hours') WHERE msg_id = ?",
            (self.MSG_ID,),
        )
        conn.commit()
        conn.close()

        # Mesmo preço deve barrar (True) — 25h < 8 dias
        self.assertTrue(state_module.asin_already_posted(asin, price=price_1))
        # Queda de 9% deve barrar (True) — 25h < 8 dias
        self.assertTrue(state_module.asin_already_posted(asin, price=price_drop_9))
        # Queda de 10% deve barrar (True) — 25h < 48h
        self.assertTrue(state_module.asin_already_posted(asin, price=price_drop_10))

        # Altera a data de postagem para 50 horas atrás
        conn = sqlite3.connect(state_module.DB_PATH)
        conn.execute(
            "UPDATE posted_messages SET posted_at = datetime('now', '-50 hours') WHERE msg_id = ?",
            (self.MSG_ID,),
        )
        conn.commit()
        conn.close()

        # Mesmo preço deve barrar (True) — 50h < 8 dias
        self.assertTrue(state_module.asin_already_posted(asin, price=price_1))
        # Aumento de preço deve barrar (True) — 50h < 8 dias
        self.assertTrue(state_module.asin_already_posted(asin, price=price_higher))
        # Queda de 9% deve barrar (True) — 50h < 8 dias
        self.assertTrue(state_module.asin_already_posted(asin, price=price_drop_9))
        # Queda de 10% deve PERMITIR (False) — 50h > 48h
        self.assertFalse(state_module.asin_already_posted(asin, price=price_drop_10))
        # Queda de 15% deve PERMITIR (False) — 50h > 48h
        self.assertFalse(state_module.asin_already_posted(asin, price=price_drop_15))

        # Altera a data de postagem para 9 dias atrás (216 horas)
        conn = sqlite3.connect(state_module.DB_PATH)
        conn.execute(
            "UPDATE posted_messages SET posted_at = datetime('now', '-9 days') WHERE msg_id = ?",
            (self.MSG_ID,),
        )
        conn.commit()
        conn.close()

        # Mesmo preço deve PERMITIR (False) — 216h > 8 dias (192h)
        self.assertFalse(state_module.asin_already_posted(asin, price=price_1))




# ===========================================================================
# 2. TESTES DE INTEGRAÇÃO — pipeline bot.py → state.py (com mocks)
# ===========================================================================

class TestBotPipelineDeduplication(unittest.IsolatedAsyncioTestCase):
    """
    Simula o handler handle_new_offer do bot.py sem nenhuma dependência
    de rede real. Valida que o bloco de deduplicação funciona no pipeline
    completo: filtro → dedup → converter → safe_send → mark_posted.
    """

    MSG_ID = "3971790914:11"
    SAMPLE_TEXT = (
        "🛒 Notebook Samsung 15' Intel Core i5\n"
        "De R$ 3.999 por R$ 2.499,90 — 37% off\n"
        "https://amzn.to/3xABCDE"
    )

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._original_db_path = state_module.DB_PATH
        state_module.DB_PATH = Path(self._tmp.name)
        state_module.close()  # reseta o singleton para usar o novo DB_PATH

    def tearDown(self):
        state_module.close()  # garante fechamento antes de deletar o arquivo
        state_module.DB_PATH = self._original_db_path
        Path(self._tmp.name).unlink(missing_ok=True)

    def _build_mock_event(self):
        """Monta um evento Telethon falso com o texto de oferta."""
        event = MagicMock()
        event.message.text = self.SAMPLE_TEXT
        event.chat_id = int(self.MSG_ID.split(":")[0])
        event.message.id = int(self.MSG_ID.split(":")[1])
        return event

    async def _run_pipeline(self, mock_send: AsyncMock, text_override: str = None) -> bool:
        """
        Executa o pipeline equivalente ao handle_new_offer do bot.py.
        Retorna True se o post foi despachado, False se bloqueado.
        """
        import src.filters as filters
        import src.converters as converters
        import src.settings as settings

        event = self._build_mock_event()
        text = text_override if text_override is not None else (event.message.text or "")
        if not text:
            return False

        chat_id = event.chat_id
        message_id = event.message.id
        msg_id = f"{chat_id}:{message_id}"

        if not filters.is_relevant(text):
            return False

        if state_module.already_posted(msg_id):
            return False  # ← BLOQUEIO DE DUPLICATA

        formatted = converters.process(text)
        if not formatted:
            return False

        # Deduplicação por ASIN (mesmo produto de afiliado diferente)
        asin = converters.extract_asin(formatted)
        price = converters.extract_price(text)
        if asin and state_module.asin_already_posted(asin, price=price, within_hours=settings.DEDUPLICATION_WINDOW_HOURS):
            state_module.mark_posted(msg_id, asin=asin, price=price)
            return False

        await mock_send(formatted)
        state_module.mark_posted(msg_id, asin=asin, price=price)
        return True

    async def test_asin_duplicate_blocked_different_msg_id(self):
        """
        Dois posts com msg_id diferentes e links de afiliados diferentes,
        mas que apontam para o mesmo produto (mesmo ASIN) e mesmo preço devem ser dedupados.
        """
        mock_send = AsyncMock()

        # Primeiro post
        text_1 = (
            "🛒 Notebook Samsung 15' Intel Core i5\n"
            "De R$ 3.999 por R$ 2.499,90 — 37% off\n"
            "https://www.amazon.com.br/dp/B0C3MB3B52?tag=afiliado1-20"
        )

        # Simula a primeira postagem do produto
        resultado_1 = await self._run_pipeline(mock_send, text_override=text_1)
        self.assertTrue(resultado_1, "O primeiro post deve ser enviado com sucesso.")

        # Segundo post: id diferente, afiliado diferente, mas mesmo produto (mesmo ASIN) e mesmo preço
        text_2 = (
            "🛒 Notebook Samsung 15' Intel Core i5\n"
            "De R$ 3.999 por R$ 2.499,90 — 37% off\n"
            "https://www.amazon.com.br/dp/B0C3MB3B52?tag=afiliado2-20"
        )

        # Moca o evento para simular um novo message_id
        with patch.object(self, '_build_mock_event') as mock_event_builder:
            event = MagicMock()
            event.message.text = text_2
            event.chat_id = 999999999
            event.message.id = 12345
            mock_event_builder.return_value = event

            # Tenta enviar o segundo post
            resultado_2 = await self._run_pipeline(mock_send, text_override=text_2)

        self.assertFalse(resultado_2, "O segundo post deve ser bloqueado por ASIN duplicado e mesmo preço.")
        # O mock_send deve ter sido chamado exatamente uma vez (só para o primeiro post)
        mock_send.assert_awaited_once()

    async def test_asin_duplicate_allowed_if_price_changes(self):
        """
        Se o produto já foi postado, mas o preço mudou significativamente (queda >= 10%),
        deve permitir a postagem após a janela de 48h. Se a queda for menor, bloqueia.
        """
        mock_send = AsyncMock()

        # Primeiro post
        text_1 = (
            "🛒 Notebook Samsung 15' Intel Core i5\n"
            "De R$ 3.999 por R$ 2.499,90 — 37% off\n"
            "https://www.amazon.com.br/dp/B0C3MB3B52?tag=afiliado1-20"
        )

        resultado_1 = await self._run_pipeline(mock_send, text_override=text_1)
        self.assertTrue(resultado_1)

        # Atualiza o timestamp da última postagem para 50 horas atrás no banco temporário
        conn = sqlite3.connect(state_module.DB_PATH)
        conn.execute(
            "UPDATE posted_messages SET posted_at = datetime('now', '-50 hours') WHERE asin = ?",
            ("B0C3MB3B52",),
        )
        conn.commit()
        conn.close()

        # Segundo post com queda de 10% (de R$ 2.499,90 para R$ 2.249,90)
        text_2 = (
            "🛒 Notebook Samsung 15' Intel Core i5\n"
            "De R$ 3.999 por R$ 2.249,90 — 42% off\n"
            "https://www.amazon.com.br/dp/B0C3MB3B52?tag=afiliado2-20"
        )

        with patch.object(self, '_build_mock_event') as mock_event_builder:
            event = MagicMock()
            event.message.text = text_2
            event.chat_id = 999999999
            event.message.id = 12345
            mock_event_builder.return_value = event

            resultado_2 = await self._run_pipeline(mock_send, text_override=text_2)

        self.assertTrue(resultado_2, "O segundo post deve ser enviado porque houve queda de 10% e já passou da janela de 48h.")

        # Terceiro post com queda de menos de 10% (de R$ 2.249,90 para R$ 2.199,90 -> queda de ~2.2%)
        # Atualiza a postagem anterior (que agora é a de R$ 2.249,90) para 49 horas atrás para que ela seja a mais recente.
        conn = sqlite3.connect(state_module.DB_PATH)
        conn.execute(
            "UPDATE posted_messages SET posted_at = datetime('now', '-49 hours') WHERE price = ?",
            ("R$ 2.249,90",),
        )
        conn.commit()
        conn.close()

        text_3 = (
            "🛒 Notebook Samsung 15' Intel Core i5\n"
            "De R$ 3.999 por R$ 2.199,90 — 44% off\n"
            "https://www.amazon.com.br/dp/B0C3MB3B52?tag=afiliado3-20"
        )

        with patch.object(self, '_build_mock_event') as mock_event_builder:
            event = MagicMock()
            event.message.text = text_3
            event.chat_id = 999999999
            event.message.id = 12346
            mock_event_builder.return_value = event

            resultado_3 = await self._run_pipeline(mock_send, text_override=text_3)

        self.assertFalse(resultado_3, "O terceiro post deve ser bloqueado porque a queda foi < 10% (janela de 8 dias ativa).")
        self.assertEqual(mock_send.await_count, 2, "Devem ocorrer apenas duas postagens enviadas (a primeira e a segunda).")



    async def test_primeira_e_segunda_tentativa(self):
        """
        Primeira chamada ao pipeline → post enviado (True).
        Segunda chamada com mesmo msg_id → bloqueado (False).
        """
        mock_send = AsyncMock()

        resultado_1 = await self._run_pipeline(mock_send)
        resultado_2 = await self._run_pipeline(mock_send)

        self.assertTrue(resultado_1, "1ª tentativa deve resultar em postagem.")
        self.assertFalse(resultado_2, "2ª tentativa deve ser BLOQUEADA pela deduplicação.")

        # Bot API deve ter sido chamada EXATAMENTE uma vez
        mock_send.assert_awaited_once()

    async def test_mensagem_diferente_nao_bloqueada(self):
        """Mensagens com msg_id distinto devem ser postadas independentemente."""
        mock_send = AsyncMock()

        # Primeiro msg_id
        await self._run_pipeline(mock_send)

        # Segundo msg_id diferente — novo evento
        event2 = self._build_mock_event()
        event2.message.id = 12  # ID diferente

        import src.filters as filters
        import src.converters as converters

        text = event2.message.text
        msg_id_2 = f"{event2.chat_id}:{event2.message.id}"

        if filters.is_relevant(text) and not state_module.already_posted(msg_id_2):
            formatted = converters.process(text)
            await mock_send(formatted)
            state_module.mark_posted(msg_id_2)

        self.assertEqual(mock_send.await_count, 2, "Duas mensagens distintas devem gerar 2 posts.")


# ===========================================================================
# 3. TESTES DE CONCORRÊNCIA — thread-safety do SQLite
# ===========================================================================

class TestStateConcurrency(unittest.TestCase):
    """
    Valida que o banco SQLite não sofre race condition quando múltiplas
    threads tentam processar o mesmo msg_id simultaneamente.

    Garante que apenas UMA thread "vence" e as demais são bloqueadas.
    """

    MSG_ID = "3971790914:11"

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._original_db_path = state_module.DB_PATH
        state_module.DB_PATH = Path(self._tmp.name)
        state_module.close()  # reseta o singleton para usar o novo DB_PATH

    def tearDown(self):
        state_module.close()  # garante fechamento antes de deletar o arquivo
        state_module.DB_PATH = self._original_db_path
        Path(self._tmp.name).unlink(missing_ok=True)

    def test_apenas_uma_thread_posta(self):
        """
        10 threads tentam processar o mesmo msg_id ao mesmo tempo.
        Apenas 1 deve conseguir postar; as outras 9 devem ser bloqueadas.
        """
        postagens_realizadas = []
        lock = threading.Lock()

        def tentar_postar():
            # Seção crítica: verificar → postar → marcar
            # O SQLite com WAL e INSERT OR IGNORE garante atomicidade.
            with lock:
                if not state_module.already_posted(self.MSG_ID):
                    state_module.mark_posted(self.MSG_ID)
                    postagens_realizadas.append(threading.current_thread().name)

        threads = [
            threading.Thread(target=tentar_postar, name=f"Thread-{i}")
            for i in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(
            len(postagens_realizadas),
            1,
            f"Esperado 1 postagem; ocorreram {len(postagens_realizadas)}: {postagens_realizadas}",
        )

    def test_sem_lock_insert_or_ignore_ainda_garante_unicidade(self):
        """
        Valida que INSERT OR IGNORE garante unicidade no banco mesmo com
        múltiplos processos/conexões independentes escrevendo simultaneamente.

        Nota de design: o singleton de state.py é para uso single-threaded
        (asyncio). Este teste simula o cenário de múltiplas conexões externas
        (ex: cron job de purge + bot rodando) e valida a garantia do SQLite
        com WAL mode — não o singleton em si.
        """
        errors = []

        # Garante que o schema existe antes das threads (via singleton)
        state_module.already_posted("warmup")
        db_path = str(state_module.DB_PATH)

        def worker():
            """Cada thread abre sua própria conexão — simula processos externos."""
            try:
                conn = sqlite3.connect(db_path, timeout=10)
                conn.execute("PRAGMA journal_mode=WAL")
                with conn:
                    conn.execute(
                        "INSERT OR IGNORE INTO posted_messages (msg_id) VALUES (?)",
                        (self.MSG_ID,),
                    )
                conn.close()
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertFalse(errors, f"Erros de concorrência detectados: {errors}")

        # Verifica unicidade final — deve haver exatamente 1 registro
        final_count = sqlite3.connect(db_path).execute(
            "SELECT COUNT(*) FROM posted_messages WHERE msg_id = ?", (self.MSG_ID,)
        ).fetchone()[0]

        self.assertEqual(
            final_count, 1, "INSERT OR IGNORE deve garantir exatamente 1 registro."
        )


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
