import { aTexto } from './periodos'

const NOMBRES_DIA = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb']

export const ESTADOS = {
  ok: 'OK',
  por_confirmar: 'Por confirmar',
  incompleta: 'Incompleta',
  sin_programacion: 'Sin programación',
}

export function formatoHoras(minutos) {
  const horas = Math.floor(minutos / 60)
  const resto = String(minutos % 60).padStart(2, '0')
  return `${horas}h ${resto}min`
}

export function horaLocal(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString('es-GT', {
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZone: 'America/Guatemala',
  })
}

// valor para un campo datetime-local, en hora de guatemala
export function fechaHoraLocal(iso) {
  if (!iso) return ''
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'America/Guatemala',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  })
    .format(new Date(iso))
    .replace(' ', 'T')
}

// motivo de las horas agregadas o corregidas a mano en una jornada
export function notaDeCorreccion(jornada) {
  const motivos = [jornada.entrada, jornada.salida]
    .flatMap((marca) => marca?.correcciones ?? [])
    .map((c) => c.motivo)
  return [...new Set(motivos)].join(' / ')
}

export function diaSemana(texto) {
  const [anio, mes, dia] = texto.split('-').map(Number)
  return NOMBRES_DIA[new Date(anio, mes - 1, dia).getDay()]
}

export function quincenaActual(hoy = new Date()) {
  const desde = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() > 15 ? 16 : 1)
  return { desde: aTexto(desde), hasta: aTexto(hoy) }
}

// minutos que se espera tras el fin del turno antes de calcular la jornada (valor por defecto del sistema)
const ESPERA_CIERRE = 240

// un turno sigue en espera si todavia no pasa su fin mas la ventana posterior
export function turnoEnEspera(fecha, turno, ahora = new Date()) {
  const fin = new Date(`${fecha}T${turno.hora_fin}`)
  if (turno.cruza_medianoche) fin.setDate(fin.getDate() + 1)
  return fin.getTime() + ESPERA_CIERRE * 60000 > ahora.getTime()
}

export function observacion(jornada) {
  const partes = []
  if (jornada.clasif_entrada === 'tardanza') partes.push(`Tardanza ${jornada.minutos_tardanza} min`)
  if (jornada.clasif_entrada === 'dentro_gracia') partes.push(`Gracia ${jornada.minutos_tardanza} min`)
  if (jornada.clasif_salida === 'anticipada') partes.push('Salida anticipada')
  if (jornada.estado !== 'ok') partes.push(ESTADOS[jornada.estado] ?? jornada.estado)
  return partes.join(' · ')
}

export function agruparPorColaborador(jornadas) {
  const grupos = new Map()
  jornadas.forEach((j) => {
    const id = j.colaboradores.id
    if (!grupos.has(id)) grupos.set(id, { colaborador: j.colaboradores, jornadas: [], total: 0 })
    const grupo = grupos.get(id)
    grupo.jornadas.push(j)
    if (j.estado !== 'sin_programacion') grupo.total += j.minutos_trabajados
  })
  return [...grupos.values()]
    .map((g) => ({ ...g, jornadas: g.jornadas.sort((a, b) => a.fecha.localeCompare(b.fecha)) }))
    .sort(
      (a, b) =>
        a.colaborador.apellidos.localeCompare(b.colaborador.apellidos) ||
        a.colaborador.nombres.localeCompare(b.colaborador.nombres)
    )
}

export function quincenasRecientes(hoy = new Date(), cantidad = 6) {
  const lista = []
  let anio = hoy.getFullYear()
  let mes = hoy.getMonth()
  let segunda = hoy.getDate() > 15

  for (let i = 0; i < cantidad; i++) {
    const inicio = new Date(anio, mes, segunda ? 16 : 1)
    const fin = segunda ? new Date(anio, mes + 1, 0) : new Date(anio, mes, 15)
    lista.push({ desde: aTexto(inicio), hasta: aTexto(fin) })
    if (segunda) {
      segunda = false
    } else {
      segunda = true
      mes -= 1
    }
  }
  return lista
}