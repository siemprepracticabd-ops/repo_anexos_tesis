import { useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import { llamarApi } from './api'
import { quetzales } from './pago'

// descuentos de una persona en una quincena; la nota sale en la boleta
export default function DescuentosManuales({ persona, desde, hasta, onCambiado, onCerrar }) {
  const [lista, setLista] = useState(null)
  const [valores, setValores] = useState({ monto: '', motivo: '' })
  const [errores, setErrores] = useState({})
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    supabase
      .from('descuentos_manuales')
      .select('id, monto, motivo, creado_en')
      .eq('colaborador_id', persona.colaborador_id)
      .eq('fecha_inicio', desde)
      .eq('fecha_fin', hasta)
      .order('creado_en')
      .then(({ data, error: falla }) => {
        if (falla) setError('No se pudieron cargar los descuentos')
        else setLista(data)
      })
  }, [persona.colaborador_id, desde, hasta, version])

  function cambiar(evento) {
    const { name, value } = evento.target
    setValores({ ...valores, [name]: value })
  }

  async function llamar(ruta, opciones) {
    setErrores({})
    setError('')
    setEnviando(true)
    try {
      await llamarApi(ruta, opciones)
      setVersion((v) => v + 1)
      onCambiado()
      return true
    } catch (falla) {
      if (falla.campos) setErrores(falla.campos)
      else if (falla.estado) setError(falla.message)
      else setError('No se pudo conectar con el servidor')
      return false
    } finally {
      setEnviando(false)
    }
  }

  async function agregar(evento) {
    evento.preventDefault()
    const listo = await llamar('/planilla/descuentos', {
      method: 'POST',
      body: JSON.stringify({ ...valores, colaborador_id: persona.colaborador_id, desde, hasta }),
    })
    if (listo) setValores({ monto: '', motivo: '' })
  }

  function quitar(descuento) {
    if (!window.confirm(`¿Quitar el descuento de ${quetzales(descuento.monto)}?`)) return
    llamar(`/planilla/descuentos/${descuento.id}`, { method: 'DELETE' })
  }

  return (
    <div>
      <h3>Descuentos de {persona.nombre}</h3>
      <p>Quincena del {desde} al {hasta}. La nota de cada descuento se imprime en la boleta.</p>

      {lista === null && !error && <p>Cargando...</p>}
      {lista?.length === 0 && <p>No hay descuentos en esta quincena.</p>}
      {lista?.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Monto</th>
              <th>Nota</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {lista.map((d) => (
              <tr key={d.id}>
                <td>{quetzales(d.monto)}</td>
                <td>{d.motivo}</td>
                <td><button type="button" disabled={enviando} onClick={() => quitar(d)}>Quitar</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <form onSubmit={agregar}>
        <h3>Agregar un descuento</h3>
        <div>
          <label htmlFor="d_monto">Monto (Q)</label>
          <input id="d_monto" name="monto" inputMode="decimal" value={valores.monto} onChange={cambiar} />
          {errores.monto && <p role="alert">{errores.monto}</p>}
        </div>
        <div>
          <label htmlFor="d_motivo">Por qué se descuenta</label>
          <textarea id="d_motivo" name="motivo" rows={2} maxLength={200} value={valores.motivo} onChange={cambiar} />
          {errores.motivo && <p role="alert">{errores.motivo}</p>}
        </div>
        <button type="submit" disabled={enviando}>{enviando ? 'Guardando...' : 'Agregar descuento'}</button>{' '}
        <button type="button" onClick={onCerrar}>Cerrar</button>
        {error && <p role="alert">{error}</p>}
      </form>
    </div>
  )
}
