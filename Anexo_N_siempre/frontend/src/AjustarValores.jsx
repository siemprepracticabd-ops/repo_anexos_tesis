import { useState } from 'react'
import { llamarApi } from './api'
import { quetzales } from './pago'

export default function AjustarValores({ persona, desde, hasta, onGuardado, onCancelar }) {
  const [valores, setValores] = useState({
    valor_hora: persona.ajuste?.valor_hora ?? '',
    valor_hora_extra: persona.ajuste?.valor_hora_extra ?? '',
    motivo: persona.ajuste?.motivo ?? '',
  })
  const [errores, setErrores] = useState({})
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  function cambiar(evento) {
    const { name, value } = evento.target
    setValores({ ...valores, [name]: value })
  }

  async function guardar(cuerpo) {
    setErrores({})
    setError('')
    setEnviando(true)

    try {
      await llamarApi('/planilla/ajustes', {
        method: 'PUT',
        body: JSON.stringify({ ...cuerpo, colaborador_id: persona.colaborador_id, desde, hasta }),
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

  function enviar(evento) {
    evento.preventDefault()
    guardar(valores)
  }

  function quitar() {
    guardar({ valor_hora: '', valor_hora_extra: '', motivo: '' })
  }

  return (
    <form onSubmit={enviar}>
      <p>
        Estos valores se usan solo en esta quincena. La ficha de {persona.nombre} no cambia.
      </p>

      {persona.forma_pago === 'por_hora' && (
        <div>
          <label htmlFor="valor_hora">Valor de la hora normal</label>
          <input
            id="valor_hora"
            name="valor_hora"
            type="number"
            step="0.01"
            min="0.01"
            placeholder={String(persona.valor_hora_defecto)}
            value={valores.valor_hora}
            onChange={cambiar}
          />
          <small> Por defecto: {quetzales(persona.valor_hora_defecto)}</small>
          {errores.valor_hora && <p role="alert">{errores.valor_hora}</p>}
        </div>
      )}

      <div>
        <label htmlFor="valor_hora_extra">Valor de la hora extra</label>
        <input
          id="valor_hora_extra"
          name="valor_hora_extra"
          type="number"
          step="0.01"
          min="0.01"
          value={valores.valor_hora_extra}
          onChange={cambiar}
        />
        <small>
          {' '}Por defecto: {quetzales(persona.valor_extra_defecto_dia)} de día, {quetzales(persona.valor_extra_defecto_noche)} nocturna
        </small>
        {errores.valor_hora_extra && <p role="alert">{errores.valor_hora_extra}</p>}
      </div>

      <div>
        <label htmlFor="motivo_ajuste">Motivo (opcional)</label>
        <textarea
          id="motivo_ajuste"
          name="motivo"
          rows={2}
          maxLength={500}
          value={valores.motivo}
          onChange={cambiar}
        />
        {errores.motivo && <p role="alert">{errores.motivo}</p>}
      </div>

      <button type="submit" disabled={enviando}>{enviando ? 'Guardando...' : 'Guardar valores'}</button>{' '}
      {persona.ajuste && (
        <>
          <button type="button" onClick={quitar} disabled={enviando}>Volver a los valores por defecto</button>{' '}
        </>
      )}
      <button type="button" onClick={onCancelar}>Cancelar</button>
      {error && <p role="alert">{error}</p>}
    </form>
  )
}