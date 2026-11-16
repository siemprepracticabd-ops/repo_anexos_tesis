# siempre

sistema de control de asistencia y planilla para sucursales con relojes biometricos.

## partes

| carpeta | contenido |
|---|---|
| `backend/` | api en flask (python 3.12), logica de negocio y pruebas en `backend/tests` |
| `frontend/` | aplicacion web en react con vite |
| `database/` | `base_de_datos.sql`: tablas, funciones, politicas y datos iniciales de postgres (supabase); `mantenimiento/` trae respaldo y restauracion |
| `agente/` | programa que corre en la pc de cada sucursal y envia las marcaciones del reloj |
| `firebase.json` | hosting del frontend y redireccion de `/api/**` a la funcion |

## puesta en marcha

1. base de datos: ejecutar `database/base_de_datos.sql` completo en el editor sql de supabase sobre una base vacia, y crear el primer usuario con su rol en la tabla `profiles`.
2. backend: copiar `backend/.env.example` a `backend/.env`, completar los valores y ejecutar:

```bash
cd backend
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests
```

3. frontend: copiar `frontend/.env.example` a `frontend/.env`, completar los valores y ejecutar:

```bash
cd frontend
npm install
npm run dev
```

4. agente: ver `agente/README.md`.

## motor de calculo

el calculo de jornadas, tardanzas, horas extra, ausencias y planilla vive en funciones de la base de datos (`calcular_jornadas`, `resolver_horas_extra`, `cerrar_planilla` y otras), no en la api. la api valida, llama a esas funciones y registra la bitacora.
