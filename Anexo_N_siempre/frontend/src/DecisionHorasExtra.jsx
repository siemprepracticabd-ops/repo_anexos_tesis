import { useState } from 'react'
import { llamarApi } from './api'
import { formatoHoras } from './tiempo'

export default function DecisionHorasExtra({ registro, rol, onGuardado, onCancelar }) {
  const [valores, setValores] = useState({
    decision: registro.estado === 'pendiente' ? 'autorizada' : registro.estado,
    horas_pagadas: registro.minutos_pagados ? registro.minutos_pagados / 60 : '',
    justificacion: registro.justificacion ?? '',
    autorizado_por: registro.autorizado_por_nombre ?? '',
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
      await llamarApi(`/horas-extra/${registro.id}/decision`, {
        method: 'PUT',
        body: JSON.stringify({
          decision: valores.decision,
          minutos_pagados: valores.horas_pagadas === '' ? '' : Number(valores.horas_pagadas) * 60,
          justificacion: valores.justificacion,
          autorizado_por: valores.autorizado_por,
        }),
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
      <p>Tiempo detectado: <strong>{formatoHoras(registro.minutos_detectados)}</strong></p>

      <div>
        <label htmlFor="decision">Decisión</label>
        <select id="decision" name="decision" value={valores.decision} onChange={cambiar}>
          <option value="autorizada">Autorizar todo</option>
          <option value="parcial">Autorizar una parte</option>
          <option value="rechazada">Rechazar</option>
        </select>
        {errores.decision && <p role="alert">{errores.decision}</p>}
      </div>

      {valores.decision === 'parcial' && (
        <div>
          <label htmlFor="horas_pagadas">
            Horas que se pagan (de {registro.minutos_detectados / 60})
          </label>
          <input
            id="horas_pagadas"
            name="horas_pagadas"
            type="number"
            min="1"
            step="1"
            max={registro.minutos_detectados / 60 - 1}
            value={valores.horas_pagadas}
            onChange={cambiar}
          />
          {errores.minutos_pagados && <p role="alert">{errores.minutos_pagados}</p>}
        </div>
      )}

      <div>
        <label htmlFor="justificacion">Justificación</label>
        <textarea
          id="justificacion"
          name="justificacion"
          rows={2}
          maxLength={500}
          value={valores.justificacion}
          onChange={cambiar}
        />
        {errores.justificacion && <p role="alert">{errores.justificacion}</p>}
      </div>

      {rol === 'rrhh' && (
        <div>
          <label htmlFor="autorizado_por">Autorizado por</label>
          <input
            id="autorizado_por"
            name="autorizado_por"
            maxLength={120}
            value={valores.autorizado_por}
            onChange={cambiar}
          />
          {errores.autorizado_por && <p role="alert">{errores.autorizado_por}</p>}
        </div>
      )}

      <button type="submit" disabled={enviando}>{enviando ? 'Guardando...' : 'Guardar decisión'}</button>{' '}
      <button type="button" onClick={onCancelar}>Cancelar</button>
      {error && <p role="alert">{error}</p>}
    </form>
  )
}