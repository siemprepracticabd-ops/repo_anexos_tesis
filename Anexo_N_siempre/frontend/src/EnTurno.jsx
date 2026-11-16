import { useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import { horaLocal } from './tiempo'

// quien esta trabajando ahora, de una sucursal a la vez
export default function EnTurno({ sucursales }) {
  const [activos, setActivos] = useState(null)
  const [elegida, setElegida] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    function cargar() {
      supabase
        .from('en_turno_ahora')
        .select('colaborador_id, sucursal_id, turno, nombres, apellidos, puesto, entrada')
        .then(({ data, error: falla }) => {
          if (falla) setError('No se pudo cargar quién está en turno')
          else {
            setError('')
            setActivos(data)
          }
        })
    }

    cargar()
    const reloj = setInterval(cargar, 60000)
    return () => clearInterval(reloj)
  }, [])

  const sucursalActual = elegida || sucursales[0]?.id || ''
  const lista = (activos ?? [])
    .filter((a) => a.sucursal_id === sucursalActual)
    .sort((a, b) => a.apellidos.localeCompare(b.apellidos) || a.nombres.localeCompare(b.nombres))
  const cuenta = (id) => (activos ?? []).filter((a) => a.sucursal_id === id).length

  return (
    <section aria-label="En turno ahora">
      <h2>En turno ahora</h2>

      {error && <p role="alert">{error}</p>}

      <div className="chips" role="group" aria-label="Sucursal">
        {sucursales.map((s) => (
          <button
            key={s.id}
            type="button"
            className="chip"
            aria-pressed={sucursalActual === s.id}
            onClick={() => setElegida(s.id)}
          >
            {s.nombre} <span>{cuenta(s.id)}</span>
          </button>
        ))}
      </div>

      {activos === null && !error && <p>Cargando...</p>}
      {activos !== null && lista.length === 0 && <p>Nadie está activo ahora en esta sucursal.</p>}

      <div className="relojes">
        {lista.map((a) => (
          <article key={a.colaborador_id} className="reloj">
            <span className="punto bien" aria-hidden="true" />
            <div>
              <strong>{a.nombres} {a.apellidos}</strong>
              <small>{[a.puesto, a.turno].filter(Boolean).join(' · ')}</small>
            </div>
            <div className="reloj-estado">
              <span>Activo</span>
              <small>Desde las {horaLocal(a.entrada)}</small>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
