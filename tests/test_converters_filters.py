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
        """R$1.100,00 — sem espaço entre R$ e o número (captura o promocional)."""
        self.assertEqual(self._price("De R$3.999 por R$1.100,00"), "R$ 1.100,00")

    def test_preco_inteiro_com_espaco(self):
        """R$ 879 — preço inteiro, sem centavos."""
        self.assertEqual(self._price("Agora por R$ 879!"), "R$ 879")

    def test_preco_com_ponto_milhar(self):
        """R$ 2.499 — ponto como separador de milhar."""
        result = self._price("R$ 2.499 à vista")
        self.assertIn("2.499", result)

    def test_multiplos_precos_retorna_promocional(self):
        """Quando há 'de R$ X por R$ Y', deve retornar o valor promocional (Y)."""
        result = self._price("De R$ 5.000 por R$ 2.499,90")
        self.assertIn("2.499,90", result)

    def test_preco_embutido_em_copywriting(self):
        """Preço no meio de frase com emojis e formatação de canal."""
        text = "🔥 SSD Samsung 1TB — por apenas R$ 379,90 no Pix!\nLink 👇"
        self.assertEqual(self._price(text), "R$ 379,90")

    def test_texto_sem_preco_retorna_vazio(self):
        """Texto sem nenhum padrão de preço deve retornar string vazia."""
        self.assertEqual(self._price("Headset Logitech — link na bio"), "")

    # --- Formatos que representam LIMITAÇÃO CONHECIDA do regex atual ---

    def test_numero_sem_cifrao_capturado(self):
        """'1100' sem R$ agora é corretamente capturado."""
        result = self._price("Notebook por apenas 1100 reais")
        self.assertEqual(result, "R$ 1100")

    def test_preco_em_dolar_nao_capturado(self):
        """USD $ 99 não deve ser capturado — padrão é estritamente R$."""
        self.assertEqual(self._price("Produto importado $ 99 dólares"), "")


# ===========================================================================
# 1B. EXTRAÇÃO DE PARCELAMENTO — _extract_installments
# ===========================================================================

class TestExtractInstallments(unittest.TestCase):
    """Valida _extract_installments contra os formatos comuns de parcelamento."""

    def _installments(self, text: str) -> str:
        return converters._extract_installments(text)

    def test_parcelamento_com_em(self):
        self.assertEqual(self._installments("por R$ 307 em 6x na Amazon"), "em 6x")

    def test_parcelamento_com_ate(self):
        self.assertEqual(self._installments("ou 3.419 até 10x"), "até 10x")

    def test_parcelamento_com_em_ate_sem_juros(self):
        self.assertEqual(self._installments("Teclado em até 12x sem juros no cartão"), "em até 12x sem juros")

    def test_quantidade_pura_nao_capturada(self):
        self.assertEqual(self._installments("Contém 5x fones de ouvido na caixa"), "")


# ===========================================================================
# 1C. EXTRAÇÃO DE CUPOM — _extract_coupon
# ===========================================================================

class TestExtractCoupon(unittest.TestCase):
    """Valida _extract_coupon contra os formatos comuns de cupom."""

    def _coupon(self, text: str) -> str:
        return converters._extract_coupon(text)

    def test_cupom_simples(self):
        self.assertEqual(self._coupon("Use o cupom: NOTE100 para ganhar desconto!"), "NOTE100")

    def test_cupom_com_emoji_e_negrito(self):
        self.assertEqual(self._coupon("🎟 CUPOM: **POUPEAGORA + NOTE300**"), "POUPEAGORA + NOTE300")

    def test_cupom_lowercase_ignorando(self):
        self.assertEqual(self._coupon("🎟️ cupom: cupom inválido com letras minúsculas"), "")

    def test_sem_cupom(self):
        self.assertEqual(self._coupon("Sem cupom e sem prime apenas preço normal"), "")


# ===========================================================================
# 1D. VERIFICAÇÃO DE PRIME — _check_prime
# ===========================================================================

class TestCheckPrime(unittest.TestCase):
    """Valida _check_prime contra frases que indicam exclusividade Prime."""

    def _prime(self, text: str) -> bool:
        return converters._check_prime(text)

    def test_prime_exclusivo_completo(self):
        self.assertTrue(self._prime("🔹 Oferta exclusiva membros Amazon Prime"))

    def test_prime_exclusivo_simples(self):
        self.assertTrue(self._prime("Exclusivo Prime"))

    def test_prime_sem_indicativo(self):
        self.assertFalse(self._prime("Sem cupom e sem prime apenas preço normal"))


