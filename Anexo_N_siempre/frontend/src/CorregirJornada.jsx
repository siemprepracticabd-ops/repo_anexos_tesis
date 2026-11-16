import { useState } from 'react'
import { llamarApi } from './api'
import { fechaHoraLocal } from './tiempo'

export default function CorregirJornada({ jornada, onGuardado, onCancelar }) {
  const inicial = {
    entrada: fechaHoraLocal(jornada.entrada?.marcado_en),
    salida: fechaHoraLocal(jornada.salida?.marcado_en),
  }
  const [valores, setValores] = useState({ ...inicial, motivo: '' })
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

    // solo se manda lo que cambio
    const cuerpo = {
      entrada: valores.entrada !== inicial.entrada ? valores.entrada : '',
      salida: valores.salida !== inicial.salida ? valores.salida : '',
      motivo: valores.motivo,
    }
    if (!cuerpo.entrada && !cuerpo.salida) {
      setError('Cambia la hora de entrada o la de salida')
      return
    }

    setEnviando(true)
    try {
      await llamarApi(`/jornadas/${jornada.id}/correccion`, { method: 'POST', body: JSON.stringify(cuerpo) })
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
        Corregir horas de {jornada.colaboradores.nombres} {jornada.colaboradores.apellidos} · {jornada.fecha}
      </h3>
      <p>La marca original se conserva. La hora nueva la reemplaza y queda el motivo registrado.</p>

      <div>
        <label htmlFor="c_entrada">Entrada</label>
        <input id="c_entrada" name="entrada" type="datetime-local" value={valores.entrada} onChange={cambiar} />
        {errores.entrada && <p role="alert">{errores.entrada}</p>}
      </div>

      <div>
        <label htmlFor="c_salida">Salida</label>
        <input id="c_salida" name="salida" type="datetime-local" value={valores.salida} onChange={cambiar} />
        {errores.salida && <p role="alert">{errores.salida}</p>}
      </div>

      <div>
        <label htmlFor="c_motivo">Motivo de la corrección</label>
        <textarea id="c_motivo" name="motivo" rows={3} maxLength={500} value={valores.motivo} onChange={cambiar} />
        {errores.motivo && <p role="alert">{errores.motivo}</p>}
      </div>

      <button type="submit" disabled={enviando}>{enviando ? 'Guardando...' : 'Guardar corrección'}</button>{' '}
      <button type="button" onClick={onCancelar}>Cancelar</button>
      {error && <p role="alert">{error}</p>}
    </form>
  )
}
