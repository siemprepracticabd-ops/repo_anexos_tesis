import { useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import { llamarApi } from './api'
import FormularioTurno from './FormularioTurno'
import Ventana from './Ventana'

function aMinutos(hora) {
  const [horas, minutos] = hora.split(':')
  return Number(horas) * 60 + Number(minutos)
}

function duracionHoras(inicio, fin) {
  const minutos = (aMinutos(fin) - aMinutos(inicio) + 1440) % 1440
  return (minutos === 0 ? 1440 : minutos) / 60
}

export default function Turnos({ rol }) {
  const [turnos, setTurnos] = useState(null)
  const [formulario, setFormulario] = useState(null)
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)

  const puedeEditar = rol === 'rrhh'

  useEffect(() => {
    supabase
      .from('turnos')
      .select(
        'id, nombre, hora_inicio, hora_fin, cruza_medianoche, tipo_jornada, horas_ordinarias, activo, asignaciones_turno(count)'
      )
      .order('hora_inicio')
      .then(({ data, error: errorTurnos }) => {
        if (errorTurnos) setError('No se pudieron cargar los turnos')
        else setTurnos(data)
      })
  }, [version])

  async function accion(ruta, opciones) {
    setError('')
    try {
      await llamarApi(ruta, opciones)
      setVersion((v) => v + 1)
    } catch (falla) {
      setError(falla.estado ? falla.message : 'No se pudo conectar con el servidor')
    }
  }

  function eliminar(turno) {
    if (!window.confirm(`¿Eliminar el turno «${turno.nombre}»?`)) return
    accion(`/turnos/${turno.id}`, { method: 'DELETE' })
  }

  function cambiarEstado(turno) {
    accion(`/turnos/${turno.id}/estado`, { method: 'PATCH', body: JSON.stringify({ activo: !turno.activo }) })
  }

  function alGuardar() {
    setFormulario(null)
    setVersion((v) => v + 1)
  }

  return (
    <main>
      <div className="encabezado">
        <h1>Turnos</h1>
        {puedeEditar && (
          <button type="button" className="principal" onClick={() => setFormulario('nuevo')}>Nuevo turno</button>
        )}
      </div>

      {error && <p role="alert">{error}</p>}
      {turnos === null && !error && <p>Cargando...</p>}

      {turnos?.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Turno</th>
              <th>Horario</th>
              <th>Duración</th>
              <th>Horas ordinarias</th>
              <th>Tipo de jornada</th>
              <th>Estado</th>
              <th>Usos</th>
              {puedeEditar && <th></th>}
            </tr>
          </thead>
          <tbody>
            {turnos.map((t) => {
              const usos = t.asignaciones_turno[0]?.count ?? 0
              return (
                  <tr key={t.id}>
                    <td>{t.nombre}</td>
                    <td>
                      {t.hora_inicio.slice(0, 5)} a {t.hora_fin.slice(0, 5)}
                      {t.cruza_medianoche && ' (día siguiente)'}
                    </td>
                    <td>{duracionHoras(t.hora_inicio, t.hora_fin)} h</td>
                    <td>{t.horas_ordinarias} h</td>
                    <td>{t.tipo_jornada}</td>
                    <td>{t.activo ? 'Activo' : 'Desactivado'}</td>
                    <td>{usos}</td>
                    {puedeEditar && (
                      <td>
                        <button
                          type="button"
                          disabled={usos > 0}
                          title={usos > 0 ? 'Ya se usó: crea uno nuevo y desactiva este' : ''}
                          onClick={() => setFormulario(t.id)}
                        >
                          Editar
                        </button>{' '}
                        <button type="button" onClick={() => cambiarEstado(t)}>
                          {t.activo ? 'Desactivar' : 'Activar'}
                        </button>{' '}
                        <button
                          type="button"
                          disabled={usos > 0}
                          title={usos > 0 ? 'Ya se usó: desactívalo' : ''}
                          onClick={() => eliminar(t)}
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

      {formulario !== null && (
        <Ventana onCerrar={() => setFormulario(null)}>
          <FormularioTurno
            turno={formulario === 'nuevo' ? null : turnos.find((t) => t.id === formulario)}
            onGuardado={alGuardar}
            onCancelar={() => setFormulario(null)}
          />
        </Ventana>
      )}
    </main>
  )
}