# ===========================================================================
# 1D-2. VERIFICAÇÃO DE PROGRAME E POUPE — _check_subscribe_and_save
# ===========================================================================

class TestCheckSubscribeAndSave(unittest.TestCase):
    """Valida _check_subscribe_and_save contra frases que indicam Programe e Poupe."""

    def _sns(self, text: str) -> bool:
        return converters._check_subscribe_and_save(text)

    def test_sns_comum(self):
        self.assertTrue(self._sns("Compre com Programe e Poupe para desconto"))

    def test_sns_com_ampersand(self):
        self.assertTrue(self._sns("Ative o Programe & Poupe no carrinho"))

    def test_sns_lowercase(self):
        self.assertTrue(self._sns("valor no programe e poupe no site"))

    def test_sns_sem_indicativo(self):
        self.assertFalse(self._sns("Preço normal sem assinatura"))


# ===========================================================================
# 1E. EXTRAÇÃO DE NOME DO PRODUTO — _extract_product_name
# ===========================================================================

class TestExtractProductName(unittest.TestCase):
    """Valida _extract_product_name contra teasers e linhas de copywriting."""

    def _product_name(self, text: str) -> str:
        return converters._extract_product_name(text)

    def test_evita_teaser_inicial_aoc(self):
        text = (
            "Para sua Sindrome de Pro Player\n\n"
            "🔥Monitor Gamer AOC Destiny 24,5 Polegadas, 240Hz\n\n"
            "💵R$ 899\n"
            "🎟Cupom: VAIPROGOL\n"
            "https://link.amazon/B0a5e17nA"
        )
        self.assertEqual(self._product_name(text), "Monitor Gamer AOC Destiny 24,5 Polegadas, 240Hz")

    def test_evita_teaser_inicial_tv(self):
        text = (
            "CABE EM QUALQUER CANTIN DA CASA\n\n"
            "📺 **Smart TV 32\" Philco Roku TV**\n\n"
            "🔥 ~~DE 999,99~~ | POR 699,90"
        )
        self.assertEqual(self._product_name(text), "Smart TV 32\" Philco Roku TV")

    def test_evita_teaser_inicial_notebook(self):
        text = (
            "TROCAR TEU NOTE QUE TA CAPENGA JÁ\n\n"
            "💻 **Notebook Lenovo Ideapad Slim 3**\n\n"
            "🔥 POR 3.229,05"
        )
        self.assertEqual(self._product_name(text), "Notebook Lenovo Ideapad Slim 3")

    def test_evita_link_como_nome_de_produto(self):
        text = (
            "SuaviPan Bolinho de Proteína Zero Açúcar Sabor Baunilha com Recheio Sabor Chocolate Caixa com 12 Unidades de 55g - R$26\n\n"
            "https://link.amazon/B0aXFlf8l"
        )
        self.assertEqual(
            self._product_name(text),
            "SuaviPan Bolinho de Proteína Zero Açúcar Sabor Baunilha com Recheio Sabor Chocol"
        )

    def test_limpa_preco_e_hifen_do_final(self):
        text = "Mawwal - Hiyam Eau De Parfum Masculino 100ml - R$50\n\nhttps://link.amazon/B02fADu0l"
        self.assertEqual(self._product_name(text), "Mawwal - Hiyam Eau De Parfum Masculino 100ml")

    def test_evita_linha_de_venda_como_nome_de_produto(self):
        text = (
            "Kit Gillette Mach3 10 cargas + Necessaire, Higiene Pessoal, Cuidado com a barba, Lâminas e Aparelhos de Barbear\n"
            "🪒🪒🪒🪒\n\n"
            "Vendido e Enviado pela Amazon\n\n"
            "Por apenas: R$76,78\n\n"
            "Frete expresso grátis (prime)\n\n"
            "https://link.amazon/B0ciJHsm6"
        )
        self.assertEqual(
            self._product_name(text),
            "Kit Gillette Mach3 10 cargas + Necessaire, Higiene Pessoal, Cuidado com a barba"
        )


# ===========================================================================
# 1F. EXTRAÇÃO DE TEASER — _extract_teaser
# ===========================================================================

