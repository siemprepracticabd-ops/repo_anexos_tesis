import { useState } from 'react'
import { llamarApi } from './api'

export default function EstadoLaboral({ colaborador, activo, hoy, onCambiado, onCancelar }) {
  const [fecha, setFecha] = useState(hoy)
  const [motivo, setMotivo] = useState('')
  const [errores, setErrores] = useState({})
  const [error, setError] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [enviando, setEnviando] = useState(false)

  const nombre = `${colaborador.nombres} ${colaborador.apellidos}`

  async function enviar(evento) {
    evento.preventDefault()
    const aviso = activo
      ? `¿Dar de baja a ${nombre}? Sus turnos programados después de esa fecha quedarán por reasignar.`
      : `¿Reactivar a ${nombre}?`
    if (!window.confirm(aviso)) return

    setErrores({})
    setError('')
    setMensaje('')
    setEnviando(true)

    try {
      if (activo) {
        const respuesta = await llamarApi(`/colaboradores/${colaborador.id}/baja`, {
          method: 'POST',
          body: JSON.stringify({ fecha, motivo }),
        })
        setMensaje(`Baja registrada. Turnos por reasignar: ${respuesta.turnos_liberados}.`)
      } else {
        await llamarApi(`/colaboradores/${colaborador.id}/reactivacion`, {
          method: 'POST',
          body: JSON.stringify({ fecha }),
        })
        setMensaje('Colaborador reactivado.')
      }
      onCambiado()
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
      <h3>{activo ? `Dar de baja a ${nombre}` : `Reactivar a ${nombre}`}</h3>

      <div>
        <label htmlFor="fecha_estado">{activo ? 'Último día de trabajo' : 'Fecha de reingreso'}</label>
        <input id="fecha_estado" type="date" value={fecha} onChange={(evento) => setFecha(evento.target.value)} />
        {errores.fecha && <p role="alert">{errores.fecha}</p>}
      </div>

      {activo && (
        <div>
          <label htmlFor="motivo_baja">Motivo de la baja</label>
          <textarea
            id="motivo_baja"
            rows={2}
            maxLength={500}
            value={motivo}
            onChange={(evento) => setMotivo(evento.target.value)}
          />
          {errores.motivo && <p role="alert">{errores.motivo}</p>}
        </div>
      )}

      <button type="submit" disabled={enviando}>
        {enviando ? 'Guardando...' : activo ? 'Dar de baja' : 'Reactivar'}
      </button>{' '}
      <button type="button" onClick={onCancelar}>Cerrar</button>
      {error && <p role="alert">{error}</p>}
      {mensaje && <p role="status">{mensaje}</p>}
    </form>
  )
}
