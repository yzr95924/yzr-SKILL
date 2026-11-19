GOLD_DISCOUNT_RATE = 0.8
SILVER_DISCOUNT_RATE = 0.9
NO_DISCOUNT_RATE = 1.0
DISCOUNT_RATES = {
    "gold": GOLD_DISCOUNT_RATE,
    "silver": SILVER_DISCOUNT_RATE,
}


def calc_discount(price, tier):
    return price * DISCOUNT_RATES.get(tier, NO_DISCOUNT_RATE)
