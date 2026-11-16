import { supabase } from './supabaseClient'

async function token() {
  const { data } = await supabase.auth.getSession()
  return data.session?.access_token
}

async function errorDeRespuesta(respuesta) {
  const cuerpo = await respuesta.json().catch(() => ({}))
  const error = new Error(cuerpo.error ?? `La API respondió ${respuesta.status}`)
  error.estado = respuesta.status
  error.campos = cuerpo.campos
  return error
}

export async function llamarApi(ruta, opciones = {}) {
  const respuesta = await fetch(`/api${ruta}`, {
    ...opciones,
    headers: {
      'Content-Type': 'application/json',
      ...opciones.headers,
      Authorization: `Bearer ${await token()}`,
    },
  })

  if (!respuesta.ok) throw await errorDeRespuesta(respuesta)
  return respuesta.json()
}

export async function abrirPdf(ruta) {
  const ventana = window.open('', '_blank')
  if (!ventana) {
    const error = new Error('El navegador bloqueó la ventana nueva. Permite las ventanas emergentes')
    error.aviso = true
    throw error
  }

  try {
    const respuesta = await fetch(`/api${ruta}`, {
      headers: { Authorization: `Bearer ${await token()}` },
    })
    if (!respuesta.ok) throw await errorDeRespuesta(respuesta)

    const url = URL.createObjectURL(await respuesta.blob())
    ventana.location.href = url
    setTimeout(() => URL.revokeObjectURL(url), 60000)
  } catch (error) {
    ventana.close()
    throw error
  }
}