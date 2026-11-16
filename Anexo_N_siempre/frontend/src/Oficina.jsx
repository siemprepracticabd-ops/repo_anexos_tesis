import { useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import { llamarApi } from './api'
import { aTexto, sumarDias } from './periodos'
import { diaSemana } from './tiempo'

function lunesDe(fecha) {
  const copia = new Date(fecha.getFullYear(), fecha.getMonth(), fecha.getDate())
  copia.setDate(copia.getDate() - ((copia.getDay() + 6) % 7))
  return aTexto(copia)
}

function diaDelMes(texto) {
  return texto.slice(8)
}

export default function Oficina({ rol }) {
  const [lunes, setLunes] = useState(() => lunesDe(new Date()))
  const [personas, setPersonas] = useState(null)
  const [horario, setHorario] = useState([])
  const [excepciones, setExcepciones] = useState({})
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState('')
  const [version, setVersion] = useState(0)

  const puedeEditar = rol === 'rrhh'
  const dias = Array.from({ length: 7 }, (_, i) => sumarDias(lunes, i))

  useEffect(() => {
    const domingo = sumarDias(lunes, 6)
    Promise.all([
      supabase
        .from('colaboradores')
        .select('id, nombres, apellidos, sucursales(nombre), periodos_laborales(fecha_ingreso, fecha_baja)')
        .eq('modalidad', 'diurna')
        .order('apellidos'),
      supabase.from('horario_diurno').select('dia_semana, trabaja_por_defecto'),
      supabase.from('dias_diurno').select('colaborador_id, fecha, tipo').gte('fecha', lunes).lte('fecha', domingo),
    ]).then(([colaboradores, base, marcados]) => {
      if (colaboradores.error || base.error || marcados.error) {
        setError('No se pudo cargar el horario de la oficina')
        return
      }
      setError('')
      setPersonas(
        colaboradores.data.filter((c) =>
          c.periodos_laborales.some((p) => p.fecha_ingreso <= domingo && (p.fecha_baja === null || p.fecha_baja >= lunes))
        )
      )
      setHorario(base.data)
      setExcepciones(Object.fromEntries(marcados.data.map((m) => [`${m.colaborador_id}|${m.fecha}`, m.tipo])))
    })
  }, [lunes, version])

  function trabajaPorHorario(fecha) {
    const [anio, mes, dia] = fecha.split('-').map(Number)
    const fila = horario.find((h) => h.dia_semana === new Date(anio, mes - 1, dia).getDay())
    return fila?.trabaja_por_defecto ?? false
  }

  function activaEl(persona, fecha) {
    return persona.periodos_laborales.some(
      (p) => fecha >= p.fecha_ingreso && (p.fecha_baja === null || fecha <= p.fecha_baja)
    )
  }

  async function cambiar(persona, fecha, tipo) {
    setError('')
    setGuardando(`${persona.id}|${fecha}`)
    try {
      await llamarApi('/oficina/dias', {
        method: 'PUT',
        body: JSON.stringify({ colaborador_id: persona.id, fecha, tipo: tipo || null }),
      })
      setVersion((v) => v + 1)
    } catch (falla) {
      if (falla.campos) setError(Object.values(falla.campos).join('. '))
      else if (falla.estado) setError(falla.message)
      else setError('No se pudo conectar con el servidor')
    } finally {
      setGuardando('')
    }
  }

  return (
    <main>
      <h1>Oficina</h1>
      <p>
        Horario base: lunes a viernes de 8:00 a 17:00 y sábado de 8:00 a 12:00, con el almuerzo dentro de las 8 horas.
        No hace falta programar: se paga lo que marquen. Aquí solo se cambia un día cuando alguien trabaja un domingo
        o cambia su descanso. Las personas se agregan en Colaboradores con la modalidad «Diurna (oficina)».
      </p>

      <p>
        <button type="button" onClick={() => setLunes(sumarDias(lunes, -7))}>Semana anterior</button>{' '}
        <button type="button" onClick={() => setLunes(lunesDe(new Date()))}>Esta semana</button>{' '}
        <button type="button" onClick={() => setLunes(sumarDias(lunes, 7))}>Semana siguiente</button>{' '}
        Semana del {lunes.split('-').reverse().join('/')}
      </p>

      {error && <p role="alert">{error}</p>}
      {personas === null && !error && <p>Cargando...</p>}
      {personas?.length === 0 && <p>Todavía no hay colaboradores con modalidad diurna.</p>}

      {personas?.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Colaborador</th>
              {dias.map((d) => (
                <th key={d}>{diaSemana(d)} {diaDelMes(d)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {personas.map((p) => (
              <tr key={p.id}>
                <td>
                  {p.nombres} {p.apellidos}
                  <br />
                  <small>{p.sucursales?.nombre}</small>
                </td>
                {dias.map((d) => {
                  const clave = `${p.id}|${d}`
                  const excepcion = excepciones[clave] ?? ''
                  if (!activaEl(p, d)) return <td key={d}>—</td>
                  const base = trabajaPorHorario(d) ? 'Trabaja' : 'Libre'
                  return (
                    <td key={d}>
                      <select
                        aria-label={`${p.nombres} ${d}`}
                        value={excepcion}
                        disabled={!puedeEditar || guardando === clave}
                        onChange={(evento) => cambiar(p, d, evento.target.value)}
                      >
                        <option value="">{base} (horario)</option>
                        <option value="trabaja">Trabaja</option>
                        <option value="libre">Libre</option>
                      </select>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  )
}
