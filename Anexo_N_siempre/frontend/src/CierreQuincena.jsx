import { useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import { abrirPdf, llamarApi } from './api'
import { agruparPorSucursal, quetzales } from './pago'

const ESTADO_BOLETA = { generada: 'Pendiente de pago', pagada: 'Pagada' }

function fechaLocal(iso) {
  return new Date(iso).toLocaleDateString('es-GT', { timeZone: 'America/Guatemala' })
}

export default function CierreQuincena({ desde, hasta, rol, hoy, listo, onCambio }) {
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [recarga, setRecarga] = useState(0)

  useEffect(() => {
    let vigente = true

    async function cargar() {
      const { data: periodo, error: falla } = await supabase
        .from('periodos_planilla')
        .select('id, estado, cerrado_en')
        .eq('fecha_inicio', desde)
        .eq('fecha_fin', hasta)
        .maybeSingle()
      if (!vigente) return
      if (falla) {
        setError('No se pudo cargar el cierre de la quincena')
        return
      }

      let boletas = []
      if (periodo?.estado === 'cerrado') {
        const respuesta = await supabase
          .from('boletas')
          .select('id, numero, estado, total_ingresos, total_descuentos, neto, colaboradores(nombres, apellidos, sucursales(nombre))')
          .eq('periodo_id', periodo.id)
          .order('numero')
        if (!vigente) return
        if (respuesta.error) {
          setError('No se pudieron cargar las boletas')
          return
        }
        boletas = respuesta.data
      }
      setError('')
      setDatos({ periodo, boletas })
    }

    cargar()
    return () => {
      vigente = false
    }
  }, [desde, hasta, recarga])

  async function ejecutar(ruta, textoListo) {
    setError('')
    setMensaje('')
    setEnviando(true)

    try {
      const respuesta = await llamarApi(ruta.url, { method: 'POST', body: ruta.cuerpo })
      setMensaje(textoListo(respuesta))
      setRecarga((r) => r + 1)
      onCambio()
    } catch (falla) {
      if (falla.campos) setError(Object.values(falla.campos).join('. '))
      else if (falla.estado) setError(falla.message)
      else setError('No se pudo conectar con el servidor')
    } finally {
      setEnviando(false)
    }
  }

  function cerrar() {
    if (!window.confirm('Se emitirán las boletas y la quincena ya no se podrá modificar. ¿Cerrar la quincena?')) return
    ejecutar(
      { url: '/planilla/cierre', cuerpo: JSON.stringify({ desde, hasta }) },
      (r) => `Quincena cerrada: ${r.boletas} boletas por un total de ${quetzales(r.neto_total)}.`
    )
  }

  function pagar() {
    if (!window.confirm('Se marcarán como pagadas todas las boletas de la quincena. ¿Continuar?')) return
    ejecutar(
      { url: `/planilla/periodos/${datos.periodo.id}/pago` },
      (r) => `Listo: ${r.boletas} boletas marcadas como pagadas.`
    )
  }


  async function abrir(ruta) {
    setError('')
    try {
      await abrirPdf(ruta)
    } catch (falla) {
      setError(falla.aviso || falla.estado ? falla.message : 'No se pudo conectar con el servidor')
    }
  }

  const cerrada = datos?.periodo?.estado === 'cerrado'
  const porPagar = datos?.boletas.filter((b) => b.estado === 'generada').length ?? 0
  const total = (datos?.boletas ?? []).reduce((suma, b) => suma + b.neto, 0)

  return (
    <section>
      <h2>{cerrada ? 'Quincena cerrada' : 'Cerrar la quincena'}</h2>

      {error && <p role="alert">{error}</p>}
      {mensaje && <p role="status">{mensaje}</p>}
      {datos === null && !error && <p>Cargando...</p>}

      {datos !== null && !cerrada && (
        <>
          {hasta >= hoy && <p>La quincena todavía no termina: se podrá cerrar después del {hasta}.</p>}
          {hasta < hoy && !listo && <p>Resuelve lo pendiente de la lista de arriba para poder cerrarla.</p>}
          {rol === 'jefe' ? (
            <button type="button" onClick={cerrar} disabled={enviando || !listo || hasta >= hoy}>
              {enviando ? 'Cerrando...' : 'Cerrar quincena y emitir boletas'}
            </button>
          ) : (
            <p>Solo el jefe puede cerrar la quincena.</p>
          )}
        </>
      )}

      {cerrada && (
        <>
          <p>Cerrada el {fechaLocal(datos.periodo.cerrado_en)}. Las boletas ya no se pueden modificar.</p>
            <p>
            <button type="button" onClick={() => abrir(`/boletas/periodo/${datos.periodo.id}/planilla.pdf`)}>
              Planilla general (PDF)
            </button>{' '}
            <button type="button" onClick={() => abrir(`/boletas/periodo/${datos.periodo.id}/boletas.pdf`)}>
              Todas las boletas (PDF)
            </button>
          </p>
                    {agruparPorSucursal(datos.boletas, (b) => b.colaboradores.sucursales?.nombre ?? 'Sin sucursal').map((grupo) => (
            <div key={grupo.nombre}>
              <h3>{grupo.nombre}</h3>
              <table>
                <thead>
                  <tr>
                    <th>Boleta</th>
                    <th>Empleado</th>
                    <th>Ingresos</th>
                    <th>Descuentos</th>
                    <th>Neto</th>
                    <th>Estado</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {grupo.elementos.map((b) => (
                    <tr key={b.id}>
                      <td>{b.numero}</td>
                      <td>{b.colaboradores.nombres} {b.colaboradores.apellidos}</td>
                      <td>{quetzales(b.total_ingresos)}</td>
                      <td>{quetzales(b.total_descuentos)}</td>
                      <td>{quetzales(b.neto)}</td>
                      <td>{ESTADO_BOLETA[b.estado]}</td>
                      <td>
                        <button type="button" onClick={() => abrir(`/boletas/${b.id}/boleta.pdf`)}>Boleta PDF</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <td colSpan={4}><strong>Subtotal {grupo.nombre}</strong></td>
                    <td><strong>{quetzales(grupo.elementos.reduce((suma, b) => suma + b.neto, 0))}</strong></td>
                    <td colSpan={2}></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          ))}
          <p><strong>Total pagado en la quincena: {quetzales(total)}</strong></p>
          {rol === 'rrhh' && porPagar > 0 && (
            <p>
              <button type="button" onClick={pagar} disabled={enviando}>
                {enviando ? 'Guardando...' : `Marcar las ${porPagar} boletas como pagadas`}
              </button>
            </p>
          )}
          {porPagar === 0 && <p>Todas las boletas están pagadas.</p>}
        </>
      )}
    </section>
  )
}