class TestExtractTeaser(unittest.TestCase):
    """Valida _extract_teaser contra formatos e exclusões."""

    def _teaser(self, text: str, product_name: str) -> str:
        return converters._extract_teaser(text, product_name)

    def test_teaser_valido_aoc(self):
        text = (
            "Para sua Sindrome de Pro Player\n\n"
            "🔥Monitor Gamer AOC Destiny 24,5 Polegadas, 240Hz\n\n"
            "💵R$ 899\n"
            "https://link.amazon/B0a5e17nA"
        )
        pn = "Monitor Gamer AOC Destiny 24,5 Polegadas, 240Hz"
        self.assertEqual(self._teaser(text, pn), "Para sua Sindrome de Pro Player")

    def test_teaser_valido_tv(self):
        text = (
            "CABE EM QUALQUER CANTIN DA CASA\n\n"
            "📺 **Smart TV 32\" Philco Roku TV**\n\n"
            "🔥 POR 699,90"
        )
        pn = "Smart TV 32\" Philco Roku TV"
        self.assertEqual(self._teaser(text, pn), "CABE EM QUALQUER CANTIN DA CASA")

    def test_sem_teaser_se_for_igual_ao_produto(self):
        text = "🔥 SSD Samsung 1TB — por apenas R$ 379,90 no Pix!"
        pn = "SSD Samsung 1TB — por apenas R$ 379,90 no Pix!"
        self.assertEqual(self._teaser(text, pn), "")


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

    TRIGGERS = set(converters._TRIGGERS)

    def _assert_post_structure(self, result: str, expect_price=True, expect_url=True):
        self.assertIn("🛒", result)
        self.assertIn("<b>", result)
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
        self.assertIsNone(result)

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

    def test_copywriting_user_example(self):
        """Testa o copywriting do exemplo do usuário: título/produto, breve descrição, valor e link."""
        text = (
            "😉 VAI DEIXAR SEU CABELO PERFEITO!\n\n"
            "👱🏻‍♀️ Eudora Siàge Cica Therapy Leave-in 100ml\n\n"
            "🔥 por R$ 30 na Amazon\n\n"
            "🛒 https://amzn.to/4f1NziF\n\n"
            "🚛 Frete grátis | Amazon Prime"
        )
        result = converters.process(text)
        self.assertIsNotNone(result)
        # Deve ter o nome do produto no título (negrito)
        self.assertIn("<b>Eudora Siàge Cica Therapy Leave-in 100ml</b>", result)
        # Deve ter a breve descrição (gatilho original) como itálico
        self.assertIn("<i>VAI DEIXAR SEU CABELO PERFEITO!</i>", result)
        # Deve ter o preço
        self.assertIn("<b>R$ 30</b>", result)
        # Deve ter a URL convertida
        self.assertIn("https://amzn.to/4f1NziF", result)
        # Não deve conter gatilhos mentais redundantes no início
        for trigger in converters._TRIGGERS:
            self.assertNotIn(trigger, result)

    def test_copywriting_programe_e_poupe(self):
        """Testa o processamento de anúncio que contém 'programe e poupe'."""
        text = (
            "🔥 Sabão em Pó Omo Sanitizante 1,6kg\n\n"
            "Preço: R$ 13,25 (Valor se comprado com programe e poupe, normal é R$ 14,72)\n\n"
            "Link: https://www.amazon.com.br/dp/B07PR12345"
        )
        result = converters.process(text)
        self.assertIsNotNone(result)
        self.assertIn("<b>Sabão em Pó Omo Sanitizante 1,6kg</b>", result)
        self.assertIn("<b>R$ 13,25</b>", result)
        self.assertIn("Valor com Programe e Poupe", result)
        self.assertIn("https://www.amazon.com.br/dp/B07PR12345", result)


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

    def test_ventilador_de_mesa_aprovado(self):
        self.assertTrue(filters.is_relevant("Ventilador de Mesa Arno 40cm por R$ 189"))
        self.assertTrue(filters.is_relevant("Ventilador de mesa Mondial 30cm por R$ 120"))

    def test_mop_limpeza_aprovado(self):
        self.assertTrue(filters.is_relevant("Mop com Balde e Esfregão Simplo por R$ 49"))

    def test_beleza_saude_aprovada(self):
        self.assertTrue(filters.is_relevant("Whey Protein Growth 1kg chocolate R$ 89,90"))

    def test_pessoal_aprovada(self):
        self.assertTrue(filters.is_relevant("Tênis Nike Air Max 36 por R$ 399"))

    def test_supermercado_aprovado(self):
        self.assertTrue(filters.is_relevant("Batata Frita Pringles Tripack por R$ 25"))
        self.assertTrue(filters.is_relevant("Chocolate Lacta 80g por R$ 5"))
        self.assertTrue(filters.is_relevant("Heinz Pack Ketchup 397G + Maionese 390G"))


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

    def test_vestuario_camiseta_aprovada(self):
        self.assertTrue(filters.is_relevant("Camiseta Nike Dri-Fit por R$ 89 — 30% off"))

    def test_vestuario_calcas_aprovada(self):
        self.assertTrue(filters.is_relevant("Calça Jeans Slim por R$ 120 — 20% off"))

    def test_eletrodomestico_geladeira_bloqueado(self):
        self.assertFalse(filters.is_relevant("Geladeira Brastemp 400L frost free R$ 2.800"))

    def test_eletrodomestico_microondas_bloqueado(self):
        self.assertFalse(filters.is_relevant("Microondas LG 30L por R$ 399 — 15% off"))

    def test_cozinha_panela_bloqueada(self):
        self.assertFalse(filters.is_relevant("Panela de pressão elétrica R$ 179"))

    def test_cerveja_bloqueada(self):
        self.assertFalse(filters.is_relevant("Baden Baden Cerveja Ale Golden, Pack 6 unids 350ml por R$ 29"))
        self.assertFalse(filters.is_relevant("Cerveja Heineken Lata 350ml"))
        self.assertFalse(filters.is_relevant("Chopp Stella Artois"))
        self.assertFalse(filters.is_relevant("Cervejas variadas em promoção"))

    # --- Edge case: categoria válida + keyword excluída no mesmo texto ---

    def test_categoria_valida_com_excluida_bloqueado(self):
        """Texto com notebook (válido) E geladeira (excluído) deve ser BLOQUEADO."""
        text = "Kit: Notebook Dell + Geladeira Consul por R$ 3.000 — 25% off"
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

    def test_coupon_announcement_is_relevant_only_if_enabled(self):
        coupon_text = (
            "💥 CHEGOU MAIS UM CUPOM AMAZON!\n"
            "🤑 Ganhe R$ 100 OFF nas compras acima de R$ 699.\n"
            "🏷️ Cupom: CHEGOU"
        )
        
        # Por padrão, ENABLE_COUPONS deve ser False
        with patch("src.filters.settings.ENABLE_COUPONS", False):
            self.assertFalse(filters.is_relevant(coupon_text))
            
        with patch("src.filters.settings.ENABLE_COUPONS", True):
            self.assertTrue(filters.is_relevant(coupon_text))



