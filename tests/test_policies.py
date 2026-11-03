from pathlib import Path

import pytest

from emporio_agent.policies import Policies

DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def policies():
    return Policies.from_dir(DATA_DIR / "policies")


def test_lookup_returns_the_text_of_a_policy_section(policies):
    text = policies.lookup("horarios")

    assert "Segunda a sexta-feira: 09:00 às 18:00" in text
    assert "Sábado: 09:00 às 13:00" in text


def test_lookup_of_an_unknown_topic_returns_none(policies):
    assert policies.lookup("astrologia") is None


def test_topics_lists_every_available_section(policies):
    assert set(policies.topics()) == {
        "loja", "horarios", "pagamento", "trocas-devolucoes", "frete-entregas",
        "promocoes", "atendimento", "garantia", "privacidade",
    }


@pytest.mark.parametrize(
    "price, max_n",
    [
        (49.9, 1),      # below R$ 50: no installments
        (99, 1),        # 2x would be 49.50 < 50
        (100, 2),
        (149, 2),       # 3x would be 49.67 < 50
        (150, 3),       # 3 x 50
        (319, 3),       # 4x would be 79.75 < 80
        (320, 4),       # 4 x 80
        (479, 5),       # 6x would be 79.83 < 80
        (480, 6),       # 6 x 80
        (699, 6),       # 7x would be 99.86 < 100
        (700, 7),       # 7 x 100
        (1199, 11),     # 12x would be 99.92 < 100
        (1200, 12),     # 12 x 100
        (2199, 12),
    ],
)
def test_installments_follow_the_tier_minimums(policies, price, max_n):
    options = policies.installment_options(price)

    assert [o.n for o in options] == list(range(1, max_n + 1))


def test_installment_value_is_the_price_split_evenly(policies):
    last = policies.installment_options(2199)[-1]

    assert (last.n, last.value) == (12, 183.25)


def test_campo_grande_order_above_500_ships_free(policies):
    quote = policies.shipping_quote(order_total=600, city="Campo Grande")

    assert quote.fee == 0
    assert quote.delivery_time == "1 a 3 dias úteis"


def test_campo_grande_order_below_500_pays_a_flat_35(policies):
    quote = policies.shipping_quote(order_total=499.9, city="campo grande")

    assert quote.fee == 35.0


def test_an_order_of_exactly_500_ships_free(policies):
    # assumption: the manual says "acima de R$ 500" free and "abaixo de R$ 500" R$ 35, leaving 500 open
    assert policies.shipping_quote(order_total=500, city="Campo Grande").fee == 0


def test_other_cities_are_quoted_by_zip_code_with_carrier_options(policies):
    quote = policies.shipping_quote(order_total=300, city="Dourados")

    assert quote.fee is None  # calculated from CEP, weight and dimensions
    assert quote.delivery_time == "PAC 5 a 12 dias úteis; SEDEX 2 a 5 dias úteis; Jadlog 3 a 8 dias úteis"
