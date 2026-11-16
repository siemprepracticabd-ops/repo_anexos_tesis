"""convierte una fila de la bitacora en texto legible: nombres en lugar de ids y una frase"""

import re
from datetime import datetime

from calendarios import GUATEMALA

UUID_TEXTO = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SIN_REGISTRO = "(ya no existe)"

TIPOS_ALERTA = {
    "marcacion_sin_colaborador": "marcación sin persona",
    "sin_programacion": "sin turno programado",
    "por_confirmar": "jornada por confirmar",
    "marcacion_faltante": "falta una marcación",
    "ausencia": "ausencia",
    "tardanzas_frecuentes": "tardanzas frecuentes",
    "exceso_horas_extra": "exceso de horas extra",
    "descanso_insuficiente": "descanso insuficiente",
}

VALORES = {
    "tiempo_completo": "Tiempo completo",
    "parcial_nocturno": "Parcial nocturno",
    "guardia": "Guardia",
    "diurna": "Diurna (oficina)",
    "salario_fijo": "Salario fijo mensual",
    "por_hora": "Por hora",
    "por_turno": "Por turno",
    "pendiente": "Pendiente",
    "autorizada": "Autorizada",
    "parcial": "Parcial",
    "rechazada": "Rechazada",
    "justificada": "Justificada",
    "sin_justificar": "Sin justificar",
    "reclasificada": "Reclasificada",
    "entrada": "Entrada",
    "salida": "Salida",
    "trabaja": "Trabaja",
    "libre": "Libre",
    "semanal": "Semanal",
    "quincenal": "Quincenal",
    "mixta": "Mixta",
    "nocturna": "Nocturna",
}

ETIQUETAS = {
    "colaborador_id": "Colaborador",
    "dispositivo_id": "Reloj",
    "sucursal_id": "Sucursal",
    "id_en_dispositivo": "Número en el reloj",
    "momento": "Fecha y hora",
    "motivo": "Motivo",
    "tipo": "Tipo",
    "fecha": "Fecha",
    "desde": "Desde",
    "hasta": "Hasta",
    "inicio": "Inicio",
    "fin": "Fin",
    "fecha_inicio": "Desde",
    "fecha_fin": "Hasta",
    "fecha_ingreso": "Fecha de ingreso",
    "dpi_ultimos4": "Últimos 4 del DPI",
    "modalidad": "Modalidad",
    "forma_pago": "Forma de pago",
    "modalidad_anterior": "Modalidad anterior",
    "modalidad_nueva": "Modalidad nueva",
    "forma_pago_anterior": "Forma de pago anterior",
    "forma_pago_nueva": "Forma de pago nueva",
    "turnos_liberados": "Turnos liberados",
    "boletas": "Boletas",
    "boletas_borradas": "Boletas borradas",
    "neto_total": "Neto total",
    "jornadas": "Jornadas calculadas",
    "ausencias": "Ausencias",
    "horas_extra": "Con horas extra",
    "sin_programacion": "Sin programación",
    "personas": "Personas",
    "celdas": "Celdas guardadas",
    "cambios": "Cambios de turno",
    "version": "Versión",
    "nombre": "Nombre",
    "serie": "Número de serie",
    "antes": "Antes",
    "despues": "Después",
    "horas_ordinarias": "Horas ordinarias",
    "detectados": "Minutos detectados",
    "estado_anterior": "Estado anterior",
    "estado_nuevo": "Estado nuevo",
    "pagados_anterior": "Minutos pagados antes",
    "pagados_nuevo": "Minutos pagados ahora",
    "descontados_anterior": "Minutos descontados antes",
    "descontados_nuevo": "Minutos descontados ahora",
    "autorizado_por": "Autorizado por",
    "valor_hora": "Valor de la hora",
    "valor_hora_extra": "Valor de la hora extra",
    "ausencias_justificadas": "Ausencias justificadas",
    "activo": "Activo",
}

DINERO = {"neto_total", "valor_hora", "valor_hora_extra"}


