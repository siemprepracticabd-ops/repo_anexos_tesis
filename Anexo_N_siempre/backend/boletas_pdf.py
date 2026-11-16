"""genera la planilla general y las boletas de pago en pdf con reportlab"""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

EMPRESA = "Tiendas Siempre"
GRIS_ENCABEZADO = colors.HexColor("#374151")
GRIS_CLARO = colors.HexColor("#F3F4F6")
ESTILOS = getSampleStyleSheet()
FORMAS_DE_PAGO = {"salario_fijo": "Salario fijo", "por_hora": "Por hora", "por_turno": "Por turno"}
ESTADOS = {"generada": "Pendiente de pago", "pagada": "Pagada"}


def quetzales(monto):
    return f"Q {float(monto):,.2f}"


def _fecha(dia):
    return dia.strftime("%d/%m/%Y")


def _cantidad(valor):
    numero = float(valor)
    return str(int(numero)) if numero.is_integer() else f"{numero:,.2f}"


def _horas(minutos):
    return f"{minutos // 60}h {minutos % 60:02d}min"


def _celda(texto, derecha=False, negrita=False, tamano=8.5):
    estilo = ParagraphStyle(
        "celda",
        parent=ESTILOS["Normal"],
        fontName="Helvetica-Bold" if negrita else "Helvetica",
        fontSize=tamano,
        leading=tamano + 2,
        alignment=2 if derecha else 0,
    )
    return Paragraph(escape(str(texto)), estilo)


def _encabezado(titulo, periodo):
    return [
        Paragraph(escape(EMPRESA), ESTILOS["Title"]),
        Paragraph(escape(titulo), ESTILOS["Heading2"]),
        Paragraph(escape(f"Quincena del {_fecha(periodo['fecha_inicio'])} al {_fecha(periodo['fecha_fin'])}"), ESTILOS["Normal"]),
        Spacer(1, 0.4 * cm),
    ]


def _tabla(filas, anchos, extra=()):
    tabla = Table(filas, colWidths=anchos, repeatRows=1)
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), GRIS_ENCABEZADO),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS_CLARO]),
                *extra,
            ]
        )
    )
    return tabla


def _encabezados(textos, derecha=()):
    estilo = ParagraphStyle("encabezado", parent=ESTILOS["Normal"], fontName="Helvetica-Bold", fontSize=8.5,
                            textColor=colors.white)
    derecha_estilo = ParagraphStyle("encabezado_d", parent=estilo, alignment=2)
    return [Paragraph(escape(t), derecha_estilo if i in derecha else estilo) for i, t in enumerate(textos)]


def _trabajo(snapshot):
    if snapshot.get("forma_pago") == "por_turno":
        return f"{snapshot.get('turnos', 0)} turnos"
    return _horas(int(snapshot.get("minutos_jornada", snapshot.get("minutos_trabajados", 0))))


def _documento(historia, pagina):
    salida = BytesIO()
    SimpleDocTemplate(
        salida,
        pagesize=pagina,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    ).build(historia)
    return salida.getvalue()


def _sucursal(boleta):
    return (boleta["colaboradores"].get("sucursales") or {}).get("nombre", "Sin sucursal")


def generar_planilla_general(periodo, boletas):
    """una tabla por sucursal, con su subtotal, y el total de toda la planilla al final"""
    filas = [
        _encabezados(
            ["Boleta", "Empleado", "Puesto", "Forma de pago", "Trabajado", "Ingresos", "Descuentos", "Neto", "Estado"],
            derecha=(5, 6, 7),
        )
    ]
    estilos = []
    grupos = {}
    for b in sorted(boletas, key=lambda b: (_sucursal(b), b["colaboradores"]["apellidos"], b["colaboradores"]["nombres"])):
        grupos.setdefault(_sucursal(b), []).append(b)

    total = [0, 0, 0]
    for sucursal, lista in grupos.items():
        fila = len(filas)
        filas.append([_celda(sucursal, negrita=True, tamano=9.5)] + [_celda("")] * 8)
        estilos += [("SPAN", (0, fila), (-1, fila)), ("BACKGROUND", (0, fila), (-1, fila), colors.HexColor("#DBEAFE"))]

        subtotal = [0, 0, 0]
        for b in lista:
            persona = b["colaboradores"]
            snapshot = b["snapshot_valores"] or {}
            filas.append(
                [
                    _celda(b["numero"]),
                    _celda(f"{persona['apellidos']}, {persona['nombres']}"),
                    _celda((persona.get("puestos") or {}).get("nombre", "")),
                    _celda(FORMAS_DE_PAGO.get(snapshot.get("forma_pago"), "")),
                    _celda(_trabajo(snapshot)),
                    _celda(quetzales(b["total_ingresos"]), derecha=True),
                    _celda(quetzales(b["total_descuentos"]), derecha=True),
                    _celda(quetzales(b["neto"]), derecha=True, negrita=True),
                    _celda(ESTADOS.get(b["estado"], b["estado"])),
                ]
            )
            for i, campo in enumerate(("total_ingresos", "total_descuentos", "neto")):
                subtotal[i] += float(b[campo])

        fila = len(filas)
        filas.append(
            [_celda(""), _celda(f"Subtotal {sucursal}", negrita=True), _celda(""), _celda(""), _celda(""),
             _celda(quetzales(subtotal[0]), derecha=True, negrita=True),
             _celda(quetzales(subtotal[1]), derecha=True, negrita=True),
             _celda(quetzales(subtotal[2]), derecha=True, negrita=True), _celda("")]
        )
        estilos.append(("BACKGROUND", (0, fila), (-1, fila), colors.HexColor("#E5E7EB")))
        total = [total[i] + subtotal[i] for i in range(3)]

    fila = len(filas)
    filas.append(
        [_celda(""), _celda("TOTAL DE LA PLANILLA", negrita=True), _celda(""), _celda(""), _celda(""),
         _celda(quetzales(total[0]), derecha=True, negrita=True),
         _celda(quetzales(total[1]), derecha=True, negrita=True),
         _celda(quetzales(total[2]), derecha=True, negrita=True), _celda("")]
    )
    estilos.append(("BACKGROUND", (0, fila), (-1, fila), colors.HexColor("#BFDBFE")))

    anchos = [1.4 * cm, 5.4 * cm, 3 * cm, 2.6 * cm, 2.6 * cm, 2.6 * cm, 2.6 * cm, 2.6 * cm, 3.2 * cm]
    historia = _encabezado("Planilla de pago", periodo)
    historia.append(_tabla(filas, anchos, extra=estilos))
    historia.append(Spacer(1, 1.6 * cm))
    firmas = Table(
        [["______________________________", "______________________________"],
         ["Elaborado por (RR. HH.)", "Aprobado por (Jefe)"]],
        colWidths=[8 * cm, 8 * cm],
    )
    firmas.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("FONTSIZE", (0, 0), (-1, -1), 8.5)]))
    historia.append(firmas)
    return _documento(historia, landscape(A4))


