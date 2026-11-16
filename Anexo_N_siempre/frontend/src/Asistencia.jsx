import { Fragment, useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import { llamarApi } from './api'
import {
  agruparPorColaborador,
  diaSemana,
  formatoHoras,
  horaLocal,
  notaDeCorreccion,
  observacion,
  quincenaActual,
} from './tiempo'
import CorregirJornada from './CorregirJornada'
import EnTurno from './EnTurno'
import Ventana from './Ventana'

export default function Asistencia({ rol }) {
  const [rango, setRango] = useState(() => quincenaActual())
  const [filtro, setFiltro] = useState('')
  const [buscar, setBuscar] = useState('')
  const [sucursales, setSucursales] = useState([])
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [calculando, setCalculando] = useState(false)
  const [corrigiendo, setCorrigiendo] = useState(null)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    supabase
      .from('sucursales')
      .select('id, nombre')
      .eq('activa', true)
      .order('nombre')
      .then(({ data }) => setSucursales(data ?? []))
  }, [])

  useEffect(() => {
    if (!rango.desde || !rango.hasta || rango.desde > rango.hasta) return

    Promise.all([
      supabase
        .from('jornadas')
        .select(
          'id, fecha, estado, minutos_trabajados, minutos_tardanza, clasif_entrada, clasif_salida, sucursal_id, colaboradores(id, nombres, apellidos, puestos(nombre), colaborador_dispositivo(id_en_dispositivo)), sucursales(nombre), entrada:marcaciones!marcacion_entrada_id(marcado_en, correcciones:correcciones_marcacion!marcacion_nueva_id(motivo)), salida:marcaciones!marcacion_salida_id(marcado_en, correcciones:correcciones_marcacion!marcacion_nueva_id(motivo)), horas_extra(minutos_detectados, estado)'
        )
        .gte('fecha', rango.desde)
        .lte('fecha', rango.hasta)
        .order('fecha'),
      supabase
        .from('ausencias')
        .select('id, fecha, estado, colaboradores(nombres, apellidos, sucursal_base_id)')
        .gte('fecha', rango.desde)
        .lte('fecha', rango.hasta)
        .order('fecha'),
    ]).then(([jornadas, ausencias]) => {
      if (jornadas.error || ausencias.error) {
        setError('No se pudo cargar la asistencia')
        return
      }
      setError('')
      setDatos({ jornadas: jornadas.data, ausencias: ausencias.data })
    })
  }, [rango.desde, rango.hasta, version])

  async function calcular() {
    setError('')
    setMensaje('')
    setCalculando(true)

    try {
      const r = await llamarApi('/jornadas/calcular', {
        method: 'POST',
        body: JSON.stringify({ desde: rango.desde, hasta: rango.hasta }),
      })
      setMensaje(
        `Listo: ${r.jornadas} jornadas calculadas, ${r.sin_programacion} sin programación, ` +
          `${r.ausencias} ausencias nuevas y ${r.horas_extra} con horas extra.`
      )
      setVersion(version + 1)
    } catch (falla) {
      if (falla.campos) setError(Object.values(falla.campos).join('. '))
      else if (falla.estado) setError(falla.message)
      else setError('No se pudo conectar con el servidor')
    } finally {
      setCalculando(false)
    }
  }

  const sinTildes = (texto) => texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
  const palabras = sinTildes(buscar).split(/\s+/).filter(Boolean)
  const coincide = (c) => {
    const nombre = sinTildes(`${c.nombres} ${c.apellidos}`)
    return palabras.every((p) => nombre.includes(p))
  }

  const jornadas = (datos?.jornadas ?? []).filter(
    (j) => (filtro === '' || j.sucursal_id === filtro) && coincide(j.colaboradores)
  )
  const ausencias = (datos?.ausencias ?? []).filter(
    (a) => (filtro === '' || a.colaboradores.sucursal_base_id === filtro) && coincide(a.colaboradores)
  )
  const grupos = agruparPorColaborador(jornadas)
  const totalMinutos = grupos.reduce((suma, g) => suma + g.total, 0)

  return (
    <main>
      <h1>Asistencia</h1>

      <EnTurno sucursales={sucursales} />

      <h2>Jornadas</h2>
      <div className="filtros">
        <label htmlFor="desde">Desde</label>
        <input
          id="desde"
          type="date"
          value={rango.desde}
          onChange={(evento) => setRango({ ...rango, desde: evento.target.value })}
        />{' '}
        <label htmlFor="hasta">Hasta</label>
        <input
          id="hasta"
          type="date"
          value={rango.hasta}
          onChange={(evento) => setRango({ ...rango, hasta: evento.target.value })}
        />{' '}
        <label htmlFor="filtro">Sucursal</label>
        <select id="filtro" value={filtro} onChange={(evento) => setFiltro(evento.target.value)}>
          <option value="">Todas las sucursales</option>
          {sucursales.map((s) => (
            <option key={s.id} value={s.id}>{s.nombre}</option>
          ))}
        </select>{' '}
        <label htmlFor="buscar">Colaborador</label>
        <input
          id="buscar"
          type="search"
          placeholder="Buscar por nombre"
          value={buscar}
          onChange={(evento) => setBuscar(evento.target.value)}
        />{' '}
        {rol === 'rrhh' && (
          <button type="button" onClick={calcular} disabled={calculando}>
            {calculando ? 'Calculando...' : 'Calcular jornadas'}
          </button>
        )}
      </div>

      {error && <p role="alert">{error}</p>}
      {mensaje && <p role="status">{mensaje}</p>}
      {datos === null && !error && <p>Cargando...</p>}

      {datos !== null && (
        <>
          <p>
            Rango: {rango.desde} a {rango.hasta} · Empleados: {grupos.length} · Jornadas: {jornadas.length} ·
            Horas totales: {formatoHoras(totalMinutos)}
          </p>

          {jornadas.length === 0 && (
            <p>No hay jornadas calculadas en este rango. Pulsa «Calcular jornadas».</p>
          )}

          {jornadas.length > 0 && (
            <div style={{ overflowX: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>Empleado</th>
                    <th>ID</th>
                    <th>Sucursal</th>
                    <th>Día</th>
                    <th>Día sem.</th>
                    <th>Entrada</th>
                    <th>Salida</th>
                    <th>Horas</th>
                    <th>Puesto</th>
                    <th>Observación</th>
                    <th>Horas extra</th>
                    {rol === 'rrhh' && <th></th>}
                  </tr>
                </thead>
                <tbody>
                  {grupos.map((g) => (
                    <Fragment key={g.colaborador.id}>
                      {g.jornadas.map((j) => {
                        const extra = Array.isArray(j.horas_extra) ? j.horas_extra[0] : j.horas_extra
                        return (
                          <tr key={j.id}>
                            <td>{g.colaborador.nombres} {g.colaborador.apellidos}</td>
                            <td>
                              {g.colaborador.colaborador_dispositivo
                                .map((e) => e.id_en_dispositivo)
                                .join(', ')}
                            </td>
                            <td>{j.sucursales?.nombre}</td>
                            <td>{j.fecha}</td>
                            <td>{diaSemana(j.fecha)}</td>
                            <td>{horaLocal(j.entrada?.marcado_en)}</td>
                            <td>{horaLocal(j.salida?.marcado_en)}</td>
                            <td>{j.estado === 'sin_programacion' ? '—' : formatoHoras(j.minutos_trabajados)}</td>
                            <td>{g.colaborador.puestos?.nombre}</td>
                            <td>
                              {observacion(j)}
                              {notaDeCorreccion(j) && <small> · Hora corregida: {notaDeCorreccion(j)}</small>}
                            </td>
                            <td>
                              {extra ? `${formatoHoras(extra.minutos_detectados)} (${extra.estado})` : ''}
                            </td>
                            {rol === 'rrhh' && (
                              <td>
                                {j.estado !== 'sin_programacion' && (
                                  <button type="button" onClick={() => setCorrigiendo(j.id)}>Corregir</button>
                                )}
                              </td>
                            )}
                          </tr>
                        )
                      })}
                      <tr>
                        <td colSpan={6}>
                          <strong>Total {g.colaborador.nombres} {g.colaborador.apellidos}</strong>
                        </td>
                        <td><strong>TOTAL HORAS:</strong></td>
                        <td><strong>{formatoHoras(g.total)}</strong></td>
                        <td colSpan={rol === 'rrhh' ? 4 : 3}></td>
                      </tr>
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {ausencias.length > 0 && (
            <section>
              <h2>Ausencias</h2>
              <table>
                <thead>
                  <tr>
                    <th>Empleado</th>
                    <th>Día</th>
                    <th>Día sem.</th>
                    <th>Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {ausencias.map((a) => (
                    <tr key={a.id}>
                      <td>{a.colaboradores.nombres} {a.colaboradores.apellidos}</td>
                      <td>{a.fecha}</td>
                      <td>{diaSemana(a.fecha)}</td>
                      <td>{a.estado === 'sin_justificar' ? 'Sin justificar' : a.estado}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
        </>
      )}

      {corrigiendo && jornadas.some((j) => j.id === corrigiendo) && (
        <Ventana onCerrar={() => setCorrigiendo(null)}>
          <CorregirJornada
            jornada={jornadas.find((j) => j.id === corrigiendo)}
            onGuardado={() => {
              setCorrigiendo(null)
              setVersion((v) => v + 1)
            }}
            onCancelar={() => setCorrigiendo(null)}
          />
        </Ventana>
      )}
    </main>
  )
}