import { Link } from 'react-router-dom'

// tarjeta de resumen: un numero grande y su etiqueta
export default function Dato({ cantidad, etiqueta, ruta, ancla, urgente, texto }) {
  const clase = `dato ${cantidad === 0 ? 'bien' : urgente ? 'mal' : 'aviso'}`
  const cuerpo = (
    <>
      <span className="dato-numero">{texto ?? cantidad}</span>
      <span className="dato-etiqueta">{etiqueta}</span>
    </>
  )
  if (cantidad === 0 || (!ruta && !ancla)) return <div className={clase}>{cuerpo}</div>
  return ancla ? (
    <a className={clase} href={ancla}>{cuerpo}</a>
  ) : (
    <Link className={clase} to={ruta}>{cuerpo}</Link>
  )
}
