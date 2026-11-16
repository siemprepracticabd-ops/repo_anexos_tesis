import { useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import { llamarApi } from './api'

export default function JustificarAusencia({ ausencia, onGuardado, onCancelar }) {
  const [tipos, setTipos] = useState([])
  const [valores, setValores] = useState({ tipo_id: '', motivo: '' })
  const [errores, setErrores] = useState({})
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    supabase
      .from('tipos_ausencia')
      .select('id, nombre, con_goce')
      .order('nombre')
      .then(({ data }) => setTipos(data ?? []))
  }, [])

  function cambiar(evento) {
    const { name, value } = evento.target
    setValores({ ...valores, [name]: value })
  }

  async function enviar(evento) {
    evento.preventDefault()
    setErrores({})
    setError('')
    setEnviando(true)

    try {
      await llamarApi(`/ausencias/${ausencia.id}/justificacion`, {
        method: 'PUT',
        body: JSON.stringify(valores),
      })
      onGuardado()
    } catch (falla) {
      if (falla.campos) setErrores(falla.campos)
      else if (falla.estado) setError(falla.message)
      else setError('No se pudo conectar con el servidor')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={enviar}>
      <div>
        <label htmlFor="tipo_id">Tipo de ausencia</label>
        <select id="tipo_id" name="tipo_id" value={valores.tipo_id} onChange={cambiar}>
          <option value="">Selecciona un tipo</option>
          {tipos.map((t) => (
            <option key={t.id} value={t.id}>
              {t.nombre} ({t.con_goce ? 'con goce' : 'sin goce'})
            </option>
          ))}
        </select>
        {errores.tipo_id && <p role="alert">{errores.tipo_id}</p>}
      </div>

      <div>
        <label htmlFor="motivo">Motivo</label>
        <textarea
          id="motivo"
          name="motivo"
          rows={2}
          maxLength={500}
          value={valores.motivo}
          onChange={cambiar}
        />
        {errores.motivo && <p role="alert">{errores.motivo}</p>}
      </div>

      <button type="submit" disabled={enviando}>{enviando ? 'Guardando...' : 'Guardar'}</button>{' '}
      <button type="button" onClick={onCancelar}>Cancelar</button>
      {error && <p role="alert">{error}</p>}
    </form>
  )
}