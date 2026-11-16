import { useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import { llamarApi } from './api'
import CamposPago from './CamposPago'

const VACIO = {
  nombres: '',
  apellidos: '',
  dpi: '',
  telefono: '',
  puesto_id: '',
  sucursal_id: '',
  fecha_ingreso: '',
  modalidad: 'tiempo_completo',
  forma_pago: 'salario_fijo',
  salario_mensual: '',
  tarifa: '',
}

function Campo({ id, etiqueta, error, children }) {
  return (
    <div>
      <label htmlFor={id}>{etiqueta}</label>
      {children}
      {error && <p role="alert">{error}</p>}
    </div>
  )
}

function textoDeError(error) {
  if (error.campos) return 'Revisa los campos marcados'
  if (error.estado) return error.message
  return 'No se pudo conectar con el servidor'
}

export default function FormularioColaborador({ sucursalInicial, onCreado }) {
  const [valores, setValores] = useState(VACIO)
  const [puestos, setPuestos] = useState([])
  const [sucursales, setSucursales] = useState([])
  const [errores, setErrores] = useState({})
  const [resultado, setResultado] = useState(null)
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    supabase
      .from('puestos')
      .select('id, nombre')
      .order('nombre')
      .then(({ data }) => setPuestos(data ?? []))

    supabase
      .from('sucursales')
      .select('id, nombre')
      .eq('activa', true)
      .order('nombre')
      .then(({ data }) => setSucursales(data ?? []))
  }, [])

  function cambiar(evento) {
    const { name, value } = evento.target
    setValores({ ...valores, [name]: value })
  }

  async function enviar(evento) {
    evento.preventDefault()
    setErrores({})
    setResultado(null)
    setEnviando(true)

    try {
      await llamarApi('/colaboradores', {
        method: 'POST',
        body: JSON.stringify({
          ...valores,
          sucursal_id: valores.sucursal_id || sucursalInicial,
        }),
      })
      setValores(VACIO)
      setResultado({ ok: true, texto: 'Colaborador registrado' })
      onCreado()
    } catch (error) {
      if (error.campos) setErrores(error.campos)
      setResultado({ ok: false, texto: textoDeError(error) })
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={enviar}>
      <h2>Nuevo colaborador</h2>

      <Campo id="nombres" etiqueta="Nombres" error={errores.nombres}>
        <input id="nombres" name="nombres" value={valores.nombres} onChange={cambiar} />
      </Campo>

      <Campo id="apellidos" etiqueta="Apellidos" error={errores.apellidos}>
        <input id="apellidos" name="apellidos" value={valores.apellidos} onChange={cambiar} />
      </Campo>

      <Campo id="dpi" etiqueta="DPI" error={errores.dpi}>
        <input
          id="dpi"
          name="dpi"
          inputMode="numeric"
          maxLength={13}
          value={valores.dpi}
          onChange={cambiar}
        />
      </Campo>

      <Campo id="telefono" etiqueta="Teléfono (opcional)" error={errores.telefono}>
        <input
          id="telefono"
          name="telefono"
          inputMode="tel"
          maxLength={9}
          value={valores.telefono}
          onChange={cambiar}
        />
      </Campo>

      <Campo id="puesto_id" etiqueta="Puesto" error={errores.puesto_id}>
        <select id="puesto_id" name="puesto_id" value={valores.puesto_id} onChange={cambiar}>
          <option value="">Selecciona un puesto</option>
          {puestos.map((p) => (
            <option key={p.id} value={p.id}>{p.nombre}</option>
          ))}
        </select>
      </Campo>

      <Campo id="sucursal_id" etiqueta="Sucursal base" error={errores.sucursal_id}>
        <select
          id="sucursal_id"
          name="sucursal_id"
          value={valores.sucursal_id || sucursalInicial}
          onChange={cambiar}
        >
          <option value="">Selecciona una sucursal</option>
          {sucursales.map((s) => (
            <option key={s.id} value={s.id}>{s.nombre}</option>
          ))}
        </select>
      </Campo>

      <Campo id="fecha_ingreso" etiqueta="Fecha de ingreso" error={errores.fecha_ingreso}>
        <input
          id="fecha_ingreso"
          name="fecha_ingreso"
          type="date"
          value={valores.fecha_ingreso}
          onChange={cambiar}
        />
      </Campo>

      <CamposPago
        valores={valores}
        errores={errores}
        onChange={(campos) => setValores({ ...valores, ...campos })}
      />

      <button type="submit" disabled={enviando}>
        {enviando ? 'Guardando...' : 'Guardar'}
      </button>

      {resultado && <p role={resultado.ok ? 'status' : 'alert'}>{resultado.texto}</p>}
    </form>
  )
}