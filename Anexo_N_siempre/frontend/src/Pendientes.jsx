import { useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import { diaSemana, formatoHoras, horaLocal } from './tiempo'
import DecisionHorasExtra from './DecisionHorasExtra'
import JustificarAusencia from './JustificarAusencia'
import RegistrarAsistencia from './RegistrarAsistencia'
import Dato from './Dato'
import Ventana from './Ventana'

const FILTROS = [
  { valor: 'pendientes', etiqueta: 'Por resolver' },
  { valor: 'resueltas', etiqueta: 'Ya resueltas' },
  { valor: 'todas', etiqueta: 'Todas' },
]

const ESTADO_EXTRA = {
  pendiente: 'Pendiente',
  autorizada: 'Autorizada',
  parcial: 'Autorizada en parte',
  rechazada: 'Rechazada',
}

const ESTADO_AUSENCIA = {
  sin_justificar: 'Sin justificar',
  justificada: 'Justificada',
  reclasificada: 'Falta injustificada',
}

function Filtro({ id, valor, onChange }) {
  return (
    <select id={id} value={valor} onChange={(evento) => onChange(evento.target.value)}>
      {FILTROS.map((f) => (
        <option key={f.valor} value={f.valor}>{f.etiqueta}</option>
      ))}
    </select>
  )
}

export default function Pendientes({ rol }) {
  const [extras, setExtras] = useState(null)
  const [ausencias, setAusencias] = useState(null)
  const [filtroExtras, setFiltroExtras] = useState('pendientes')
  const [filtroAusencias, setFiltroAusencias] = useState('pendientes')
  const [decidiendo, setDecidiendo] = useState(null)
  const [justificando, setJustificando] = useState(null)
  const [registrando, setRegistrando] = useState(null)
  const [totales, setTotales] = useState({ extras: null, ausencias: null })
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)

  useEffect(() => {
    Promise.all([
      supabase.from('horas_extra').select('id').eq('estado', 'pendiente'),
      supabase.from('ausencias').select('id').eq('estado', 'sin_justificar'),
    ]).then(([porDecidir, sinJustificar]) => {
      if (!porDecidir.error && !sinJustificar.error) {
        setTotales({ extras: porDecidir.data.length, ausencias: sinJustificar.data.length })
      }
    })
  }, [version])

  useEffect(() => {
    let consulta = supabase
      .from('horas_extra')
      .select(
        'id, minutos_detectados, minutos_pagados, estado, justificacion, autorizado_por_nombre, jornadas(fecha, sucursales(nombre), colaboradores(nombres, apellidos, puestos(nombre)), entrada:marcaciones!marcacion_entrada_id(marcado_en), salida:marcaciones!marcacion_salida_id(marcado_en))'
      )
      .limit(200)
    if (filtroExtras === 'pendientes') consulta = consulta.eq('estado', 'pendiente')
    if (filtroExtras === 'resueltas') consulta = consulta.neq('estado', 'pendiente')

    consulta.then(({ data, error: falla }) => {
      if (falla) setError('No se pudieron cargar las horas extra')
      else setExtras(data.sort((a, b) => a.jornadas.fecha.localeCompare(b.jornadas.fecha)))
    })
  }, [filtroExtras, version])

  useEffect(() => {
    let consulta = supabase
      .from('ausencias')
      .select(
        'id, fecha, estado, colaboradores(nombres, apellidos, puestos(nombre)), tipos_ausencia(nombre)'
      )
      .order('fecha')
      .limit(200)
    if (filtroAusencias === 'pendientes') consulta = consulta.eq('estado', 'sin_justificar')
    if (filtroAusencias === 'resueltas') consulta = consulta.neq('estado', 'sin_justificar')

    consulta.then(({ data, error: falla }) => {
      if (falla) setError('No se pudieron cargar las ausencias')
      else setAusencias(data)
    })
  }, [filtroAusencias, version])

  function alGuardar() {
    setDecidiendo(null)
    setJustificando(null)
    setVersion(version + 1)
  }

  return (
    <main>
      <h1>Pendientes</h1>
      {error && <p role="alert">{error}</p>}

      {totales.extras !== null && (
        <div className="datos datos-dos">
          <Dato cantidad={totales.extras} etiqueta="Horas extra por decidir" ancla="#horas-extra" />
          <Dato cantidad={totales.ausencias} etiqueta="Ausencias sin justificar" ancla="#ausencias" urgente />
        </div>
      )}

      <section id="horas-extra">
        <h2>Horas extra</h2>
        <div className="filtros">
          <label htmlFor="filtro_extras">Mostrar</label>
          <Filtro id="filtro_extras" valor={filtroExtras} onChange={setFiltroExtras} />
        </div>

        {extras === null && <p>Cargando...</p>}
        {extras?.length === 0 && <p>No hay horas extra en esta lista.</p>}

        {extras?.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Empleado</th>
                <th>Puesto</th>
                <th>Sucursal</th>
                <th>Día</th>
                <th>Entrada</th>
                <th>Salida</th>
                <th>Detectado</th>
                <th>Estado</th>
                <th>Se paga</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {extras.map((x) => (
                  <tr key={x.id}>
                    <td>{x.jornadas.colaboradores.nombres} {x.jornadas.colaboradores.apellidos}</td>
                    <td>{x.jornadas.colaboradores.puestos?.nombre}</td>
                    <td>{x.jornadas.sucursales?.nombre}</td>
                    <td>{x.jornadas.fecha} ({diaSemana(x.jornadas.fecha)})</td>
                    <td>{horaLocal(x.jornadas.entrada?.marcado_en)}</td>
                    <td>{horaLocal(x.jornadas.salida?.marcado_en)}</td>
                    <td>{formatoHoras(x.minutos_detectados)}</td>
                    <td>{ESTADO_EXTRA[x.estado]}</td>
                    <td>{x.minutos_pagados === null ? '' : formatoHoras(x.minutos_pagados)}</td>
                    <td>
                      <button type="button" onClick={() => setDecidiendo(x.id)}>
                        {x.estado === 'pendiente' ? 'Decidir' : 'Corregir'}
                      </button>
                    </td>
                  </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section id="ausencias">
        <h2>Ausencias</h2>
        <div className="filtros">
          <label htmlFor="filtro_ausencias">Mostrar</label>
          <Filtro id="filtro_ausencias" valor={filtroAusencias} onChange={setFiltroAusencias} />
        </div>

        {ausencias === null && <p>Cargando...</p>}
        {ausencias?.length === 0 && <p>No hay ausencias en esta lista.</p>}

        {ausencias?.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Empleado</th>
                <th>Puesto</th>
                <th>Día</th>
                <th>Estado</th>
                <th>Tipo</th>
                {rol === 'rrhh' && <th></th>}
              </tr>
            </thead>
            <tbody>
              {ausencias.map((a) => (
                  <tr key={a.id}>
                    <td>{a.colaboradores.nombres} {a.colaboradores.apellidos}</td>
                    <td>{a.colaboradores.puestos?.nombre}</td>
                    <td>{a.fecha} ({diaSemana(a.fecha)})</td>
                    <td>{ESTADO_AUSENCIA[a.estado]}</td>
                    <td>{a.tipos_ausencia?.nombre}</td>
                    {rol === 'rrhh' && (
                      <td>
                        <button type="button" onClick={() => setJustificando(a.id)}>
                          {a.estado === 'sin_justificar' ? 'Justificar' : 'Corregir'}
                        </button>
                        {a.estado === 'sin_justificar' && (
                          <>
                            {' '}
                            <button type="button" onClick={() => setRegistrando(a.id)}>Sí asistió</button>
                          </>
                        )}
                      </td>
                    )}
                  </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {decidiendo && extras?.some((x) => x.id === decidiendo) && (
        <Ventana onCerrar={() => setDecidiendo(null)}>
          <DecisionHorasExtra
            registro={extras.find((x) => x.id === decidiendo)}
            rol={rol}
            onGuardado={alGuardar}
            onCancelar={() => setDecidiendo(null)}
          />
        </Ventana>
      )}

      {registrando && ausencias?.some((a) => a.id === registrando) && (
        <Ventana onCerrar={() => setRegistrando(null)}>
          <RegistrarAsistencia
            ausencia={ausencias.find((a) => a.id === registrando)}
            onGuardado={() => {
              setRegistrando(null)
              alGuardar()
            }}
            onCancelar={() => setRegistrando(null)}
          />
        </Ventana>
      )}

      {justificando && ausencias?.some((a) => a.id === justificando) && (
        <Ventana onCerrar={() => setJustificando(null)}>
          <JustificarAusencia
            ausencia={ausencias.find((a) => a.id === justificando)}
            onGuardado={alGuardar}
            onCancelar={() => setJustificando(null)}
          />
        </Ventana>
      )}
    </main>
  )
}