class TestGetCategory(unittest.TestCase):
    """Valida a detecção de categoria pelo get_category()."""

    def test_tecnologia(self):
        self.assertEqual(filters.get_category("Notebook Dell i7"), "tecnologia")

    def test_smart_home(self):
        self.assertEqual(filters.get_category("Echo Dot com Alexa"), "smart_home")

    def test_ventilador_de_mesa_smart_home(self):
        self.assertEqual(filters.get_category("Ventilador de Mesa Arno"), "smart_home")

    def test_mop_smart_home(self):
        self.assertEqual(filters.get_category("Mop com Balde e Esfregão"), "smart_home")

    def test_beleza_saude(self):
        self.assertEqual(filters.get_category("Whey Protein 1kg"), "beleza_saude")

    def test_pessoal(self):
        self.assertEqual(filters.get_category("Tênis Adidas Ultra Boost"), "pessoal")

    def test_supermercado(self):
        self.assertEqual(filters.get_category("Batata Frita Pringles"), "supermercado")
        self.assertEqual(filters.get_category("Chocolate Lacta"), "supermercado")
        self.assertEqual(filters.get_category("Heinz Pack Ketchup + Maionese"), "supermercado")


    def test_vestuario(self):
        self.assertEqual(filters.get_category("Kit 12 Cuecas Boxer Reebok"), "vestuario")
        self.assertEqual(filters.get_category("Camiseta Nike Dri-Fit"), "vestuario")

    def test_sem_categoria_retorna_none(self):
        self.assertIsNone(filters.get_category("Produto genérico sem categoria"))

    def test_coupon_category_only_if_enabled(self):
        coupon_text = (
            "💥 CHEGOU MAIS UM CUPOM AMAZON!\n"
            "🤑 Ganhe R$ 100 OFF nas compras acima de R$ 699.\n"
            "🏷️ Cupom: CHEGOU"
        )
        
        with patch("src.filters.settings.ENABLE_COUPONS", False):
            self.assertIsNone(filters.get_category(coupon_text))
            
        with patch("src.filters.settings.ENABLE_COUPONS", True):
            self.assertEqual(filters.get_category(coupon_text), "cupons")




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
# 7. PIPELINE COMPLETO ASSÍNCRONO — process_async()
# ===========================================================================

