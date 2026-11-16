import { useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import { llamarApi } from './api'

export default function EnlaceReloj({ colaborador, onEnlazado, onCancelar }) {
  const [relojes, setRelojes] = useState([])
  const [conocidos, setConocidos] = useState([])
  const [ocupados, setOcupados] = useState([])
  const [relojId, setRelojId] = useState('')
  const [idReloj, setIdReloj] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    supabase
      .from('dispositivos')
      .select('id, nombre, sucursal_id')
      .eq('activo', true)
      .order('nombre')
      .then(({ data }) => setRelojes(data ?? []))

    supabase
      .from('dispositivo_usuarios')
      .select('dispositivo_id, id_en_dispositivo, nombre')
      .then(({ data }) => setConocidos(data ?? []))

    supabase
      .from('colaborador_dispositivo')
      .select('dispositivo_id, id_en_dispositivo')
      .then(({ data }) => setOcupados(data ?? []))
  }, [])

  const relojDeSuSucursal = relojes.find((r) => r.sucursal_id === colaborador.sucursal_base_id)
  const relojElegido = relojId || relojDeSuSucursal?.id || ''

  const sugerencias = conocidos.filter(
    (u) =>
      u.dispositivo_id === relojElegido &&
      !ocupados.some(
        (o) => o.dispositivo_id === relojElegido && o.id_en_dispositivo === u.id_en_dispositivo
      )
  )

  async function enviar(evento) {
    evento.preventDefault()
    setError('')
    setEnviando(true)

    try {
      await llamarApi(`/colaboradores/${colaborador.id}/enlaces`, {
        method: 'POST',
        body: JSON.stringify({ dispositivo_id: relojElegido, id_en_dispositivo: idReloj }),
      })
      onEnlazado()
    } catch (falla) {
      if (falla.campos) setError(Object.values(falla.campos).join('. '))
      else if (falla.estado) setError(falla.message)
      else setError('No se pudo conectar con el servidor')
    } finally {
      setEnviando(false)
    }
  }

  const idSelect = `reloj-${colaborador.id}`
  const idCampo = `idreloj-${colaborador.id}`
  const idLista = `sugerencias-${colaborador.id}`

  return (
    <form onSubmit={enviar}>
      <label htmlFor={idSelect}>Reloj</label>
      <select id={idSelect} value={relojElegido} onChange={(evento) => setRelojId(evento.target.value)}>
        <option value="">Selecciona un reloj</option>
        {relojes.map((r) => (
          <option key={r.id} value={r.id}>{r.nombre}</option>
        ))}
      </select>

      <label htmlFor={idCampo}>ID en el reloj</label>
      <input
        id={idCampo}
        list={idLista}
        maxLength={24}
        value={idReloj}
        onChange={(evento) => setIdReloj(evento.target.value)}
      />
      <datalist id={idLista}>
        {sugerencias.map((u) => (
          <option key={u.id_en_dispositivo} value={u.id_en_dispositivo}>{u.nombre}</option>
        ))}
      </datalist>

      <button type="submit" disabled={enviando}>
        {enviando ? 'Guardando...' : 'Guardar enlace'}
      </button>
      <button type="button" onClick={onCancelar}>Cancelar</button>

      {error && <p role="alert">{error}</p>}
    </form>
  )
}