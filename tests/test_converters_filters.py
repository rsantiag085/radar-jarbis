"""
Suíte de testes de robustez para src/converters.py e src/filters.py.

Cobre:
    1. Extração de preço — formatos variados (R$1.100,00 / R$ 879 / bare 1100)
    2. Injeção de tag de afiliado — URL limpa, com tag antiga, com múltiplos params
    3. convert_urls — substituição em texto completo de copywriting
    4. process() — pipeline completo end-to-end
    5. Filtros — categorias, exclusões, desconto mínimo, edge cases de copywriting
"""

import re
import urllib.parse
import unittest
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import src.converters as converters
import src.filters as filters

AFFILIATE_TAG = "noradardojarb-20"


# ===========================================================================
# 1. EXTRAÇÃO DE PREÇO — _extract_price
# ===========================================================================

class TestExtractPrice(unittest.TestCase):
    """Valida _extract_price contra os formatos de preço mais comuns em grupos de ofertas."""

    def _price(self, text: str) -> str:
        return converters._extract_price(text)

    # --- Formatos com R$ que DEVEM ser capturados ---

    def test_formato_padrao_com_centavos(self):
        """R$ 1.299,90 — formato canônico brasileiro."""
        self.assertEqual(self._price("Produto por R$ 1.299,90 no Pix"), "R$ 1.299,90")

    def test_sem_espaco_apos_cifrao(self):
        """R$1.100,00 — sem espaço entre R$ e o número."""
        self.assertEqual(self._price("De R$3.999 por R$1.100,00"), "R$3.999")  # captura o primeiro

    def test_preco_inteiro_com_espaco(self):
        """R$ 879 — preço inteiro, sem centavos."""
        self.assertEqual(self._price("Agora por R$ 879!"), "R$ 879")

    def test_preco_com_ponto_milhar(self):
        """R$ 2.499 — ponto como separador de milhar."""
        result = self._price("R$ 2.499 à vista")
        self.assertIn("2.499", result)

    def test_multiplos_precos_retorna_primeiro(self):
        """Quando há 'de R$ X por R$ Y', deve retornar o primeiro encontrado."""
        result = self._price("De R$ 5.000 por R$ 2.499,90")
        self.assertIn("5.000", result)

    def test_preco_embutido_em_copywriting(self):
        """Preço no meio de frase com emojis e formatação de canal."""
        text = "🔥 SSD Samsung 1TB — por apenas R$ 379,90 no Pix!\nLink 👇"
        self.assertEqual(self._price(text), "R$ 379,90")

    def test_texto_sem_preco_retorna_vazio(self):
        """Texto sem nenhum padrão de preço deve retornar string vazia."""
        self.assertEqual(self._price("Headset Logitech — link na bio"), "")

    # --- Formatos que representam LIMITAÇÃO CONHECIDA do regex atual ---

    def test_numero_sem_cifrao_nao_capturado(self):
        """
        '1100' sem R$ NÃO é capturado pelo regex atual (R\\$\\s*[\\d.,]+).
        Este teste documenta a limitação — se falhar, o padrão foi melhorado.
        """
        result = self._price("Notebook por apenas 1100 reais")
        self.assertEqual(
            result, "",
            "Limitação conhecida: bare numbers sem R$ não são capturados pelo _PRICE_PATTERN atual."
        )

    def test_preco_em_dolar_nao_capturado(self):
        """USD $ 99 não deve ser capturado — padrão é estritamente R$."""
        self.assertEqual(self._price("Produto importado $ 99 dólares"), "")


# ===========================================================================
# 2. INJEÇÃO DE TAG — _inject_affiliate_tag
# ===========================================================================

