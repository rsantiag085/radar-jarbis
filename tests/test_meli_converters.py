"""
Testes unitários para os módulos de conversão e extração do Mercado Livre.
"""

import unittest
from unittest.mock import patch, AsyncMock
from src import meli, converters_meli


class TestMeliConverters(unittest.IsolatedAsyncioTestCase):
    def test_is_meli_url(self):
        self.assertTrue(meli.is_meli_url("https://www.mercadolivre.com.br/produto/p/MLB61080793"))
        self.assertTrue(meli.is_meli_url("https://produto.mercadolivre.com.br/MLB-12345678-item"))
        self.assertTrue(meli.is_meli_url("https://meli.la/2n6qwfd"))
        self.assertFalse(meli.is_meli_url("https://www.amazon.com.br/dp/B08N5WRWNW"))
        self.assertFalse(meli.is_meli_url("https://magazineluiza.com.br/p/123"))

    def test_extract_meli_item_id(self):
        self.assertEqual(meli.extract_meli_item_id("https://www.mercadolivre.com.br/p/MLB61080793"), "MLB61080793")
        self.assertEqual(meli.extract_meli_item_id("https://produto.mercadolivre.com.br/MLB-4806851859-item"), "MLB4806851859")
        self.assertEqual(meli.extract_meli_item_id("https://www.mercadolivre.com.br/up/MLBU4152340456"), "MLBU4152340456")
        self.assertIsNone(meli.extract_meli_item_id("https://amazon.com.br/dp/B08N5WRWNW"))

    @patch("src.meli.resolve_and_extract_meli_item", new_callable=AsyncMock)
    @patch("src.meli.generate_meli_affiliate_link", new_callable=AsyncMock)
    async def test_process_async_meli_post_with_cookies(self, mock_generate, mock_resolve):
        mock_resolve.return_value = ("MLB61080793", "https://www.mercadolivre.com.br/p/MLB61080793")
        mock_generate.return_value = "https://meli.la/test1234"
        text = (
            "🔥 Kit 4 Prateleiras De Parede Em Madeira\n"
            "De R$ 180,00 por apenas R$ 119,90 em até 3x sem juros\n"
            "Compre aqui: https://meli.la/2n6qwfd"
        )
        result = await converters_meli.process_async(text, cookies_str="fake_cookie")
        self.assertIsNotNone(result)
        self.assertIn("https://meli.la/test1234", result)
        self.assertNotIn("https://meli.la/2n6qwfd", result, "Não deve conter o link do concorrente")
        self.assertIn("Kit 4 Prateleiras De Parede", result)
        self.assertIn("R$ 119,90", result)

    @patch("src.meli.resolve_and_extract_meli_item", new_callable=AsyncMock)
    async def test_process_async_fallback_without_cookies(self, mock_resolve):
        mock_resolve.return_value = ("MLB61080793", "https://www.mercadolivre.com.br/p/MLB61080793")
        text = (
            "🔥 Kit 4 Prateleiras De Parede Em Madeira\n"
            "De R$ 180,00 por apenas R$ 119,90\n"
            "Compre aqui: https://meli.la/concorrente123"
        )
        # Sem cookies configurados
        result = await converters_meli.process_async(text, cookies_str="", affiliate_tag="noradardojarbis")
        self.assertIsNotNone(result)
        self.assertNotIn("https://meli.la/concorrente123", result, "Nunca deve vazar o link do concorrente")
        self.assertIn("https://www.mercadolivre.com.br/p/MLB61080793?matt_word=noradardojarbis", result)

    @patch("httpx.AsyncClient.get")
    async def test_resolve_and_extract_meli_item_from_social_html(self, mock_get):
        # Simula resposta de um link meli.la que redireciona para a vitrine social do concorrente
        mock_resp = AsyncMock()
        mock_resp.url = "https://www.mercadolivre.com.br/social/concorrente?matt_tool=99999"
        mock_resp.text = """
        <html>
            <a href="https://www.mercadolivre.com.br/produto-teste/up/MLBU4228166339?polycard_client=recommendations_home_affiliate-profile&wid=MLB4857636415&matt_tool=99999#tag">Comprar</a>
        </html>
        """
        mock_get.return_value = mock_resp

        item_id, clean_url = await meli.resolve_and_extract_meli_item("https://meli.la/2FGNRxN")
        self.assertEqual(item_id, "MLBU4228166339")
        self.assertEqual(clean_url, "https://www.mercadolivre.com.br/produto-teste/up/MLBU4228166339")
        self.assertNotIn("matt_tool=99999", clean_url, "Deve limpar parâmetros de afiliados do concorrente")


if __name__ == "__main__":
    unittest.main()
