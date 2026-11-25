from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, LongTable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .quotes import date_label, local_datetime, money, quantity_text, quote_number

INK = colors.HexColor("#292123")
MUTED = colors.HexColor("#66554E")
BRONZE = colors.HexColor("#80573D")
CHAMPAGNE = colors.HexColor("#E8CDB0")
CREAM = colors.HexColor("#F8F2EA")
RULE = colors.HexColor("#E3D7CA")
PAPER = colors.HexColor("#FFFDFA")
WIDTH = A4[0] - 96
FONTS = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("Venna-Regular", str(FONTS / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("Venna-Bold", str(FONTS / "VeraBd.ttf")))


def paragraph(text, *, font="Venna-Regular", size=9, color=INK, align=0, leading=None):
    safe = escape(str(text or "—")).replace("\n", "<br/>")
    style = ParagraphStyle("venna", fontName=font, fontSize=size, leading=leading or size * 1.35,
                           textColor=color, alignment=align, splitLongWords=True)
    return Paragraph(safe, style)


def label(text):
    return paragraph(text.upper(), font="Venna-Bold", size=7, color=BRONZE)


def heading(text):
    return paragraph(text, font="Venna-Regular", size=17)


def pair(name, value):
    return [label(name), Spacer(1, 3), paragraph(value)]


def information_panel(rows):
    table = Table(rows, colWidths=[WIDTH / 2] * 2, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CREAM),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def draw_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(RULE)
    canvas.line(48, 42, A4[0] - 48, 42)
    canvas.setFont("Venna-Regular", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(48, 29, "VENNA  ·  Mármores e Revestimentos  ·  CNPJ 69.965.547/0001-28")
    canvas.drawRightString(A4[0] - 48, 29, f"Página {doc.page}")
    canvas.restoreState()


def quote_pdf(quote, revision):
    stream = BytesIO()
    code = quote_number(quote)
    data = revision.data
    client = data["customer"]
    issued = local_datetime(revision.issued_at)
    document = SimpleDocTemplate(
        stream, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=37, bottomMargin=57,
        title=f"VENNA | {code} V{revision.number}", author="VENNA Mármores e Revestimentos",
    )
    # Use the actual frame's width (ReportLab adds 6 pt of padding on each side).
    content_width = WIDTH
    issued_label = issued.strftime("%d/%m/%Y")
    heading_bar = Table([
        [paragraph("V E N N A", font="Venna-Regular", size=28, color=PAPER),
         paragraph("PROPOSTA COMERCIAL", font="Venna-Bold", size=8, color=CHAMPAGNE, align=TA_RIGHT)],
        [paragraph("MÁRMORES E REVESTIMENTOS", size=8, color=CHAMPAGNE),
         paragraph(f"{code}  ·  Revisão {revision.number}", size=9, color=PAPER, align=TA_RIGHT)],
    ], colWidths=[content_width * .53, content_width * .47])
    heading_bar.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), INK), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 12), ("BOTTOMPADDING", (0, 1), (-1, 1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 15), ("RIGHTPADDING", (0, 0), (-1, -1), 15),
    ]))

    document_info = information_panel([
        [pair("Emissão", issued_label), pair("Responsável", data["seller"])],
        [pair("Validade", date_label(data["valid_until"])), pair("Telefone comercial", data["seller_phone"])],
    ])
    customer_info = information_panel([
        [pair("Nome ou empresa", client["name"]), pair("Telefone", client["phone"])],
        [pair("Cidade/UF", client["city"]), pair("CPF/CNPJ", client["document"])],
    ])

    delivery_parts = [data.get("delivery_street", ""), data.get("delivery_number", ""),
                      data.get("delivery_neighborhood", ""), data.get("delivery_city", ""),
                      data.get("delivery_cep", "")]
    delivery_address = ", ".join(p for p in delivery_parts if p)
    has_delivery = bool(delivery_address)

    widths = [39, content_width - 290, 87, 67, 97]
    product_rows = [[paragraph(text, font="Venna-Bold", size=8, color=PAPER, align=alignment)
                     for text, alignment in (("Item", TA_CENTER), ("Produto ou serviço", 0),
                                             ("Valor unitário", TA_RIGHT), ("Quantidade", TA_RIGHT),
                                             ("Valor total", TA_RIGHT))]]
    for index, item in enumerate(data["items"], 1):
        product_rows.append([
            paragraph(f"{index:02d}", size=8, align=TA_CENTER), paragraph(item["description"]),
            paragraph(money(item["rate"]), size=8.5, align=TA_RIGHT),
            paragraph(f'{quantity_text(item["quantity"])} {item["unit"]}', size=8.5, align=TA_RIGHT),
            paragraph(money(item["total"]), size=8.5, align=TA_RIGHT),
        ])
    items = LongTable(product_rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRONZE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER, CREAM]),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LINEBELOW", (0, 1), (-1, -1), .35, RULE),
    ]))

    freight_known = data["freight"] is not None
    totals = Table([
        [paragraph("Subtotal"), paragraph(money(data["subtotal"]), align=TA_RIGHT)],
        [paragraph("Frete"), paragraph(money(data["freight"]) if freight_known else "A confirmar", align=TA_RIGHT)],
        [paragraph("Valor total" if freight_known else "Total sem frete", font="Venna-Bold", color=PAPER, size=11),
         paragraph(money(data["total"]), font="Venna-Bold", color=CHAMPAGNE, size=12, align=TA_RIGHT)],
    ], colWidths=[content_width / 2] * 2, hAlign="LEFT")
    totals.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 1), CREAM), ("BACKGROUND", (0, 2), (-1, 2), INK),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))

    story = [heading_bar, Spacer(1, 11), document_info, Spacer(1, 13),
             heading("Dados do cliente"), Spacer(1, 6), customer_info, Spacer(1, 13)]
    if has_delivery:
        delivery_info = information_panel([[pair("Endereço de entrega", delivery_address), pair("CEP", data.get("delivery_cep", ""))]])
        story += [heading("Local de entrega"), Spacer(1, 6), delivery_info, Spacer(1, 13)]
    story += [heading("Produtos e serviços"), Spacer(1, 6), items, Spacer(1, 9), totals]
    terms = [
        ("Prazo de entrega", data["delivery"]),
        ("Formas e condições de pagamento", data["payment"]),
        ("Descarregamento", data["unloading"]),
        ("Observações", data["remarks"]),
    ]
    terms = [(name, value) for name, value in terms if value]
    for index, (name, value) in enumerate(terms):
        prefix = [Spacer(1, 14), heading("Condições comerciais"), Spacer(1, 7)] if index == 0 else [Spacer(1, 7)]
        story.append(KeepTogether([*prefix, label(name), Spacer(1, 3), paragraph(value)]))
    document.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    stream.seek(0)
    return stream
