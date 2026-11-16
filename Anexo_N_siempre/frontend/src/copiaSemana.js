import { sumarDias } from './periodos'

export function copiarInvirtiendo(origen, turnos, guardadas, idsColaboradores) {
  const manana = turnos.find((t) => t.nombre === 'Mañana')
  const tarde = turnos.find((t) => t.nombre === 'Tarde')
  const activos = new Set(turnos.map((t) => t.id))
  const inversion = {}
  if (manana && tarde) {
    inversion[manana.id] = tarde.id
    inversion[tarde.id] = manana.id
  }

  const nuevos = {}
  origen.forEach((a) => {
    const clave = `${a.colaborador_id}|${sumarDias(a.fecha, 7)}`
    const valor = a.turno_id ?? 'libre'
    if (clave in guardadas) return
    if (!idsColaboradores.has(a.colaborador_id)) return
    if (valor !== 'libre' && !activos.has(valor)) return
    nuevos[clave] = inversion[valor] ?? valor
  })
  return nuevos
}