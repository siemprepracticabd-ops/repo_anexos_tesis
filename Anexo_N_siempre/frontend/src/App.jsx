import { useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import Login from './Login'
import Acceso from './Acceso'

export default function App() {
  const [sesion, setSesion] = useState(undefined)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSesion(data.session))

    const { data } = supabase.auth.onAuthStateChange((_evento, nuevaSesion) => {
      setSesion(nuevaSesion)
    })

    return () => data.subscription.unsubscribe()
  }, [])

  if (sesion === undefined) return <p>Cargando...</p>
  if (sesion === null) return <Login />
    return <Acceso sesion={sesion} />
}