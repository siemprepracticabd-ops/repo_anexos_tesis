import { Fragment, useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import { llamarApi } from './api'
import { agruparPorSucursal, etiquetaDe, FORMAS_DE_PAGO, quetzales } from './pago'
import { formatoHoras } from './tiempo'
import AjustarValores from './AjustarValores'
import DescuentosManuales from './DescuentosManuales'
import Ventana from './Ventana'

function sumar(personas) {
  return personas.reduce(
    (suma, p) => ({
      ingresos: suma.ingresos + p.total_ingresos,
      descuentos: suma.descuentos + p.total_descuentos,
      neto: suma.neto + p.neto,
    }),
    { ingresos: 0, descuentos: 0, neto: 0 }
  )
}

export default function PagoQuincena({ desde, hasta, rol, version }) {
  const [personas, setPersonas] = useState(null)
  const [abierto, setAbierto] = useState(null)
  const [descontando, setDescontando] = useState(null)
  const [error, setError] = useState('')
  const [recarga, setRecarga] = useState(0)

  useEffect(() => {
    let vigente = true
    Promise.all([
      llamarApi(`/planilla?desde=${desde}&hasta=${hasta}`),
      supabase.from('colaboradores').select('id, sucursales(nombre)'),
    ])
      .then(([planilla, colaboradores]) => {
        if (!vigente) return
        if (colaboradores.error) {
          setError('No se pudieron cargar las sucursales')
          return
        }
        const sucursalDe = Object.fromEntries(colaboradores.data.map((c) => [c.id, c.sucursales?.nombre]))
        setError('')
        setPersonas(planilla.personas.map((p) => ({ ...p, sucursal: sucursalDe[p.colaborador_id] ?? 'Sin sucursal' })))
      })
      .catch((falla) => {
        if (vigente) setError(falla.estado ? falla.message : 'No se pudo conectar con el servidor')
      })
    return () => {
      vigente = false
    }
  }, [desde, hasta, version, recarga])

  function alGuardar() {
    setAbierto(null)
    setRecarga((r) => r + 1)
  }

  const total = sumar(personas ?? [])

  return (
    <section>
      <h2>Pago de la quincena (vista previa)</h2>
      <p>
        Es lo que se pagaría hoy. Se paga la jornada completa; las horas registradas son las que marcó en el reloj.
        Las horas extra que siguen por decidir todavía no se suman.
        {rol === 'rrhh' && ' Puedes cambiar el valor de la hora solo para esta quincena.'}
      </p>

      {error && <p role="alert">{error}</p>}
      {personas === null && !error && <p>Calculando...</p>}
      {personas?.length === 0 && <p>No hay personas con contrato activo en esta quincena.</p>}

      {personas?.length > 0 &&
        agruparPorSucursal(personas, (p) => p.sucursal).map((grupo) => {
          const subtotal = sumar(grupo.elementos)
          return (
            <div key={grupo.nombre}>
              <h3>{grupo.nombre}</h3>
              <table>
                <thead>
                  <tr>
                    <th>Empleado</th>
                    <th>Forma de pago</th>
                    <th>Horas de jornada</th>
                    <th>Horas registradas</th>
                    <th>Valor de la hora</th>
                    <th>Ingresos</th>
                    <th>Descuentos</th>
                    <th>Neto</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {grupo.elementos.map((p) => (
                    <Fragment key={p.colaborador_id}>
                      <tr>
                        <td>{p.nombre}</td>
                        <td>{etiquetaDe(FORMAS_DE_PAGO, p.forma_pago)}</td>
                        <td>{p.forma_pago === 'por_turno' ? `${p.turnos} turnos` : formatoHoras(p.minutos_jornada ?? p.minutos_trabajados)}</td>
                        <td>{formatoHoras(p.minutos_trabajados)}</td>
                        <td>
                          {p.valor_hora === null ? '' : quetzales(p.valor_hora)}
                          {p.ajuste && ' (ajustado)'}
                        </td>
                        <td>{quetzales(p.total_ingresos)}</td>
                        <td>{quetzales(p.total_descuentos)}</td>
                        <td><strong>{quetzales(p.neto)}</strong></td>
                        <td>
                          <button type="button" onClick={() => setAbierto(abierto === p.colaborador_id ? null : p.colaborador_id)}>
                            {abierto === p.colaborador_id ? 'Cerrar' : 'Detalle'}
                          </button>{' '}
                          <button type="button" onClick={() => setDescontando(p.colaborador_id)}>Descuentos</button>
                        </td>
                      </tr>
                      {abierto === p.colaborador_id && (
                        <tr>
                          <td colSpan={8}>
                            {p.lineas.length === 0 && <p>Sin pagos en esta quincena.</p>}
                            {p.lineas.length > 0 && (
                              <table>
                                <thead>
                                  <tr>
                                    <th>Concepto</th>
                                    <th>Cantidad</th>
                                    <th>Valor</th>
                                    <th>Monto</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {p.lineas.map((l, i) => (
                                    <tr key={`${i}-${l.concepto}`}>
                                      <td>{l.tipo === 'descuento' ? `(−) ${l.concepto}` : l.concepto}</td>
                                      <td>{l.cantidad}</td>
                                      <td>{quetzales(l.valor_unitario)}</td>
                                      <td>{quetzales(l.monto)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                            {p.ajuste?.motivo && <p>Motivo del ajuste: {p.ajuste.motivo}</p>}
                            {rol === 'rrhh' && (
                              <AjustarValores
                                persona={p}
                                desde={desde}
                                hasta={hasta}
                                onGuardado={alGuardar}
                                onCancelar={() => setAbierto(null)}
                              />
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <td colSpan={4}><strong>Subtotal {grupo.nombre}</strong></td>
                    <td><strong>{quetzales(subtotal.ingresos)}</strong></td>
                    <td><strong>{quetzales(subtotal.descuentos)}</strong></td>
                    <td><strong>{quetzales(subtotal.neto)}</strong></td>
                    <td></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )
        })}

      {personas?.length > 0 && (
        <p>
          <strong>
            Total de la quincena: {quetzales(total.ingresos)} de ingresos, {quetzales(total.descuentos)} de
            descuentos, {quetzales(total.neto)} netos.
          </strong>
        </p>
      )}

      {descontando && personas?.some((p) => p.colaborador_id === descontando) && (
        <Ventana onCerrar={() => setDescontando(null)}>
          <DescuentosManuales
            persona={personas.find((p) => p.colaborador_id === descontando)}
            desde={desde}
            hasta={hasta}
            onCambiado={() => setRecarga((r) => r + 1)}
            onCerrar={() => setDescontando(null)}
          />
        </Ventana>
      )}
    </section>
  )
}