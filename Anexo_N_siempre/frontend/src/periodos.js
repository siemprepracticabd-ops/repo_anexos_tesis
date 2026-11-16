const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

export function aTexto(fecha) {
  const mes = String(fecha.getMonth() + 1).padStart(2, '0')
  const dia = String(fecha.getDate()).padStart(2, '0')
  return `${fecha.getFullYear()}-${mes}-${dia}`
}

function corta(fecha) {
  return `${fecha.getDate()} ${MESES[fecha.getMonth()]}`
}

function periodo(inicio, fin) {
  return {
    inicio: aTexto(inicio),
    fin: aTexto(fin),
    etiqueta: `${corta(inicio)} al ${corta(fin)} ${fin.getFullYear()}`,
  }
}

export function sugerirPeriodos(tipo, hoy = new Date()) {
  const anio = hoy.getFullYear()
  const mes = hoy.getMonth()
  const dia = hoy.getDate()
  const lista = []

  if (tipo === 'semanal') {
    const desdeLunes = (hoy.getDay() + 6) % 7
    for (let i = 0; i < 8; i++) {
      const inicio = new Date(anio, mes, dia - desdeLunes + 7 * i)
      const fin = new Date(anio, mes, dia - desdeLunes + 7 * i + 6)
      lista.push(periodo(inicio, fin))
    }
  }

  if (tipo === 'quincenal') {
    let mesActual = mes
    let segunda = dia > 15
    for (let i = 0; i < 6; i++) {
      const inicio = new Date(anio, mesActual, segunda ? 16 : 1)
      const fin = segunda ? new Date(anio, mesActual + 1, 0) : new Date(anio, mesActual, 15)
      lista.push(periodo(inicio, fin))
      if (segunda) mesActual += 1
      segunda = !segunda
    }
  }

  return lista
}

export function sumarDias(texto, dias) {
  const [anio, mes, dia] = texto.split('-').map(Number)
  return aTexto(new Date(anio, mes - 1, dia + dias))
}