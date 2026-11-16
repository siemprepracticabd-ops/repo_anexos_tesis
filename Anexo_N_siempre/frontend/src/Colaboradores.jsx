import { useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import FormularioColaborador from './FormularioColaborador'
import EnlaceReloj from './EnlaceReloj'
import CambiarCondiciones from './CambiarCondiciones'
import EstadoLaboral from './EstadoLaboral'
import Licencias from './Licencias'
import Ventana from './Ventana'
import { llamarApi } from './api'
import { aTexto } from './periodos'
import { MODALIDADES, condicionVigente, etiquetaDe, textoDePago } from './pago'

function estaActivo(colaborador, hoy) {
  return colaborador.periodos_laborales.some(
    (p) => p.fecha_ingreso <= hoy && (p.fecha_baja === null || p.fecha_baja >= hoy)
  )
}

function textoEstado(colaborador, hoy) {
  if (estaActivo(colaborador, hoy)) {
    const proxima = colaborador.periodos_laborales.find((p) => p.fecha_baja !== null && p.fecha_baja >= hoy)
    return proxima ? `Baja el ${proxima.fecha_baja}` : 'Activo'
  }
  const bajas = colaborador.periodos_laborales.filter((p) => p.fecha_baja !== null).map((p) => p.fecha_baja).sort()
  return bajas.length > 0 ? `De baja desde ${bajas[bajas.length - 1]}` : 'Sin contrato'
}

export default function Colaboradores() {
  const [colaboradores, setColaboradores] = useState(null)
  const [sucursales, setSucursales] = useState([])
  const [filtro, setFiltro] = useState('')
  const [ventana, setVentana] = useState(null)
  const [mostrarBajas, setMostrarBajas] = useState(false)
  const [hoy] = useState(() => aTexto(new Date()))
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)

  useEffect(() => {
    supabase
      .from('colaboradores')
      .select(
        'id, nombres, apellidos, dpi, telefono, sucursal_base_id, modalidad, puestos(nombre), sucursales(nombre), colaborador_dispositivo(dispositivo_id, id_en_dispositivo, dispositivos(nombre)), colaborador_salarios(forma_pago, salario_mensual, tarifa, vigente_desde, vigente_hasta), periodos_laborales(fecha_ingreso, fecha_baja, motivo_baja), licencias(id, fecha_desde, fecha_hasta, motivo, tipos_ausencia(nombre))'
      )
      .order('apellidos')
      .then(({ data, error: errorLista }) => {
        if (errorLista) setError('No se pudo cargar la lista')
        else setColaboradores(data)
      })
  }, [version])

  useEffect(() => {
    supabase
      .from('sucursales')
      .select('id, nombre')
      .eq('activa', true)
      .order('nombre')
      .then(({ data }) => setSucursales(data ?? []))
  }, [])

  const visibles = (colaboradores ?? [])
    .filter((c) => filtro === '' || c.sucursal_base_id === filtro)
    .filter((c) => mostrarBajas || estaActivo(c, hoy))
    .sort(
      (a, b) =>
        (a.sucursales?.nombre ?? '').localeCompare(b.sucursales?.nombre ?? '') ||
        a.apellidos.localeCompare(b.apellidos)
    )

  async function quitarEnlace(colaborador, enlace) {
    const texto = `${enlace.id_en_dispositivo} (${enlace.dispositivos?.nombre})`
    const nombre = `${colaborador.nombres} ${colaborador.apellidos}`
    if (!window.confirm(`¿Quitar el enlace ${texto} de ${nombre}?`)) return

    setError('')
    try {
      await llamarApi(`/colaboradores/${colaborador.id}/enlaces/${enlace.dispositivo_id}`, {
        method: 'DELETE',
      })
      setVersion(version + 1)
    } catch {
      setError('No se pudo quitar el enlace')
    }
  }

  function alCerrarVentana() {
    setVentana(null)
    setVersion((v) => v + 1)
  }

  const elegido = ventana?.id ? colaboradores?.find((c) => c.id === ventana.id) : null

  return (
    <main>
      <div className="encabezado">
        <h1>Colaboradores</h1>
        <button type="button" className="principal" onClick={() => setVentana({ tipo: 'nuevo' })}>
          Nuevo colaborador
        </button>
      </div>

      <div className="filtros">
        <label htmlFor="filtro">Mostrar</label>
        <select id="filtro" value={filtro} onChange={(evento) => setFiltro(evento.target.value)}>
          <option value="">Todas las sucursales</option>
          {sucursales.map((s) => (
            <option key={s.id} value={s.id}>{s.nombre}</option>
          ))}
        </select>
        <label htmlFor="bajas">
          <input
            id="bajas"
            type="checkbox"
            checked={mostrarBajas}
            onChange={(evento) => setMostrarBajas(evento.target.checked)}
          />{' '}
          Mostrar las personas de baja
        </label>
      </div>

      {error && <p role="alert">{error}</p>}
      {colaboradores === null && !error && <p>Cargando...</p>}
      {colaboradores?.length === 0 && <p>Todavía no hay colaboradores registrados.</p>}
      {colaboradores?.length > 0 && visibles.length === 0 && (
        <p>No hay colaboradores en esta sucursal.</p>
      )}

      {visibles.length > 0 && (
        <>
          <p>{visibles.length} {visibles.length === 1 ? 'colaborador' : 'colaboradores'}</p>
          <table>
            <thead>
              <tr>
                <th>Nombre</th>
                <th>DPI</th>
                <th>Teléfono</th>
                <th>Puesto</th>
                <th>Sucursal base</th>
                <th>Modalidad</th>
                <th>Pago</th>
                <th>Estado</th>
                <th>ID en reloj</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {visibles.map((c) => (
                <tr key={c.id}>
                  <td>{c.apellidos}, {c.nombres}</td>
                  <td>···{c.dpi.slice(-4)}</td>
                  <td>{c.telefono}</td>
                  <td>{c.puestos?.nombre}</td>
                  <td>{c.sucursales?.nombre}</td>
                  <td>{etiquetaDe(MODALIDADES, c.modalidad)}</td>
                  <td>{textoDePago(condicionVigente(c.colaborador_salarios, hoy))}</td>
                  <td>{textoEstado(c, hoy)}</td>
                  <td>
                    {c.colaborador_dispositivo.length === 0 && 'Sin enlazar'}
                    {c.colaborador_dispositivo.map((e) => (
                      <div key={e.dispositivo_id}>
                        {e.id_en_dispositivo} ({e.dispositivos?.nombre}){' '}
                        <button type="button" onClick={() => quitarEnlace(c, e)}>Quitar</button>
                      </div>
                    ))}
                  </td>
                  <td>
                    <button type="button" onClick={() => setVentana({ tipo: 'enlazar', id: c.id })}>Enlazar</button>{' '}
                    <button type="button" onClick={() => setVentana({ tipo: 'condiciones', id: c.id })}>Condiciones</button>{' '}
                    <button type="button" onClick={() => setVentana({ tipo: 'licencias', id: c.id })}>Licencias</button>{' '}
                    <button type="button" onClick={() => setVentana({ tipo: 'estado', id: c.id })}>
                      {estaActivo(c, hoy) ? 'Baja' : 'Reactivar'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {ventana?.tipo === 'nuevo' && (
        <Ventana onCerrar={alCerrarVentana}>
          <FormularioColaborador sucursalInicial={filtro} onCreado={() => setVersion((v) => v + 1)} />
        </Ventana>
      )}

      {elegido && ventana.tipo === 'enlazar' && (
        <Ventana onCerrar={alCerrarVentana}>
          <EnlaceReloj colaborador={elegido} onEnlazado={alCerrarVentana} onCancelar={alCerrarVentana} />
        </Ventana>
      )}

      {elegido && ventana.tipo === 'condiciones' && (
        <Ventana onCerrar={alCerrarVentana}>
          <CambiarCondiciones
            colaborador={elegido}
            vigente={condicionVigente(elegido.colaborador_salarios, hoy)}
            onCambiado={alCerrarVentana}
            onCancelar={alCerrarVentana}
          />
        </Ventana>
      )}

      {elegido && ventana.tipo === 'licencias' && (
        <Ventana onCerrar={alCerrarVentana}>
          <Licencias
            colaborador={elegido}
            hoy={hoy}
            onCambiado={() => setVersion((v) => v + 1)}
            onCancelar={alCerrarVentana}
          />
        </Ventana>
      )}

      {elegido && ventana.tipo === 'estado' && (
        <Ventana onCerrar={alCerrarVentana}>
          <EstadoLaboral
            colaborador={elegido}
            activo={estaActivo(elegido, hoy)}
            hoy={hoy}
            onCambiado={alCerrarVentana}
            onCancelar={alCerrarVentana}
          />
        </Ventana>
      )}
    </main>
  )
}