def _pagina_boleta(periodo, b):
    persona = b["colaboradores"]
    snapshot = b["snapshot_valores"] or {}
    historia = _encabezado(f"Boleta de pago N.º {b['numero']}", periodo)

    datos = Table(
        [
            [_celda("Empleado", negrita=True), _celda(f"{persona['nombres']} {persona['apellidos']}"),
             _celda("Puesto", negrita=True), _celda((persona.get("puestos") or {}).get("nombre", ""))],
            [_celda("Sucursal", negrita=True), _celda((persona.get("sucursales") or {}).get("nombre", "")),
             _celda("Forma de pago", negrita=True), _celda(FORMAS_DE_PAGO.get(snapshot.get("forma_pago"), ""))],
            [_celda("Trabajado", negrita=True), _celda(_trabajo(snapshot)),
             _celda("Estado", negrita=True), _celda(ESTADOS.get(b["estado"], b["estado"]))],
        ],
        colWidths=[3 * cm, 6 * cm, 3 * cm, 5.5 * cm],
    )
    datos.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB"))]))
    historia += [datos, Spacer(1, 0.5 * cm)]

    detalles = sorted(b["boleta_detalles"], key=lambda d: d["tipo"] != "ingreso")
    filas = [_encabezados(["Concepto", "Cantidad", "Valor", "Monto"], derecha=(1, 2, 3))]
    for d in detalles:
        descuento = d["tipo"] == "descuento"
        filas.append(
            [
                _celda(f"(-) {d['concepto']}" if descuento else d["concepto"]),
                _celda(_cantidad(d["cantidad"]), derecha=True),
                _celda(quetzales(d["valor_unitario"]), derecha=True),
                _celda(("-" if descuento else "") + quetzales(d["monto"]), derecha=True),
            ]
        )
    filas += [
        [_celda(""), _celda(""), _celda("Total de ingresos", negrita=True, derecha=True),
         _celda(quetzales(b["total_ingresos"]), derecha=True, negrita=True)],
        [_celda(""), _celda(""), _celda("Total de descuentos", negrita=True, derecha=True),
         _celda(("-" if float(b["total_descuentos"]) else "") + quetzales(b["total_descuentos"]), derecha=True, negrita=True)],
        [_celda(""), _celda(""), _celda("NETO A PAGAR", negrita=True, derecha=True, tamano=10),
         _celda(quetzales(b["neto"]), derecha=True, negrita=True, tamano=10)],
    ]
    historia.append(_tabla(filas, [8 * cm, 2.5 * cm, 3.5 * cm, 3.5 * cm],
                           extra=[("BACKGROUND", (0, -3), (-1, -1), colors.HexColor("#E5E7EB"))]))

    ajuste = snapshot.get("ajuste")
    if ajuste:
        nota = "Los valores de hora de esta quincena fueron ajustados por RR. HH."
        if ajuste.get("motivo"):
            nota += f" Motivo: {ajuste['motivo']}"
        historia += [Spacer(1, 0.4 * cm), Paragraph(escape(nota), ESTILOS["Italic"])]

    historia.append(Spacer(1, 2.2 * cm))
    firma = Table([["______________________________", "Fecha: ____ / ____ / ________"],
                   ["Firma del empleado (recibí conforme)", ""]], colWidths=[9 * cm, 8 * cm])
    firma.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("FONTSIZE", (0, 0), (-1, -1), 8.5)]))
    historia.append(firma)
    return historia


def generar_boletas(periodo, boletas):
    """una boleta por pagina, en orden"""
    historia = []
    for i, b in enumerate(boletas):
        if i:
            historia.append(PageBreak())
        historia += _pagina_boleta(periodo, b)
    return _documento(historia, A4)