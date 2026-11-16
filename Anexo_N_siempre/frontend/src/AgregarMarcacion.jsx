import { useState } from 'react'
import { llamarApi } from './api'

export default function AgregarMarcacion({ jornada, onGuardado, onCancelar }) {
  const [valores, setValores] = useState({
    fecha: jornada.fecha,
    hora: '',
    tipo: jornada.entrada ? 'salida' : 'entrada',
    motivo: '',
  })
  const [errores, setErrores] = useState({})
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

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
      await llamarApi('/marcaciones-manuales', {
        method: 'POST',
        body: JSON.stringify({ ...valores, colaborador_id: jornada.colaboradores.id }),
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
        <label htmlFor="tipo">Marcación que faltó</label>
        <select id="tipo" name="tipo" value={valores.tipo} onChange={cambiar}>
          <option value="entrada">Entrada</option>
          <option value="salida">Salida</option>
        </select>
        {errores.tipo && <p role="alert">{errores.tipo}</p>}
      </div>

      <div>
        <label htmlFor="fecha">Día</label>
        <input id="fecha" name="fecha" type="date" value={valores.fecha} onChange={cambiar} />
        {errores.fecha && <p role="alert">{errores.fecha}</p>}
      </div>

      <div>
        <label htmlFor="hora">Hora</label>
        <input id="hora" name="hora" type="time" value={valores.hora} onChange={cambiar} />
        {errores.hora && <p role="alert">{errores.hora}</p>}
      </div>

      <div>
        <label htmlFor="motivo">Motivo</label>
        <textarea id="motivo" name="motivo" rows={2} maxLength={500} value={valores.motivo} onChange={cambiar} />
        {errores.motivo && <p role="alert">{errores.motivo}</p>}
      </div>

      <button type="submit" disabled={enviando}>{enviando ? 'Guardando...' : 'Agregar marcación'}</button>{' '}
      <button type="button" onClick={onCancelar}>Cancelar</button>
      {error && <p role="alert">{error}</p>}
    </form>
  )
}