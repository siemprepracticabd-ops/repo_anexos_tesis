import { useState } from 'react'
import { llamarApi } from './api'

export default function DecisionDescuento({ registro, rol, onGuardado, onCancelar }) {
  const [valores, setValores] = useState({
    decision: registro.estado === 'pendiente' ? 'aplicado' : registro.estado,
    horas_descontadas: registro.minutos_descontados ? registro.minutos_descontados / 60 : '',
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
      await llamarApi(`/descuentos/${registro.id}/decision`, {
        method: 'PUT',
        body: JSON.stringify({
          decision: valores.decision,
          minutos_descontados: valores.horas_descontadas === '' ? '' : Number(valores.horas_descontadas) * 60,
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
      <p>
        Tardanzas y salidas anticipadas acumuladas en la quincena: <strong>{registro.minutos_detectados / 60} h</strong>.
        Solo se descuentan horas completas.
      </p>

      <div>
        <label htmlFor="decision_descuento">Decisión</label>
        <select id="decision_descuento" name="decision" value={valores.decision} onChange={cambiar}>
          <option value="aplicado">Descontar todo</option>
          <option value="parcial">Descontar una parte</option>
          <option value="no_aplicado">No descontar</option>
        </select>
        {errores.decision && <p role="alert">{errores.decision}</p>}
      </div>

      {valores.decision === 'parcial' && (
        <div>
          <label htmlFor="horas_descontadas">
            Horas que se descuentan (de {registro.minutos_detectados / 60})
          </label>
          <input
            id="horas_descontadas"
            name="horas_descontadas"
            type="number"
            min="1"
            step="1"
            max={registro.minutos_detectados / 60 - 1}
            value={valores.horas_descontadas}
            onChange={cambiar}
          />
          {errores.minutos_descontados && <p role="alert">{errores.minutos_descontados}</p>}
        </div>
      )}

      <div>
        <label htmlFor="justificacion_descuento">Justificación</label>
        <textarea
          id="justificacion_descuento"
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
          <label htmlFor="autorizado_por_descuento">Autorizado por</label>
          <input
            id="autorizado_por_descuento"
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