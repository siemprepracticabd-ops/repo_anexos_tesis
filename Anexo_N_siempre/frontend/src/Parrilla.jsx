import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { supabase } from './supabaseClient'
import { abrirPdf, llamarApi } from './api'
import { aTexto, sumarDias } from './periodos'
import { copiarInvirtiendo } from './copiaSemana'
import PanelPublicacion from './PanelPublicacion'

const NOMBRES_DIA = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb']

function diasDelPeriodo(inicio, fin) {
  const [anio, mes, dia] = inicio.split('-').map(Number)
  const dias = []
  for (let i = 0; i < 31; i++) {
    const fecha = new Date(anio, mes - 1, dia + i)
    const texto = aTexto(fecha)
    dias.push({ texto, etiqueta: `${NOMBRES_DIA[fecha.getDay()]} ${fecha.getDate()}` })
    if (texto === fin) break
  }
  return dias
}

export default function Parrilla({ rol }) {
  const { id } = useParams()
  const navegar = useNavigate()
  const [datos, setDatos] = useState(null)
  const [cambios, setCambios] = useState({})
  const [filtro, setFiltro] = useState('')
  const [error, setError] = useState('')
  const [errorCarga, setErrorCarga] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    Promise.all([
      supabase
        .from('programaciones')
        .select('id, tipo, fecha_inicio, fecha_fin, version, estado, publicada_en')
        .eq('id', id)
        .single(),
      supabase.from('turnos').select('id, nombre').eq('activo', true).eq('de_oficina', false).order('hora_inicio'),
      supabase
        .from('colaboradores')
        .select('id, nombres, apellidos, sucursal_base_id, periodos_laborales(fecha_ingreso, fecha_baja)')
        .neq('modalidad', 'diurna')
        .order('apellidos'),
      supabase.from('sucursales').select('id, nombre').eq('activa', true).order('nombre'),
      supabase
        .from('asignaciones_turno')
        .select('colaborador_id, fecha, turno_id, sucursal_id')
        .eq('programacion_id', id),
    ]).then(async ([programacion, turnos, colaboradores, sucursales, asignaciones]) => {
      const falla = [programacion, turnos, colaboradores, sucursales, asignaciones].some(
        (r) => r.error
      )
      if (falla) {
        setErrorCarga('No se pudo cargar la programación')
        return
      }
      const guardadas = {}
      asignaciones.data.forEach((a) => {
        guardadas[`${a.colaborador_id}|${a.fecha}`] = {
          valor: a.turno_id ?? 'libre',
          sucursal_id: a.sucursal_id,
        }
      })
      const p = programacion.data
      const [versiones, cambiosTurno] = await Promise.all([
        supabase
          .from('programaciones')
          .select('id, version, estado')
          .eq('tipo', p.tipo)
          .eq('fecha_inicio', p.fecha_inicio)
          .eq('fecha_fin', p.fecha_fin)
          .eq('automatica', false)
          .order('version'),
        supabase
          .from('cambios_turno')
          .select(
            'motivo, turno_anterior:turnos!turno_anterior_id(nombre), turno_nuevo:turnos!turno_nuevo_id(nombre), asignaciones_turno!inner(colaborador_id, fecha, programacion_id)'
          )
          .eq('asignaciones_turno.programacion_id', id),
      ])
      if (versiones.error || cambiosTurno.error) {
        setErrorCarga('No se pudo cargar la programación')
        return
      }
      setDatos({
        programacion: p,
        turnos: turnos.data,
        colaboradores: colaboradores.data.filter((c) =>
          c.periodos_laborales.some(
            (l) => l.fecha_ingreso <= p.fecha_fin && (l.fecha_baja === null || l.fecha_baja >= p.fecha_inicio)
          )
        ),
        sucursales: sucursales.data,
        guardadas,
        versiones: versiones.data,
        cambiosTurno: cambiosTurno.data,
      })
      setCambios({})
    })
  }, [id, version])

  if (errorCarga) return <main><p role="alert">{errorCarga}</p></main>
  if (datos === null) return <main><p>Cargando...</p></main>

  const { programacion, turnos, colaboradores, sucursales, guardadas, versiones, cambiosTurno } = datos
  const esUltima = versiones.every((v) => v.version <= programacion.version)
  const editable = rol === 'rrhh' && programacion.estado === 'borrador'
  const dias = diasDelPeriodo(programacion.fecha_inicio, programacion.fecha_fin)
  const visibles = colaboradores.filter((c) => filtro === '' || c.sucursal_base_id === filtro)
  const grupos = [
    ...sucursales.map((s) => ({ id: s.id, nombre: s.nombre, personas: visibles.filter((c) => c.sucursal_base_id === s.id) })),
    {
      id: '',
      nombre: 'Sin sucursal',
      personas: visibles.filter((c) => !sucursales.some((s) => s.id === c.sucursal_base_id)),
    },
  ].filter((g) => g.personas.length > 0)

  function valorDe(clave) {
    return cambios[clave] ?? guardadas[clave]?.valor ?? ''
  }

  const pendientes = Object.keys(cambios).filter(
    (clave) => cambios[clave] !== (guardadas[clave]?.valor ?? '')
  )

  function cambiar(clave, valor) {
    setMensaje('')
    setCambios({ ...cambios, [clave]: valor })
  }

  async function copiarSemanaAnterior() {
    setError('')
    setMensaje('')

    const anterior = await supabase
      .from('programaciones')
      .select('id')
      .eq('tipo', 'semanal')
      .eq('fecha_fin', sumarDias(programacion.fecha_inicio, -1))
      .eq('automatica', false)
      .order('version', { ascending: false })
      .limit(1)
    if (anterior.error) {
      setError('No se pudo buscar la semana anterior')
      return
    }
    if (anterior.data.length === 0) {
      setMensaje('No hay una programación semanal anterior a esta')
      return
    }

    const origen = await supabase
      .from('asignaciones_turno')
      .select('colaborador_id, fecha, turno_id')
      .eq('programacion_id', anterior.data[0].id)
    if (origen.error) {
      setError('No se pudo leer la semana anterior')
      return
    }

    const nuevos = copiarInvirtiendo(
      origen.data,
      turnos,
      guardadas,
      new Set(colaboradores.map((c) => c.id))
    )
    const copiadas = Object.keys(nuevos).length
    setCambios({ ...cambios, ...nuevos })
    setMensaje(
      copiadas === 0
        ? 'No había celdas por copiar'
        : `Se copiaron ${copiadas} celdas con Mañana y Tarde invertidos. Revisa y pulsa Guardar`
    )
  }

    async function verPdf(consulta) {
    setError('')
    try {
      await abrirPdf(`/programaciones/${id}/calendario.pdf${consulta}`)
    } catch (falla) {
      setError(falla.estado || falla.aviso ? falla.message : 'No se pudo abrir el PDF')
    }
  }

  async function guardar() {
    setError('')
    setMensaje('')
    setGuardando(true)

    const celdas = pendientes.map((clave) => {
      const [colaboradorId, fecha] = clave.split('|')
      const colaborador = colaboradores.find((c) => c.id === colaboradorId)
      return {
        colaborador_id: colaboradorId,
        fecha,
        turno_id: cambios[clave] === 'libre' ? null : cambios[clave],
        sucursal_id: guardadas[clave]?.sucursal_id ?? colaborador.sucursal_base_id,
      }
    })

    try {
      await llamarApi(`/programaciones/${id}/asignaciones`, {
        method: 'PUT',
        body: JSON.stringify({ celdas }),
      })
      setMensaje('Cambios guardados')
      setVersion(version + 1)
    } catch (falla) {
      setError(falla.estado ? falla.message : 'No se pudo conectar con el servidor')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <main>
      <p><Link to="/programacion">Volver a las programaciones</Link></p>
      <h1>
        Programación {programacion.tipo}: {programacion.fecha_inicio} al {programacion.fecha_fin}
      </h1>
      <p>
        Versión {programacion.version}, estado: {programacion.estado}
        {programacion.publicada_en &&
          `, publicada el ${new Date(programacion.publicada_en).toLocaleString('es-GT')}`}
      </p>
      {versiones.length > 1 && (
        <p>
          Versiones:{' '}
          {versiones.map((v) =>
            v.id === programacion.id ? (
              <strong key={v.id}>v{v.version} ({v.estado}) </strong>
            ) : (
              <span key={v.id}>
                <Link to={`/programacion/${v.id}`}>v{v.version} ({v.estado})</Link>{' '}
              </span>
            )
          )}
        </p>
      )}
      {!editable && <p>Esta programación solo se puede consultar.</p>}

      <div className="filtros">
        <label htmlFor="filtro">Mostrar</label>
        <select id="filtro" value={filtro} onChange={(evento) => setFiltro(evento.target.value)}>
          <option value="">Todas las sucursales, separadas</option>
          {sucursales.map((s) => (
            <option key={s.id} value={s.id}>{s.nombre}</option>
          ))}
        </select>
      </div>

      {error && <p role="alert">{error}</p>}
      {visibles.length === 0 && <p>No hay colaboradores en esta sucursal.</p>}

      {grupos.map((grupo) => (
        <section key={grupo.id}>
          <div className="encabezado">
            <h2>{grupo.nombre} <small>({grupo.personas.length})</small></h2>
            {grupo.id && (
              <button type="button" onClick={() => verPdf(`?sucursal=${grupo.id}`)}>Calendario en PDF</button>
            )}
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Colaborador</th>
                  {dias.map((d) => (
                    <th key={d.texto}>{d.etiqueta}</th>
                  ))}
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {grupo.personas.map((c) => (
                  <tr key={c.id}>
                    <td>{c.apellidos}, {c.nombres}</td>
                    {dias.map((d) => {
                      const clave = `${c.id}|${d.texto}`
                      return (
                        <td key={d.texto}>
                          <select
                            aria-label={`${c.apellidos}, ${c.nombres} el ${d.etiqueta}`}
                            value={valorDe(clave)}
                            disabled={!editable}
                            onChange={(evento) => cambiar(clave, evento.target.value)}
                          >
                            <option value="" disabled={clave in guardadas}>Sin asignar</option>
                            <option value="libre">Libre</option>
                            {turnos.map((t) => (
                              <option key={t.id} value={t.id}>{t.nombre}</option>
                            ))}
                          </select>
                        </td>
                      )
                    })}
                    <td>
                      <button type="button" onClick={() => verPdf(`?colaborador=${c.id}`)}>
                        Hoja PDF
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      {editable && programacion.tipo === 'semanal' && (
        <p>
          <button type="button" onClick={copiarSemanaAnterior} disabled={guardando}>
            Copiar semana anterior (invirtiendo Mañana y Tarde)
          </button>
        </p>
      )}

      {editable && (
        <p>
          <button type="button" onClick={guardar} disabled={guardando || pendientes.length === 0}>
            {guardando ? 'Guardando...' : `Guardar cambios (${pendientes.length})`}
          </button>
        </p>
      )}
      {mensaje && <p role="status">{mensaje}</p>}

      {rol === 'rrhh' && (
        <PanelPublicacion
          programacion={programacion}
          esUltima={esUltima}
          pendientes={pendientes.length}
          onPublicada={() => setVersion(version + 1)}
          onVersionCreada={(nuevaId) => navegar(`/programacion/${nuevaId}`)}
        />
      )}

      {cambiosTurno.length > 0 && (
        <section>
          <h2>Cambios respecto a la versión anterior</h2>
          <table>
            <thead>
              <tr>
                <th>Colaborador</th>
                <th>Fecha</th>
                <th>Antes</th>
                <th>Ahora</th>
                <th>Motivo</th>
              </tr>
            </thead>
            <tbody>
              {[...cambiosTurno]
                .sort((a, b) => a.asignaciones_turno.fecha.localeCompare(b.asignaciones_turno.fecha))
                .map((c) => {
                  const persona = colaboradores.find((x) => x.id === c.asignaciones_turno.colaborador_id)
                  return (
                    <tr key={`${c.asignaciones_turno.colaborador_id}|${c.asignaciones_turno.fecha}`}>
                      <td>{persona ? `${persona.apellidos}, ${persona.nombres}` : ''}</td>
                      <td>{c.asignaciones_turno.fecha}</td>
                      <td>{c.turno_anterior?.nombre ?? 'Libre o sin asignar'}</td>
                      <td>{c.turno_nuevo?.nombre ?? 'Libre'}</td>
                      <td>{c.motivo}</td>
                    </tr>
                  )
                })}
            </tbody>
          </table>
        </section>
      )}
    </main>
  )
}