class TestProcessAsync(unittest.IsolatedAsyncioTestCase):
    """Valida o output HTML do process_async() de forma assíncrona."""

    TRIGGERS = set(converters._TRIGGERS)

    def _assert_post_structure(self, result: str, expect_price=True, expect_url=True):
        self.assertIn("🛒", result)
        self.assertIn("<b>", result)
        if expect_price:
            self.assertIn("💰", result)
        if expect_url:
            self.assertIn("🔗", result)
            self.assertIn(AFFILIATE_TAG, result)

    async def test_copywriting_completo_padrao_async(self):
        text = (
            "🛒 Notebook Dell Inspiron 15\n"
            "De R$ 4.999 por R$ 2.799,90 — 44% off\n"
            "https://www.amazon.com.br/dp/B09XYZ?tag=outro-20"
        )
        result = await converters.process_async(text)
        self._assert_post_structure(result)
        self.assertNotIn("outro-20", result)

    async def test_copywriting_sem_preco_async(self):
        text = "💻 Monitor LG 27' 4K\nhttps://www.amazon.com.br/dp/B09XYZ"
        result = await converters.process_async(text)
        self._assert_post_structure(result, expect_price=False)

    async def test_copywriting_com_link_encurtado_resolvido_async(self):
        text = (
            "🛒 Notebook Dell Inspiron 15\n"
            "De R$ 4.999 por R$ 2.799,90\n"
            "https://amzn.to/3xyz"
        )
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
            result = await converters.process_async(text)
            self._assert_post_structure(result)
            self.assertIn("https://www.amazon.com.br/dp/B09G3HRMVB?tag=noradardojarb-20", result)


class TestExtractAsin(unittest.TestCase):
    """Valida a extração de ASIN de URLs da Amazon e blocos de texto."""

    def test_extract_asin_from_various_url_formats(self):
        # 1. Formato padrão dp
        url1 = "https://www.amazon.com.br/dp/B0C3MB3B52"
        self.assertEqual(converters.extract_asin(url1), "B0C3MB3B52")

        # 2. Formato gp/product
        url2 = "https://www.amazon.com.br/gp/product/B0C3MB3B52"
        self.assertEqual(converters.extract_asin(url2), "B0C3MB3B52")

        # 3. Formato com nome do produto antes do dp
        url3 = "https://www.amazon.com.br/Echo-Dot-5%C2%AA-gera%C3%A7%C3%A3o-Preta/dp/B09B8V1C6N"
        self.assertEqual(converters.extract_asin(url3), "B09B8V1C6N")

        # 4. Formato gp/aw/d
        url4 = "https://www.amazon.com.br/gp/aw/d/B09B8V1C6N"
        self.assertEqual(converters.extract_asin(url4), "B09B8V1C6N")

        # 5. Formato com parâmetros na URL
        url5 = "https://amazon.com.br/dp/B09B8V1C6N/ref=nosim?tag=noradardojarb-20"
        self.assertEqual(converters.extract_asin(url5), "B09B8V1C6N")

        # 6. Formato com query parameter asin=...
        url6 = "https://www.amazon.com.br/search?query=notebook&asin=B0C3MB3B52"
        self.assertEqual(converters.extract_asin(url6), "B0C3MB3B52")

        # 7. Formato com lowercase no ASIN deve retornar em UPPERCASE
        url7 = "https://www.amazon.com.br/dp/b0c3mb3b52"
        self.assertEqual(converters.extract_asin(url7), "B0C3MB3B52")

    def test_extract_asin_from_text_block(self):
        # Texto contendo um link Amazon
        text = (
            "🔥 OFERTA PRIME DAY 🔥\n\n"
            "🛒 Notebook Dell Inspiron 15\n"
            "De R$ 4.999 por R$ 2.799,90\n\n"
            "🔗 Link: https://www.amazon.com.br/dp/B09G3HRMVB?tag=noradardojarb-20\n"
        )
        self.assertEqual(converters.extract_asin(text), "B09G3HRMVB")

    def test_extract_asin_invalid_or_missing(self):
        # Link que não é Amazon
        url_non_amazon = "https://www.magazineluiza.com.br/produto/12345"
        self.assertIsNone(converters.extract_asin(url_non_amazon))

        # Texto vazio/None
        self.assertIsNone(converters.extract_asin(""))
        self.assertIsNone(converters.extract_asin(None))




