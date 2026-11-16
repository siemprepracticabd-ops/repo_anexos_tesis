import { useState } from 'react'
import { llamarApi } from './api'
import { aTexto } from './periodos'
import CamposPago from './CamposPago'

export default function CambiarCondiciones({ colaborador, vigente, onCambiado, onCancelar }) {
  const [valores, setValores] = useState(() => ({
    modalidad: colaborador.modalidad,
    forma_pago: vigente?.forma_pago ?? 'salario_fijo',
    salario_mensual: vigente?.salario_mensual ?? '',
    tarifa: vigente?.tarifa ?? '',
    desde: aTexto(new Date()),
  }))
  const [errores, setErrores] = useState({})
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function enviar(evento) {
    evento.preventDefault()
    setErrores({})
    setError('')
    setEnviando(true)

    try {
      await llamarApi(`/colaboradores/${colaborador.id}/condiciones`, {
        method: 'PUT',
        body: JSON.stringify(valores),
      })
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
      <h3>Condiciones de {colaborador.nombres} {colaborador.apellidos}</h3>

      <CamposPago
        valores={valores}
        errores={errores}
        onChange={(campos) => setValores({ ...valores, ...campos })}
      />

      <div>
        <label htmlFor="desde">Vigente desde</label>
        <input
          id="desde"
          type="date"
          value={valores.desde}
          onChange={(evento) => setValores({ ...valores, desde: evento.target.value })}
        />
        {errores.desde && <p role="alert">{errores.desde}</p>}
      </div>

      <button type="submit" disabled={enviando}>{enviando ? 'Guardando...' : 'Guardar condiciones'}</button>{' '}
      <button type="button" onClick={onCancelar}>Cancelar</button>
      {error && <p role="alert">{error}</p>}
    </form>
  )
}