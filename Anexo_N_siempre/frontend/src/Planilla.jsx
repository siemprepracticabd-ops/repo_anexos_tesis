import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from './supabaseClient'
import { llamarApi } from './api'
import { aTexto } from './periodos'
import { diaSemana, formatoHoras, horaLocal, quincenasRecientes, turnoEnEspera } from './tiempo'
import AgregarMarcacion from './AgregarMarcacion'
import ConfirmarJornada from './ConfirmarJornada'
import DecisionDescuento from './DecisionDescuento'
import PagoQuincena from './PagoQuincena'
import CierreQuincena from './CierreQuincena'
import Dato from './Dato'
import Ventana from './Ventana'

const ESTADO_DESCUENTO = {
  pendiente: 'Pendiente',
  aplicado: 'Se descuenta todo',
  parcial: 'Se descuenta una parte',
  no_aplicado: 'No se descuenta',
}

const SELECT_JORNADAS =
  'id, fecha, estado, colaboradores(id, nombres, apellidos, puestos(nombre)), sucursales(nombre), entrada:marcaciones!marcacion_entrada_id(marcado_en), salida:marcaciones!marcacion_salida_id(marcado_en)'

export default function Planilla({ rol }) {
  const [quincenas] = useState(() => quincenasRecientes())
  const [hoy] = useState(() => aTexto(new Date()))
  const [indice, setIndice] = useState(0)
  const [datos, setDatos] = useState(null)
  const [abierto, setAbierto] = useState(null)
  const [error, setError] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [calculando, setCalculando] = useState(false)
  const [version, setVersion] = useState(0)

  const { desde, hasta } = quincenas[indice]

  useEffect(() => {
    Promise.all([
      supabase
        .from('jornadas')
        .select(SELECT_JORNADAS)
        .in('estado', ['incompleta', 'por_confirmar'])
        .gte('fecha', desde)
        .lte('fecha', hasta)
        .order('fecha'),
      supabase
        .from('ausencias')
        .select('id', { count: 'exact', head: true })
        .eq('estado', 'sin_justificar')
        .gte('fecha', desde)
        .lte('fecha', hasta),
      supabase
        .from('horas_extra')
        .select('id, jornadas!inner(fecha)', { count: 'exact', head: true })
        .eq('estado', 'pendiente')
        .gte('jornadas.fecha', desde)
        .lte('jornadas.fecha', hasta),
      supabase
        .from('descuentos_tiempo')
        .select(
          'id, minutos_detectados, estado, minutos_descontados, justificacion, autorizado_por_nombre, colaboradores(id, nombres, apellidos, puestos(nombre))'
        )
        .eq('fecha_inicio', desde)
        .eq('fecha_fin', hasta),
      supabase
        .from('asignaciones_vigentes')
        .select('id, fecha, turno_id')
        .eq('estado', 'programado')
        .not('turno_id', 'is', null)
        .gte('fecha', desde)
        .lte('fecha', hasta)
        .lt('fecha', hoy),
      supabase
        .from('jornadas')
        .select('asignacion_id')
        .not('asignacion_id', 'is', null)
        .gte('fecha', desde)
        .lte('fecha', hasta)
        .lt('fecha', hoy),
      supabase
        .from('ausencias')
        .select('asignacion_id')
        .gte('fecha', desde)
        .lte('fecha', hasta)
        .lt('fecha', hoy),
      supabase.from('turnos').select('id, hora_fin, cruza_medianoche'),
    ]).then(([jornadas, ausencias, extras, descuentos, asignaciones, calculadas, ausenciasTotal, turnos]) => {
      if (
        jornadas.error || ausencias.error || extras.error || descuentos.error ||
        asignaciones.error || calculadas.error || ausenciasTotal.error || turnos.error
      ) {
        setError('No se pudo cargar la quincena')
        return
      }
      setError('')
      const resueltas = new Set([...calculadas.data, ...ausenciasTotal.data].map((x) => x.asignacion_id))
      const turnoPor = new Map(turnos.data.map((t) => [t.id, t]))
      const ahora = new Date()
      const sinResolver = asignaciones.data.filter((a) => !resueltas.has(a.id))
      const enEspera = sinResolver.filter((a) => {
        const turno = turnoPor.get(a.turno_id)
        return turno && turnoEnEspera(a.fecha, turno, ahora)
      }).length
      setDatos({
        incompletas: jornadas.data.filter((j) => j.estado === 'incompleta'),
        porConfirmar: jornadas.data.filter((j) => j.estado === 'por_confirmar'),
        ausencias: ausencias.count,
        sinCalcular: sinResolver.length - enEspera,
        enEspera,
        extras: extras.count,
        descuentos: descuentos.data.sort((a, b) =>
          a.colaboradores.apellidos.localeCompare(b.colaboradores.apellidos)
        ),
      })
    })
  }, [desde, hasta, hoy, version])

  async function calcular() {
    setError('')
    setMensaje('')
    setCalculando(true)

    try {
      const calculo = await llamarApi('/jornadas/calcular', {
        method: 'POST',
        body: JSON.stringify({ desde, hasta: hasta < hoy ? hasta : hoy }),
      })
      const descuentos = await llamarApi('/descuentos/preparar', {
        method: 'POST',
        body: JSON.stringify({ desde, hasta }),
      })
      setMensaje(
        `Listo: ${calculo.jornadas} jornadas calculadas y ${descuentos.personas} persona(s) con horas por revisar.`
      )
      setVersion((v) => v + 1)
    } catch (falla) {
      if (falla.campos) setError(Object.values(falla.campos).join('. '))
      else if (falla.estado) setError(falla.message)
      else setError('No se pudo conectar con el servidor')
    } finally {
      setCalculando(false)
    }
  }

  function alGuardar() {
    setAbierto(null)
    setVersion((v) => v + 1)
  }

  function abrir(tipo, id) {
    setAbierto({ tipo, id })
  }

  const pendientesDescuento = datos?.descuentos.filter((d) => d.estado === 'pendiente').length ?? 0
  const lista = datos && [
    { etiqueta: 'Jornadas incompletas', cantidad: datos.incompletas.length, ancla: '#incompletas', urgente: true },
    { etiqueta: 'Jornadas por confirmar', cantidad: datos.porConfirmar.length, ancla: '#por-confirmar' },
    { etiqueta: 'Ausencias sin justificar', cantidad: datos.ausencias, ruta: '/pendientes', urgente: true },
    { etiqueta: 'Horas extra por decidir', cantidad: datos.extras, ruta: '/pendientes' },
    { etiqueta: 'Descuentos por decidir', cantidad: pendientesDescuento, ancla: '#descuentos' },
    { etiqueta: 'Turnos sin calcular', cantidad: datos.sinCalcular, urgente: true },
    { etiqueta: 'Turnos en espera de cierre', cantidad: datos.enEspera },
  ]
  const todoListo = lista?.every((punto) => punto.cantidad === 0)
  const jornadaAbierta =
    abierto && (abierto.tipo === 'marcacion' || abierto.tipo === 'confirmar')
      ? [...(datos?.incompletas ?? []), ...(datos?.porConfirmar ?? [])].find((j) => j.id === abierto.id)
      : null
  const descuentoAbierto =
    abierto?.tipo === 'descuento' ? datos?.descuentos.find((d) => d.id === abierto.id) : null

  function tablaJornadas(jornadas, tipo, textoBoton) {
    return (
      <table>
        <thead>
          <tr>
            <th>Empleado</th>
            <th>Puesto</th>
            <th>Sucursal</th>
            <th>Día</th>
            <th>Entrada</th>
            <th>Salida</th>
            {rol === 'rrhh' && <th></th>}
          </tr>
        </thead>
        <tbody>
          {jornadas.map((j) => (
              <tr key={j.id}>
                <td>{j.colaboradores.nombres} {j.colaboradores.apellidos}</td>
                <td>{j.colaboradores.puestos?.nombre}</td>
                <td>{j.sucursales?.nombre}</td>
                <td>{j.fecha} ({diaSemana(j.fecha)})</td>
                <td>{horaLocal(j.entrada?.marcado_en)}</td>
                <td>{horaLocal(j.salida?.marcado_en)}</td>
                {rol === 'rrhh' && (
                  <td>
                    <button type="button" onClick={() => abrir(tipo, j.id)}>{textoBoton}</button>
                  </td>
                )}
              </tr>
          ))}
        </tbody>
      </table>
    )
  }

  return (
    <main>
      <h1>Planilla</h1>

      <div className="filtros">
        <label htmlFor="quincena">Quincena</label>
        <select id="quincena" value={indice} onChange={(evento) => setIndice(Number(evento.target.value))}>
          {quincenas.map((q, i) => (
            <option key={q.desde} value={i}>{q.desde} al {q.hasta}</option>
          ))}
        </select>
        {rol === 'rrhh' && (
          <button type="button" className="principal" onClick={calcular} disabled={calculando}>
            {calculando ? 'Calculando...' : 'Calcular jornadas y preparar descuentos'}
          </button>
        )}
      </div>

      {error && <p role="alert">{error}</p>}
      {mensaje && <p role="status">{mensaje}</p>}
      {datos === null && !error && <p>Cargando...</p>}

      {datos !== null && (
        <>
          <section>
            <h2>Para poder cerrar la quincena</h2>
            <div className="datos">
              {lista.map((punto) => (
                <Dato key={punto.etiqueta} {...punto} />
              ))}
            </div>
            {(datos.ausencias > 0 || datos.extras > 0) && (
              <p>Las ausencias y las horas extra se resuelven en <Link to="/pendientes">Pendientes</Link>.</p>
            )}
            {datos.enEspera > 0 && (
              <p>Los turnos en espera terminaron hace menos de 4 horas. Se calculan solos al pulsar «Calcular jornadas» cuando pase ese tiempo.</p>
            )}
            <p className={todoListo ? 'vacio' : ''}>
              {todoListo ? 'No hay nada pendiente en esta quincena.' : 'Resuelve lo pendiente para poder cerrarla.'}
            </p>
          </section>

          {datos.incompletas.length > 0 && (
            <section id="incompletas">
              <h2>Jornadas incompletas</h2>
              <p>Falta la entrada o la salida. Agrega la marcación que faltó, con el motivo.</p>
              {tablaJornadas(datos.incompletas, 'marcacion', 'Agregar marcación')}
            </section>
          )}

          {datos.porConfirmar.length > 0 && (
            <section id="por-confirmar">
              <h2>Jornadas por confirmar</h2>
              <p>Marcó en otra sucursal o a una hora muy distinta del turno. Confírmala si es correcta.</p>
              {tablaJornadas(datos.porConfirmar, 'confirmar', 'Confirmar')}
            </section>
          )}

          <section id="descuentos">
            <h2>Descuentos por tardanza y salida anticipada</h2>
            {datos.descuentos.length === 0 && (
              <p>No hay horas por revisar. Pulsa «Calcular jornadas y preparar descuentos» si acabas de cargar marcaciones.</p>
            )}
            {datos.descuentos.length > 0 && (
              <table>
                <thead>
                  <tr>
                    <th>Empleado</th>
                    <th>Puesto</th>
                    <th>Horas acumuladas</th>
                    <th>Estado</th>
                    <th>Se descuenta</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {datos.descuentos.map((d) => (
                      <tr key={d.id}>
                        <td>{d.colaboradores.nombres} {d.colaboradores.apellidos}</td>
                        <td>{d.colaboradores.puestos?.nombre}</td>
                        <td>{formatoHoras(d.minutos_detectados)}</td>
                        <td>{ESTADO_DESCUENTO[d.estado]}</td>
                        <td>{d.minutos_descontados === null ? '' : formatoHoras(d.minutos_descontados)}</td>
                        <td>
                          <button type="button" onClick={() => abrir('descuento', d.id)}>
                            {d.estado === 'pendiente' ? 'Decidir' : 'Corregir'}
                          </button>
                        </td>
                      </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
          <PagoQuincena key={`pago-${desde}`} desde={desde} hasta={hasta} rol={rol} version={version} />

          <CierreQuincena
            key={`cierre-${desde}`}
            desde={desde}
            hasta={hasta}
            rol={rol}
            hoy={hoy}
            listo={todoListo}
            onCambio={() => setVersion((v) => v + 1)}
          />
        </>
      )}

      {jornadaAbierta && (
        <Ventana onCerrar={() => setAbierto(null)}>
          {abierto.tipo === 'marcacion' ? (
            <AgregarMarcacion jornada={jornadaAbierta} onGuardado={alGuardar} onCancelar={() => setAbierto(null)} />
          ) : (
            <ConfirmarJornada jornada={jornadaAbierta} onGuardado={alGuardar} onCancelar={() => setAbierto(null)} />
          )}
        </Ventana>
      )}

      {descuentoAbierto && (
        <Ventana onCerrar={() => setAbierto(null)}>
          <DecisionDescuento
            registro={descuentoAbierto}
            rol={rol}
            onGuardado={alGuardar}
            onCancelar={() => setAbierto(null)}
          />
        </Ventana>
      )}
    </main>
  )
}