class Contexto:
    """nombres ya buscados en la base para los ids que aparecen en la pagina de la bitacora"""

    def __init__(self, personas=None, relojes=None, periodos=None, programaciones=None, casos=None):
        self.personas = personas or {}
        self.relojes = relojes or {}
        self.periodos = periodos or {}
        self.programaciones = programaciones or {}
        # id de un registro (horas extra, ausencia, jornada, alerta...) -> {"persona", "fecha", "tipo"}
        self.casos = casos or {}

    def persona(self, id_):
        return self.personas.get(id_) or SIN_REGISTRO

    def reloj(self, id_):
        return self.relojes.get(id_) or SIN_REGISTRO

    def nombre_de(self, valor):
        """nombre que corresponde a un id, o none si no se encontro en ninguna lista"""
        for tabla in (self.personas, self.relojes, self.periodos, self.programaciones):
            if valor in tabla:
                return tabla[valor]
        if valor in self.casos:
            caso = self.casos[valor]
            return " · ".join(str(x) for x in (caso.get("persona"), fecha_corta(caso.get("fecha"))) if x)
        return None


def fecha_corta(valor):
    if not valor:
        return ""
    try:
        return datetime.fromisoformat(str(valor)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(valor)


def fecha_hora(valor):
    try:
        momento = datetime.fromisoformat(str(valor))
    except ValueError:
        return str(valor)
    if momento.tzinfo is not None:
        momento = momento.astimezone(GUATEMALA)
    return momento.strftime("%d/%m/%Y %H:%M")


def hora_corta(valor):
    if not valor:
        return "sin marca"
    try:
        momento = datetime.fromisoformat(str(valor))
    except ValueError:
        return str(valor)
    if momento.tzinfo is not None:
        momento = momento.astimezone(GUATEMALA)
    return momento.strftime("%H:%M")


def dinero(valor):
    try:
        return f"Q {float(valor):,.2f}"
    except (TypeError, ValueError):
        return str(valor)


def rango(inicio, fin):
    return f"del {fecha_corta(inicio)} al {fecha_corta(fin)}"


def valor_legible(clave, valor, c):
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if clave in DINERO:
        return dinero(valor)
    if isinstance(valor, str):
        if UUID_TEXTO.match(valor):
            return c.nombre_de(valor) or SIN_REGISTRO
        if re.match(r"^\d{4}-\d{2}-\d{2}T", valor):
            return fecha_hora(valor)
        if re.match(r"^\d{4}-\d{2}-\d{2}$", valor):
            return fecha_corta(valor)
        if valor == "diurna" and not clave.startswith("modalidad"):
            return "Diurna"
        return VALORES.get(valor, valor)
    return str(valor)


def lineas(detalle, c, prefijo=""):
    """detalle como lista de (etiqueta, texto) sin ids ni claves tecnicas"""
    resultado = []
    for clave, valor in (detalle or {}).items():
        if valor is None or valor == "":
            continue
        etiqueta = prefijo + ETIQUETAS.get(clave, clave.replace("_", " ").capitalize())
        if isinstance(valor, dict):
            resultado.extend(lineas(valor, c, prefijo=f"{etiqueta}: "))
        else:
            resultado.append((etiqueta, valor_legible(clave, valor, c)))
    return resultado


def describir(fila, c):
    """una frase de lo que se hizo, por ejemplo: «agrego una marcacion de salida a ana perez (21/10/2026"""
    accion, tabla = fila["accion"], fila["tabla"]
    d = fila.get("detalle") or {}
    registro = fila.get("registro_id")
    persona = c.persona(d["colaborador_id"]) if d.get("colaborador_id") else None
    caso = c.casos.get(registro, {})

    if tabla == "marcaciones" and accion == "agregar_marcacion":
        tipo = VALORES.get(d.get("tipo"), d.get("tipo") or "").lower()
        return f"Agregó una marcación de {tipo} a {persona} ({fecha_hora(d.get('momento'))})"
    if tabla == "jornadas" and accion == "calcular":
        return (
            f"Calculó las jornadas {rango(d.get('desde'), d.get('hasta'))}: {d.get('jornadas', 0)} jornadas, "
            f"{d.get('ausencias', 0)} ausencias, {d.get('horas_extra', 0)} con horas extra, "
            f"{d.get('sin_programacion', 0)} sin programación"
        )
    if tabla == "jornadas" and accion == "corregir":
        partes = []
        for etiqueta, antes, despues in (
            ("entrada", d.get("entrada_antes"), d.get("entrada_despues")),
            ("salida", d.get("salida_antes"), d.get("salida_despues")),
        ):
            if despues:
                partes.append(f"{etiqueta} {hora_corta(antes)} a {hora_corta(despues)}")
        return f"Corrigió la jornada de {persona} del {fecha_corta(d.get('fecha'))}: {', '.join(partes)}"
    if tabla == "jornadas" and accion == "confirmar":
        return f"Confirmó la jornada de {caso.get('persona', SIN_REGISTRO)} del {fecha_corta(caso.get('fecha'))}"
    if tabla == "ausencias" and accion == "registrar_asistencia":
        return (
            f"Registró la asistencia de {persona} del {fecha_corta(d.get('fecha'))} "
            f"({hora_corta(d.get('entrada'))} a {hora_corta(d.get('salida'))}) porque olvidó marcar"
        )
    if tabla == "ausencias":
        return f"Justificó la ausencia de {caso.get('persona', SIN_REGISTRO)} del {fecha_corta(caso.get('fecha'))} como {d.get('tipo', 'otro motivo')}"
    if tabla == "horas_extra":
        nuevo = VALORES.get(d.get("estado_nuevo"), d.get("estado_nuevo") or "").lower()
        return (
            f"Decidió las horas extra de {caso.get('persona', SIN_REGISTRO)} del {fecha_corta(caso.get('fecha'))}: "
            f"{nuevo}, {d.get('pagados_nuevo', 0)} de {d.get('detectados', 0)} min a pagar"
        )
    if tabla == "descuentos_tiempo" and accion == "decidir":
        nuevo = VALORES.get(d.get("estado_nuevo"), d.get("estado_nuevo") or "").lower()
        return (
            f"Decidió el descuento por tardanza de {caso.get('persona', SIN_REGISTRO)}: {nuevo}, "
            f"{d.get('descontados_nuevo', 0)} de {d.get('detectados', 0)} min a descontar"
        )
    if tabla == "descuentos_tiempo":
        return f"Preparó los descuentos por tardanza {rango(d.get('inicio'), d.get('fin'))} ({d.get('personas', 0)} personas)"
    if tabla == "colaboradores":
        nombre = c.persona(registro)
        if accion == "crear":
            return f"Registró a {nombre} (ingreso {fecha_corta(d.get('fecha_ingreso'))})"
        if accion == "baja":
            return f"Dio de baja a {nombre} a partir del {fecha_corta(d.get('fecha'))}"
        if accion == "reactivar":
            return f"Reactivó a {nombre} desde el {fecha_corta(d.get('fecha'))}"
        if accion == "cambiar_condiciones":
            return f"Cambió las condiciones de pago de {nombre} desde el {fecha_corta(d.get('desde'))}"
    if tabla == "colaborador_dispositivo":
        reloj = c.reloj(d.get("dispositivo_id"))
        quien = c.persona(registro)
        if accion == "enlazar":
            return f"Enlazó a {quien} con el reloj «{reloj}» (número {d.get('id_en_dispositivo')})"
        if accion == "desenlazar":
            return f"Quitó el enlace del número {d.get('id_en_dispositivo')} del reloj «{reloj}»"
    if tabla == "dispositivos":
        reloj = d.get("nombre") or c.reloj(registro)
        frases = {
            "crear": f"Registró el reloj «{reloj}» (serie {d.get('serie')})",
            "regenerar_clave": f"Generó una clave nueva para el reloj «{reloj}»",
            "activar": f"Activó el reloj «{reloj}»",
            "desactivar": f"Desactivó el reloj «{reloj}»",
        }
        if accion in frases:
            return frases[accion]
    if tabla == "sucursales" and accion == "crear":
        return f"Creó la sucursal «{d.get('nombre')}»"
    if tabla == "programaciones":
        etiqueta = c.programaciones.get(registro, SIN_REGISTRO)
        if accion == "crear":
            return f"Creó la programación {VALORES.get(d.get('tipo'), '').lower()} {rango(d.get('fecha_inicio'), d.get('fecha_fin'))}"
        if accion == "publicar":
            return f"Publicó la programación {etiqueta} (versión {d.get('version')}, {d.get('cambios', 0)} cambios de turno)"
        if accion == "crear_version":
            return f"Creó la versión {d.get('version')} de la programación {etiqueta}"
    if tabla == "asignaciones_turno":
        return f"Guardó {d.get('celdas', 0)} turnos en la programación {c.programaciones.get(registro, SIN_REGISTRO)}"
    if tabla == "periodos_planilla":
        etiqueta = c.periodos.get(registro) or (rango(d.get("inicio"), d.get("fin")) if d.get("inicio") else SIN_REGISTRO)
        if accion == "cerrar":
            return f"Cerró la quincena {etiqueta}: {d.get('boletas', 0)} boletas, neto {dinero(d.get('neto_total'))}"
        if accion == "pagar":
            return f"Marcó como pagada la quincena {etiqueta} ({d.get('boletas', 0)} boletas)"
        if accion == "reabrir":
            return f"Reabrió la quincena {rango(d.get('inicio'), d.get('fin'))} y borró {d.get('boletas_borradas', 0)} boletas"
    if tabla == "descuentos_manuales":
        quien = persona or SIN_REGISTRO
        rango_texto = rango(d.get("inicio"), d.get("fin"))
        if accion == "crear":
            return f"Descontó {dinero(d.get('monto'))} a {quien} en la quincena {rango_texto}: {d.get('motivo')}"
        return f"Quitó el descuento de {dinero(d.get('monto'))} a {quien} de la quincena {rango_texto}"
    if tabla == "ajustes_planilla":
        return (
            f"Ajustó el valor de la hora de {c.persona(registro)} para la quincena {rango(d.get('inicio'), d.get('fin'))}: "
            f"hora {dinero(d.get('valor_hora'))}, hora extra {dinero(d.get('valor_hora_extra'))}"
        )
    if tabla == "licencias":
        if accion == "crear":
            return f"Registró {str(d.get('tipo', 'una licencia')).lower()} a {persona} {rango(d.get('desde'), d.get('hasta'))}"
        if accion == "anular":
            return f"Anuló la licencia de {persona} {rango(d.get('desde'), d.get('hasta'))}"
    if tabla == "alertas":
        return (
            f"Marcó como vista la alerta de {TIPOS_ALERTA.get(caso.get('tipo'), 'otro tipo')} de "
            f"{caso.get('persona', SIN_REGISTRO)} del {fecha_corta(caso.get('fecha'))}"
        )
    if tabla == "puestos":
        if accion == "crear":
            return f"Creó el puesto «{d.get('nombre')}»"
        if accion == "renombrar":
            return f"Renombró el puesto «{d.get('antes')}» a «{d.get('despues')}»"
        if accion == "eliminar":
            return f"Eliminó el puesto «{d.get('nombre')}»"
    if tabla == "turnos":
        if accion == "crear":
            return f"Creó el turno «{d.get('nombre')}» ({str(d.get('inicio', ''))[:5]} a {str(d.get('fin', ''))[:5]})"
        if accion == "editar":
            return f"Editó el turno «{(d.get('despues') or {}).get('nombre')}»"
        if accion == "eliminar":
            return f"Eliminó el turno «{d.get('nombre')}»"
        if accion in ("activar", "desactivar"):
            return f"{'Activó' if accion == 'activar' else 'Desactivó'} un turno"
    if tabla == "dias_diurno":
        dia = fecha_corta(d.get("fecha"))
        if d.get("tipo") == "trabaja":
            return f"Marcó que {c.persona(registro)} trabaja el {dia}"
        if d.get("tipo") == "libre":
            return f"Marcó que {c.persona(registro)} descansa el {dia}"
        return f"Volvió al horario base de {c.persona(registro)} el {dia}"
    return f"{accion.replace('_', ' ').capitalize()} · {tabla.replace('_', ' ')}"
