GOLD_DISCOUNT_RATE = 0.8
SILVER_DISCOUNT_RATE = 0.9
NO_DISCOUNT_RATE = 1.0
DISCOUNT_RATES = {
    "gold": GOLD_DISCOUNT_RATE,
    "silver": SILVER_DISCOUNT_RATE,
}


def calc_discount(price, tier):
    return price * DISCOUNT_RATES.get(tier, NO_DISCOUNT_RATE)


def test_gold_discount():
    # Goal: verify gold-tier orders receive the configured discount
    # Case: a gold-tier order with subtotal 100
    # Checks: discounted subtotal is 80
    # Steps: call calc_discount and compare the result with 80
    assert calc_discount(100, "gold") == 80


def test_silver_discount():
    assert calc_discount(100, "silver") == 90
