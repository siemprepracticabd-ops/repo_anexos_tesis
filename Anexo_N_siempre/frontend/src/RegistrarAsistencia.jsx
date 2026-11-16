import { useState } from 'react'
import { llamarApi } from './api'

// suma un dia a una fecha aaaa-mm-dd, para turnos que cruzan la medianoche
function diaSiguiente(fecha) {
  const d = new Date(`${fecha}T12:00:00`)
  d.setDate(d.getDate() + 1)
  return d.toLocaleDateString('en-CA')
}

export default function RegistrarAsistencia({ ausencia, onGuardado, onCancelar }) {
  const [valores, setValores] = useState({ entrada: '', salida: '', motivo: '' })
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

    if (!valores.entrada || !valores.salida) {
      setErrores({
        entrada: valores.entrada ? '' : 'Indica la hora',
        salida: valores.salida ? '' : 'Indica la hora',
      })
      return
    }

    // si la salida es menor o igual que la entrada, salio al dia siguiente
    const diaSalida = valores.salida <= valores.entrada ? diaSiguiente(ausencia.fecha) : ausencia.fecha
    setEnviando(true)
    try {
      await llamarApi(`/ausencias/${ausencia.id}/asistencia`, {
        method: 'POST',
        body: JSON.stringify({
          entrada: `${ausencia.fecha}T${valores.entrada}`,
          salida: `${diaSalida}T${valores.salida}`,
          motivo: valores.motivo,
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
      <h3>
        Registrar asistencia de {ausencia.colaboradores.nombres} {ausencia.colaboradores.apellidos} · {ausencia.fecha}
      </h3>
      <p>Para cuando sí llegó y olvidó marcar. La ausencia se convierte en jornada y queda el motivo registrado.</p>

      <div>
        <label htmlFor="r_entrada">Hora de entrada</label>
        <input id="r_entrada" name="entrada" type="time" value={valores.entrada} onChange={cambiar} />
        {errores.entrada && <p role="alert">{errores.entrada}</p>}
      </div>

      <div>
        <label htmlFor="r_salida">Hora de salida</label>
        <input id="r_salida" name="salida" type="time" value={valores.salida} onChange={cambiar} />
        {errores.salida && <p role="alert">{errores.salida}</p>}
      </div>

      <div>
        <label htmlFor="r_motivo">Motivo</label>
        <textarea id="r_motivo" name="motivo" rows={3} maxLength={500} value={valores.motivo} onChange={cambiar} />
        {errores.motivo && <p role="alert">{errores.motivo}</p>}
      </div>

      <button type="submit" disabled={enviando}>{enviando ? 'Guardando...' : 'Registrar asistencia'}</button>{' '}
      <button type="button" onClick={onCancelar}>Cancelar</button>
      {error && <p role="alert">{error}</p>}
    </form>
  )
}