class TestInjectAffiliateTag(unittest.TestCase):
    """Valida que a tag é injetada/substituída corretamente e outros params são preservados."""

    def _inject(self, url: str) -> str:
        return converters._inject_affiliate_tag(url)

    def _get_tag(self, url: str) -> str:
        return urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("tag", [""])[0]

    # --- URLs sem tag anterior ---

    def test_amazon_com_br_sem_tag(self):
        url = "https://www.amazon.com.br/dp/B09G3HRMVB"
        result = self._inject(url)
        self.assertEqual(self._get_tag(result), AFFILIATE_TAG)

    def test_amzn_to_curto_sem_tag(self):
        url = "https://amzn.to/3xABCDE"
        result = self._inject(url)
        self.assertEqual(self._get_tag(result), AFFILIATE_TAG)

    def test_a_co_curto_sem_tag(self):
        url = "https://a.co/d/9aBcDeF"
        result = self._inject(url)
        self.assertEqual(self._get_tag(result), AFFILIATE_TAG)

    # --- URLs com tag concorrente — deve ser SUBSTITUÍDA ---

    def test_tag_concorrente_substituida(self):
        """Tag de outro afiliado deve ser sobrescrita, não duplicada."""
        url = "https://www.amazon.com.br/dp/B09G3HRMVB?tag=concorrente-20"
        result = self._inject(url)
        self.assertEqual(self._get_tag(result), AFFILIATE_TAG)
        self.assertNotIn("concorrente-20", result)

    def test_tag_propria_idempotente(self):
        """Re-injetar nossa própria tag não deve alterar a URL."""
        url = f"https://www.amazon.com.br/dp/B09G3HRMVB?tag={AFFILIATE_TAG}"
        result = self._inject(url)
        self.assertEqual(self._get_tag(result), AFFILIATE_TAG)
        self.assertEqual(result.count(AFFILIATE_TAG), 1)

    # --- URLs com múltiplos parâmetros — outros params PRESERVADOS ---

    def test_outros_params_preservados(self):
        """ref, keywords, etc. devem ser mantidos; apenas tag é substituída."""
        url = "https://www.amazon.com.br/s?k=ssd&ref=nb_sb_noss&tag=antigo-22"
        result = self._inject(url)
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(result).query)
        self.assertEqual(parsed["tag"], [AFFILIATE_TAG])
        self.assertIn("k", parsed)
        self.assertIn("ref", parsed)

    def test_url_com_muitos_params_antigos(self):
        """URL realista com vários parâmetros de rastreamento."""
        url = (
            "https://www.amazon.com.br/dp/B09G3HRMVB"
            "?th=1&psc=1&tag=vendedor-21&linkCode=ll1&linkId=abc123&language=pt_BR"
        )
        result = self._inject(url)
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(result).query)
        self.assertEqual(parsed["tag"], [AFFILIATE_TAG])
        self.assertIn("th", parsed)
        self.assertIn("psc", parsed)
        self.assertNotIn("vendedor-21", result)

    # --- URLs não-Amazon — NÃO devem ser modificadas ---

    def test_url_nao_amazon_intocada(self):
        url = "https://www.mercadolivre.com.br/produto/123"
        self.assertEqual(self._inject(url), url)

    def test_url_magazineluiza_intocada(self):
        url = "https://www.magazineluiza.com.br/produto/abc"
        self.assertEqual(self._inject(url), url)

    def test_url_bit_ly_intocada(self):
        """bit.ly não é domínio Amazon — não deve ser modificado."""
        url = "https://bit.ly/3xCurto"
        self.assertEqual(self._inject(url), url)


# ===========================================================================
# 3. CONVERT_URLS — substituição em texto completo
# ===========================================================================

class TestConvertUrls(unittest.TestCase):
    """Valida convert_urls em textos realistas de copywriting."""

    def test_texto_com_url_amazon_simples(self):
        text = "Oferta: https://www.amazon.com.br/dp/B001 — corre!"
        result = converters.convert_urls(text)
        self.assertIn(f"tag={AFFILIATE_TAG}", result)

    def test_texto_com_url_amzn_to(self):
        text = "🔥 Confira: https://amzn.to/3aBcDeF"
        result = converters.convert_urls(text)
        self.assertIn(f"tag={AFFILIATE_TAG}", result)

    def test_tag_antiga_no_texto_substituida(self):
        text = "Link: https://www.amazon.com.br/dp/B001?tag=rival-20 confira!"
        result = converters.convert_urls(text)
        self.assertNotIn("rival-20", result)
        self.assertIn(AFFILIATE_TAG, result)

    def test_url_nao_amazon_no_texto_preservada(self):
        text = "Fonte: https://www.techtudo.com.br/review/produto — compre em https://amzn.to/3link"
        result = converters.convert_urls(text)
        self.assertIn("techtudo.com.br/review/produto", result)
        self.assertIn(f"tag={AFFILIATE_TAG}", result)

    def test_multiplas_urls_amazon_no_texto(self):
        """Todas as URLs Amazon no texto devem receber a tag."""
        text = (
            "Opção 1: https://www.amazon.com.br/dp/AAA\n"
            "Opção 2: https://www.amazon.com.br/dp/BBB?tag=outro-20"
        )
        result = converters.convert_urls(text)
        count = result.count(f"tag={AFFILIATE_TAG}")
        self.assertEqual(count, 2, "Ambas as URLs Amazon devem ter a tag injetada.")

    def test_texto_sem_url_nao_alterado(self):
        text = "Produto incrível com 40% off, R$ 199,90."
        self.assertEqual(converters.convert_urls(text), text)


