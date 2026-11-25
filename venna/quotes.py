import re
from datetime import date, timezone
from zoneinfo import ZoneInfo

AREA_SCALE = 10_000
MAX_LINES = 40
LOCAL_TZ = ZoneInfo("America/Sao_Paulo")


class InvalidForm(ValueError):
    pass


def text_field(form, name, max_length, label, *, required=False):
    value = form.get(name, "").strip()
    if required and not value:
        raise InvalidForm(f"Preencha {label}.")
    if len(value) > max_length:
        raise InvalidForm(f"{label.capitalize()} aceita até {max_length} caracteres.")
    return value


def parse_date(value, label):
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise InvalidForm(f"Confira a data de {label}.") from error
    if parsed.isoformat() != value or not 2000 <= parsed.year <= 2100:
        raise InvalidForm(f"Confira a data de {label}.")
    return parsed


def parse_amount(value, decimals, label, *, optional=False, positive=False):
    value = value.strip()
    if not value and optional:
        return None
    if decimals == 2:
        value = re.sub(r"^R\$\s*", "", value)
    if re.fullmatch(r"[1-9][0-9]{0,2}(?:\.[0-9]{3})+(?:,[0-9]+)?", value):
        value = value.replace(".", "")
    match = re.fullmatch(r"([0-9]{1,20})(?:[,.]([0-9]+))?", value)
    if not match or len(match[2] or "") > decimals or int(match[1]) > 999_999_999:
        raise InvalidForm(f"{label} deve ser um número com até {decimals} casas decimais.")
    units = int(match[1]) * 10**decimals + int((match[2] or "").ljust(decimals, "0"))
    if positive and not units:
        raise InvalidForm(f"{label} deve ser maior que zero.")
    return units


def round_line(quantity, rate):
    return (quantity * rate + AREA_SCALE // 2) // AREA_SCALE


def parse_quote(form, lead, seller, today):
    titles = form.getlist("description")
    quantities = form.getlist("quantity")
    rates = form.getlist("rate")
    types = form.getlist("unit")
    count = len(titles)
    if not 1 <= count <= MAX_LINES or any(len(column) != count for column in (quantities, rates, types)):
        raise InvalidForm(f"Inclua de 1 a {MAX_LINES} itens completos.")
    items = []
    for index, (description, quantity, rate, unit) in enumerate(zip(titles, quantities, rates, types), 1):
        description = description.strip()
        if not description or len(description) > 150 or unit not in {"m²", "un"}:
            raise InvalidForm(f"Confira a descrição e a unidade do item {index}.")
        qty = parse_amount(quantity, 4, f"Quantidade do item {index}", positive=True)
        price = parse_amount(rate, 2, f"Valor unitário do item {index}")
        items.append(dict(description=description, quantity=qty, rate=price, unit=unit, total=round_line(qty, price)))
    freight = parse_amount(form.get("freight", ""), 2, "Frete", optional=True)
    valid_until = parse_date(form.get("valid_until", ""), "validade")
    if valid_until and valid_until < today:
        raise InvalidForm("A validade deve ser igual ou posterior à data de emissão.")
    subtotal = sum(item["total"] for item in items)
    return dict(
        items=items,
        subtotal=subtotal,
        freight=freight,
        total=subtotal + (freight or 0),
        seller=seller,
        seller_phone=text_field(form, "seller_phone", 36, "o telefone da vendedora"),
        customer={key: getattr(lead, key) for key in ("name", "phone", "city", "document")},
        valid_until=valid_until.isoformat() if valid_until else "",
        delivery=text_field(form, "delivery", 280, "o prazo de entrega"),
        payment=text_field(form, "payment", 500, "as condições de pagamento"),
        unloading=text_field(form, "unloading", 500, "as condições de descarregamento"),
        remarks=text_field(form, "remarks", 800, "as observações"),
        delivery_cep=text_field(form, "delivery_cep", 9, "o CEP de entrega"),
        delivery_street=text_field(form, "delivery_street", 200, "o logradouro de entrega"),
        delivery_number=text_field(form, "delivery_number", 20, "o número de entrega"),
        delivery_neighborhood=text_field(form, "delivery_neighborhood", 100, "o bairro de entrega"),
        delivery_city=text_field(form, "delivery_city", 100, "a cidade de entrega"),
    )


def number_input(value, decimals):
    whole, fraction = divmod(value, 10**decimals)
    fraction_text = str(fraction).zfill(decimals).rstrip("0")
    return f"{whole},{fraction_text}" if fraction_text else str(whole)


def money(cents):
    whole, fraction = divmod(cents, 100)
    grouped = f"{whole:,}".replace(",", ".")
    return f"R$ {grouped},{fraction:02d}"


def quantity_text(value):
    whole, fraction = divmod(value, AREA_SCALE)
    fraction_text = str(fraction).zfill(4).rstrip("0")
    grouped = f"{whole:,}".replace(",", ".")
    return f"{grouped},{fraction_text}" if fraction_text else grouped


def local_datetime(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(LOCAL_TZ)


def quote_number(quote):
    return f"ORC-{local_datetime(quote.created_at):%Y%m%d}-{quote.id:03d}"


def date_label(value):
    return date.fromisoformat(value).strftime("%d/%m/%Y") if value else "A definir"
