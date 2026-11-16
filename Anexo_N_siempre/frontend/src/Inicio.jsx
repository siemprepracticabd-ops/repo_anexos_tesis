import { useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import { llamarApi } from './api'
import { horaLocal } from './tiempo'
import Dato from './Dato'
import EnTurnoResumen from './EnTurnoResumen'

// gravedad: 'alta' pide atencion hoy, 'media' conviene revisarla, 'baja' es informativa
const TIPOS_ALERTA = {
  ausencia: { etiqueta: 'Ausencia', gravedad: 'alta' },
  exceso_horas_extra: { etiqueta: 'Exceso de horas extra', gravedad: 'alta' },
  marcacion_sin_colaborador: { etiqueta: 'Marcación sin persona', gravedad: 'alta' },
  marcacion_faltante: { etiqueta: 'Falta una marcación', gravedad: 'media' },
  por_confirmar: { etiqueta: 'Jornada por confirmar', gravedad: 'media' },
  sin_programacion: { etiqueta: 'Sin turno programado', gravedad: 'media' },
  tardanzas_frecuentes: { etiqueta: 'Tardanzas frecuentes', gravedad: 'baja' },
  descanso_insuficiente: { etiqueta: 'Descanso insuficiente', gravedad: 'baja' },
}

function fechaCorta(texto) {
  if (!texto) return ''
  const [anio, mes, dia] = texto.split('-')
  return `${dia}/${mes}/${anio}`
}

function descripcion(alerta) {
  const d = alerta.detalle ?? {}
  switch (alerta.tipo) {
    case 'tardanzas_frecuentes':
      return `${d.tardanzas} tardanzas en la quincena que empieza el ${fechaCorta(alerta.fecha)}`
    case 'exceso_horas_extra':
      return d.alcance === 'semana'
        ? `${d.minutos} min de hora extra en la semana del ${fechaCorta(alerta.fecha)} (máximo ${d.maximo})`
        : `${d.minutos} min de hora extra en un día (máximo ${d.maximo})`
    case 'descanso_insuficiente':
      return `${d.horas} h de descanso antes de este turno (mínimo ${d.minimo})`
    case 'ausencia':
      return 'No se presentó a su turno'
    case 'marcacion_faltante':
      return 'Jornada con una sola marcación'
    case 'por_confirmar':
      return 'La jornada necesita confirmación de RR. HH.'
    case 'sin_programacion':
      return 'Marcó sin tener un turno programado'
    default:
      return alerta.dispositivos?.nombre ? `Reloj: ${alerta.dispositivos.nombre}` : ''
  }
}

function minutosDesde(iso, ahora) {
  return iso ? Math.floor((ahora - new Date(iso)) / 60000) : null
}

function hace(minutos) {
  if (minutos === null) return 'Nunca ha reportado'
  if (minutos < 1) return 'Hace un momento'
  if (minutos < 60) return `Hace ${minutos} min`
  if (minutos < 1440) return `Hace ${Math.floor(minutos / 60)} h`
  return `Hace ${Math.floor(minutos / 1440)} días`
}

function estadoDelReloj(minutos) {
  if (minutos !== null && minutos <= 60) return { clase: 'bien', texto: 'En línea' }
  if (minutos !== null && minutos <= 1440) return { clase: 'aviso', texto: 'Sin reportar' }
  return { clase: 'mal', texto: 'Desconectado' }
}

function saludo(fecha) {
  const hora = Number(new Intl.DateTimeFormat('es-GT', { hour: 'numeric', hourCycle: 'h23', timeZone: 'America/Guatemala' }).format(fecha))
  if (hora < 12) return 'Buenos días'
  if (hora < 19) return 'Buenas tardes'
  return 'Buenas noches'
}

export default function Inicio({ perfil }) {
  const [ahora] = useState(() => Date.now())
  const [datos, setDatos] = useState(null)
  const [tipo, setTipo] = useState('')
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)

  useEffect(() => {
    const contar = (tabla, filtro) => filtro(supabase.from(tabla).select('id', { count: 'exact', head: true }))

    Promise.all([
      supabase
        .from('alertas')
        .select('id, tipo, fecha, detalle, creada_en, colaboradores(nombres, apellidos), dispositivos(nombre)')
        .eq('estado', 'abierta')
        .order('creada_en', { ascending: false })
        .limit(50),
      contar('ausencias', (q) => q.eq('estado', 'sin_justificar')),
      contar('horas_extra', (q) => q.eq('estado', 'pendiente')),
      contar('jornadas', (q) => q.eq('estado', 'incompleta')),
      contar('jornadas', (q) => q.eq('estado', 'por_confirmar')),
      contar('descuentos_tiempo', (q) => q.eq('estado', 'pendiente')),
      supabase
        .from('dispositivos')
        .select('id, nombre, ultima_sincronizacion, sucursales(nombre)')
        .eq('activo', true)
        .order('nombre'),
    ]).then(([alertas, ausencias, extras, incompletas, porConfirmar, descuentos, relojes]) => {
      const falla = [alertas, ausencias, extras, incompletas, porConfirmar, descuentos, relojes].some((r) => r.error)
      if (falla) {
        setError('No se pudo cargar el resumen')
        return
      }
      setError('')
      setDatos({
        alertas: alertas.data,
        pendientes: [
          { etiqueta: 'Ausencias sin justificar', cantidad: ausencias.count, ruta: '/pendientes', urgente: true },
          { etiqueta: 'Horas extra por decidir', cantidad: extras.count, ruta: '/pendientes' },
          { etiqueta: 'Jornadas incompletas', cantidad: incompletas.count, ruta: '/planilla', urgente: true },
          { etiqueta: 'Jornadas por confirmar', cantidad: porConfirmar.count, ruta: '/planilla' },
          { etiqueta: 'Descuentos por decidir', cantidad: descuentos.count, ruta: '/planilla' },
        ],
        relojes: relojes.data,
      })
    })
  }, [version])

  async function resolver(alerta) {
    setError('')
    try {
      await llamarApi(`/alertas/${alerta.id}/resolver`, { method: 'POST' })
      setVersion((v) => v + 1)
    } catch (falla) {
      setError(falla.estado ? falla.message : 'No se pudo conectar con el servidor')
    }
  }

  const totalPendiente = datos?.pendientes.reduce((suma, p) => suma + p.cantidad, 0) ?? 0
  const porTipo = {}
  datos?.alertas.forEach((a) => {
    porTipo[a.tipo] = (porTipo[a.tipo] ?? 0) + 1
  })
  const alertasVisibles = datos?.alertas.filter((a) => tipo === '' || a.tipo === tipo) ?? []
  const relojesEnLinea = datos?.relojes.filter((r) => estadoDelReloj(minutosDesde(r.ultima_sincronizacion, ahora)).clase === 'bien').length ?? 0

  return (
    <main>
      <header className="bienvenida">
        <h1>{saludo(new Date(ahora))}, {perfil.full_name}</h1>
        <p>
          {datos === null
            ? 'Cargando el resumen...'
            : totalPendiente + datos.alertas.length === 0
              ? 'Todo en orden: no hay nada pendiente.'
              : `Tienes ${totalPendiente} ${totalPendiente === 1 ? 'pendiente' : 'pendientes'} y ${datos.alertas.length} ${datos.alertas.length === 1 ? 'alerta abierta' : 'alertas abiertas'}.`}
        </p>
      </header>

      {error && <p role="alert">{error}</p>}

      {datos !== null && (
        <>
          <section aria-label="Resumen">
            <div className="datos">
              {datos.pendientes.map((p) => (
                <Dato key={p.etiqueta} {...p} />
              ))}
              <Dato cantidad={datos.alertas.length} etiqueta="Alertas abiertas" ancla="#alertas" urgente />
              <div className={`dato ${relojesEnLinea === datos.relojes.length ? 'bien' : 'aviso'}`}>
                <span className="dato-numero">{relojesEnLinea}/{datos.relojes.length}</span>
                <span className="dato-etiqueta">Relojes en línea</span>
              </div>
            </div>
          </section>

          <EnTurnoResumen />

          <section id="alertas">
            <h2>Alertas abiertas</h2>
            {datos.alertas.length === 0 && <p className="vacio">No hay alertas abiertas.</p>}
            {datos.alertas.length > 0 && (
              <>
                <div className="chips" role="group" aria-label="Filtrar alertas por tipo">
                  <button type="button" className="chip" aria-pressed={tipo === ''} onClick={() => setTipo('')}>
                    Todas <span>{datos.alertas.length}</span>
                  </button>
                  {Object.entries(porTipo).map(([clave, cantidad]) => (
                    <button
                      key={clave}
                      type="button"
                      className="chip"
                      aria-pressed={tipo === clave}
                      onClick={() => setTipo(tipo === clave ? '' : clave)}
                    >
                      {TIPOS_ALERTA[clave]?.etiqueta ?? clave} <span>{cantidad}</span>
                    </button>
                  ))}
                </div>

                <div className="alertas">
                  {alertasVisibles.map((a) => {
                    const info = TIPOS_ALERTA[a.tipo] ?? { etiqueta: a.tipo, gravedad: 'baja' }
                    return (
                      <article key={a.id} className={`alerta ${info.gravedad}`}>
                        <div className="alerta-cuerpo">
                          <span className="insignia">{info.etiqueta}</span>
                          <strong>{a.colaboradores ? `${a.colaboradores.nombres} ${a.colaboradores.apellidos}` : 'Sin persona'}</strong>
                          <span className="alerta-texto">{descripcion(a)}</span>
                          <small>{fechaCorta(a.fecha)}</small>
                        </div>
                        <button type="button" onClick={() => resolver(a)}>Marcar como vista</button>
                      </article>
                    )
                  })}
                </div>
              </>
            )}
          </section>

          <section>
            <h2>Relojes</h2>
            <div className="relojes">
              {datos.relojes.map((r) => {
                const minutos = minutosDesde(r.ultima_sincronizacion, ahora)
                const estado = estadoDelReloj(minutos)
                return (
                  <article key={r.id} className="reloj">
                    <span className={`punto ${estado.clase}`} aria-hidden="true" />
                    <div>
                      <strong>{r.nombre}</strong>
                      <small>{r.sucursales?.nombre}</small>
                    </div>
                    <div className="reloj-estado">
                      <span>{estado.texto}</span>
                      <small>
                        {hace(minutos)}
                        {r.ultima_sincronizacion && ` (${horaLocal(r.ultima_sincronizacion)})`}
                      </small>
                    </div>
                  </article>
                )
              })}
            </div>
          </section>
        </>
      )}
    </main>
  )
}