# ===========================================================================
# 4. PIPELINE COMPLETO — process()
# ===========================================================================

class TestProcess(unittest.TestCase):
    """Valida o output HTML do process() contra estrutura esperada."""

    TRIGGERS = {"⚠️ MENOR PREÇO HISTÓRICO", "⚡ CORRE ANTES QUE ACABE", "📉 BUG DE PREÇO"}

    def _assert_post_structure(self, result: str, expect_price=True, expect_url=True):
        self.assertTrue(any(t in result for t in self.TRIGGERS), "Deve conter gatilho mental.")
        self.assertIn("🛒", result)
        self.assertIn("<b>", result)
        self.assertIn("Links qualificados de associado.", result)
        if expect_price:
            self.assertIn("💰", result)
        if expect_url:
            self.assertIn("🔗", result)
            self.assertIn(AFFILIATE_TAG, result)

    def test_copywriting_completo_padrao(self):
        text = (
            "🛒 Notebook Dell Inspiron 15\n"
            "De R$ 4.999 por R$ 2.799,90 — 44% off\n"
            "https://www.amazon.com.br/dp/B09XYZ?tag=outro-20"
        )
        result = converters.process(text)
        self._assert_post_structure(result)
        self.assertNotIn("outro-20", result)

    def test_copywriting_sem_preco(self):
        text = "💻 Monitor LG 27' 4K\nhttps://amzn.to/3Monitor"
        result = converters.process(text)
        self._assert_post_structure(result, expect_price=False)

    def test_copywriting_sem_url_amazon(self):
        text = "🎧 Headset HyperX Cloud II por R$ 299,90\nLink: https://bit.ly/headset"
        result = converters.process(text)
        self._assert_post_structure(result, expect_url=False)

    def test_copywriting_preco_sem_espaco_cifrao(self):
        """R$1.100,00 (sem espaço) deve ser extraído e aparecer no post."""
        text = "SSD Kingston 1TB por R$1.100,00\nhttps://amzn.to/3SSD"
        result = converters.process(text)
        self.assertIn("1.100", result)

    def test_copywriting_preco_inteiro(self):
        """R$ 879 (inteiro, sem centavos) deve aparecer no post."""
        text = "Teclado Mecânico Redragon por R$ 879\nhttps://amzn.to/3Teclado"
        result = converters.process(text)
        self.assertIn("879", result)


# ===========================================================================
# 5. FILTROS — is_relevant() e get_category()
# ===========================================================================

