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
