import { useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import { llamarApi } from './api'

const VACIO = { serie: '', nombre: '', modelo: '', sucursal_id: '', sucursal_nueva: '' }
const NUEVA = '__nueva'

function fechaHora(iso) {
  return new Date(iso).toLocaleString('es-GT', { timeZone: 'America/Guatemala', hourCycle: 'h23' })
}

export default function Relojes({ rol }) {
  const [relojes, setRelojes] = useState(null)
  const [sucursales, setSucursales] = useState([])
  const [valores, setValores] = useState(VACIO)
  const [errores, setErrores] = useState({})
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [clave, setClave] = useState(null)
  const [version, setVersion] = useState(0)

  const puedeEditar = rol === 'jefe'

  useEffect(() => {
    supabase
      .from('dispositivos')
      .select('id, serie, nombre, modelo, activo, ultima_sincronizacion, sucursales(nombre)')
      .order('nombre')
      .then(({ data, error: falla }) => {
        if (falla) setError('No se pudieron cargar los relojes')
        else setRelojes(data)
      })
  }, [version])

  useEffect(() => {
    supabase
      .from('sucursales')
      .select('id, nombre')
      .order('nombre')
      .then(({ data }) => setSucursales(data ?? []))
  }, [])

  function cambiar(evento) {
    const { name, value } = evento.target
    setValores({ ...valores, [name]: value })
  }

  async function llamar(ruta, cuerpo) {
    setErrores({})
    setError('')
    setEnviando(true)
    try {
      const respuesta = await llamarApi(ruta, { method: 'POST', body: JSON.stringify(cuerpo ?? {}) })
      setVersion((v) => v + 1)
      return respuesta
    } catch (falla) {
      if (falla.campos) setErrores(falla.campos)
      else if (falla.estado) setError(falla.message)
      else setError('No se pudo conectar con el servidor')
      return null
    } finally {
      setEnviando(false)
    }
  }

  async function registrar(evento) {
    evento.preventDefault()
    const { sucursal_id: elegida, sucursal_nueva: nombreNuevo, ...resto } = valores
    const cuerpo = elegida === NUEVA ? { ...resto, sucursal_nueva: nombreNuevo } : { ...resto, sucursal_id: elegida }
    const respuesta = await llamar('/relojes', cuerpo)
    if (respuesta) {
      setClave({ serie: respuesta.serie, api_key: respuesta.api_key })
      setValores(VACIO)
      supabase
        .from('sucursales')
        .select('id, nombre')
        .order('nombre')
        .then(({ data }) => setSucursales(data ?? []))
    }
  }

  async function regenerar(reloj) {
    if (!window.confirm(`¿Generar una clave nueva para «${reloj.nombre}»? La clave anterior deja de funcionar.`)) return
    const respuesta = await llamar(`/relojes/${reloj.id}/clave`)
    if (respuesta) setClave({ serie: respuesta.serie, api_key: respuesta.api_key })
  }

  async function cambiarEstado(reloj) {
    if (reloj.activo && !window.confirm(`¿Desactivar «${reloj.nombre}»? No se recibirán sus marcaciones.`)) return
    await llamar(`/relojes/${reloj.id}/estado`, { activo: !reloj.activo })
  }

  async function copiar() {
    try {
      await navigator.clipboard.writeText(clave.api_key)
    } catch {
      setError('No se pudo copiar. Selecciona la clave y cópiala a mano')
    }
  }

  return (
    <main>
      <h1>Relojes</h1>
      <p>Cada reloj biométrico se registra con su número de serie. Al registrarlo se genera la clave que se instala en el agente de esa sucursal.</p>

      {clave && (
        <section>
          <h2>Clave del reloj {clave.serie}</h2>
          <p role="status">Guárdala ahora: por seguridad no se vuelve a mostrar. Si se pierde, se genera una nueva.</p>
          <p><code>{clave.api_key}</code></p>
          <p>
            <button type="button" onClick={copiar}>Copiar clave</button>{' '}
            <button type="button" onClick={() => setClave(null)}>Ya la guardé</button>
          </p>
          <p>En el equipo de la sucursal, pon esta clave y el número de serie <strong>{clave.serie}</strong> en el config.json del agente.</p>
        </section>
      )}

      {puedeEditar && (
        <form onSubmit={registrar}>
          <h2>Registrar reloj</h2>
          <div>
            <label htmlFor="r_serie">Número de serie</label>
            <input id="r_serie" name="serie" value={valores.serie} maxLength={40} onChange={cambiar} />
            {errores.serie && <p role="alert">{errores.serie}</p>}
          </div>
          <div>
            <label htmlFor="r_nombre">Nombre</label>
            <input id="r_nombre" name="nombre" value={valores.nombre} maxLength={60} onChange={cambiar} placeholder="Reloj Sucursal Norte" />
            {errores.nombre && <p role="alert">{errores.nombre}</p>}
          </div>
          <div>
            <label htmlFor="r_modelo">Modelo (opcional)</label>
            <input id="r_modelo" name="modelo" value={valores.modelo} maxLength={60} onChange={cambiar} placeholder="CLK-960" />
            {errores.modelo && <p role="alert">{errores.modelo}</p>}
          </div>
          <div>
            <label htmlFor="r_sucursal">Sucursal</label>
            <select id="r_sucursal" name="sucursal_id" value={valores.sucursal_id} onChange={cambiar}>
              <option value="">Elige...</option>
              {sucursales.map((s) => (
                <option key={s.id} value={s.id}>{s.nombre}</option>
              ))}
              <option value={NUEVA}>+ Sucursal nueva...</option>
            </select>
            {errores.sucursal_id && <p role="alert">{errores.sucursal_id}</p>}
          </div>
          <div hidden={valores.sucursal_id !== NUEVA}>
            <label htmlFor="r_sucursal_nueva">Nombre de la sucursal nueva</label>
            <input id="r_sucursal_nueva" name="sucursal_nueva" value={valores.sucursal_nueva} maxLength={60} onChange={cambiar} />
            {errores.sucursal_nueva && <p role="alert">{errores.sucursal_nueva}</p>}
          </div>
          <button type="submit" disabled={enviando}>Registrar reloj</button>
        </form>
      )}

      {error && <p role="alert">{error}</p>}
      {relojes === null && !error && <p>Cargando...</p>}
      {relojes?.length === 0 && <p>Todavía no hay relojes registrados.</p>}

      {relojes?.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Reloj</th>
              <th>Sucursal</th>
              <th>Serie</th>
              <th>Modelo</th>
              <th>Estado</th>
              <th>Última sincronización</th>
              {puedeEditar && <th></th>}
            </tr>
          </thead>
          <tbody>
            {relojes.map((r) => (
              <tr key={r.id}>
                <td>{r.nombre}</td>
                <td>{r.sucursales?.nombre}</td>
                <td>{r.serie}</td>
                <td>{r.modelo}</td>
                <td>{r.activo ? 'Activo' : 'Desactivado'}</td>
                <td>{r.ultima_sincronizacion ? fechaHora(r.ultima_sincronizacion) : 'Nunca'}</td>
                {puedeEditar && (
                  <td>
                    <button type="button" disabled={enviando} onClick={() => regenerar(r)}>Nueva clave</button>{' '}
                    <button type="button" disabled={enviando} onClick={() => cambiarEstado(r)}>
                      {r.activo ? 'Desactivar' : 'Activar'}
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  )
}
