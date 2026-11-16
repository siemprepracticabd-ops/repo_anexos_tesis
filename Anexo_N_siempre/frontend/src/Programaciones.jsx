import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from './supabaseClient'
import FormularioProgramacion from './FormularioProgramacion'

function fechaLarga(texto) {
  const [anio, mes, dia] = texto.split('-')
  return `${dia}/${mes}/${anio}`
}

export default function Programaciones({ rol }) {
  const [programaciones, setProgramaciones] = useState(null)
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)

  useEffect(() => {
    supabase
      .from('programaciones')
      .select('id, tipo, fecha_inicio, fecha_fin, version, estado')
      .eq('automatica', false)
      .order('fecha_inicio', { ascending: false })
      .then(({ data, error: errorLista }) => {
        if (errorLista) setError('No se pudieron cargar las programaciones')
        else setProgramaciones(data)
      })
  }, [version])

  const existentes = new Set((programaciones ?? []).map((p) => `${p.tipo}|${p.fecha_inicio}`))

  return (
    <main>
      <h1>Programación</h1>

      {rol === 'rrhh' && (
        <FormularioProgramacion existentes={existentes} onCreada={() => setVersion(version + 1)} />
      )}

      {error && <p role="alert">{error}</p>}
      {programaciones === null && !error && <p>Cargando...</p>}
      {programaciones?.length === 0 && <p>Todavía no hay programaciones.</p>}

      {programaciones?.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Período</th>
              <th>Tipo</th>
              <th>Versión</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {programaciones.map((p) => (
              <tr key={p.id}>
                <td>
                <Link to={`/programacion/${p.id}`}>
                    {fechaLarga(p.fecha_inicio)} al {fechaLarga(p.fecha_fin)}
                </Link>
                </td>
                <td>{p.tipo}</td>
                <td>{p.version}</td>
                <td>{p.estado}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  )
}