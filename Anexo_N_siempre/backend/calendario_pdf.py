"""genera los calendarios de turnos en pdf con reportlab"""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NOMBRES_DIA = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
COLORES_TURNO = {
    "Mañana": "#FDE68A",
    "Tarde": "#FDBA74",
    "Noche": "#93C5FD",
    "Guardia 24h": "#C4B5FD",
    "Libre": "#E5E7EB",
}
GRIS_ENCABEZADO = colors.HexColor("#374151")
ESTILOS = getSampleStyleSheet()


def _color(turno):
    return colors.HexColor(COLORES_TURNO.get(turno, "#FFFFFF"))


def _fecha(dia):
    return dia.strftime("%d/%m/%Y")


def _celda(texto, tamano, color=None, negrita=False):
    estilo = ParagraphStyle(
        "celda",
        parent=ESTILOS["Normal"],
        fontName="Helvetica-Bold" if negrita else "Helvetica",
        fontSize=tamano,
        leading=tamano + 1.5,
        alignment=1,
        textColor=color or colors.black,
    )
    return Paragraph(escape(texto), estilo)


def _encabezado(titulo, periodo, version, estado, publicada_en):
    historia = [
        Paragraph(escape(titulo), ESTILOS["Title"]),
        Paragraph(escape(f"{periodo} · Versión {version}"), ESTILOS["Normal"]),
    ]
    if estado == "borrador":
        aviso = ParagraphStyle("aviso", parent=ESTILOS["Normal"], textColor=colors.HexColor("#B91C1C"))
        historia.append(Paragraph("<b>BORRADOR: todavía no es la programación oficial</b>", aviso))
    elif publicada_en:
        historia.append(Paragraph(escape(f"Publicada el {publicada_en}"), ESTILOS["Normal"]))
    historia.append(Spacer(1, 0.4 * cm))
    return historia


def _leyenda(turnos):
    nombres = [t for t in COLORES_TURNO if t in turnos]
    if not nombres:
        return []
    celdas = [_celda(n, 8) for n in nombres]
    tabla = Table([celdas], colWidths=[2.8 * cm] * len(nombres), hAlign="LEFT")
    estilo = [("BOX", (0, 0), (-1, -1), 0.25, colors.grey), ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey)]
    estilo += [("BACKGROUND", (i, 0), (i, 0), _color(n)) for i, n in enumerate(nombres)]
    tabla.setStyle(TableStyle(estilo))
    return [Spacer(1, 0.4 * cm), tabla]


def _pie(lienzo, documento):
    lienzo.saveState()
    lienzo.setFont("Helvetica", 8)
    lienzo.setFillColor(colors.grey)
    lienzo.drawString(documento.leftMargin, 0.8 * cm, "Siempre · Control de asistencia")
    lienzo.drawRightString(documento.pagesize[0] - documento.rightMargin, 0.8 * cm, f"Página {documento.page}")
    lienzo.restoreState()


def _construir(historia, tamano_pagina, titulo_pdf):
    salida = BytesIO()
    documento = SimpleDocTemplate(
        salida,
        pagesize=tamano_pagina,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=titulo_pdf,
        author="Siempre",
    )
    documento.build(historia, onFirstPage=_pie, onLaterPages=_pie)
    return salida.getvalue()


def generar_calendario(titulo, periodo, version, estado, publicada_en, dias, filas):
    """cuadricula de colaboradores (filas) por dias (columnas)"""
    if not dias:
        raise ValueError("La programación no tiene días")
    tamano_pagina = landscape(A4)
    ancho_util = tamano_pagina[0] - 3 * cm
    ancho_nombre = 5.5 * cm
    tamano = 8 if len(dias) <= 8 else 6.5

    encabezado = [_celda("Colaborador", tamano, colors.white, True)]
    encabezado += [_celda(f"{NOMBRES_DIA[d.weekday()]} {d.day}", tamano, colors.white, True) for d in dias]
    datos = [encabezado]
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), GRIS_ENCABEZADO),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]

    usados = set()
    for numero, (nombre, turnos) in enumerate(filas, start=1):
        fila = [Paragraph(escape(nombre), ParagraphStyle("nombre", parent=ESTILOS["Normal"], fontSize=tamano + 1))]
        for columna, turno in enumerate(turnos, start=1):
            fila.append(_celda(turno, tamano))
            if turno:
                usados.add(turno)
                estilo.append(("BACKGROUND", (columna, numero), (columna, numero), _color(turno)))
        datos.append(fila)

    anchos = [ancho_nombre] + [(ancho_util - ancho_nombre) / len(dias)] * len(dias)
    tabla = Table(datos, colWidths=anchos, repeatRows=1)
    tabla.setStyle(TableStyle(estilo))

    historia = _encabezado(titulo, periodo, version, estado, publicada_en) + [tabla] + _leyenda(usados)
    return _construir(historia, tamano_pagina, titulo)


def generar_hoja_individual(nombre, sucursal, periodo, version, estado, publicada_en, filas):
    """hoja de una persona"""
    historia = _encabezado(nombre, f"{sucursal} · {periodo}", version, estado, publicada_en)

    datos = [[_celda(t, 10, colors.white, True) for t in ("Fecha", "Día", "Turno", "Horario")]]
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), GRIS_ENCABEZADO),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    usados = set()
    for numero, (dia, turno, horario) in enumerate(filas, start=1):
        datos.append(
            [_celda(_fecha(dia), 10), _celda(NOMBRES_DIA[dia.weekday()], 10), _celda(turno or "Sin asignar", 10), _celda(horario, 10)]
        )
        if turno:
            usados.add(turno)
            estilo.append(("BACKGROUND", (2, numero), (2, numero), _color(turno)))

    tabla = Table(datos, colWidths=[3.5 * cm, 2.5 * cm, 4 * cm, 4.5 * cm], repeatRows=1, hAlign="LEFT")
    tabla.setStyle(TableStyle(estilo))
    return _construir(historia + [tabla] + _leyenda(usados), A4, nombre)