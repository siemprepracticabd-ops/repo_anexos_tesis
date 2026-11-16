import { useState } from 'react'
import { llamarApi } from './api'

export default function PanelPublicacion({ programacion, esUltima, pendientes, onPublicada, onVersionCreada }) {
  const [motivo, setMotivo] = useState('')
  const [error, setError] = useState('')
  const [ocupado, setOcupado] = useState(false)

  const pideMotivo = programacion.version > 1

  async function ejecutar(ruta, cuerpo) {
    setError('')
    setOcupado(true)
    try {
      return await llamarApi(`/programaciones/${programacion.id}/${ruta}`, {
        method: 'POST',
        body: JSON.stringify(cuerpo),
      })
    } catch (falla) {
      setError(falla.estado ? falla.message : 'No se pudo conectar con el servidor')
      return null
    } finally {
      setOcupado(false)
    }
  }

  async function publicar() {
    const texto = `¿Publicar la versión ${programacion.version}? Ya no se podrá editar.`
    if (!window.confirm(texto)) return
    if (await ejecutar('publicar', { motivo })) {
      setMotivo('')
      onPublicada()
    }
  }

  async function crearVersion() {
    const texto = `¿Crear la versión ${programacion.version + 1} para modificar esta programación?`
    if (!window.confirm(texto)) return
    const nueva = await ejecutar('versiones', {})
    if (nueva) onVersionCreada(nueva.id)
  }

  if (programacion.estado === 'borrador') {
    return (
      <section>
        <h2>Publicar</h2>
        {pideMotivo && (
          <>
            <label htmlFor="motivo">Motivo del cambio</label>
            <textarea
              id="motivo"
              rows={2}
              maxLength={500}
              value={motivo}
              onChange={(evento) => setMotivo(evento.target.value)}
            />
          </>
        )}
        {pendientes > 0 && <p>Guarda los cambios antes de publicar.</p>}
        <button
          type="button"
          onClick={publicar}
          disabled={ocupado || pendientes > 0 || (pideMotivo && motivo.trim() === '')}
        >
          {ocupado ? 'Publicando...' : `Publicar versión ${programacion.version}`}
        </button>
        {error && <p role="alert">{error}</p>}
      </section>
    )
  }

  if (programacion.estado === 'publicada' && esUltima) {
    return (
      <section>
        <h2>Modificar</h2>
        <p>Una programación publicada no se edita: se crea una versión nueva y se explica el cambio.</p>
        <button type="button" onClick={crearVersion} disabled={ocupado}>
          Crear versión {programacion.version + 1}
        </button>
        {error && <p role="alert">{error}</p>}
      </section>
    )
  }

  return null
}