class TestIsRelevant(unittest.TestCase):
    """Testa o motor de filtragem com cenários complexos de copywriting."""

    # --- Aprovações esperadas ---

    def test_tecnologia_aprovada(self):
        self.assertTrue(filters.is_relevant("Notebook Dell i5 por R$ 2.499 — 30% off"))

    def test_smart_home_aprovada(self):
        self.assertTrue(filters.is_relevant("Echo Dot 5ª geração (Alexa) por R$ 199"))

    def test_beleza_saude_aprovada(self):
        self.assertTrue(filters.is_relevant("Whey Protein Growth 1kg chocolate R$ 89,90"))

    def test_pessoal_aprovada(self):
        self.assertTrue(filters.is_relevant("Tênis Nike Air Max 36 por R$ 399"))

    def test_sem_desconto_mencionado_aprovada(self):
        """Sem % de desconto no texto, o filtro de desconto não é ativado."""
        self.assertTrue(filters.is_relevant("SSD Samsung 1TB por R$ 379 — oferta relâmpago"))

    def test_desconto_exatamente_10_aprovado(self):
        self.assertTrue(filters.is_relevant("Monitor 10% off — confira o headset!"))

    def test_desconto_alto_aprovado(self):
        self.assertTrue(filters.is_relevant("Smartwatch com 45% de desconto — imperdível!"))

    # --- Bloqueios esperados por desconto insuficiente ---

    def test_desconto_9_bloqueado(self):
        self.assertFalse(filters.is_relevant("Notebook com 9% off — aproveite!"))

    def test_desconto_zero_bloqueado(self):
        self.assertFalse(filters.is_relevant("Cadeira gamer 0% off na compra"))

    def test_desconto_1_bloqueado(self):
        self.assertFalse(filters.is_relevant("SSD com apenas 1% desconto"))

    # --- Bloqueios por categoria excluída ---

    def test_vestuario_camiseta_bloqueado(self):
        self.assertFalse(filters.is_relevant("Camiseta Nike Dri-Fit por R$ 89 — 30% off"))

    def test_vestuario_calcas_bloqueado(self):
        self.assertFalse(filters.is_relevant("Calça Jeans Slim por R$ 120 — 20% off"))

    def test_eletrodomestico_geladeira_bloqueado(self):
        self.assertFalse(filters.is_relevant("Geladeira Brastemp 400L frost free R$ 2.800"))

    def test_eletrodomestico_microondas_bloqueado(self):
        self.assertFalse(filters.is_relevant("Microondas LG 30L por R$ 399 — 15% off"))

    def test_cozinha_panela_bloqueada(self):
        self.assertFalse(filters.is_relevant("Panela de pressão elétrica R$ 179"))

    # --- Edge case: categoria válida + keyword excluída no mesmo texto ---

    def test_categoria_valida_com_excluida_bloqueado(self):
        """Texto com notebook (válido) E camiseta (excluído) deve ser BLOQUEADO."""
        text = "Kit: Notebook Dell + Camiseta Nike por R$ 3.000 — 25% off"
        self.assertFalse(filters.is_relevant(text))

    # --- Textos sem categoria conhecida ---

    def test_texto_generico_sem_categoria_bloqueado(self):
        self.assertFalse(filters.is_relevant("Ótima oferta hoje! Não perca!"))

    def test_texto_vazio_bloqueado(self):
        self.assertFalse(filters.is_relevant(""))

    # --- Case insensitivity ---

    def test_keyword_maiuscula_aprovada(self):
        self.assertTrue(filters.is_relevant("NOTEBOOK Dell por R$ 2.000"))

    def test_keyword_mista_aprovada(self):
        self.assertTrue(filters.is_relevant("Monitores 4K em promoção — Smart TV 55'"))

    # --- Copywriting com emojis e formatação de canal ---

    def test_copywriting_rico_em_emojis_aprovado(self):
        text = (
            "🔥💥 OFERTA IMPERDÍVEL 💥🔥\n"
            "🎧 Headset HyperX Cloud Alpha\n"
            "💰 De R$ 599 por R$ 329,90 (45% OFF)\n"
            "⏰ Só hoje!\nhttps://amzn.to/3Headset"
        )
        self.assertTrue(filters.is_relevant(text))

    def test_desconto_em_formato_desc(self):
        """Padrão '30% desc' deve ser reconhecido pelo _DISCOUNT_PATTERN."""
        self.assertTrue(filters.is_relevant("SSD com 30% desc — imperdível"))

    def test_desconto_em_formato_de_desconto(self):
        """Padrão '25% de desconto' deve ser reconhecido."""
        self.assertTrue(filters.is_relevant("Teclado mecânico com 25% de desconto"))


class TestGetCategory(unittest.TestCase):
    """Valida a detecção de categoria pelo get_category()."""

    def test_tecnologia(self):
        self.assertEqual(filters.get_category("Notebook Dell i7"), "tecnologia")

    def test_smart_home(self):
        self.assertEqual(filters.get_category("Echo Dot com Alexa"), "smart_home")

    def test_beleza_saude(self):
        self.assertEqual(filters.get_category("Whey Protein 1kg"), "beleza_saude")

    def test_pessoal(self):
        self.assertEqual(filters.get_category("Tênis Adidas Ultra Boost"), "pessoal")

    def test_sem_categoria_retorna_none(self):
        self.assertIsNone(filters.get_category("Produto genérico sem categoria"))



# ===========================================================================
# 6. EXPANSÃO E CONVERSÃO DE LINK — expandir_e_converter_link
# ===========================================================================

class TestExpandirEConverterLink(unittest.IsolatedAsyncioTestCase):
    """Valida a função assíncrona expandir_e_converter_link."""

    async def test_deve_expandir_link_encurtado_e_injetar_tag_amazon(self):
        url_encurtada = "https://amzn.divulgador.link/xyz"
        
        import httpx
        
        mock_client = MagicMock()
        mock_client_context = AsyncMock()
        mock_client_context.__aenter__.return_value = mock_client
        
        mock_stream = AsyncMock()
        mock_response = MagicMock()
        mock_response.url = httpx.URL("https://www.amazon.com.br/dp/B09G3HRMVB")
        
        mock_stream.__aenter__.return_value = mock_response
        mock_client.stream.return_value = mock_stream
        
        with patch("src.converters.httpx.AsyncClient", return_value=mock_client_context):
            res = await converters.expandir_e_converter_link(url_encurtada)
            self.assertEqual(res, "https://www.amazon.com.br/dp/B09G3HRMVB?tag=noradardojarb-20")


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
