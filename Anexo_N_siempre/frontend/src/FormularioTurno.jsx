import { useState } from 'react'
import { llamarApi } from './api'

export default function FormularioTurno({ turno, onGuardado, onCancelar }) {
  const [valores, setValores] = useState({
    nombre: turno?.nombre ?? '',
    hora_inicio: turno?.hora_inicio.slice(0, 5) ?? '07:00',
    hora_fin: turno?.hora_fin.slice(0, 5) ?? '17:00',
    tipo_jornada: turno?.tipo_jornada ?? 'diurna',
    horas_ordinarias: turno?.horas_ordinarias ?? 8,
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
      await llamarApi(turno ? `/turnos/${turno.id}` : '/turnos', {
        method: turno ? 'PUT' : 'POST',
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
      <h2>{turno ? `Editar turno: ${turno.nombre}` : 'Nuevo turno'}</h2>

      <div>
        <label htmlFor="nombre">Nombre</label>
        <input id="nombre" name="nombre" maxLength={60} value={valores.nombre} onChange={cambiar} />
        {errores.nombre && <p role="alert">{errores.nombre}</p>}
      </div>

      <div>
        <label htmlFor="hora_inicio">Hora de inicio</label>
        <input id="hora_inicio" name="hora_inicio" type="time" value={valores.hora_inicio} onChange={cambiar} />
        {errores.hora_inicio && <p role="alert">{errores.hora_inicio}</p>}
      </div>

      <div>
        <label htmlFor="hora_fin">Hora de fin</label>
        <input id="hora_fin" name="hora_fin" type="time" value={valores.hora_fin} onChange={cambiar} />
        {errores.hora_fin && <p role="alert">{errores.hora_fin}</p>}
      </div>

      <div>
        <label htmlFor="horas_ordinarias">Horas ordinarias</label>
        <input
          id="horas_ordinarias"
          name="horas_ordinarias"
          type="number"
          min="0.25"
          max="24"
          step="0.25"
          value={valores.horas_ordinarias}
          onChange={cambiar}
        />
        {errores.horas_ordinarias && <p role="alert">{errores.horas_ordinarias}</p>}
      </div>

      <div>
        <label htmlFor="tipo_jornada">Tipo de jornada</label>
        <select id="tipo_jornada" name="tipo_jornada" value={valores.tipo_jornada} onChange={cambiar}>
          <option value="diurna">Diurna</option>
          <option value="mixta">Mixta</option>
          <option value="nocturna">Nocturna</option>
        </select>
        {errores.tipo_jornada && <p role="alert">{errores.tipo_jornada}</p>}
      </div>

      <button type="submit" disabled={enviando}>{enviando ? 'Guardando...' : 'Guardar turno'}</button>{' '}
      <button type="button" onClick={onCancelar}>Cancelar</button>
      {error && <p role="alert">{error}</p>}
    </form>
  )
}