import { useState } from 'react'
import { llamarApi } from './api'

export default function ConfirmarJornada({ jornada, onGuardado, onCancelar }) {
  const [motivo, setMotivo] = useState('')
  const [errores, setErrores] = useState({})
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function enviar(evento) {
    evento.preventDefault()
    setErrores({})
    setError('')
    setEnviando(true)

    try {
      await llamarApi(`/jornadas/${jornada.id}/confirmacion`, {
        method: 'POST',
        body: JSON.stringify({ motivo }),
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
        <label htmlFor="motivo_confirmacion">Por qué la jornada es correcta</label>
        <textarea
          id="motivo_confirmacion"
          rows={2}
          maxLength={500}
          value={motivo}
          onChange={(evento) => setMotivo(evento.target.value)}
        />
        {errores.motivo && <p role="alert">{errores.motivo}</p>}
      </div>

      <button type="submit" disabled={enviando}>{enviando ? 'Guardando...' : 'Confirmar jornada'}</button>{' '}
      <button type="button" onClick={onCancelar}>Cancelar</button>
      {error && <p role="alert">{error}</p>}
    </form>
  )
}