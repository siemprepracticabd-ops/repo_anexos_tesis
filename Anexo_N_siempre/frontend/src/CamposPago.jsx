import { FORMAS_DE_PAGO, MODALIDADES, formaSugerida } from './pago'

const ETIQUETA_MONTO = {
  salario_fijo: 'Salario mensual (Q)',
  por_hora: 'Valor de la hora (Q)',
  por_turno: 'Valor por turno (Q)',
}

export default function CamposPago({ valores, errores, onChange }) {
  const campoMonto = valores.forma_pago === 'salario_fijo' ? 'salario_mensual' : 'tarifa'

  return (
    <>
      <div>
        <label htmlFor="modalidad">Modalidad</label>
        <select
          id="modalidad"
          value={valores.modalidad}
          onChange={(evento) =>
            onChange({ modalidad: evento.target.value, forma_pago: formaSugerida(evento.target.value) })
          }
        >
          {MODALIDADES.map((m) => (
            <option key={m.valor} value={m.valor}>{m.etiqueta}</option>
          ))}
        </select>
        {errores.modalidad && <p role="alert">{errores.modalidad}</p>}
      </div>

      <div>
        <label htmlFor="forma_pago">Forma de pago</label>
        <select
          id="forma_pago"
          value={valores.forma_pago}
          onChange={(evento) => onChange({ forma_pago: evento.target.value })}
        >
          {FORMAS_DE_PAGO.map((f) => (
            <option key={f.valor} value={f.valor}>{f.etiqueta}</option>
          ))}
        </select>
        {errores.forma_pago && <p role="alert">{errores.forma_pago}</p>}
      </div>

      <div>
        <label htmlFor={campoMonto}>{ETIQUETA_MONTO[valores.forma_pago]}</label>
        <input
          id={campoMonto}
          type="number"
          min="0"
          step="0.01"
          value={valores[campoMonto]}
          onChange={(evento) => onChange({ [campoMonto]: evento.target.value })}
        />
        {errores[campoMonto] && <p role="alert">{errores[campoMonto]}</p>}
      </div>
    </>
  )
}