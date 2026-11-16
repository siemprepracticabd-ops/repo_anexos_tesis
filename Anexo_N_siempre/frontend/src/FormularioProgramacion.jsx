import { useState } from 'react'
import { llamarApi } from './api'
import { sugerirPeriodos } from './periodos'

export default function FormularioProgramacion({ existentes, onCreada }) {
  const [tipo, setTipo] = useState('semanal')
  const [inicio, setInicio] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  const periodos = sugerirPeriodos(tipo)

  function cambiarTipo(evento) {
    setTipo(evento.target.value)
    setInicio('')
  }

  async function enviar(evento) {
    evento.preventDefault()
    setError('')
    setEnviando(true)

    try {
      await llamarApi('/programaciones', {
        method: 'POST',
        body: JSON.stringify({ tipo, fecha_inicio: inicio }),
      })
      setInicio('')
      onCreada()
    } catch (falla) {
      if (falla.campos) setError(Object.values(falla.campos).join('. '))
      else if (falla.estado) setError(falla.message)
      else setError('No se pudo conectar con el servidor')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={enviar}>
      <h2>Nueva programación</h2>

      <label htmlFor="tipo">Tipo</label>
      <select id="tipo" value={tipo} onChange={cambiarTipo}>
        <option value="semanal">Semanal (lunes a domingo)</option>
        <option value="quincenal">Quincenal (1 al 15, 16 al fin de mes)</option>
      </select>

      <label htmlFor="inicio">Período</label>
      <select id="inicio" value={inicio} onChange={(evento) => setInicio(evento.target.value)}>
        <option value="">Selecciona un período</option>
        {periodos.map((p) => {
          const yaExiste = existentes.has(`${tipo}|${p.inicio}`)
          return (
            <option key={p.inicio} value={p.inicio} disabled={yaExiste}>
              {p.etiqueta}{yaExiste && ' (ya creada)'}
            </option>
          )
        })}
      </select>

      <button type="submit" disabled={enviando || inicio === ''}>
        {enviando ? 'Creando...' : 'Crear'}
      </button>

      {error && <p role="alert">{error}</p>}
    </form>
  )
}