# ===========================================================================
# 4. ANÚNCIOS DE CUPONS GERAIS
# ===========================================================================

class TestCouponAnnouncements(unittest.TestCase):
    """Valida a detecção e formatação de anúncios de cupons gerais."""

    def setUp(self):
        self.original_enable_coupons = converters.settings.ENABLE_COUPONS
        converters.settings.ENABLE_COUPONS = True

    def tearDown(self):
        converters.settings.ENABLE_COUPONS = self.original_enable_coupons


    def test_detection_coupon_announcement(self):
        # 1. Anúncio geral de cupom
        text1 = (
            "💥 CHEGOU MAIS UM CUPOM AMAZON!\n"
            "🤑 Ganhe R$ 100 OFF nas compras acima de R$ 699.\n"
            "🛒 https://amzn.to/4rg5Zl0\n"
            "🏷️ Cupom: CHEGOU\n"
            "⚠️ Válido para alguns produtos. Faça o teste.\n"
            "💙 Exclusivo membros prime"
        )
        self.assertTrue(converters._is_coupon_announcement(text1))

        # 2. Oferta de produto com cupom (deve ser falsa para anúncio geral)
        text2 = (
            "💻 Notebook Lenovo IdeaPad Ryzen 5\n"
            "🔥 Menor preço do ano!\n"
            "💰 De R$ 3.000 por R$ 2.499\n"
            "🎟️ Use o cupom: LENOVO50\n"
            "🛒 https://amzn.to/3ryG4r\n"
        )
        self.assertFalse(converters._is_coupon_announcement(text2))

        # 3. Oferta de fone de ouvido com cupom (contém a preposição 'de' que causava falso positivo)
        text3 = (
            "ESSE OUVIDO MERECE JBL\n\n"
            "🎧 Fone de Ouvido Over-Ear JBL Tune 530BT\n\n"
            "🔥 DE 299 | POR 155,22 no Pix\n"
            "🎟️ Resgate o cupom: VAMOPRIMEDAY\n\n"
            "🔗 https://amzn.divulgador.link/a0sya1YR\n"
            "🔹 Oferta exclusiva membros Amazon Prime"
        )
        self.assertFalse(converters._is_coupon_announcement(text3))

    def test_coupon_benefit_extraction(self):
        text = (
            "💥 CHEGOU MAIS UM CUPOM AMAZON!\n"
            "🤑 Ganhe R$ 100 OFF nas compras acima de R$ 699.\n"
            "🏷️ Cupom: CHEGOU"
        )
        self.assertEqual(
            converters._extract_coupon_benefit(text),
            "Ganhe R$ 100 OFF nas compras acima de R$ 699."
        )

    def test_coupon_formatting(self):
        text = (
            "💥 CHEGOU MAIS UM CUPOM AMAZON!\n"
            "🤑 Ganhe R$ 100 OFF nas compras acima de R$ 699.\n"
            "🛒 https://amzn.to/4rg5Zl0\n"
            "🏷️ Cupom: CHEGOU\n"
            "⚠️ Válido para alguns produtos. Faça o teste.\n"
            "💙 Exclusivo membros prime"
        )
        
        # Como o process normal necessita de requests mockados, testamos o fluxo de formatação interna
        coupon = converters._extract_coupon(text)
        benefit = converters._extract_coupon_benefit(text)
        has_prime = converters._check_prime(text)
        teaser = converters._extract_teaser(text, benefit)
        formatted = converters._format_coupon_post(benefit, "https://amazon.com.br/dp/B0XXXX", coupon, has_prime, teaser)
        
        self.assertIn("🔥 CUPOM AMAZON 🔥", formatted)
        self.assertIn("Ganhe R$ 100 OFF nas compras acima de R$ 699.", formatted)
        self.assertIn("Cupom: <b>CHEGOU</b>", formatted)
        self.assertIn("Exclusivo Membros Prime", formatted)


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
