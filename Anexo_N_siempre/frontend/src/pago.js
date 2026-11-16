export const MODALIDADES = [
  { valor: 'tiempo_completo', etiqueta: 'Tiempo completo' },
  { valor: 'parcial_nocturno', etiqueta: 'Parcial nocturno' },
  { valor: 'guardia', etiqueta: 'Guardia' },
  { valor: 'diurna', etiqueta: 'Diurna (oficina)' },
]

export const FORMAS_DE_PAGO = [
  { valor: 'salario_fijo', etiqueta: 'Salario fijo mensual' },
  { valor: 'por_hora', etiqueta: 'Por hora' },
  { valor: 'por_turno', etiqueta: 'Por turno' },
]

const FORMA_SUGERIDA = {
  tiempo_completo: 'salario_fijo',
  parcial_nocturno: 'por_hora',
  guardia: 'por_turno',
}

const dinero = new Intl.NumberFormat('es-GT', { style: 'currency', currency: 'GTQ' })

export function formaSugerida(modalidad) {
  return FORMA_SUGERIDA[modalidad]
}

export function etiquetaDe(lista, valor) {
  return lista.find((x) => x.valor === valor)?.etiqueta ?? valor
}

export function condicionVigente(condiciones, hoy) {
  const vigentes = condiciones.filter(
    (c) => c.vigente_desde <= hoy && (c.vigente_hasta === null || c.vigente_hasta >= hoy)
  )
  return vigentes[0] ?? null
}

export function textoDePago(condicion) {
  if (!condicion) return 'Sin condiciones'
  if (condicion.forma_pago === 'salario_fijo') return `${dinero.format(condicion.salario_mensual)} al mes`
  if (condicion.forma_pago === 'por_hora') return `${dinero.format(condicion.tarifa)} por hora`
  return `${dinero.format(condicion.tarifa)} por turno`
}

export function quetzales(monto) {
  return dinero.format(monto)
}

export function agruparPorSucursal(lista, nombreDe) {
  const grupos = new Map()
  for (const elemento of lista) {
    const nombre = nombreDe(elemento)
    if (!grupos.has(nombre)) grupos.set(nombre, [])
    grupos.get(nombre).push(elemento)
  }
  return [...grupos.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([nombre, elementos]) => ({ nombre, elementos }))
}