import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from './supabaseClient'

// cuadro pequeno para el inicio: quien esta activo ahora, por sucursal
export default function EnTurnoResumen() {
  const [grupos, setGrupos] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    function cargar() {
      Promise.all([
        supabase.from('en_turno_ahora').select('colaborador_id, sucursal_id, nombres, apellidos'),
        supabase.from('sucursales').select('id, nombre').eq('activa', true).order('nombre'),
      ]).then(([activos, sucursales]) => {
        if (activos.error || sucursales.error) {
          setError('No se pudo cargar quién está en turno')
          return
        }
        setError('')
        setGrupos(
          sucursales.data.map((s) => ({
            id: s.id,
            nombre: s.nombre,
            personas: activos.data
              .filter((a) => a.sucursal_id === s.id)
              .sort((a, b) => a.nombres.localeCompare(b.nombres)),
          }))
        )
      })
    }

    cargar()
    const reloj = setInterval(cargar, 60000)
    return () => clearInterval(reloj)
  }, [])

  return (
    <section aria-label="En turno ahora">
      <h2>En turno ahora</h2>
      {error && <p role="alert">{error}</p>}
      {grupos === null && !error && <p>Cargando...</p>}

      <div className="en-turno">
        {grupos?.map((g) => (
          <div key={g.id} className={`en-turno-caja ${g.personas.length > 0 ? 'con-gente' : ''}`}>
            <strong>{g.nombre}</strong>
            <span className="en-turno-cuenta">{g.personas.length}</span>
            <small>
              {g.personas.length === 0
                ? 'Nadie activo'
                : g.personas.map((p) => `${p.nombres} ${p.apellidos.split(' ')[0]}`).join(', ')}
            </small>
          </div>
        ))}
      </div>
      <p><small><Link to="/asistencia">Ver el detalle en Asistencia</Link></small></p>
    </section>
  )
}
