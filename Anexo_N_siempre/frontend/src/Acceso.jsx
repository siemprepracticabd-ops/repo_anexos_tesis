import { useEffect, useState } from 'react'
import { supabase } from './supabaseClient'
import Inicio from './Inicio'
import SinPermiso from './SinPermiso'
import { Link, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import Colaboradores from './Colaboradores'
import Turnos from './Turnos'
import Programaciones from './Programaciones'
import Parrilla from './Parrilla'
import Asistencia from './Asistencia'
import Pendientes from './Pendientes'
import Puestos from './Puestos'
import Planilla from './Planilla'
import Bitacora from './Bitacora'
import Relojes from './Relojes'
import Oficina from './Oficina'

const ROLES_PERMITIDOS = ['rrhh', 'jefe']

export default function Acceso({ sesion }) {
  const [perfil, setPerfil] = useState(undefined)
  const [alertas, setAlertas] = useState(0)
  const { pathname } = useLocation()

  useEffect(() => {
    supabase
      .from('profiles')
      .select('full_name, role')
      .eq('id', sesion.user.id)
      .single()
      .then(({ data, error }) => setPerfil(error ? null : data))
  }, [sesion.user.id])

  useEffect(() => {
    if (!perfil || !ROLES_PERMITIDOS.includes(perfil.role)) return undefined

    function contar() {
      supabase
        .from('alertas')
        .select('id')
        .eq('estado', 'abierta')
        .then(({ data }) => setAlertas(data?.length ?? 0))
    }

    contar()
    const reloj = setInterval(contar, 60000)
    return () => clearInterval(reloj)
  }, [perfil, pathname])

  if (perfil === undefined) return <p>Cargando...</p>
  if (perfil === null || !ROLES_PERMITIDOS.includes(perfil.role)) return <SinPermiso />
    return (
    <>
      <nav>
        <NavLink to="/">Inicio</NavLink>
        <NavLink to="/turnos">Turnos</NavLink>
        <NavLink to="/programacion">Programación</NavLink>
        <NavLink to="/oficina">Oficina</NavLink>
        <NavLink to="/asistencia">Asistencia</NavLink>
        <NavLink to="/pendientes">Pendientes</NavLink>
        <NavLink to="/colaboradores">Colaboradores</NavLink>
        <NavLink to="/puestos">Puestos</NavLink>
        <NavLink to="/planilla">Planilla</NavLink>
        <NavLink to="/relojes">Relojes</NavLink>
        <NavLink to="/bitacora">Bitácora</NavLink>
        <div className="nav-usuario">
          <Link to="/" title="Alertas abiertas">
            Alertas{alertas > 0 && <span className="nav-contador">{alertas}</span>}
          </Link>
          <button type="button" onClick={() => supabase.auth.signOut()}>Salir</button>
        </div>
      </nav>

      <Routes>
        <Route path="/" element={<Inicio sesion={sesion} perfil={perfil} />} />
        <Route path="/colaboradores" element={<Colaboradores />} />
        <Route path="/turnos" element={<Turnos rol={perfil.role} />} />
        <Route path="/puestos" element={<Puestos rol={perfil.role} />} />
        <Route path="/programacion" element={<Programaciones rol={perfil.role} />} />
        <Route path="/asistencia" element={<Asistencia rol={perfil.role} />} />
        <Route path="/pendientes" element={<Pendientes rol={perfil.role} />} />
        <Route path="/planilla" element={<Planilla rol={perfil.role} />} />
        <Route path="/oficina" element={<Oficina rol={perfil.role} />} />
        <Route path="/relojes" element={<Relojes rol={perfil.role} />} />
        <Route path="/bitacora" element={<Bitacora />} />
        <Route path="*" element={<main><p>Página no encontrada</p></main>} />
        <Route path="/programacion/:id" element={<Parrilla rol={perfil.role} />} />
      </Routes>
    </>
  )
}