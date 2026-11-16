import { useState } from 'react'
import { supabase } from './supabaseClient'
import logo from './assets/logo.svg'

export default function Login() {
  const [correo, setCorreo] = useState('')
  const [clave, setClave] = useState('')
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  async function entrar(evento) {
    evento.preventDefault()
    setError('')
    setCargando(true)

    const { error: errorLogin } = await supabase.auth.signInWithPassword({
      email: correo,
      password: clave,
    })

    setCargando(false)

    if (errorLogin) {
      setError('Correo o contraseña incorrectos')
    }
  }

  return (
    <main className="login">
      <div className="login-tarjeta">
        <img className="login-logo" src={logo} alt="Siempre" />
        <h1>Control de asistencia</h1>
        <p className="login-subtitulo">Ingresa con tu cuenta</p>

        <form className="login-formulario" onSubmit={entrar}>
          <label htmlFor="correo">Correo</label>
          <input
            id="correo"
            type="email"
            autoComplete="email"
            required
            value={correo}
            onChange={(evento) => setCorreo(evento.target.value)}
          />

          <label htmlFor="clave">Contraseña</label>
          <input
            id="clave"
            type="password"
            autoComplete="current-password"
            required
            value={clave}
            onChange={(evento) => setClave(evento.target.value)}
          />

          <button type="submit" disabled={cargando}>
            {cargando ? 'Entrando...' : 'Entrar'}
          </button>

          {error && <p role="alert" className="login-error">{error}</p>}
        </form>
      </div>
    </main>
  )
}