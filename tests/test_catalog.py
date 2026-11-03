from pathlib import Path

import pytest

from emporio_agent.catalog import Catalog

DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def catalog():
    return Catalog.from_csv_dir(DATA_DIR)


def test_get_product_returns_name_category_and_price(catalog):
    product = catalog.get_product(95)

    assert product.name == "Takamine GD20 Dreadnought Natural"
    assert product.category == "Violões"
    assert product.list_price == 2199.0
    assert product.price == 2199.0
    assert product.discount_percent is None
    assert product.availability == "available"


def test_active_promotion_lowers_the_price_and_keeps_the_original(catalog):
    product = catalog.get_product(94)  # Taylor 110e, 8% off, promotion is_active=1

    assert product.list_price == 5999.0
    assert product.discount_percent == 8
    assert product.price == 5519.08


def test_inactive_promotions_are_ignored(catalog):
    product = catalog.get_product(93)  # Martin D-28 has two promotions, both is_active=0

    assert product.price == product.list_price == 11499.0
    assert product.discount_percent is None


@pytest.mark.parametrize(
    "product_id, expected",
    [
        (95, "available"),         # active, stock 5
        (96, "out_of_stock"),      # active, stock 0
        (113, "discontinued"),     # discontinued, stock 0
        (136, "discontinued"),     # discontinued but CSV shows stock 13: status wins
        (130, "coming_soon"),      # coming_soon but CSV shows stock 2: status wins
    ],
)
def test_availability_follows_status_first_then_stock(catalog, product_id, expected):
    assert catalog.get_product(product_id).availability == expected


def ids(products):
    return [p.id for p in products]


def test_search_by_model_name_ignores_case_and_requires_every_word(catalog):
    assert ids(catalog.search_products(query="takamine GD20")) == [95]


def test_search_by_brand_returns_every_model_of_that_brand(catalog):
    assert set(ids(catalog.search_products(query="Takamine"))) == {95, 100, 105, 115}


def test_search_ignores_accents(catalog):
    results = catalog.search_products(query="violao nylon")  # category is "Violões"

    assert 81 in ids(results)  # Yamaha C40 Nylon Natural


def test_violoes_up_to_1000_reais(catalog):
    results = catalog.search_products(category="Violões", max_price=1000, limit=20)

    # literal list taken from the CSV: every Violões product whose price is <= 1000
    assert set(ids(results)) == {81, 82, 83, 84, 85, 86, 87, 88, 89, 91, 96, 107, 112, 113}


def test_price_filter_uses_the_promotional_price(catalog):
    # Ohana CK-20: list 549, 20% off => 439.20
    results = catalog.search_products(category="Ukuleles", max_price=450)

    assert 121 in ids(results)
    assert all(p.price <= 450 for p in results)


def test_min_price_filter(catalog):
    results = catalog.search_products(category="Violões", min_price=11000)

    assert set(ids(results)) == {93, 108}  # Martin D-28 11499 and D-28E 12000


def test_results_are_capped_at_ten_by_default_and_unavailable_ones_rank_last(catalog):
    results = catalog.search_products(category="Violões", max_price=1000)

    assert len(results) == 10
    assert all(p.availability == "available" for p in results)  # 96 and 113 are cut


def test_limit_can_be_raised(catalog):
    results = catalog.search_products(category="Violões", max_price=1000, limit=20)

    assert len(results) == 14


def test_discounted_products_come_before_full_price_ones(catalog):
    results = catalog.search_products(category="Ukuleles", limit=20)

    # 127 (Kalani, 10% off, 323.10) and 121 (Ohana, 20% off, 439.20) are the only active promotions
    assert ids(results)[:2] == [127, 121]
    assert ids(results)[-1] == 130  # coming_soon goes last


def test_text_relevance_beats_discount(catalog):
    results = catalog.search_products(query="nylon")

    # 121 (Ohana ukulele) is discounted but only has nylon strings in its specs
    assert "nylon" in results[0].name.lower()
    assert results[0].id != 121


def test_unknown_product_id_returns_none(catalog):
    assert catalog.get_product(9999) is None


def test_search_with_no_match_returns_an_empty_list(catalog):
    assert catalog.search_products(query="trompete de ouro maciço") == []


def test_search_with_no_criteria_returns_nothing(catalog):
    assert catalog.search_products() == []


@pytest.mark.parametrize(
    "unavailable_id, expected",
    [
        (96, [107, 82, 86]),     # out of stock, 799.90: same category, +-30%, closest price first
        (113, [86, 87, 107]),    # discontinued, 749
        (130, [126, 129, 125]),  # coming soon, 1749; price tie broken by lower price
    ],
)
def test_alternatives_are_available_same_category_within_30_percent_closest_first(
    catalog, unavailable_id, expected
):
    assert ids(catalog.suggest_alternatives(unavailable_id)) == expected


def test_alternatives_for_an_unknown_product_are_empty(catalog):
    assert catalog.suggest_alternatives(9999) == []
