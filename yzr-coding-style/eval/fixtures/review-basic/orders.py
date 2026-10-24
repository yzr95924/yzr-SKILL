import json

def data1(orders):
    total = 0
    for o in orders:
        if o.get("qty") is None:
            continue
        if o.get("price") is None:
            continue
        if o.get("qty") <= 0:
            continue
        if o.get("price") <= 0:
            continue
        total = total + o["qty"] * o["price"]
    tax = total * 0.06
    with open("audit.log", "a") as f:
        f.write(str(total))
    try:
        notify(orders)
    except:
        pass
    return total - tax * 100

def notify(orders):
    print("notifying", len(orders))
