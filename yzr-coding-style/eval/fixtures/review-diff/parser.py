def parse_row(line):
    parts = line.split(",")
    if len(parts) != 3:
        return None
    name, qty, price = parts
    if not qty.isdigit() or not price.isdigit():
        return None
    return {"name": name, "qty": int(qty), "price": int(price)}

def legacy_check(text):
    if text is None:
        return False
    if len(text) == 0:
        return False
    if "\x00" in text:
        return False
    return True
