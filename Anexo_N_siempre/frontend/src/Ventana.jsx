import { useEffect, useRef } from 'react'

// ventana emergente sobre la pantalla: se cierra con esc, con la x o al hacer clic fuera
export default function Ventana({ onCerrar, children }) {
  const dialogo = useRef(null)

  useEffect(() => {
    if (dialogo.current && !dialogo.current.open) dialogo.current.showModal()
  }, [])

  return (
    <dialog
      ref={dialogo}
      className="ventana"
      onClose={onCerrar}
      onClick={(evento) => {
        if (evento.target === dialogo.current) dialogo.current.close()
      }}
    >
      <div className="ventana-contenido">
        <button
          type="button"
          className="ventana-cerrar"
          aria-label="Cerrar la ventana"
          onClick={() => dialogo.current.close()}
        >
          ×
        </button>
        {children}
      </div>
    </dialog>
  )
}
