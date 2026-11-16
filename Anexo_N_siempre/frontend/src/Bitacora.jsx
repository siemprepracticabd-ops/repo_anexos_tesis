import { useEffect, useState } from 'react'
import { llamarApi } from './api'

const ACCIONES = {
  crear: 'Crear',
  guardar: 'Guardar',
  publicar: 'Publicar',
  calcular: 'Calcular jornadas',
  preparar: 'Preparar descuentos',
  agregar_marcacion: 'Agregar marcación',
  confirmar: 'Confirmar jornada',
  justificar: 'Justificar ausencia',
  autorizar: 'Decidir horas extra',
  corregir: 'Corregir horas',
  registrar_asistencia: 'Registrar asistencia',
  decidir: 'Decidir',
  ajustar: 'Ajustar valores de hora',
  cerrar: 'Cerrar quincena',
  pagar: 'Marcar como pagado',
  reabrir: 'Reabrir quincena',
  baja: 'Dar de baja',
  reactivar: 'Reactivar',
  anular: 'Anular',
  resolver: 'Resolver alerta',
  enlazar: 'Enlazar reloj',
  desenlazar: 'Quitar enlace del reloj',
  regenerar_clave: 'Generar clave nueva',
  activar: 'Activar',
  desactivar: 'Desactivar',
}

const TABLAS = {
  colaboradores: 'Colaboradores',
  colaborador_dispositivo: 'Enlaces con el reloj',
  programaciones: 'Programaciones',
  asignaciones_turno: 'Turnos asignados',
  jornadas: 'Jornadas',
  marcaciones: 'Marcaciones',
  ausencias: 'Ausencias',
  horas_extra: 'Horas extra',
  descuentos_tiempo: 'Descuentos por tardanza',
  periodos_planilla: 'Quincenas',
  ajustes_planilla: 'Ajustes de planilla',
  licencias: 'Licencias',
  alertas: 'Alertas',
  puestos: 'Puestos',
  dispositivos: 'Relojes',
  descuentos_manuales: 'Descuentos de planilla',
  sucursales: 'Sucursales',
  dias_diurno: 'Horario de oficina',
  turnos: 'Turnos',
}

const FILTROS_VACIOS = { desde: '', hasta: '', usuario: '', accion: '', tabla: '' }

function fechaHora(iso) {
  return new Date(iso).toLocaleString('es-GT', { timeZone: 'America/Guatemala', hourCycle: 'h23' })
}

export default function Bitacora() {
  const [opciones, setOpciones] = useState({ acciones: [], tablas: [], usuarios: [] })
  const [escritos, setEscritos] = useState(FILTROS_VACIOS)
  const [filtros, setFiltros] = useState(FILTROS_VACIOS)
  const [pagina, setPagina] = useState(1)
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    llamarApi('/bitacora/opciones')
      .then(setOpciones)
      .catch(() => setError('No se pudieron cargar los filtros'))
  }, [])

  useEffect(() => {
    let vigente = true
    const consulta = new URLSearchParams({ pagina })
    for (const [clave, valor] of Object.entries(filtros)) {
      if (valor) consulta.set(clave, valor)
    }

    llamarApi(`/bitacora?${consulta}`)
      .then((respuesta) => {
        if (!vigente) return
        setError('')
        setDatos(respuesta)
      })
      .catch((falla) => {
        if (vigente) {
          setError(falla.campos ? Object.values(falla.campos).join('. ') : `No se pudo cargar la bitácora (${falla.message})`)
        }
      })
    return () => {
      vigente = false
    }
  }, [filtros, pagina])

  function cambiar(evento) {
    const { name, value } = evento.target
    setEscritos({ ...escritos, [name]: value })
  }

  function buscar(evento) {
    evento.preventDefault()
    setPagina(1)
    setFiltros(escritos)
  }

  function limpiar() {
    setEscritos(FILTROS_VACIOS)
    setPagina(1)
    setFiltros(FILTROS_VACIOS)
  }

  return (
    <main>
      <h1>Bitácora</h1>
      <p>Registro de todo lo que se hace en el sistema. Solo se puede consultar: no se edita ni se borra.</p>

      <form className="filtros" onSubmit={buscar}>
        <label htmlFor="b_desde">Desde</label>{' '}
        <input id="b_desde" name="desde" type="date" value={escritos.desde} onChange={cambiar} />{' '}
        <label htmlFor="b_hasta">Hasta</label>{' '}
        <input id="b_hasta" name="hasta" type="date" value={escritos.hasta} onChange={cambiar} />{' '}
        <label htmlFor="b_usuario">Quién</label>{' '}
        <select id="b_usuario" name="usuario" value={escritos.usuario} onChange={cambiar}>
          <option value="">Todos</option>
          {opciones.usuarios.map((u) => (
            <option key={u.id} value={u.id}>{u.nombre}</option>
          ))}
        </select>{' '}
        <label htmlFor="b_accion">Acción</label>{' '}
        <select id="b_accion" name="accion" value={escritos.accion} onChange={cambiar}>
          <option value="">Todas</option>
          {opciones.acciones.map((a) => (
            <option key={a} value={a}>{ACCIONES[a] ?? a}</option>
          ))}
        </select>{' '}
        <label htmlFor="b_tabla">Sobre qué</label>{' '}
        <select id="b_tabla" name="tabla" value={escritos.tabla} onChange={cambiar}>
          <option value="">Todo</option>
          {opciones.tablas.map((t) => (
            <option key={t} value={t}>{TABLAS[t] ?? t}</option>
          ))}
        </select>{' '}
        <button type="submit">Buscar</button>{' '}
        <button type="button" onClick={limpiar}>Limpiar</button>
      </form>

      {error && <p role="alert">{error}</p>}
      {datos === null && !error && <p>Cargando...</p>}
      {datos?.filas.length === 0 && <p>No hay registros con esos filtros.</p>}

      {datos?.filas.length > 0 && (
        <>
          <table>
            <thead>
              <tr>
                <th>Cuándo</th>
                <th>Quién</th>
                <th>Qué se hizo</th>
                <th>Detalle</th>
              </tr>
            </thead>
            <tbody>
              {datos.filas.map((f) => (
                <tr key={f.id}>
                  <td>{fechaHora(f.creado_en)}</td>
                  <td>{f.usuario ?? 'Sistema'}</td>
                  <td>{f.descripcion}</td>
                  <td>
                    {f.detalle.length > 0 && (
                      <details>
                        <summary>Ver</summary>
                        <dl>
                          {f.detalle.map((linea) => (
                            <div key={linea.etiqueta}>
                              <dt>{linea.etiqueta}</dt>
                              <dd>{linea.valor}</dd>
                            </div>
                          ))}
                        </dl>
                      </details>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <p>
            <button type="button" onClick={() => setPagina(pagina - 1)} disabled={pagina === 1}>Anterior</button>{' '}
            Página {pagina}{' '}
            <button type="button" onClick={() => setPagina(pagina + 1)} disabled={!datos.hay_mas}>Siguiente</button>
          </p>
        </>
      )}
    </main>
  )
}
