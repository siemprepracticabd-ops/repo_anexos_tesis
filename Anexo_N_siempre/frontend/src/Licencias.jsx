import { useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import { llamarApi } from './api'

export default function Licencias({ colaborador, hoy, onCambiado, onCancelar }) {
  const [tipos, setTipos] = useState([])
  const [valores, setValores] = useState({ tipo_id: '', desde: hoy, hasta: hoy, motivo: '' })
  const [errores, setErrores] = useState({})
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    supabase
      .from('tipos_ausencia')
      .select('id, nombre')
      .order('nombre')
      .then(({ data }) => setTipos(data ?? []))
  }, [])

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
      onCambiado()
    } catch (falla) {
      if (falla.campos) setErrores(falla.campos)
      else if (falla.estado) setError(falla.message)
      else setError('No se pudo conectar con el servidor')
    } finally {
      setEnviando(false)
    }
  }

  function enviar(evento) {
    evento.preventDefault()
    llamar(`/colaboradores/${colaborador.id}/licencias`, { method: 'POST', body: JSON.stringify(valores) })
  }

  function anular(licencia) {
    if (!window.confirm(`¿Anular la licencia del ${licencia.fecha_desde} al ${licencia.fecha_hasta}?`)) return
    llamar(`/colaboradores/licencias/${licencia.id}`, { method: 'DELETE' })
  }

  const licencias = [...colaborador.licencias].sort((a, b) => b.fecha_desde.localeCompare(a.fecha_desde))

  return (
    <div>
      <h3>Permisos y suspensiones de {colaborador.nombres} {colaborador.apellidos}</h3>

      {licencias.length === 0 && <p>No tiene licencias registradas.</p>}
      {licencias.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Tipo</th>
              <th>Desde</th>
              <th>Hasta</th>
              <th>Motivo</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {licencias.map((l) => (
              <tr key={l.id}>
                <td>{l.tipos_ausencia?.nombre}</td>
                <td>{l.fecha_desde}</td>
                <td>{l.fecha_hasta}</td>
                <td>{l.motivo}</td>
                <td>
                  <button type="button" onClick={() => anular(l)} disabled={enviando}>Anular</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <form onSubmit={enviar}>
        <div>
          <label htmlFor="tipo_licencia">Tipo</label>
          <select id="tipo_licencia" name="tipo_id" value={valores.tipo_id} onChange={cambiar}>
            <option value="">Elige el tipo</option>
            {tipos.map((t) => (
              <option key={t.id} value={t.id}>{t.nombre}</option>
            ))}
          </select>
          {errores.tipo_id && <p role="alert">{errores.tipo_id}</p>}
        </div>

        <div>
          <label htmlFor="desde_licencia">Desde</label>
          <input id="desde_licencia" name="desde" type="date" value={valores.desde} onChange={cambiar} />
          {errores.desde && <p role="alert">{errores.desde}</p>}
        </div>

        <div>
          <label htmlFor="hasta_licencia">Hasta</label>
          <input id="hasta_licencia" name="hasta" type="date" value={valores.hasta} onChange={cambiar} />
          {errores.hasta && <p role="alert">{errores.hasta}</p>}
        </div>

        <div>
          <label htmlFor="motivo_licencia">Motivo</label>
          <textarea
            id="motivo_licencia"
            name="motivo"
            rows={2}
            maxLength={500}
            value={valores.motivo}
            onChange={cambiar}
          />
          {errores.motivo && <p role="alert">{errores.motivo}</p>}
        </div>

        <button type="submit" disabled={enviando}>{enviando ? 'Guardando...' : 'Registrar licencia'}</button>{' '}
        <button type="button" onClick={onCancelar}>Cerrar</button>
        {error && <p role="alert">{error}</p>}
      </form>
    </div>
  )
}
