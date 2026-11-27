"""
Testes unitários e de integração para o bot unificado (Amazon + Mercado Livre),
incluindo roteamento de plataforma, cooldown de categoria/subtipo e deduplicação no mesmo banco SQLite.
"""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("TELEGRAM_API_ID", "123456")
os.environ.setdefault("TELEGRAM_API_HASH", "0" * 32)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
os.environ.setdefault("SOURCE_CHANNEL_IDS", "-1001234567890")
os.environ.setdefault("OUTPUT_CHANNEL_ID", "@test_channel")

from src import bot, filters, settings, state


class TestUnifiedBotAndCooldowns(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._original_db_path = state.DB_PATH
        state.DB_PATH = Path(self._tmp.name)
        state.close()

        self._orig_rate_limit = settings.RATE_LIMIT_DELAY
        self._orig_cooldown = getattr(settings, "ENABLE_COOLDOWN", True)
        settings.RATE_LIMIT_DELAY = 0.0
        settings.ENABLE_COOLDOWN = False

    def tearDown(self):
        settings.RATE_LIMIT_DELAY = self._orig_rate_limit
        settings.ENABLE_COOLDOWN = self._orig_cooldown
        state.close()
        state.DB_PATH = self._original_db_path
        Path(self._tmp.name).unlink(missing_ok=True)

    def test_detect_platform(self):
        self.assertEqual(
            bot.detect_platform("Notebook Dell https://www.amazon.com.br/dp/B0C3MB3B52"),
            "amazon",
        )
        self.assertEqual(
            bot.detect_platform("Headset Gamer https://amzn.to/3xyz123"),
            "amazon",
        )
        self.assertEqual(
            bot.detect_platform("Headset Gamer https://a.co/d/09dAAQ5U"),
            "amazon",
        )
        self.assertEqual(
            bot.detect_platform("Headset Gamer https://meli.la/2Tbwa4p"),
            "meli",
        )
        self.assertEqual(
            bot.detect_platform("Monitor LG https://produto.mercadolivre.com.br/MLB-12345678-monitor"),
            "meli",
        )
        self.assertEqual(
            bot.detect_platform("Oferta com encurtador generico https://bit.ly/3abcDEF"),
            "unknown",
        )
        self.assertEqual(
            bot.detect_platform("Texto sem link algum"),
            "none",
        )

    def test_get_subtype_and_cooldown_state(self):
        self.assertEqual(filters.get_subtype("Headset Gamer Redragon Zeus Lite"), "fone")
        self.assertEqual(filters.get_subtype("Tênis Nike Air Max"), "tenis")
        self.assertEqual(filters.get_subtype("EUCERIN Sérum Facial Anti-idade Epigenetic"), "skincare")
        self.assertEqual(filters.get_subtype("Jogo de Panelas Tramontina"), "panelas")

        # Antes de registrar cooldown
        self.assertFalse(state.is_category_in_cooldown("tecnologia", minutes=62))
        self.assertFalse(state.is_subtype_in_cooldown("fone", minutes=62))
        self.assertFalse(state.is_global_in_cooldown())

        # Registra 1º post na categoria (ainda NÃO deve entrar em cooldown pois o limite é 2 posts por categoria/plataforma)
        chosen = state.record_cooldown(
            category="tecnologia",
            subtype="fone",
            min_global_minutes=4,
            max_global_minutes=14,
            platform="amazon",
            category_window_minutes=62,
            category_max_posts=2,
        )
        self.assertGreaterEqual(chosen, 4.0)
        self.assertLessEqual(chosen, 14.0)
        self.assertTrue(state.is_global_in_cooldown(platform="amazon"))
        self.assertFalse(state.is_category_in_cooldown("tecnologia", minutes=62, platform="amazon", max_posts=2))
        self.assertTrue(state.is_subtype_in_cooldown("fone", minutes=62))
        self.assertFalse(state.is_category_in_cooldown("pessoal", minutes=62, platform="amazon", max_posts=2))

        # Registra 2º post na mesma categoria/plataforma -> AGORA entra em cooldown de categoria (2/2)
        state.record_cooldown(
            category="tecnologia",
            subtype="monitor",
            platform="amazon",
            category_window_minutes=62,
            category_max_posts=2,
        )
        self.assertTrue(state.is_category_in_cooldown("tecnologia", minutes=62, platform="amazon", max_posts=2))
        # E a mesma categoria no Meli ainda está livre (0/2)!
        self.assertFalse(state.is_category_in_cooldown("tecnologia", minutes=62, platform="meli", max_posts=2))

        # Simula expiração do global (20 min atrás), mas categoria ainda ativa (2 posts há 45 min < 62 min)
        conn = sqlite3.connect(state.DB_PATH)
        conn.execute(
            "UPDATE category_cooldowns SET last_posted_at = datetime('now', '-1 minute') WHERE category = '__post_next_allowed_amazon__'"
        )
        conn.execute(
            "UPDATE category_cooldowns SET last_posted_at = datetime('now', '-45 minutes') || '|' || datetime('now', '-30 minutes') WHERE category = 'amazon:tecnologia'"
        )
        conn.execute("UPDATE subtype_cooldowns SET last_posted_at = datetime('now', '-45 minutes')")
        conn.commit()
        conn.close()

        self.assertFalse(state.is_global_in_cooldown(platform="amazon"))
        self.assertTrue(state.is_category_in_cooldown("tecnologia", minutes=62, platform="amazon", max_posts=2))
        self.assertTrue(state.is_subtype_in_cooldown("fone", minutes=62))

        # Simula expiração de 1 dos posts (65 min atrás e 30 min atrás -> apenas 1 post recente na janela < 2 -> LIBERA!)
        conn = sqlite3.connect(state.DB_PATH)
        conn.execute(
            "UPDATE category_cooldowns SET last_posted_at = datetime('now', '-65 minutes') || '|' || datetime('now', '-30 minutes') WHERE category = 'amazon:tecnologia'"
        )
        conn.execute("UPDATE subtype_cooldowns SET last_posted_at = datetime('now', '-65 minutes')")
        conn.commit()
        conn.close()

        self.assertFalse(state.is_category_in_cooldown("tecnologia", minutes=62, platform="amazon", max_posts=2))
        self.assertFalse(state.is_subtype_in_cooldown("fone", minutes=62))

    @patch("src.telemetry.start_span")
    @patch("src.meli.generate_meli_affiliate_link", new_callable=AsyncMock)
    @patch("src.bot._safe_send", new_callable=AsyncMock)
    @patch("src.meli.resolve_and_extract_meli_item", new_callable=AsyncMock)
    async def test_unified_routing_amazon_and_meli_in_same_db(
        self, mock_meli_resolve, mock_safe_send, mock_meli_gen, mock_span
    ):
        mock_safe_send.return_value = True
        mock_meli_resolve.return_value = ("MLB61080793", "https://www.mercadolivre.com.br/p/MLB61080793")
        mock_meli_gen.return_value = "https://meli.la/afiliado123"

        # 1. Mensagem Amazon
        msg_amz = MagicMock()
        msg_amz.id = 101
        msg_amz.chat_id = -100111
        msg_amz.photo = None
        msg_amz.text = (
            "💻 Notebook Dell Inspiron i5\n"
            "Por R$ 2.499,90 em até 10x sem juros\n"
            "https://www.amazon.com.br/dp/B0C3MB3B52"
        )

        await bot.process_message_object(-100111, msg_amz)

        # 2. Mensagem Mercado Livre
        msg_meli = MagicMock()
        msg_meli.id = 102
        msg_meli.chat_id = -100111
        msg_meli.photo = None
        msg_meli.text = (
            "🎧 Headset Gamer Redragon Zeus Lite Preto\n"
            "Por R$ 199,90\n"
            "https://meli.la/2Tbwa4p"
        )

        await bot.process_message_object(-100111, msg_meli)

        # Ambas devem ter sido enviadas
        self.assertEqual(mock_safe_send.await_count, 2)
        self.assertTrue(state.already_posted("amazon:-100111:101"))
        self.assertTrue(state.already_posted("meli:-100111:102"))
        self.assertTrue(state.asin_already_posted("B0C3MB3B52", price="R$ 2.499,90"))
        self.assertTrue(state.asin_already_posted("MLB61080793", price="R$ 199,90"))

        # 3. Repetir o mesmo produto do Meli em outra mensagem deve ser bloqueado por deduplicação de item_id
        msg_meli_dup = MagicMock()
        msg_meli_dup.id = 103
        msg_meli_dup.chat_id = -100111
        msg_meli_dup.photo = None
        msg_meli_dup.text = (
            "🎧 Headset Gamer Redragon Zeus Lite Preto\n"
            "Por R$ 199,90\n"
            "https://meli.la/outroLinkConcorrente"
        )

        await bot.process_message_object(-100111, msg_meli_dup)
        self.assertEqual(mock_safe_send.await_count, 2, "Duplicata do Meli deve ser bloqueada.")

    @patch("src.telemetry.start_span")
    @patch("src.meli.generate_meli_affiliate_link", new_callable=AsyncMock)
    @patch("src.meli.resolve_and_extract_meli_item", new_callable=AsyncMock)
    @patch("src.bot._safe_send", new_callable=AsyncMock)
    async def test_cooldown_blocks_same_category_when_enabled(
        self, mock_safe_send, mock_meli_resolve, mock_meli_gen, mock_span
    ):
        mock_safe_send.return_value = True
        mock_meli_resolve.return_value = ("MLB999999", "https://www.mercadolivre.com.br/p/MLB999999")
        mock_meli_gen.return_value = "https://meli.la/meli999"
        settings.ENABLE_COOLDOWN = True

        # 1º post Amazon de tecnologia (notebook)
        msg_1 = MagicMock()
        msg_1.id = 201
        msg_1.chat_id = -100222
        msg_1.photo = None
        msg_1.text = (
            "💻 Notebook Lenovo IdeaPad\n"
            "Por R$ 2.399,00\n"
            "https://www.amazon.com.br/dp/B099999991"
        )
        await bot.process_message_object(-100222, msg_1)
        self.assertEqual(mock_safe_send.await_count, 1)

        # 2º post Amazon de OUTRA categoria (pessoal - tênis) logo em seguida -> bloqueado pelo COOLDOWN INDIVIDUAL DA AMAZON (4-14 min)
        msg_other_cat = MagicMock()
        msg_other_cat.id = 202
        msg_other_cat.chat_id = -100222
        msg_other_cat.photo = None
        msg_other_cat.text = (
            "👟 Tênis Nike Air Max\n"
            "Por R$ 399,00\n"
            "https://www.amazon.com.br/dp/B099999993"
        )
        await bot.process_message_object(-100222, msg_other_cat)
        self.assertEqual(mock_safe_send.await_count, 1, "Deve bloquear post da Amazon durante o cooldown individual da Amazon (4-14 min).")

        # Post do MERCADO LIVRE de outra categoria (beleza - perfume) dentro do mesmo intervalo -> PERMITIDO (cooldown individual por plataforma!)
        msg_meli_independent = MagicMock()
        msg_meli_independent.id = 205
        msg_meli_independent.chat_id = -100222
        msg_meli_independent.photo = None
        msg_meli_independent.text = (
            "🧴 Perfume Eau de Parfum 100ml\n"
            "Por R$ 249,00\n"
            "https://meli.la/2Tbwa4p"
        )
        await bot.process_message_object(-100222, msg_meli_independent)
        self.assertEqual(mock_safe_send.await_count, 2, "Deve permitir 1 post do Meli no intervalo mesmo com a Amazon em cooldown.")

        # Libera o cooldown individual da Amazon no banco (simulando que passaram 15 minutos), mantendo o de categoria (62 min)
        conn = sqlite3.connect(state.DB_PATH)
        conn.execute(
            "UPDATE category_cooldowns SET last_posted_at = datetime('now', '-1 minute') WHERE category = '__post_next_allowed_amazon__'"
        )
        conn.commit()
        conn.close()

        # 2º post Amazon da MESMA categoria (tecnologia - monitor, subtipo diferente) dentro dos 62 min -> PERMITIDO (2º de 2 posts da categoria na Amazon!)
        msg_2 = MagicMock()
        msg_2.id = 203
        msg_2.chat_id = -100222
        msg_2.photo = None
        msg_2.text = (
            "🖥️ Monitor LG UltraGear 24\n"
            "Por R$ 899,00\n"
            "https://www.amazon.com.br/dp/B099999992"
        )
        await bot.process_message_object(-100222, msg_2)
        self.assertEqual(mock_safe_send.await_count, 3, "Deve permitir o 2º post da mesma categoria na Amazon dentro de 62 min.")

        # Libera novamente o cooldown individual de 4-14 min da Amazon
        conn = sqlite3.connect(state.DB_PATH)
        conn.execute(
            "UPDATE category_cooldowns SET last_posted_at = datetime('now', '-1 minute') WHERE category = '__post_next_allowed_amazon__'"
        )
        conn.commit()
        conn.close()

        # 3º post Amazon da MESMA categoria (tecnologia - teclado) dentro dos 62 min -> BLOQUEADO (já atingiu 2 posts de tecnologia na Amazon!)
        msg_3_blocked = MagicMock()
        msg_3_blocked.id = 206
        msg_3_blocked.chat_id = -100222
        msg_3_blocked.photo = None
        msg_3_blocked.text = (
            "⌨️ Teclado Mecânico Gamer\n"
            "Por R$ 199,00\n"
            "https://www.amazon.com.br/dp/B099999995"
        )
        await bot.process_message_object(-100222, msg_3_blocked)
        self.assertEqual(mock_safe_send.await_count, 3, "Deve bloquear o 3º post da mesma categoria na Amazon dentro de 62 min.")

        # 4º post Amazon de outra categoria (pessoal - tênis) -> APROVADO!
        msg_4 = MagicMock()
        msg_4.id = 204
        msg_4.chat_id = -100222
        msg_4.photo = None
        msg_4.text = (
            "👟 Tênis Adidas Ultraboost\n"
            "Por R$ 499,00\n"
            "https://www.amazon.com.br/dp/B099999994"
        )
        await bot.process_message_object(-100222, msg_4)
        self.assertEqual(mock_safe_send.await_count, 4, "Deve permitir post Amazon de outra categoria.")

    @patch("src.telemetry.start_span")
    @patch("src.bot.user_client.download_media", new_callable=AsyncMock)
    @patch("src.converters.fetch_clean_product_image", new_callable=AsyncMock)
    @patch("src.meli.generate_meli_affiliate_link", new_callable=AsyncMock)
    @patch("src.meli.resolve_and_extract_meli_item", new_callable=AsyncMock)
    @patch("src.converters.expandir_e_converter_link", new_callable=AsyncMock)
    @patch("src.bot._safe_send", new_callable=AsyncMock)
    async def test_divulgador_inteligente_routes_amazon_and_falls_back_to_meli(
        self,
        mock_safe_send,
        mock_expand_amz,
        mock_meli_resolve,
        mock_meli_gen,
        mock_fetch_clean_img,
        mock_download_media,
        mock_span,
    ):
        mock_safe_send.return_value = True
        mock_fetch_clean_img.return_value = b"CLEAN_STORE_JPEG_BYTES"

        # 1. Oferta Amazon via divulgadorinteligente.com COM card rosa anexado no Telegram (message.photo != None)
        mock_expand_amz.return_value = "https://www.amazon.com.br/dp/B0BZZK3R5S?tag=seutag-20"
        msg_amz_bridge = MagicMock()
        msg_amz_bridge.id = 301
        msg_amz_bridge.chat_id = -1003857632716
        msg_amz_bridge.photo = MagicMock()  # Simula o card rosa original do canal da Jessica
        msg_amz_bridge.text = (
            "🛍️Máscara Capilar Kérastase Nutritive Masquintense, 200ml\n\n"
            "💸por R$185,10 🚨🚨\n\n"
            "👉Link p/ comprar:  https://divulgadorinteligente.com/promosjessicanevile/p/TXLU9Zf3UH"
        )
        await bot.process_message_object(-1003857632716, msg_amz_bridge)
        self.assertEqual(mock_safe_send.await_count, 1)
        # NUNCA deve baixar o message.photo do Telegram quando vier de divulgadorinteligente / jessicanevilepromo
        mock_download_media.assert_not_awaited()
        self.assertEqual(mock_safe_send.await_args_list[0].kwargs.get("photo_bytes"), b"CLEAN_STORE_JPEG_BYTES")
        self.assertTrue(state.asin_already_posted("B0BZZK3R5S", price="R$ 185,10"))

        # 2. Oferta Mercado Livre via divulgadorinteligente.com (fallback automático do pipeline unknown -> meli)
        mock_expand_amz.return_value = "https://meli.la/13Duyx3"
        mock_meli_resolve.return_value = (
            "MLBU3721832026",
            "https://www.mercadolivre.com.br/kit-cetaphil/up/MLBU3721832026",
        )
        mock_meli_gen.return_value = "https://meli.la/nossoAfiliado99"

        msg_meli_bridge = MagicMock()
        msg_meli_bridge.id = 302
        msg_meli_bridge.chat_id = -1003857632716
        msg_meli_bridge.photo = MagicMock()
        msg_meli_bridge.text = (
            "🛍️Kit Cetaphil: 1 Creme Hidratante Neutra 453g + 1 Loção Hidratante Neutra 473ml\n\n"
            "💸por R$ 88,41 🚨🚨\n\n"
            "Cupom:  SOHOJEBF\n\n"
            "👉Link p/ comprar:  https://divulgadorinteligente.com/promosjessicanevile/p/ebpbX004k8"
        )
        await bot.process_message_object(-1003857632716, msg_meli_bridge)
        self.assertEqual(mock_safe_send.await_count, 2)
        mock_download_media.assert_not_awaited()
        self.assertEqual(mock_safe_send.await_args_list[1].kwargs.get("photo_bytes"), b"CLEAN_STORE_JPEG_BYTES")
        self.assertTrue(state.asin_already_posted("MLBU3721832026", price="R$ 88,41"))


if __name__ == "__main__":
    unittest.main()
