import { supabase } from './supabaseClient'

export default function SinPermiso() {
  return (
    <main>
      <h1>Sin permiso</h1>
      <p>Tu cuenta no tiene acceso al sistema. Pide a Recursos Humanos que la habiliten.</p>
      <button onClick={() => supabase.auth.signOut()}>Salir</button>
    </main>
  )
}