import { useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import { llamarApi } from './api'

function textoDeError(falla) {
  if (falla.campos) return Object.values(falla.campos).join('. ')
  if (falla.estado) return falla.message
  return 'No se pudo conectar con el servidor'
}

export default function Puestos({ rol }) {
  const [puestos, setPuestos] = useState(null)
  const [nuevo, setNuevo] = useState('')
  const [editando, setEditando] = useState(null)
  const [nombreEditado, setNombreEditado] = useState('')
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)

  const puedeEditar = rol === 'rrhh'

  useEffect(() => {
    supabase
      .from('puestos')
      .select('id, nombre, colaboradores(count)')
      .order('nombre')
      .then(({ data, error: falla }) => {
        if (falla) setError('No se pudieron cargar los puestos')
        else setPuestos(data)
      })
  }, [version])

  async function ejecutar(accion) {
    setError('')
    try {
      await accion()
      setVersion((v) => v + 1)
      return true
    } catch (falla) {
      setError(textoDeError(falla))
      return false
    }
  }

  async function crear(evento) {
    evento.preventDefault()
    const listo = await ejecutar(() =>
      llamarApi('/puestos', { method: 'POST', body: JSON.stringify({ nombre: nuevo }) })
    )
    if (listo) setNuevo('')
  }

  async function guardarNombre(evento) {
    evento.preventDefault()
    const listo = await ejecutar(() =>
      llamarApi(`/puestos/${editando}`, { method: 'PUT', body: JSON.stringify({ nombre: nombreEditado }) })
    )
    if (listo) setEditando(null)
  }

  async function eliminar(puesto) {
    if (!window.confirm(`¿Eliminar el puesto «${puesto.nombre}»?`)) return
    await ejecutar(() => llamarApi(`/puestos/${puesto.id}`, { method: 'DELETE' }))
  }

  return (
    <main>
      <h1>Puestos</h1>

      {puedeEditar && (
        <form onSubmit={crear}>
          <label htmlFor="nuevo">Nuevo puesto</label>{' '}
          <input id="nuevo" value={nuevo} maxLength={60} onChange={(evento) => setNuevo(evento.target.value)} />{' '}
          <button type="submit">Agregar</button>
        </form>
      )}

      {error && <p role="alert">{error}</p>}
      {puestos === null && !error && <p>Cargando...</p>}
      {puestos?.length === 0 && <p>Todavía no hay puestos.</p>}

      {puestos?.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Puesto</th>
              <th>Colaboradores</th>
              {puedeEditar && <th></th>}
            </tr>
          </thead>
          <tbody>
            {puestos.map((p) => {
              const usos = p.colaboradores[0]?.count ?? 0
              return (
                <tr key={p.id}>
                  <td>
                    {editando === p.id ? (
                      <form onSubmit={guardarNombre}>
                        <input
                          value={nombreEditado}
                          maxLength={60}
                          onChange={(evento) => setNombreEditado(evento.target.value)}
                        />{' '}
                        <button type="submit">Guardar</button>{' '}
                        <button type="button" onClick={() => setEditando(null)}>Cancelar</button>
                      </form>
                    ) : (
                      p.nombre
                    )}
                  </td>
                  <td>{usos}</td>
                  {puedeEditar && (
                    <td>
                      <button
                        type="button"
                        onClick={() => {
                          setEditando(p.id)
                          setNombreEditado(p.nombre)
                        }}
                      >
                        Renombrar
                      </button>{' '}
                      <button
                        type="button"
                        disabled={usos > 0}
                        title={usos > 0 ? 'Hay colaboradores con este puesto' : ''}
                        onClick={() => eliminar(p)}
                      >
                        Eliminar
                      </button>
                    </td>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </main>
  )
}