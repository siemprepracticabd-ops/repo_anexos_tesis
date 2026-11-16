-- base de datos de siempre: tablas, funciones, politicas y datos iniciales
-- se ejecuta completa en el sql editor de supabase sobre una base vacia

create extension if not exists btree_gist;

-- enums
create type rol_usuario as enum ('rrhh', 'jefe');
create type tipo_jornada as enum ('diurna', 'mixta', 'nocturna');
create type tipo_programacion as enum ('semanal', 'quincenal');
create type estado_programacion as enum ('borrador', 'publicada', 'cerrada');
create type estado_asignacion as enum ('programado', 'a_reasignar');
create type tipo_marcacion as enum ('entrada', 'salida', 'desconocido');
create type origen_marcacion as enum ('lector', 'manual');
create type clasif_entrada as enum ('puntual', 'dentro_gracia', 'tardanza');
create type clasif_salida as enum ('normal', 'anticipada');
create type estado_jornada as enum ('ok', 'por_confirmar', 'incompleta', 'sin_programacion');
create type estado_ausencia as enum ('sin_justificar', 'justificada', 'reclasificada');
create type estado_horas_extra as enum ('pendiente', 'autorizada', 'parcial', 'rechazada');
create type estado_periodo as enum ('abierto', 'cerrado');
create type estado_boleta as enum ('generada', 'pagada');
create type tipo_detalle_boleta as enum ('ingreso', 'descuento');
create type tipo_alerta as enum (
  'marcacion_sin_colaborador', 'sin_programacion', 'por_confirmar', 'marcacion_faltante',
  'ausencia', 'tardanzas_frecuentes', 'exceso_horas_extra', 'descanso_insuficiente'
);
create type estado_alerta as enum ('abierta', 'resuelta');

-- seguridad
create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  role rol_usuario not null
);

create table bitacora (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid references profiles(id),
  accion text not null,
  tabla text not null,
  registro_id uuid,
  detalle jsonb,
  creado_en timestamptz not null default now()
);

-- catalogos
create table sucursales (
  id uuid primary key default gen_random_uuid(),
  nombre text not null unique,
  direccion text,
  activa boolean not null default true
);

create table puestos (
  id uuid primary key default gen_random_uuid(),
  nombre text not null unique
);

create table dispositivos (
  id uuid primary key default gen_random_uuid(),
  sucursal_id uuid not null references sucursales(id),
  serie text not null unique,
  nombre text not null,
  modelo text,
  api_key_hash text not null,
  activo boolean not null default true,
  ultima_sincronizacion timestamptz
);

create table tipos_ausencia (
  id uuid primary key default gen_random_uuid(),
  nombre text not null unique,
  con_goce boolean not null,
  descuenta_dia boolean not null
);

create table turnos (
  id uuid primary key default gen_random_uuid(),
  nombre text not null unique,
  hora_inicio time not null,
  hora_fin time not null,
  cruza_medianoche boolean not null default false,
  tipo_jornada tipo_jornada not null,
  horas_ordinarias numeric not null check (horas_ordinarias > 0)
);

create table parametros (
  id uuid primary key default gen_random_uuid(),
  clave text not null,
  valor numeric not null,
  sucursal_id uuid references sucursales(id),
  turno_id uuid references turnos(id),
  vigente_desde date not null,
  unique nulls not distinct (clave, sucursal_id, turno_id, vigente_desde)
);

-- personal
create table colaboradores (
  id uuid primary key default gen_random_uuid(),
  nombres text not null,
  apellidos text not null,
  dpi text not null unique,
  telefono text,
  puesto_id uuid not null references puestos(id),
  sucursal_base_id uuid not null references sucursales(id)
);

create table colaborador_dispositivo (
  colaborador_id uuid not null references colaboradores(id),
  dispositivo_id uuid not null references dispositivos(id),
  id_en_dispositivo text not null,
  primary key (dispositivo_id, id_en_dispositivo),
  unique (colaborador_id, dispositivo_id)
);

create table dispositivo_usuarios (
  dispositivo_id uuid not null references dispositivos(id),
  id_en_dispositivo text not null,
  nombre text not null,
  actualizado_en timestamptz not null default now(),
  primary key (dispositivo_id, id_en_dispositivo)
);

create table periodos_laborales (
  id uuid primary key default gen_random_uuid(),
  colaborador_id uuid not null references colaboradores(id),
  fecha_ingreso date not null,
  fecha_baja date,
  motivo_baja text,
  check (fecha_baja is null or fecha_baja >= fecha_ingreso)
);

create table colaborador_salarios (
  id uuid primary key default gen_random_uuid(),
  colaborador_id uuid not null references colaboradores(id),
  salario_mensual numeric not null check (salario_mensual > 0),
  vigente_desde date not null,
  vigente_hasta date,
  check (vigente_hasta is null or vigente_hasta >= vigente_desde),
  constraint salarios_sin_traslape exclude using gist (
    colaborador_id with =,
    daterange(vigente_desde, coalesce(vigente_hasta + 1, 'infinity'::date), '[)') with &&
  )
);

create table licencias (
  id uuid primary key default gen_random_uuid(),
  colaborador_id uuid not null references colaboradores(id),
  tipo_ausencia_id uuid not null references tipos_ausencia(id),
  fecha_desde date not null,
  fecha_hasta date not null,
  motivo text,
  registrado_por uuid references profiles(id),
  check (fecha_hasta >= fecha_desde)
);

-- programacion de turnos
create table programaciones (
  id uuid primary key default gen_random_uuid(),
  tipo tipo_programacion not null,
  fecha_inicio date not null,
  fecha_fin date not null,
  version int not null default 1,
  estado estado_programacion not null default 'borrador',
  publicada_en timestamptz,
  publicada_por uuid references profiles(id),
  check (fecha_fin >= fecha_inicio),
  unique (tipo, fecha_inicio, fecha_fin, version)
);

create table asignaciones_turno (
  id uuid primary key default gen_random_uuid(),
  programacion_id uuid not null references programaciones(id),
  colaborador_id uuid not null references colaboradores(id),
  fecha date not null,
  turno_id uuid references turnos(id),
  sucursal_id uuid not null references sucursales(id),
  estado estado_asignacion not null default 'programado',
  unique (programacion_id, colaborador_id, fecha)
);

create table cambios_turno (
  id uuid primary key default gen_random_uuid(),
  asignacion_id uuid not null references asignaciones_turno(id),
  turno_anterior_id uuid references turnos(id),
  turno_nuevo_id uuid references turnos(id),
  motivo text,
  autorizado_por uuid references profiles(id),
  creado_en timestamptz not null default now()
);

-- asistencia
create table marcaciones (
  id uuid primary key default gen_random_uuid(),
  dispositivo_id uuid references dispositivos(id),
  id_en_dispositivo text,
  colaborador_id uuid references colaboradores(id),
  marcado_en timestamptz not null,
  tipo tipo_marcacion not null default 'desconocido',
  origen origen_marcacion not null default 'lector',
  codigo_punch smallint,
  es_duplicada boolean not null default false,
  payload_crudo jsonb,
  recibido_en timestamptz not null default now(),
  check (
    (origen = 'lector' and dispositivo_id is not null and id_en_dispositivo is not null)
    or (origen = 'manual' and colaborador_id is not null)
  ),
  unique (dispositivo_id, id_en_dispositivo, marcado_en)
);

create table correcciones_marcacion (
  id uuid primary key default gen_random_uuid(),
  marcacion_nueva_id uuid not null references marcaciones(id),
  marcacion_original_id uuid references marcaciones(id),
  motivo text not null,
  corregido_por uuid references profiles(id),
  creado_en timestamptz not null default now()
);

create table jornadas (
  id uuid primary key default gen_random_uuid(),
  asignacion_id uuid unique references asignaciones_turno(id),
  colaborador_id uuid not null references colaboradores(id),
  sucursal_id uuid not null references sucursales(id),
  fecha date not null,
  marcacion_entrada_id uuid references marcaciones(id),
  marcacion_salida_id uuid references marcaciones(id),
  minutos_trabajados int default 0,
  minutos_tardanza int default 0,
  minutos_faltantes int default 0,
  minutos_jornada int,
  clasif_entrada clasif_entrada,
  clasif_salida clasif_salida,
  estado estado_jornada not null
);

create table ausencias (
  id uuid primary key default gen_random_uuid(),
  asignacion_id uuid not null unique references asignaciones_turno(id),
  colaborador_id uuid not null references colaboradores(id),
  fecha date not null,
  estado estado_ausencia not null default 'sin_justificar',
  tipo_ausencia_id uuid references tipos_ausencia(id),
  licencia_id uuid references licencias(id),
  minutos_ausentes int,
  detectada_en timestamptz not null default now()
);

create table notas_asistencia (
  id uuid primary key default gen_random_uuid(),
  jornada_id uuid references jornadas(id),
  ausencia_id uuid references ausencias(id),
  texto text not null,
  autor_id uuid references profiles(id),
  creado_en timestamptz not null default now(),
  check (jornada_id is not null or ausencia_id is not null)
);

create table horas_extra (
  id uuid primary key default gen_random_uuid(),
  jornada_id uuid not null unique references jornadas(id),
  minutos_detectados int not null check (minutos_detectados > 0),
  estado estado_horas_extra not null default 'pendiente',
  minutos_pagados int check (minutos_pagados is null or minutos_pagados >= 0),
  justificacion text,
  autorizado_por_nombre text,
  registrado_por uuid references profiles(id),
  decidido_en timestamptz,
  check (minutos_pagados is null or minutos_pagados <= minutos_detectados),
  check (estado = 'pendiente' or (nullif(trim(justificacion), '') is not null and minutos_pagados is not null))
);

create table alertas (
  id uuid primary key default gen_random_uuid(),
  tipo tipo_alerta not null,
  estado estado_alerta not null default 'abierta',
  colaborador_id uuid references colaboradores(id),
  dispositivo_id uuid references dispositivos(id),
  fecha date,
  detalle jsonb,
  creada_en timestamptz not null default now(),
  resuelta_por uuid references profiles(id),
  resuelta_en timestamptz
);

-- planilla
create table periodos_planilla (
  id uuid primary key default gen_random_uuid(),
  fecha_inicio date not null,
  fecha_fin date not null,
  estado estado_periodo not null default 'abierto',
  cerrado_por uuid references profiles(id),
  cerrado_en timestamptz,
  aprobado_por uuid references profiles(id),
  check (fecha_fin >= fecha_inicio),
  unique (fecha_inicio, fecha_fin)
);

create table boletas (
  id uuid primary key default gen_random_uuid(),
  numero int generated always as identity unique,
  periodo_id uuid not null references periodos_planilla(id),
  colaborador_id uuid not null references colaboradores(id),
  boleta_origen_id uuid references boletas(id),
  estado estado_boleta not null default 'generada',
  total_ingresos numeric not null default 0,
  total_descuentos numeric not null default 0,
  neto numeric not null default 0,
  snapshot_valores jsonb,
  pagada_en timestamptz,
  pagada_por uuid references profiles(id)
);

create table boleta_detalles (
  id uuid primary key default gen_random_uuid(),
  boleta_id uuid not null references boletas(id),
  tipo tipo_detalle_boleta not null,
  concepto text not null,
  sucursal_id uuid references sucursales(id),
  cantidad numeric,
  valor_unitario numeric,
  monto numeric not null,
  horas_extra_id uuid references horas_extra(id),
  ausencia_id uuid references ausencias(id)
);

-- indices (marcaciones no lleva indice aparte por dispositivo/id/fecha: el unique de la tabla ya crea
create index on marcaciones (colaborador_id, marcado_en);
create index on asignaciones_turno (colaborador_id, fecha);
create index on jornadas (colaborador_id, fecha);
create index on ausencias (colaborador_id, fecha);
create index on colaborador_salarios (colaborador_id, vigente_desde);
create index on alertas (estado, tipo);
create index on boletas (periodo_id, colaborador_id);

-- reglas en la base
create function marcar_duplicada() returns trigger as $$
begin
  if new.origen = 'lector' and exists (
    select 1 from marcaciones
    where dispositivo_id = new.dispositivo_id
      and id_en_dispositivo = new.id_en_dispositivo
      and not es_duplicada
      and marcado_en >= new.marcado_en - interval '60 seconds'
      and marcado_en < new.marcado_en
  ) then
    new.es_duplicada := true;
  end if;
  return new;
end;
$$ language plpgsql;

create trigger marcaciones_duplicadas
  before insert on marcaciones
  for each row execute function marcar_duplicada();

create function bloquear_cambios() returns trigger as $$
begin
  raise exception '% es inmutable', tg_table_name;
end;
$$ language plpgsql;

create trigger marcaciones_inmutables
  before update or delete on marcaciones
  for each row execute function bloquear_cambios();

create trigger boleta_detalles_inmutables
  before update or delete on boleta_detalles
  for each row execute function bloquear_cambios();

create function proteger_boleta() returns trigger as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'las boletas no se borran';
  end if;
  if (new.numero, new.periodo_id, new.colaborador_id, new.boleta_origen_id,
      new.total_ingresos, new.total_descuentos, new.neto, new.snapshot_valores)
     is distinct from
     (old.numero, old.periodo_id, old.colaborador_id, old.boleta_origen_id,
      old.total_ingresos, old.total_descuentos, old.neto, old.snapshot_valores) then
    raise exception 'una boleta emitida no se modifica; emite una boleta de ajuste';
  end if;
  return new;
end;
$$ language plpgsql;

create trigger boletas_protegidas
  before update or delete on boletas
  for each row execute function proteger_boleta();

create function salario_en(p_colaborador uuid, p_fecha date) returns numeric
language sql stable as $$
  select salario_mensual from colaborador_salarios
  where colaborador_id = p_colaborador
    and vigente_desde <= p_fecha
    and (vigente_hasta is null or vigente_hasta >= p_fecha)
$$;

create function registrar_aumento(p_colaborador uuid, p_salario numeric, p_desde date)
returns void as $$
begin
  update colaborador_salarios
     set vigente_hasta = p_desde - 1
   where colaborador_id = p_colaborador and vigente_hasta is null and vigente_desde < p_desde;
  insert into colaborador_salarios (colaborador_id, salario_mensual, vigente_desde)
  values (p_colaborador, p_salario, p_desde);
end;
$$ language plpgsql;

-- vistas
create view marcaciones_resueltas with (security_invoker = true) as
select m.id, m.marcado_en,
       m.marcado_en at time zone 'America/Guatemala' as marcado_en_local,
       m.tipo, m.origen, m.es_duplicada,
       s.nombre as sucursal, d.nombre as dispositivo, m.id_en_dispositivo,
       coalesce(m.colaborador_id, cd.colaborador_id) as colaborador_id,
       coalesce(c.nombres || ' ' || c.apellidos, du.nombre) as colaborador,
       du.nombre as nombre_en_dispositivo
from marcaciones m
left join dispositivos d on d.id = m.dispositivo_id
left join sucursales s on s.id = d.sucursal_id
left join colaborador_dispositivo cd
  on cd.dispositivo_id = m.dispositivo_id and cd.id_en_dispositivo = m.id_en_dispositivo
left join colaboradores c on c.id = coalesce(m.colaborador_id, cd.colaborador_id)
left join dispositivo_usuarios du
  on du.dispositivo_id = m.dispositivo_id and du.id_en_dispositivo = m.id_en_dispositivo;

create view asignaciones_vigentes with (security_invoker = true) as
select distinct on (a.colaborador_id, a.fecha) a.*
from asignaciones_turno a
join programaciones p on p.id = a.programacion_id
where p.estado in ('publicada', 'cerrada')
order by a.colaborador_id, a.fecha, p.publicada_en desc;

-- seguridad (rls) las escrituras las hace flask con la clave service_role (ignora rls)
create function rol_actual() returns rol_usuario
language sql stable security definer set search_path = public as $$
  select role from profiles where id = auth.uid()
$$;

revoke execute on function rol_actual() from public, anon;
grant execute on function rol_actual() to authenticated;
revoke execute on function registrar_aumento(uuid, numeric, date) from public, anon, authenticated;

alter table profiles enable row level security;
create policy perfil_propio on profiles for select to authenticated
  using (id = auth.uid() or rol_actual() = 'rrhh');

do $$
declare t text;
begin
  foreach t in array array[
    'bitacora', 'sucursales', 'puestos', 'dispositivos', 'tipos_ausencia', 'turnos', 'parametros',
    'colaboradores', 'colaborador_dispositivo', 'dispositivo_usuarios', 'periodos_laborales',
    'colaborador_salarios', 'licencias', 'programaciones', 'asignaciones_turno', 'cambios_turno',
    'marcaciones', 'correcciones_marcacion', 'jornadas', 'ausencias', 'notas_asistencia',
    'horas_extra', 'alertas', 'periodos_planilla', 'boletas', 'boleta_detalles'
  ] loop
    execute format('alter table %I enable row level security', t);
    execute format(
      'create policy lectura_rrhh_jefe on %I for select to authenticated using (rol_actual() in (''rrhh'', ''jefe''))',
      t
    );
  end loop;
end $$;

-- la clave de los relojes nunca debe leerse desde la pantalla
revoke select on dispositivos from anon, authenticated;
grant select (id, sucursal_id, serie, nombre, modelo, activo, ultima_sincronizacion)
  on dispositivos to authenticated;

-- defensa en profundidad: aunque rls ya bloquea
revoke insert, update, delete on all tables in schema public from anon, authenticated;

-- pide a la api de supabase que vuelva a leer el esquema (si no, a veces
notify pgrst, 'reload schema';

-- despues de crear un usuario en authentication > users, dale su rol

-- datos base del sistema

-- turnos: valores iniciales de trabajo
insert into turnos (nombre, hora_inicio, hora_fin, cruza_medianoche, tipo_jornada, horas_ordinarias)
values
  ('Mañana', '06:00', '14:00', false, 'diurna',   8),
  ('Tarde',  '14:00', '22:00', false, 'mixta',    8),
  ('Noche',  '22:00', '06:00', true,  'nocturna', 8)
on conflict (nombre) do nothing;

-- tipos de ausencia con_goce = se paga el dia descuenta_dia = se descuenta el dia de la planilla
insert into tipos_ausencia (nombre, con_goce, descuenta_dia)
values
  ('Permiso con goce de salario', true,  false),
  ('Permiso sin goce de salario', false, true),
  ('Incapacidad IGSS',            false, true),
  ('Vacaciones',                  true,  false),
  ('Suspensión disciplinaria',    false, true),
  ('Falta injustificada',         false, true)
on conflict (nombre) do nothing;

-- parametros globales (sin sucursal ni turno), vigentes desde 2026-01-01
insert into parametros (clave, valor, vigente_desde)
values
  ('gracia_minutos',               10,   '2026-01-01'),  -- tolerancia de entrada y salida
  ('ausencia_minutos',             60,   '2026-01-01'),  -- sin marcar tras este tiempo = ausencia
  ('recargo_hora_extra',           1.5,  '2026-01-01'),  -- art
  ('extra_minimo_minutos',         30,   '2026-01-01'),  -- menos de esto no se considera extra
  ('extra_maximo_dia_minutos',     120,  '2026-01-01'),  -- alerta si se supera por dia
  ('extra_maximo_semana_minutos',  720,  '2026-01-01'),  -- alerta si se supera por semana
  ('descanso_minimo_horas',        8,    '2026-01-01'),  -- alerta si hay menos entre jornadas
  ('tardanzas_alerta_quincena',    3,    '2026-01-01'),  -- tardanzas o llegadas en gracia que disparan alerta
  ('dias_base_salario',            30,   '2026-01-01'),  -- valor hora = salario / 30 / 8
  ('horas_base_dia',               8,    '2026-01-01')
on conflict do nothing;

-- alta de colaborador en una sola transaccion

create function crear_colaborador(
  p_nombres text,
  p_apellidos text,
  p_dpi text,
  p_telefono text,
  p_puesto_id uuid,
  p_sucursal_id uuid,
  p_fecha_ingreso date,
  p_salario numeric,
  p_usuario uuid
) returns uuid
language plpgsql as $$
declare
  nuevo uuid;
begin
  insert into colaboradores (nombres, apellidos, dpi, telefono, puesto_id, sucursal_base_id)
  values (p_nombres, p_apellidos, p_dpi, nullif(p_telefono, ''), p_puesto_id, p_sucursal_id)
  returning id into nuevo;

  insert into periodos_laborales (colaborador_id, fecha_ingreso)
  values (nuevo, p_fecha_ingreso);

  insert into colaborador_salarios (colaborador_id, salario_mensual, vigente_desde)
  values (nuevo, p_salario, p_fecha_ingreso);

  -- en la bitacora no se guarda el dpi completo, solo sus ultimos 4 digitos
  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (
    p_usuario, 'crear', 'colaboradores', nuevo,
    jsonb_build_object('dpi_ultimos4', right(p_dpi, 4), 'fecha_ingreso', p_fecha_ingreso)
  );

  return nuevo;
end;
$$;

revoke execute on function crear_colaborador(text, text, text, text, uuid, uuid, date, numeric, uuid)
  from public, anon, authenticated;

-- pide a la api de supabase que reconozca la funcion nueva
notify pgrst, 'reload schema';

-- catalogo de puestos de la empresa

insert into puestos (nombre)
values
  ('Cajero'),
  ('Encargado de tienda'),
  ('Guardia')
on conflict (nombre) do nothing;

-- segunda sucursal del piloto: sucursal sur

insert into sucursales (nombre)
values ('Sucursal Sur')
on conflict (nombre) do nothing;

-- enlazar a un colaborador con su id dentro de un reloj, dejando constancia en la bitacora

create function enlazar_colaborador(
  p_colaborador uuid,
  p_dispositivo uuid,
  p_id text,
  p_usuario uuid
) returns boolean
language plpgsql as $$
begin
  insert into colaborador_dispositivo (colaborador_id, dispositivo_id, id_en_dispositivo)
  values (p_colaborador, p_dispositivo, p_id);

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (
    p_usuario, 'enlazar', 'colaborador_dispositivo', p_colaborador,
    jsonb_build_object('dispositivo_id', p_dispositivo, 'id_en_dispositivo', p_id)
  );

  return true;
end;
$$;

revoke execute on function enlazar_colaborador(uuid, uuid, text, uuid)
  from public, anon, authenticated;

notify pgrst, 'reload schema';

-- quitar el enlace de un colaborador con un reloj, dejando constancia en la bitacora

create function desenlazar_colaborador(
  p_colaborador uuid,
  p_dispositivo uuid,
  p_usuario uuid
) returns boolean
language plpgsql as $$
declare
  quitado text;
begin
  delete from colaborador_dispositivo
   where colaborador_id = p_colaborador
     and dispositivo_id = p_dispositivo
  returning id_en_dispositivo into quitado;

  if quitado is null then
    return false;
  end if;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (
    p_usuario, 'desenlazar', 'colaborador_dispositivo', p_colaborador,
    jsonb_build_object('dispositivo_id', p_dispositivo, 'id_en_dispositivo', quitado)
  );

  return true;
end;
$$;

revoke execute on function desenlazar_colaborador(uuid, uuid, uuid)
  from public, anon, authenticated;

notify pgrst, 'reload schema';

-- turnos reales de la empresa

alter table turnos add column activo boolean not null default true;

update turnos set hora_inicio = '05:00', hora_fin = '13:00', cruza_medianoche = false,
                  tipo_jornada = 'mixta', horas_ordinarias = 8
 where nombre = 'Mañana';

update turnos set hora_inicio = '13:00', hora_fin = '21:00', cruza_medianoche = false,
                  tipo_jornada = 'mixta', horas_ordinarias = 8
 where nombre = 'Tarde';

update turnos set hora_inicio = '21:00', hora_fin = '05:00', cruza_medianoche = true,
                  tipo_jornada = 'nocturna', horas_ordinarias = 8
 where nombre = 'Noche';

insert into turnos (nombre, hora_inicio, hora_fin, cruza_medianoche, tipo_jornada, horas_ordinarias)
values ('Guardia 24h', '07:00', '07:00', true, 'nocturna', 24)
on conflict (nombre) do nothing;

-- regla de forma: un turno cruza la medianoche exactamente cuando su hora de fin es igual o menor
alter table turnos add constraint turnos_cruce_coherente
  check (cruza_medianoche = (hora_fin <= hora_inicio));

-- crear una programacion de turnos (semanal o quincenal) en estado 'borrador' y version 1

create function crear_programacion(
  p_tipo tipo_programacion,
  p_inicio date,
  p_fin date,
  p_usuario uuid
) returns uuid
language plpgsql as $$
declare
  nueva uuid;
begin
  insert into programaciones (tipo, fecha_inicio, fecha_fin)
  values (p_tipo, p_inicio, p_fin)
  returning id into nueva;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (
    p_usuario, 'crear', 'programaciones', nueva,
    jsonb_build_object('tipo', p_tipo, 'fecha_inicio', p_inicio, 'fecha_fin', p_fin)
  );

  return nueva;
end;
$$;

revoke execute on function crear_programacion(tipo_programacion, date, date, uuid)
  from public, anon, authenticated;

notify pgrst, 'reload schema';

-- guardar las celdas de la parrilla de una programacion

create function guardar_asignaciones(
  p_programacion uuid,
  p_asignaciones jsonb,
  p_usuario uuid
) returns int
language plpgsql as $$
declare
  prog programaciones%rowtype;
  guardadas int;
begin
  select * into prog from programaciones where id = p_programacion for update;
  if not found then
    raise exception 'La programacion no existe' using errcode = 'P0002';
  end if;
  if prog.estado <> 'borrador' then
    raise exception 'La programacion ya no es un borrador' using errcode = '55000';
  end if;

  if exists (
    select 1
    from jsonb_to_recordset(p_asignaciones)
      as x(colaborador_id uuid, fecha date, turno_id uuid, sucursal_id uuid)
    where x.fecha < prog.fecha_inicio or x.fecha > prog.fecha_fin
  ) then
    raise exception 'Hay fechas fuera del periodo de la programacion' using errcode = '23514';
  end if;

  if exists (
    select 1
    from jsonb_to_recordset(p_asignaciones)
      as x(colaborador_id uuid, fecha date, turno_id uuid, sucursal_id uuid)
    join turnos t on t.id = x.turno_id
    where not t.activo
  ) then
    raise exception 'Hay turnos desactivados' using errcode = '23514';
  end if;

  if exists (
    select 1
    from jsonb_to_recordset(p_asignaciones)
      as x(colaborador_id uuid, fecha date, turno_id uuid, sucursal_id uuid)
    group by x.colaborador_id, x.fecha
    having count(*) > 1
  ) then
    raise exception 'Hay celdas repetidas' using errcode = '23514';
  end if;

  insert into asignaciones_turno (programacion_id, colaborador_id, fecha, turno_id, sucursal_id)
  select p_programacion, x.colaborador_id, x.fecha, x.turno_id, x.sucursal_id
  from jsonb_to_recordset(p_asignaciones)
    as x(colaborador_id uuid, fecha date, turno_id uuid, sucursal_id uuid)
  on conflict (programacion_id, colaborador_id, fecha)
  do update set turno_id = excluded.turno_id, sucursal_id = excluded.sucursal_id;
  get diagnostics guardadas = row_count;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (
    p_usuario, 'guardar', 'asignaciones_turno', p_programacion,
    jsonb_build_object('celdas', guardadas)
  );

  return guardadas;
end;
$$;

revoke execute on function guardar_asignaciones(uuid, jsonb, uuid)
  from public, anon, authenticated;

notify pgrst, 'reload schema';

-- publicar una programacion y crear versiones nuevas

create function publicar_programacion(
  p_programacion uuid,
  p_motivo text,
  p_usuario uuid
) returns int
language plpgsql as $$
declare
  prog programaciones%rowtype;
  anterior uuid;
  motivo text := nullif(trim(coalesce(p_motivo, '')), '');
  cambios int := 0;
begin
  select * into prog from programaciones where id = p_programacion for update;
  if not found then
    raise exception 'La programacion no existe' using errcode = 'P0002';
  end if;
  if prog.estado <> 'borrador' then
    raise exception 'La programacion ya no es un borrador' using errcode = '55000';
  end if;
  if not exists (select 1 from asignaciones_turno where programacion_id = prog.id) then
    raise exception 'No hay turnos asignados para publicar' using errcode = '22023';
  end if;

  if prog.version > 1 then
    if motivo is null then
      raise exception 'Escribe el motivo del cambio' using errcode = '22023';
    end if;

    select id into anterior from programaciones
    where tipo = prog.tipo and fecha_inicio = prog.fecha_inicio
      and fecha_fin = prog.fecha_fin and version = prog.version - 1;

    insert into cambios_turno (asignacion_id, turno_anterior_id, turno_nuevo_id, motivo, autorizado_por)
    select nueva.id, vieja.turno_id, nueva.turno_id, motivo, p_usuario
    from asignaciones_turno nueva
    left join asignaciones_turno vieja
      on vieja.programacion_id = anterior
     and vieja.colaborador_id = nueva.colaborador_id
     and vieja.fecha = nueva.fecha
    where nueva.programacion_id = prog.id
      and (vieja.id is null or vieja.turno_id is distinct from nueva.turno_id);
    get diagnostics cambios = row_count;
  end if;

  update programaciones
  set estado = 'publicada', publicada_en = now(), publicada_por = p_usuario
  where id = prog.id;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (
    p_usuario, 'publicar', 'programaciones', prog.id,
    jsonb_build_object('version', prog.version, 'cambios', cambios, 'motivo', motivo)
  );

  return prog.version;
end;
$$;

create function crear_version_programacion(
  p_programacion uuid,
  p_usuario uuid
) returns uuid
language plpgsql as $$
declare
  origen programaciones%rowtype;
  nueva uuid;
begin
  select * into origen from programaciones where id = p_programacion for update;
  if not found then
    raise exception 'La programacion no existe' using errcode = 'P0002';
  end if;
  if origen.estado <> 'publicada' then
    raise exception 'Solo se puede crear una version desde una programacion publicada' using errcode = '55000';
  end if;

  insert into programaciones (tipo, fecha_inicio, fecha_fin, version)
  values (origen.tipo, origen.fecha_inicio, origen.fecha_fin, origen.version + 1)
  returning id into nueva;

  insert into asignaciones_turno (programacion_id, colaborador_id, fecha, turno_id, sucursal_id)
  select nueva, colaborador_id, fecha, turno_id, sucursal_id
  from asignaciones_turno
  where programacion_id = origen.id;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (
    p_usuario, 'crear_version', 'programaciones', nueva,
    jsonb_build_object('desde', origen.id, 'version', origen.version + 1)
  );

  return nueva;
end;
$$;

revoke execute on function publicar_programacion(uuid, text, uuid) from public, anon, authenticated;
revoke execute on function crear_version_programacion(uuid, uuid) from public, anon, authenticated;

notify pgrst, 'reload schema';

-- modalidad de trabajo y forma de pago de cada colaborador

create type modalidad_laboral as enum ('tiempo_completo', 'parcial_nocturno', 'guardia');
create type forma_pago as enum ('salario_fijo', 'por_hora', 'por_turno');

alter table colaboradores
  add column modalidad modalidad_laboral not null default 'tiempo_completo';

alter table colaborador_salarios
  add column forma_pago forma_pago not null default 'salario_fijo',
  add column tarifa numeric check (tarifa > 0),
  alter column salario_mensual drop not null,
  add constraint pago_coherente check (
    (forma_pago = 'salario_fijo' and salario_mensual is not null and tarifa is null)
    or (forma_pago in ('por_hora', 'por_turno') and tarifa is not null and salario_mensual is null)
  );

drop function crear_colaborador(text, text, text, text, uuid, uuid, date, numeric, uuid);

create function crear_colaborador(
  p_nombres text,
  p_apellidos text,
  p_dpi text,
  p_telefono text,
  p_puesto_id uuid,
  p_sucursal_id uuid,
  p_fecha_ingreso date,
  p_modalidad modalidad_laboral,
  p_forma_pago forma_pago,
  p_salario numeric,
  p_tarifa numeric,
  p_usuario uuid
) returns uuid
language plpgsql as $$
declare
  nuevo uuid;
begin
  insert into colaboradores (nombres, apellidos, dpi, telefono, puesto_id, sucursal_base_id, modalidad)
  values (p_nombres, p_apellidos, p_dpi, nullif(p_telefono, ''), p_puesto_id, p_sucursal_id, p_modalidad)
  returning id into nuevo;

  insert into periodos_laborales (colaborador_id, fecha_ingreso)
  values (nuevo, p_fecha_ingreso);

  insert into colaborador_salarios (colaborador_id, forma_pago, salario_mensual, tarifa, vigente_desde)
  values (nuevo, p_forma_pago, p_salario, p_tarifa, p_fecha_ingreso);

  -- en la bitacora no se guarda el dpi completo, solo sus ultimos 4 digitos
  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (
    p_usuario, 'crear', 'colaboradores', nuevo,
    jsonb_build_object(
      'dpi_ultimos4', right(p_dpi, 4), 'fecha_ingreso', p_fecha_ingreso,
      'modalidad', p_modalidad, 'forma_pago', p_forma_pago
    )
  );

  return nuevo;
end;
$$;

create function cambiar_condiciones_pago(
  p_colaborador uuid,
  p_modalidad modalidad_laboral,
  p_forma_pago forma_pago,
  p_salario numeric,
  p_tarifa numeric,
  p_desde date,
  p_usuario uuid
) returns void
language plpgsql as $$
declare
  actual colaborador_salarios%rowtype;
  modalidad_anterior modalidad_laboral;
begin
  select modalidad into modalidad_anterior from colaboradores where id = p_colaborador for update;
  if not found then
    raise exception 'El colaborador no existe' using errcode = 'P0002';
  end if;

  select * into actual from colaborador_salarios
  where colaborador_id = p_colaborador and vigente_hasta is null
  order by vigente_desde desc limit 1;

  if found then
    if p_desde <= actual.vigente_desde then
      raise exception 'La fecha debe ser posterior al inicio de las condiciones actuales (%)', actual.vigente_desde
        using errcode = '22023';
    end if;
    update colaborador_salarios set vigente_hasta = p_desde - 1 where id = actual.id;
  end if;

  insert into colaborador_salarios (colaborador_id, forma_pago, salario_mensual, tarifa, vigente_desde)
  values (p_colaborador, p_forma_pago, p_salario, p_tarifa, p_desde);

  update colaboradores set modalidad = p_modalidad where id = p_colaborador;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (
    p_usuario, 'cambiar_condiciones', 'colaboradores', p_colaborador,
    jsonb_build_object(
      'desde', p_desde,
      'modalidad_anterior', modalidad_anterior, 'modalidad_nueva', p_modalidad,
      'forma_pago_anterior', actual.forma_pago, 'forma_pago_nueva', p_forma_pago
    )
  );
end;
$$;

revoke execute on function crear_colaborador(text, text, text, text, uuid, uuid, date, modalidad_laboral, forma_pago, numeric, numeric, uuid)
  from public, anon, authenticated;
revoke execute on function cambiar_condiciones_pago(uuid, modalidad_laboral, forma_pago, numeric, numeric, date, uuid)
  from public, anon, authenticated;

notify pgrst, 'reload schema';

-- base del motor de jornadas parametros con vigencia y una jornada por colaborador y dia

create function parametro_en(
  p_clave text,
  p_fecha date,
  p_sucursal uuid default null,
  p_turno uuid default null
) returns numeric
language sql stable as $$
  select valor
  from parametros
  where clave = p_clave
    and vigente_desde <= p_fecha
    and (sucursal_id is null or sucursal_id = p_sucursal)
    and (turno_id is null or turno_id = p_turno)
  order by (turno_id is not null) desc, (sucursal_id is not null) desc, vigente_desde desc
  limit 1
$$;

revoke execute on function parametro_en(text, date, uuid, uuid) from public, anon, authenticated;

insert into parametros (clave, valor, vigente_desde)
values
  ('ventana_previa_minutos',     240, '2026-01-01'),  -- una marcacion hasta 4 h antes del inicio es de ese turno
  ('ventana_posterior_minutos',  240, '2026-01-01')  -- y hasta 4 h despues del fin
on conflict do nothing;

create unique index jornadas_colaborador_fecha on jornadas (colaborador_id, fecha);

notify pgrst, 'reload schema';

-- motor de jornadas cruza las marcaciones del reloj con los turnos programados y calcula

insert into parametros (clave, valor, vigente_desde)
values ('sesion_minima_minutos', 30, '2026-01-01')  -- una salida debe llegar al menos 30 min despues de la entrada
on conflict do nothing;

create function calcular_jornadas(
  p_desde date,
  p_hasta date,
  p_usuario uuid,
  p_ahora timestamptz default now()
) returns jsonb
language plpgsql as $$
declare
  n_jornadas int;
  n_sin_programacion int;
  n_ausencias int;
  n_extras int;
begin
  if p_hasta < p_desde then
    raise exception 'El rango de fechas no es valido' using errcode = '22023';
  end if;
  if p_hasta - p_desde > 62 then
    raise exception 'El rango no puede pasar de 62 dias' using errcode = '22023';
  end if;

  drop table if exists _asig, _marcas, _asignada, _calc, _huerfanas;

  -- 1
  create temp table _asig on commit drop as
  select a.id as asignacion_id, a.colaborador_id, a.fecha, a.sucursal_id, a.turno_id, t.nombre as turno,
         (a.fecha + t.hora_inicio) at time zone 'America/Guatemala' as inicio,
         ((a.fecha + t.hora_inicio) at time zone 'America/Guatemala')
           + make_interval(secs => (case when t.cruza_medianoche
                                         then extract(epoch from (t.hora_fin - t.hora_inicio)) + 86400
                                         else extract(epoch from (t.hora_fin - t.hora_inicio)) end)::double precision) as fin,
         coalesce(parametro_en('gracia_minutos', a.fecha, a.sucursal_id, a.turno_id), 10) as gracia,
         coalesce(parametro_en('ausencia_minutos', a.fecha, a.sucursal_id, a.turno_id), 60) as ausencia,
         coalesce(parametro_en('extra_minimo_minutos', a.fecha, a.sucursal_id, a.turno_id), 30) as extra_minimo,
         coalesce(parametro_en('sesion_minima_minutos', a.fecha, a.sucursal_id, a.turno_id), 30) as sesion_minima,
         coalesce(parametro_en('ventana_previa_minutos', a.fecha, a.sucursal_id, a.turno_id), 240) as previa,
         coalesce(parametro_en('ventana_posterior_minutos', a.fecha, a.sucursal_id, a.turno_id), 240) as posterior,
         (a.fecha between p_desde and p_hasta
            and not exists (select 1 from periodos_planilla pp
                            where pp.estado = 'cerrado' and a.fecha between pp.fecha_inicio and pp.fecha_fin)) as procesar,
         exists (select 1 from licencias l
                 where l.colaborador_id = a.colaborador_id and a.fecha between l.fecha_desde and l.fecha_hasta) as con_licencia
  from asignaciones_vigentes a
  join turnos t on t.id = a.turno_id
  where a.turno_id is not null
    and a.estado = 'programado'
    and a.fecha between p_desde - 1 and p_hasta + 1;

  -- 2
  create temp table _marcas on commit drop as
  select m.id, coalesce(m.colaborador_id, cd.colaborador_id) as colaborador_id, m.marcado_en, d.sucursal_id
  from marcaciones m
  left join colaborador_dispositivo cd
    on cd.dispositivo_id = m.dispositivo_id and cd.id_en_dispositivo = m.id_en_dispositivo
  left join dispositivos d on d.id = m.dispositivo_id
  where not m.es_duplicada
    and coalesce(m.colaborador_id, cd.colaborador_id) is not null
    and m.marcado_en >= ((p_desde - 2)::timestamp at time zone 'America/Guatemala')
    and m.marcado_en <  ((p_hasta + 4)::timestamp at time zone 'America/Guatemala');

  -- 3
  create temp table _asignada on commit drop as
  select distinct on (m.id)
         m.id as marca_id, m.colaborador_id, m.marcado_en, m.sucursal_id as sucursal_marca, a.asignacion_id
  from _marcas m
  join _asig a
    on a.colaborador_id = m.colaborador_id
   and m.marcado_en >= a.inicio - make_interval(mins => a.previa::int)
   and m.marcado_en <= a.fin + make_interval(mins => a.posterior::int)
  order by m.id,
           case when m.marcado_en between a.inicio and a.fin then 0
                else least(abs(extract(epoch from (m.marcado_en - a.inicio))),
                           abs(extract(epoch from (m.marcado_en - a.fin)))) end,
           a.inicio;

  -- 4
  create temp table _calc on commit drop as
  with ordenadas as (
    select x.*, row_number() over (partition by x.asignacion_id order by x.marcado_en, x.marca_id) as rn
    from _asignada x
  ),
  primeras as (
    select * from ordenadas where rn = 1
  ),
  salidas as (
    select distinct on (o.asignacion_id) o.asignacion_id, o.marca_id, o.marcado_en, o.sucursal_marca
    from ordenadas o
    join primeras p on p.asignacion_id = o.asignacion_id
    join _asig a on a.asignacion_id = o.asignacion_id
    where o.marcado_en >= p.marcado_en + make_interval(mins => a.sesion_minima::int)
    order by o.asignacion_id, o.marcado_en
  ),
  unidas as (
    select a.*, p.marca_id as primera_id, p.marcado_en as primera, p.sucursal_marca as primera_suc,
           s.marca_id as salida_id, s.marcado_en as salida_t, s.sucursal_marca as salida_suc,
           (s.marca_id is null and p.marcado_en > a.inicio + (a.fin - a.inicio) / 2) as solo_salida
    from _asig a
    join primeras p on p.asignacion_id = a.asignacion_id
    left join salidas s on s.asignacion_id = a.asignacion_id
  ),
  tiempos as (
    select u.*,
           case when u.solo_salida then null else u.primera_id end as e_id,
           case when u.solo_salida then null else u.primera end as e,
           case when u.solo_salida then u.primera_id else u.salida_id end as s_id,
           case when u.solo_salida then u.primera else u.salida_t end as s,
           case when u.solo_salida then u.primera_suc else u.salida_suc end as s_suc,
           case when u.solo_salida then null else u.primera_suc end as e_suc
    from unidas u
  )
  select t.asignacion_id, t.colaborador_id, t.fecha, t.sucursal_id, t.turno, t.inicio, t.fin, t.procesar,
         t.e_id, t.s_id,
         case when t.e is not null and t.e > t.inicio
              then floor(extract(epoch from (t.e - t.inicio)) / 60)::int else 0 end as min_tardanza,
         case when t.e is null then null
              when t.e <= t.inicio then 'puntual'::clasif_entrada
              when extract(epoch from (t.e - t.inicio)) <= t.gracia * 60 then 'dentro_gracia'::clasif_entrada
              else 'tardanza'::clasif_entrada end as clasif_entrada,
         case when t.s is null then null
              when t.s < t.fin - make_interval(mins => t.gracia::int) then 'anticipada'::clasif_salida
              else 'normal'::clasif_salida end as clasif_salida,
         case when t.e is not null and t.s is not null
              then floor(greatest(0, extract(epoch from (least(t.s, t.fin) - greatest(t.e, t.inicio)))) / 60)::int
              else 0 end as min_trabajados,
         case when t.s is not null and t.s < t.fin
              then floor(extract(epoch from (t.fin - t.s)) / 60)::int else 0 end as min_anticipada,
         case when t.s is not null and t.s > t.fin
                   and floor(extract(epoch from (t.s - t.fin)) / 60) >= t.extra_minimo
              then floor(extract(epoch from (t.s - t.fin)) / 60)::int else 0 end as min_extra,
         t.gracia,
         case
           when t.e is null or t.s is null then 'incompleta'::estado_jornada
           when (t.e_suc is not null and t.e_suc <> t.sucursal_id)
             or (t.s_suc is not null and t.s_suc <> t.sucursal_id)
             or t.e < t.inicio - interval '120 minutes'
             or t.e > t.inicio + (t.fin - t.inicio) / 2 then 'por_confirmar'::estado_jornada
           else 'ok'::estado_jornada
         end as estado,
         (t.fin + make_interval(mins => t.posterior::int) <= p_ahora) as cerrado
  from tiempos t;

  -- 5
  insert into jornadas (asignacion_id, colaborador_id, sucursal_id, fecha, marcacion_entrada_id, marcacion_salida_id,
                        minutos_trabajados, minutos_tardanza, minutos_faltantes, clasif_entrada, clasif_salida, estado)
  select c.asignacion_id, c.colaborador_id, c.sucursal_id, c.fecha, c.e_id, c.s_id,
         c.min_trabajados, c.min_tardanza,
         case when c.estado = 'incompleta' then 0
              else (case when c.clasif_entrada = 'tardanza' then c.min_tardanza else 0 end)
                 + (case when c.clasif_salida = 'anticipada' then c.min_anticipada else 0 end) end,
         c.clasif_entrada, c.clasif_salida, c.estado
  from _calc c
  where c.procesar and c.cerrado
  on conflict (colaborador_id, fecha) do update set
    asignacion_id = excluded.asignacion_id,
    sucursal_id = excluded.sucursal_id,
    marcacion_entrada_id = excluded.marcacion_entrada_id,
    marcacion_salida_id = excluded.marcacion_salida_id,
    minutos_trabajados = excluded.minutos_trabajados,
    minutos_tardanza = excluded.minutos_tardanza,
    minutos_faltantes = excluded.minutos_faltantes,
    clasif_entrada = excluded.clasif_entrada,
    clasif_salida = excluded.clasif_salida,
    estado = excluded.estado;
  get diagnostics n_jornadas = row_count;

  -- 6
  create temp table _huerfanas on commit drop as
  select distinct on (m.colaborador_id, (m.marcado_en at time zone 'America/Guatemala')::date)
         m.colaborador_id,
         (m.marcado_en at time zone 'America/Guatemala')::date as fecha,
         m.id as marca_id, m.marcado_en,
         coalesce(m.sucursal_id, c.sucursal_base_id) as sucursal_id
  from _marcas m
  join colaboradores c on c.id = m.colaborador_id
  where not exists (select 1 from _asignada x where x.marca_id = m.id)
    and (m.marcado_en at time zone 'America/Guatemala')::date between p_desde and p_hasta
    and not exists (select 1 from periodos_planilla pp
                    where pp.estado = 'cerrado'
                      and (m.marcado_en at time zone 'America/Guatemala')::date between pp.fecha_inicio and pp.fecha_fin)
  order by m.colaborador_id, (m.marcado_en at time zone 'America/Guatemala')::date, m.marcado_en;

  insert into jornadas (asignacion_id, colaborador_id, sucursal_id, fecha, marcacion_entrada_id, marcacion_salida_id,
                        minutos_trabajados, minutos_tardanza, minutos_faltantes, estado)
  select null, h.colaborador_id, h.sucursal_id, h.fecha, h.marca_id, s.id,
         coalesce(floor(extract(epoch from (s.marcado_en - h.marcado_en)) / 60)::int, 0), 0, 0, 'sin_programacion'
  from _huerfanas h
  left join lateral (
    select m2.id, m2.marcado_en
    from _marcas m2
    where m2.colaborador_id = h.colaborador_id
      and (m2.marcado_en at time zone 'America/Guatemala')::date = h.fecha
      and not exists (select 1 from _asignada x where x.marca_id = m2.id)
      and m2.marcado_en >= h.marcado_en + interval '30 minutes'
    order by m2.marcado_en
    limit 1
  ) s on true
  on conflict (colaborador_id, fecha) do nothing;
  get diagnostics n_sin_programacion = row_count;

  -- 7
  with retiradas as (
    delete from ausencias au
    using _asignada x
    where au.asignacion_id = x.asignacion_id and au.estado = 'sin_justificar'
    returning au.colaborador_id, au.fecha
  )
  update alertas al
  set estado = 'resuelta', resuelta_en = now()
  from retiradas r
  where al.tipo = 'ausencia' and al.estado = 'abierta'
    and al.colaborador_id = r.colaborador_id and al.fecha = r.fecha;

  insert into ausencias (asignacion_id, colaborador_id, fecha)
  select a.asignacion_id, a.colaborador_id, a.fecha
  from _asig a
  where a.procesar
    and not a.con_licencia
    and p_ahora >= a.inicio + make_interval(mins => a.ausencia::int)
    and not exists (select 1 from _asignada x where x.asignacion_id = a.asignacion_id)
  on conflict (asignacion_id) do nothing;
  get diagnostics n_ausencias = row_count;

  -- 8
  insert into horas_extra (jornada_id, minutos_detectados)
  select j.id, c.min_extra
  from _calc c
  join jornadas j on j.colaborador_id = c.colaborador_id and j.fecha = c.fecha
  where c.procesar and c.cerrado and c.min_extra > 0 and c.estado <> 'incompleta'
  on conflict (jornada_id) do update set minutos_detectados = excluded.minutos_detectados
    where horas_extra.estado = 'pendiente';
  get diagnostics n_extras = row_count;

  delete from horas_extra h
  using jornadas j, _calc c
  where h.jornada_id = j.id and j.colaborador_id = c.colaborador_id and j.fecha = c.fecha
    and c.procesar and c.cerrado and c.min_extra = 0 and h.estado = 'pendiente';

  -- 9
  insert into alertas (tipo, colaborador_id, fecha, detalle)
  select v.tipo, v.colaborador_id, v.fecha, v.detalle
  from (
    select case j.estado when 'por_confirmar' then 'por_confirmar'::tipo_alerta
                         when 'incompleta' then 'marcacion_faltante'::tipo_alerta
                         else 'sin_programacion'::tipo_alerta end as tipo,
           j.colaborador_id, j.fecha, jsonb_build_object('jornada_id', j.id) as detalle
    from jornadas j
    where j.fecha between p_desde and p_hasta and j.estado in ('por_confirmar', 'incompleta', 'sin_programacion')
    union all
    select 'ausencia'::tipo_alerta, au.colaborador_id, au.fecha, jsonb_build_object('ausencia_id', au.id)
    from ausencias au
    where au.fecha between p_desde and p_hasta and au.estado = 'sin_justificar'
  ) v
  where not exists (
    select 1 from alertas al
    where al.tipo = v.tipo and al.colaborador_id = v.colaborador_id and al.fecha = v.fecha and al.estado = 'abierta'
  );

  insert into bitacora (usuario_id, accion, tabla, detalle)
  values (
    p_usuario, 'calcular', 'jornadas',
    jsonb_build_object('desde', p_desde, 'hasta', p_hasta, 'jornadas', n_jornadas,
                       'sin_programacion', n_sin_programacion, 'ausencias', n_ausencias, 'horas_extra', n_extras)
  );

  return jsonb_build_object('jornadas', n_jornadas, 'sin_programacion', n_sin_programacion,
                            'ausencias', n_ausencias, 'horas_extra', n_extras);
end;
$$;

revoke execute on function calcular_jornadas(date, date, uuid, timestamptz) from public, anon, authenticated;

notify pgrst, 'reload schema';

-- decisiones de rr hh sobre horas extra y ausencias

create function resolver_horas_extra(
  p_horas_extra uuid,
  p_decision estado_horas_extra,
  p_minutos_pagados int,
  p_justificacion text,
  p_autorizado_por text,
  p_usuario uuid
) returns void
language plpgsql as $$
declare
  actual horas_extra%rowtype;
  dia date;
  pagados int;
  texto text := nullif(trim(coalesce(p_justificacion, '')), '');
begin
  select * into actual from horas_extra where id = p_horas_extra for update;
  if not found then
    raise exception 'El registro de horas extra no existe' using errcode = 'P0002';
  end if;

  select fecha into dia from jornadas where id = actual.jornada_id;
  if exists (select 1 from periodos_planilla where estado = 'cerrado' and dia between fecha_inicio and fecha_fin) then
    raise exception 'Esa quincena ya esta cerrada' using errcode = '55000';
  end if;

  if p_decision = 'pendiente' then
    raise exception 'Elige autorizar, autorizar parcial o rechazar' using errcode = '22023';
  end if;
  if texto is null then
    raise exception 'La justificacion es obligatoria' using errcode = '22023';
  end if;

  pagados := case p_decision
    when 'autorizada' then actual.minutos_detectados
    when 'rechazada' then 0
    else p_minutos_pagados
  end;
  if p_decision = 'parcial' and (pagados is null or pagados <= 0 or pagados >= actual.minutos_detectados) then
    raise exception 'En una autorizacion parcial las horas pagadas deben ser mayores que 0 y menores que las detectadas (% h)', actual.minutos_detectados / 60
      using errcode = '22023';
  end if;
  if p_decision = 'parcial' and pagados % 60 <> 0 then
    raise exception 'Solo se pueden pagar horas extra completas' using errcode = '22023';
  end if;

  update horas_extra
  set estado = p_decision,
      minutos_pagados = pagados,
      justificacion = texto,
      autorizado_por_nombre = nullif(trim(coalesce(p_autorizado_por, '')), ''),
      registrado_por = p_usuario,
      decidido_en = now()
  where id = p_horas_extra;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (
    p_usuario, 'decidir', 'horas_extra', p_horas_extra,
    jsonb_build_object(
      'detectados', actual.minutos_detectados,
      'estado_anterior', actual.estado, 'pagados_anterior', actual.minutos_pagados,
      'estado_nuevo', p_decision, 'pagados_nuevo', pagados,
      'autorizado_por', nullif(trim(coalesce(p_autorizado_por, '')), '')
    )
  );
end;
$$;

create function justificar_ausencia(
  p_ausencia uuid,
  p_tipo uuid,
  p_motivo text,
  p_usuario uuid
) returns void
language plpgsql as $$
declare
  actual ausencias%rowtype;
  tipo_nombre text;
  nuevo_estado estado_ausencia;
  texto text := nullif(trim(coalesce(p_motivo, '')), '');
begin
  select * into actual from ausencias where id = p_ausencia for update;
  if not found then
    raise exception 'La ausencia no existe' using errcode = 'P0002';
  end if;

  if exists (select 1 from periodos_planilla where estado = 'cerrado' and actual.fecha between fecha_inicio and fecha_fin) then
    raise exception 'Esa quincena ya esta cerrada' using errcode = '55000';
  end if;

  select nombre into tipo_nombre from tipos_ausencia where id = p_tipo;
  if not found then
    raise exception 'El tipo de ausencia no existe' using errcode = '23503';
  end if;
  if texto is null then
    raise exception 'El motivo es obligatorio' using errcode = '22023';
  end if;

  nuevo_estado := case when tipo_nombre = 'Falta injustificada' then 'reclasificada' else 'justificada' end;

  update ausencias set estado = nuevo_estado, tipo_ausencia_id = p_tipo where id = p_ausencia;

  insert into notas_asistencia (ausencia_id, texto, autor_id) values (p_ausencia, texto, p_usuario);

  update alertas
  set estado = 'resuelta', resuelta_por = p_usuario, resuelta_en = now()
  where tipo = 'ausencia' and estado = 'abierta'
    and colaborador_id = actual.colaborador_id and fecha = actual.fecha;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (
    p_usuario, 'justificar', 'ausencias', p_ausencia,
    jsonb_build_object('estado_anterior', actual.estado, 'estado_nuevo', nuevo_estado, 'tipo', tipo_nombre)
  );
end;
$$;

revoke execute on function resolver_horas_extra(uuid, estado_horas_extra, int, text, text, uuid)
  from public, anon, authenticated;
revoke execute on function justificar_ausencia(uuid, uuid, text, uuid)
  from public, anon, authenticated;

notify pgrst, 'reload schema';

-- correccion del motor de jornadas: respeta el tipo de marcacion del reloj

create or replace function calcular_jornadas(
  p_desde date,
  p_hasta date,
  p_usuario uuid,
  p_ahora timestamptz default now()
) returns jsonb
language plpgsql as $$
declare
  n_jornadas int;
  n_sin_programacion int;
  n_ausencias int;
  n_extras int;
begin
  if p_hasta < p_desde then
    raise exception 'El rango de fechas no es valido' using errcode = '22023';
  end if;
  if p_hasta - p_desde > 62 then
    raise exception 'El rango no puede pasar de 62 dias' using errcode = '22023';
  end if;

  drop table if exists _asig, _marcas, _asignada, _calc, _huerfanas;

  -- 1
  create temp table _asig on commit drop as
  select a.id as asignacion_id, a.colaborador_id, a.fecha, a.sucursal_id, a.turno_id, t.nombre as turno,
         (a.fecha + t.hora_inicio) at time zone 'America/Guatemala' as inicio,
         ((a.fecha + t.hora_inicio) at time zone 'America/Guatemala')
           + make_interval(secs => (case when t.cruza_medianoche
                                         then extract(epoch from (t.hora_fin - t.hora_inicio)) + 86400
                                         else extract(epoch from (t.hora_fin - t.hora_inicio)) end)::double precision) as fin,
         coalesce(parametro_en('gracia_minutos', a.fecha, a.sucursal_id, a.turno_id), 10) as gracia,
         coalesce(parametro_en('ausencia_minutos', a.fecha, a.sucursal_id, a.turno_id), 60) as ausencia,
         coalesce(parametro_en('extra_minimo_minutos', a.fecha, a.sucursal_id, a.turno_id), 30) as extra_minimo,
         coalesce(parametro_en('sesion_minima_minutos', a.fecha, a.sucursal_id, a.turno_id), 30) as sesion_minima,
         coalesce(parametro_en('ventana_previa_minutos', a.fecha, a.sucursal_id, a.turno_id), 240) as previa,
         coalesce(parametro_en('ventana_posterior_minutos', a.fecha, a.sucursal_id, a.turno_id), 240) as posterior,
         (a.fecha between p_desde and p_hasta
            and not exists (select 1 from periodos_planilla pp
                            where pp.estado = 'cerrado' and a.fecha between pp.fecha_inicio and pp.fecha_fin)) as procesar,
         exists (select 1 from licencias l
                 where l.colaborador_id = a.colaborador_id and a.fecha between l.fecha_desde and l.fecha_hasta) as con_licencia
  from asignaciones_vigentes a
  join turnos t on t.id = a.turno_id
  where a.turno_id is not null
    and a.estado = 'programado'
    and a.fecha between p_desde - 1 and p_hasta + 1;

  -- 2
  create temp table _marcas on commit drop as
  select m.id, coalesce(m.colaborador_id, cd.colaborador_id) as colaborador_id, m.marcado_en, m.tipo, d.sucursal_id
  from marcaciones m
  left join colaborador_dispositivo cd
    on cd.dispositivo_id = m.dispositivo_id and cd.id_en_dispositivo = m.id_en_dispositivo
  left join dispositivos d on d.id = m.dispositivo_id
  where not m.es_duplicada
    and coalesce(m.colaborador_id, cd.colaborador_id) is not null
    and m.marcado_en >= ((p_desde - 2)::timestamp at time zone 'America/Guatemala')
    and m.marcado_en <  ((p_hasta + 4)::timestamp at time zone 'America/Guatemala');

  -- 3
  create temp table _asignada on commit drop as
  select distinct on (m.id)
         m.id as marca_id, m.colaborador_id, m.marcado_en, m.tipo, m.sucursal_id as sucursal_marca, a.asignacion_id
  from _marcas m
  join _asig a
    on a.colaborador_id = m.colaborador_id
   and m.marcado_en >= a.inicio - make_interval(mins => a.previa::int)
   and m.marcado_en <= a.fin + make_interval(mins => a.posterior::int)
  order by m.id,
           case when m.marcado_en between a.inicio and a.fin then 0
                else least(abs(extract(epoch from (m.marcado_en - a.inicio))),
                           abs(extract(epoch from (m.marcado_en - a.fin)))) end,
           a.inicio;

  -- 4
  create temp table _calc on commit drop as
  with ordenadas as (
    select x.*, row_number() over (partition by x.asignacion_id order by x.marcado_en, x.marca_id) as rn
    from _asignada x
  ),
  primeras as (
    select * from ordenadas where rn = 1
  ),
  salidas as (
    select distinct on (o.asignacion_id) o.asignacion_id, o.marca_id, o.marcado_en, o.sucursal_marca
    from ordenadas o
    join primeras p on p.asignacion_id = o.asignacion_id
    join _asig a on a.asignacion_id = o.asignacion_id
    where o.marcado_en >= p.marcado_en + make_interval(mins => a.sesion_minima::int)
    order by o.asignacion_id, o.marcado_en
  ),
  unidas as (
    select a.*, p.marca_id as primera_id, p.marcado_en as primera, p.sucursal_marca as primera_suc,
           s.marca_id as salida_id, s.marcado_en as salida_t, s.sucursal_marca as salida_suc,
           (s.marca_id is null and (p.tipo = 'salida' or p.marcado_en > a.inicio + (a.fin - a.inicio) / 2)) as solo_salida
    from _asig a
    join primeras p on p.asignacion_id = a.asignacion_id
    left join salidas s on s.asignacion_id = a.asignacion_id
  ),
  tiempos as (
    select u.*,
           case when u.solo_salida then null else u.primera_id end as e_id,
           case when u.solo_salida then null else u.primera end as e,
           case when u.solo_salida then u.primera_id else u.salida_id end as s_id,
           case when u.solo_salida then u.primera else u.salida_t end as s,
           case when u.solo_salida then u.primera_suc else u.salida_suc end as s_suc,
           case when u.solo_salida then null else u.primera_suc end as e_suc
    from unidas u
  )
  select t.asignacion_id, t.colaborador_id, t.fecha, t.sucursal_id, t.turno, t.inicio, t.fin, t.procesar,
         t.e_id, t.s_id,
         case when t.e is not null and t.e > t.inicio
              then floor(extract(epoch from (t.e - t.inicio)) / 60)::int else 0 end as min_tardanza,
         case when t.e is null then null
              when t.e <= t.inicio then 'puntual'::clasif_entrada
              when extract(epoch from (t.e - t.inicio)) <= t.gracia * 60 then 'dentro_gracia'::clasif_entrada
              else 'tardanza'::clasif_entrada end as clasif_entrada,
         case when t.s is null then null
              when t.s < t.fin - make_interval(mins => t.gracia::int) then 'anticipada'::clasif_salida
              else 'normal'::clasif_salida end as clasif_salida,
         case when t.e is not null and t.s is not null
              then floor(greatest(0, extract(epoch from (least(t.s, t.fin) - greatest(t.e, t.inicio)))) / 60)::int
              else 0 end as min_trabajados,
         case when t.s is not null and t.s < t.fin
              then floor(extract(epoch from (t.fin - t.s)) / 60)::int else 0 end as min_anticipada,
         case when t.s is not null and t.s > t.fin
                   and floor(extract(epoch from (t.s - t.fin)) / 60) >= t.extra_minimo
              then floor(extract(epoch from (t.s - t.fin)) / 60)::int else 0 end as min_extra,
         t.gracia,
         case
           when t.e is null or t.s is null then 'incompleta'::estado_jornada
           when (t.e_suc is not null and t.e_suc <> t.sucursal_id)
             or (t.s_suc is not null and t.s_suc <> t.sucursal_id)
             or t.e < t.inicio - interval '120 minutes'
             or t.e > t.inicio + (t.fin - t.inicio) / 2 then 'por_confirmar'::estado_jornada
           else 'ok'::estado_jornada
         end as estado,
         (t.fin + make_interval(mins => t.posterior::int) <= p_ahora) as cerrado
  from tiempos t;

  -- 5
  insert into jornadas (asignacion_id, colaborador_id, sucursal_id, fecha, marcacion_entrada_id, marcacion_salida_id,
                        minutos_trabajados, minutos_tardanza, minutos_faltantes, clasif_entrada, clasif_salida, estado)
  select c.asignacion_id, c.colaborador_id, c.sucursal_id, c.fecha, c.e_id, c.s_id,
         c.min_trabajados, c.min_tardanza,
         case when c.estado = 'incompleta' then 0
              else (case when c.clasif_entrada = 'tardanza' then c.min_tardanza else 0 end)
                 + (case when c.clasif_salida = 'anticipada' then c.min_anticipada else 0 end) end,
         c.clasif_entrada, c.clasif_salida, c.estado
  from _calc c
  where c.procesar and c.cerrado
  on conflict (colaborador_id, fecha) do update set
    asignacion_id = excluded.asignacion_id,
    sucursal_id = excluded.sucursal_id,
    marcacion_entrada_id = excluded.marcacion_entrada_id,
    marcacion_salida_id = excluded.marcacion_salida_id,
    minutos_trabajados = excluded.minutos_trabajados,
    minutos_tardanza = excluded.minutos_tardanza,
    minutos_faltantes = excluded.minutos_faltantes,
    clasif_entrada = excluded.clasif_entrada,
    clasif_salida = excluded.clasif_salida,
    estado = excluded.estado;
  get diagnostics n_jornadas = row_count;

  -- 6
  create temp table _huerfanas on commit drop as
  select distinct on (m.colaborador_id, (m.marcado_en at time zone 'America/Guatemala')::date)
         m.colaborador_id,
         (m.marcado_en at time zone 'America/Guatemala')::date as fecha,
         m.id as marca_id, m.marcado_en, m.tipo,
         coalesce(m.sucursal_id, c.sucursal_base_id) as sucursal_id
  from _marcas m
  join colaboradores c on c.id = m.colaborador_id
  where not exists (select 1 from _asignada x where x.marca_id = m.id)
    and (m.marcado_en at time zone 'America/Guatemala')::date between p_desde and p_hasta
    and not exists (select 1 from periodos_planilla pp
                    where pp.estado = 'cerrado'
                      and (m.marcado_en at time zone 'America/Guatemala')::date between pp.fecha_inicio and pp.fecha_fin)
  order by m.colaborador_id, (m.marcado_en at time zone 'America/Guatemala')::date, m.marcado_en;

  insert into jornadas (asignacion_id, colaborador_id, sucursal_id, fecha, marcacion_entrada_id, marcacion_salida_id,
                        minutos_trabajados, minutos_tardanza, minutos_faltantes, estado)
  select null, h.colaborador_id, h.sucursal_id, h.fecha,
         case when h.tipo = 'salida' then null else h.marca_id end,
         case when h.tipo = 'salida' then h.marca_id else s.id end,
         case when h.tipo = 'salida' then 0
              else coalesce(floor(extract(epoch from (s.marcado_en - h.marcado_en)) / 60)::int, 0) end,
         0, 0, 'sin_programacion'
  from _huerfanas h
  left join lateral (
    select m2.id, m2.marcado_en
    from _marcas m2
    where m2.colaborador_id = h.colaborador_id
      and (m2.marcado_en at time zone 'America/Guatemala')::date = h.fecha
      and not exists (select 1 from _asignada x where x.marca_id = m2.id)
      and m2.marcado_en >= h.marcado_en + interval '30 minutes'
    order by m2.marcado_en
    limit 1
  ) s on true
  on conflict (colaborador_id, fecha) do update set
    sucursal_id = excluded.sucursal_id,
    marcacion_entrada_id = excluded.marcacion_entrada_id,
    marcacion_salida_id = excluded.marcacion_salida_id,
    minutos_trabajados = excluded.minutos_trabajados
    where jornadas.asignacion_id is null and jornadas.estado = 'sin_programacion';
  get diagnostics n_sin_programacion = row_count;

  -- 7
  with retiradas as (
    delete from ausencias au
    using _asignada x
    where au.asignacion_id = x.asignacion_id and au.estado = 'sin_justificar'
    returning au.colaborador_id, au.fecha
  )
  update alertas al
  set estado = 'resuelta', resuelta_en = now()
  from retiradas r
  where al.tipo = 'ausencia' and al.estado = 'abierta'
    and al.colaborador_id = r.colaborador_id and al.fecha = r.fecha;

  insert into ausencias (asignacion_id, colaborador_id, fecha)
  select a.asignacion_id, a.colaborador_id, a.fecha
  from _asig a
  where a.procesar
    and not a.con_licencia
    and p_ahora >= a.inicio + make_interval(mins => a.ausencia::int)
    and not exists (select 1 from _asignada x where x.asignacion_id = a.asignacion_id)
  on conflict (asignacion_id) do nothing;
  get diagnostics n_ausencias = row_count;

  -- 8
  insert into horas_extra (jornada_id, minutos_detectados)
  select j.id, c.min_extra
  from _calc c
  join jornadas j on j.colaborador_id = c.colaborador_id and j.fecha = c.fecha
  where c.procesar and c.cerrado and c.min_extra > 0 and c.estado <> 'incompleta'
  on conflict (jornada_id) do update set minutos_detectados = excluded.minutos_detectados
    where horas_extra.estado = 'pendiente';
  get diagnostics n_extras = row_count;

  delete from horas_extra h
  using jornadas j, _calc c
  where h.jornada_id = j.id and j.colaborador_id = c.colaborador_id and j.fecha = c.fecha
    and c.procesar and c.cerrado and c.min_extra = 0 and h.estado = 'pendiente';

  -- 9
  insert into alertas (tipo, colaborador_id, fecha, detalle)
  select v.tipo, v.colaborador_id, v.fecha, v.detalle
  from (
    select case j.estado when 'por_confirmar' then 'por_confirmar'::tipo_alerta
                         when 'incompleta' then 'marcacion_faltante'::tipo_alerta
                         else 'sin_programacion'::tipo_alerta end as tipo,
           j.colaborador_id, j.fecha, jsonb_build_object('jornada_id', j.id) as detalle
    from jornadas j
    where j.fecha between p_desde and p_hasta and j.estado in ('por_confirmar', 'incompleta', 'sin_programacion')
    union all
    select 'ausencia'::tipo_alerta, au.colaborador_id, au.fecha, jsonb_build_object('ausencia_id', au.id)
    from ausencias au
    where au.fecha between p_desde and p_hasta and au.estado = 'sin_justificar'
  ) v
  where not exists (
    select 1 from alertas al
    where al.tipo = v.tipo and al.colaborador_id = v.colaborador_id and al.fecha = v.fecha and al.estado = 'abierta'
  );

  insert into bitacora (usuario_id, accion, tabla, detalle)
  values (
    p_usuario, 'calcular', 'jornadas',
    jsonb_build_object('desde', p_desde, 'hasta', p_hasta, 'jornadas', n_jornadas,
                       'sin_programacion', n_sin_programacion, 'ausencias', n_ausencias, 'horas_extra', n_extras)
  );

  return jsonb_build_object('jornadas', n_jornadas, 'sin_programacion', n_sin_programacion,
                            'ausencias', n_ausencias, 'horas_extra', n_extras);
end;
$$;

revoke execute on function calcular_jornadas(date, date, uuid, timestamptz) from public, anon, authenticated;

notify pgrst, 'reload schema';

-- puestos y turnos administrables desde el sistema

-- puestos
create function crear_puesto(p_nombre text, p_usuario uuid) returns uuid
language plpgsql as $$
declare
  v_nombre text := nullif(trim(coalesce(p_nombre, '')), '');
  nuevo uuid;
begin
  if v_nombre is null then
    raise exception 'El nombre del puesto es obligatorio' using errcode = '22023';
  end if;
  if exists (select 1 from puestos where lower(puestos.nombre) = lower(v_nombre)) then
    raise exception 'Ya existe un puesto con ese nombre' using errcode = '23505';
  end if;

  insert into puestos (nombre) values (v_nombre) returning id into nuevo;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'crear', 'puestos', nuevo, jsonb_build_object('nombre', v_nombre));
  return nuevo;
end;
$$;

create function renombrar_puesto(p_id uuid, p_nombre text, p_usuario uuid) returns void
language plpgsql as $$
declare
  v_nombre text := nullif(trim(coalesce(p_nombre, '')), '');
  anterior text;
begin
  select puestos.nombre into anterior from puestos where id = p_id for update;
  if not found then
    raise exception 'El puesto no existe' using errcode = 'P0002';
  end if;
  if v_nombre is null then
    raise exception 'El nombre del puesto es obligatorio' using errcode = '22023';
  end if;
  if exists (select 1 from puestos where lower(puestos.nombre) = lower(v_nombre) and id <> p_id) then
    raise exception 'Ya existe un puesto con ese nombre' using errcode = '23505';
  end if;

  update puestos set nombre = v_nombre where id = p_id;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'renombrar', 'puestos', p_id, jsonb_build_object('antes', anterior, 'despues', v_nombre));
end;
$$;

create function eliminar_puesto(p_id uuid, p_usuario uuid) returns void
language plpgsql as $$
declare
  anterior text;
  en_uso int;
begin
  select puestos.nombre into anterior from puestos where id = p_id for update;
  if not found then
    raise exception 'El puesto no existe' using errcode = 'P0002';
  end if;

  select count(*) into en_uso from colaboradores where puesto_id = p_id;
  if en_uso > 0 then
    raise exception 'No se puede eliminar: % colaborador(es) tienen este puesto', en_uso using errcode = '23503';
  end if;

  delete from puestos where id = p_id;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'eliminar', 'puestos', p_id, jsonb_build_object('nombre', anterior));
end;
$$;

-- turnos
create function validar_turno(
  p_nombre text, p_inicio time, p_fin time, p_horas numeric
) returns void
language plpgsql as $$
declare
  ventana numeric;
begin
  if nullif(trim(coalesce(p_nombre, '')), '') is null then
    raise exception 'El nombre del turno es obligatorio' using errcode = '22023';
  end if;
  if p_inicio is null or p_fin is null then
    raise exception 'Indica la hora de inicio y la de fin' using errcode = '22023';
  end if;
  if p_horas is null or p_horas <= 0 or p_horas > 24 then
    raise exception 'Las horas ordinarias deben estar entre 0 y 24' using errcode = '22023';
  end if;

  ventana := case when p_fin <= p_inicio
                  then extract(epoch from (p_fin - p_inicio)) / 3600 + 24
                  else extract(epoch from (p_fin - p_inicio)) / 3600 end;
  if p_horas > ventana then
    raise exception 'Las horas ordinarias (%) no pueden ser mas que la duracion del horario (% h)', p_horas, ventana
      using errcode = '22023';
  end if;
end;
$$;

create function crear_turno(
  p_nombre text, p_inicio time, p_fin time, p_tipo tipo_jornada, p_horas numeric, p_usuario uuid
) returns uuid
language plpgsql as $$
declare
  v_nombre text := trim(coalesce(p_nombre, ''));
  nuevo uuid;
begin
  perform validar_turno(p_nombre, p_inicio, p_fin, p_horas);
  if exists (select 1 from turnos where lower(turnos.nombre) = lower(v_nombre)) then
    raise exception 'Ya existe un turno con ese nombre' using errcode = '23505';
  end if;

  insert into turnos (nombre, hora_inicio, hora_fin, cruza_medianoche, tipo_jornada, horas_ordinarias)
  values (v_nombre, p_inicio, p_fin, p_fin <= p_inicio, p_tipo, p_horas)
  returning id into nuevo;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'crear', 'turnos', nuevo,
          jsonb_build_object('nombre', v_nombre, 'inicio', p_inicio, 'fin', p_fin, 'tipo', p_tipo, 'horas_ordinarias', p_horas));
  return nuevo;
end;
$$;

create function editar_turno(
  p_id uuid, p_nombre text, p_inicio time, p_fin time, p_tipo tipo_jornada, p_horas numeric, p_usuario uuid
) returns void
language plpgsql as $$
declare
  actual turnos%rowtype;
  v_nombre text := trim(coalesce(p_nombre, ''));
begin
  select * into actual from turnos where id = p_id for update;
  if not found then
    raise exception 'El turno no existe' using errcode = 'P0002';
  end if;
  if exists (select 1 from asignaciones_turno where turno_id = p_id) then
    raise exception 'Este turno ya se uso en una programacion y no se puede editar: crea uno nuevo y desactiva este'
      using errcode = '55000';
  end if;

  perform validar_turno(p_nombre, p_inicio, p_fin, p_horas);
  if exists (select 1 from turnos where lower(turnos.nombre) = lower(v_nombre) and id <> p_id) then
    raise exception 'Ya existe un turno con ese nombre' using errcode = '23505';
  end if;

  update turnos
  set nombre = v_nombre, hora_inicio = p_inicio, hora_fin = p_fin,
      cruza_medianoche = p_fin <= p_inicio, tipo_jornada = p_tipo, horas_ordinarias = p_horas
  where id = p_id;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'editar', 'turnos', p_id,
          jsonb_build_object('antes', to_jsonb(actual),
                             'despues', jsonb_build_object('nombre', v_nombre, 'inicio', p_inicio, 'fin', p_fin,
                                                           'tipo', p_tipo, 'horas_ordinarias', p_horas)));
end;
$$;

create function cambiar_estado_turno(p_id uuid, p_activo boolean, p_usuario uuid) returns void
language plpgsql as $$
begin
  update turnos set activo = p_activo where id = p_id;
  if not found then
    raise exception 'El turno no existe' using errcode = 'P0002';
  end if;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, case when p_activo then 'activar' else 'desactivar' end, 'turnos', p_id, null);
end;
$$;

create function eliminar_turno(p_id uuid, p_usuario uuid) returns void
language plpgsql as $$
declare
  anterior text;
begin
  select turnos.nombre into anterior from turnos where id = p_id for update;
  if not found then
    raise exception 'El turno no existe' using errcode = 'P0002';
  end if;
  if exists (select 1 from asignaciones_turno where turno_id = p_id)
     or exists (select 1 from parametros where turno_id = p_id) then
    raise exception 'Este turno ya se uso y no se puede eliminar: desactivalo'
      using errcode = '55000';
  end if;

  delete from turnos where id = p_id;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'eliminar', 'turnos', p_id, jsonb_build_object('nombre', anterior));
end;
$$;

revoke execute on function crear_puesto(text, uuid) from public, anon, authenticated;
revoke execute on function renombrar_puesto(uuid, text, uuid) from public, anon, authenticated;
revoke execute on function eliminar_puesto(uuid, uuid) from public, anon, authenticated;
revoke execute on function validar_turno(text, time, time, numeric) from public, anon, authenticated;
revoke execute on function crear_turno(text, time, time, tipo_jornada, numeric, uuid) from public, anon, authenticated;
revoke execute on function editar_turno(uuid, text, time, time, tipo_jornada, numeric, uuid) from public, anon, authenticated;
revoke execute on function cambiar_estado_turno(uuid, boolean, uuid) from public, anon, authenticated;
revoke execute on function eliminar_turno(uuid, uuid) from public, anon, authenticated;

notify pgrst, 'reload schema';

-- descuentos por tardanza y salida anticipada, planilla)

create type estado_descuento as enum ('pendiente', 'aplicado', 'parcial', 'no_aplicado');

create table descuentos_tiempo (
  id uuid primary key default gen_random_uuid(),
  colaborador_id uuid not null references colaboradores(id),
  fecha_inicio date not null,
  fecha_fin date not null,
  minutos_detectados int not null check (minutos_detectados > 0),
  estado estado_descuento not null default 'pendiente',
  minutos_descontados int check (minutos_descontados is null or minutos_descontados >= 0),
  justificacion text,
  autorizado_por_nombre text,
  decidido_por uuid references profiles(id),
  decidido_en timestamptz,
  check (fecha_fin >= fecha_inicio),
  check (minutos_descontados is null or minutos_descontados <= minutos_detectados),
  check (estado = 'pendiente' or (nullif(trim(justificacion), '') is not null and minutos_descontados is not null)),
  unique (colaborador_id, fecha_inicio, fecha_fin)
);

alter table descuentos_tiempo enable row level security;
create policy lectura_rrhh_jefe on descuentos_tiempo
  for select to authenticated using (rol_actual() in ('rrhh', 'jefe'));
revoke insert, update, delete on descuentos_tiempo from anon, authenticated;

create function preparar_descuentos(p_inicio date, p_fin date, p_usuario uuid) returns int
language plpgsql as $$
declare
  n int;
begin
  if p_fin < p_inicio or p_fin - p_inicio > 31 then
    raise exception 'El periodo debe ser de 1 a 32 dias' using errcode = '22023';
  end if;
  if exists (select 1 from periodos_planilla
             where estado = 'cerrado' and fecha_inicio <= p_fin and fecha_fin >= p_inicio) then
    raise exception 'Esa quincena ya esta cerrada' using errcode = '55000';
  end if;

  create temp table _minutos on commit drop as
  -- los minutos se acumulan en la quincena y solo cuentan las horas completas
  select j.colaborador_id, (sum(j.minutos_faltantes) / 60 * 60)::int as minutos
  from jornadas j
  where j.fecha between p_inicio and p_fin
    and j.estado = 'ok'
    and j.minutos_faltantes > 0
  group by j.colaborador_id
  having sum(j.minutos_faltantes) >= 60;

  insert into descuentos_tiempo (colaborador_id, fecha_inicio, fecha_fin, minutos_detectados)
  select colaborador_id, p_inicio, p_fin, minutos from _minutos
  on conflict (colaborador_id, fecha_inicio, fecha_fin) do update set
    minutos_detectados = excluded.minutos_detectados,
    estado = case when descuentos_tiempo.minutos_detectados <> excluded.minutos_detectados
                  then 'pendiente'::estado_descuento else descuentos_tiempo.estado end,
    minutos_descontados = case when descuentos_tiempo.minutos_detectados <> excluded.minutos_detectados
                               then null else descuentos_tiempo.minutos_descontados end,
    justificacion = case when descuentos_tiempo.minutos_detectados <> excluded.minutos_detectados
                         then null else descuentos_tiempo.justificacion end,
    autorizado_por_nombre = case when descuentos_tiempo.minutos_detectados <> excluded.minutos_detectados
                                 then null else descuentos_tiempo.autorizado_por_nombre end,
    decidido_por = case when descuentos_tiempo.minutos_detectados <> excluded.minutos_detectados
                        then null else descuentos_tiempo.decidido_por end,
    decidido_en = case when descuentos_tiempo.minutos_detectados <> excluded.minutos_detectados
                       then null else descuentos_tiempo.decidido_en end;
  get diagnostics n = row_count;

  delete from descuentos_tiempo d
  where d.fecha_inicio = p_inicio and d.fecha_fin = p_fin
    and not exists (select 1 from _minutos m where m.colaborador_id = d.colaborador_id);

  insert into bitacora (usuario_id, accion, tabla, detalle)
  values (p_usuario, 'preparar', 'descuentos_tiempo',
          jsonb_build_object('inicio', p_inicio, 'fin', p_fin, 'personas', n));
  return n;
end;
$$;

create function resolver_descuento(
  p_id uuid,
  p_decision estado_descuento,
  p_minutos int,
  p_justificacion text,
  p_autorizado_por text,
  p_usuario uuid
) returns void
language plpgsql as $$
declare
  actual descuentos_tiempo%rowtype;
  texto text := nullif(trim(coalesce(p_justificacion, '')), '');
  descontados int;
begin
  select * into actual from descuentos_tiempo where id = p_id for update;
  if not found then
    raise exception 'El descuento no existe' using errcode = 'P0002';
  end if;
  if exists (select 1 from periodos_planilla
             where estado = 'cerrado' and fecha_inicio <= actual.fecha_fin and fecha_fin >= actual.fecha_inicio) then
    raise exception 'Esa quincena ya esta cerrada' using errcode = '55000';
  end if;
  if p_decision = 'pendiente' then
    raise exception 'Elige descontar, descontar una parte o no descontar' using errcode = '22023';
  end if;
  if texto is null then
    raise exception 'La justificacion es obligatoria' using errcode = '22023';
  end if;

  descontados := case p_decision
    when 'aplicado' then actual.minutos_detectados
    when 'no_aplicado' then 0
    else p_minutos
  end;
  if p_decision = 'parcial' and (descontados is null or descontados <= 0 or descontados >= actual.minutos_detectados) then
    raise exception 'En un descuento parcial las horas deben ser mayores que 0 y menores que las detectadas (% h)', actual.minutos_detectados / 60
      using errcode = '22023';
  end if;
  if p_decision = 'parcial' and descontados % 60 <> 0 then
    raise exception 'Solo se pueden descontar horas completas' using errcode = '22023';
  end if;

  update descuentos_tiempo
  set estado = p_decision, minutos_descontados = descontados, justificacion = texto,
      autorizado_por_nombre = nullif(trim(coalesce(p_autorizado_por, '')), ''),
      decidido_por = p_usuario, decidido_en = now()
  where id = p_id;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'decidir', 'descuentos_tiempo', p_id,
          jsonb_build_object('detectados', actual.minutos_detectados,
                             'estado_anterior', actual.estado, 'descontados_anterior', actual.minutos_descontados,
                             'estado_nuevo', p_decision, 'descontados_nuevo', descontados));
end;
$$;

revoke execute on function preparar_descuentos(date, date, uuid) from public, anon, authenticated;
revoke execute on function resolver_descuento(uuid, estado_descuento, int, text, text, uuid) from public, anon, authenticated;

notify pgrst, 'reload schema';

-- resolver jornadas "incompletas" y "por confirmar"

alter table jornadas
  add column confirmada_por uuid references profiles(id),
  add column confirmada_en timestamptz,
  add column motivo_confirmacion text;

create function conservar_confirmacion() returns trigger
language plpgsql as $$
begin
  if old.confirmada_en is not null then
    if new.marcacion_entrada_id is not distinct from old.marcacion_entrada_id
       and new.marcacion_salida_id is not distinct from old.marcacion_salida_id then
      new.confirmada_por := old.confirmada_por;
      new.confirmada_en := old.confirmada_en;
      new.motivo_confirmacion := old.motivo_confirmacion;
      if new.estado = 'por_confirmar' then
        new.estado := 'ok';
      end if;
    else
      new.confirmada_por := null;
      new.confirmada_en := null;
      new.motivo_confirmacion := null;
    end if;
  end if;
  return new;
end;
$$;

create trigger jornadas_conservan_confirmacion
  before update on jornadas
  for each row execute function conservar_confirmacion();

create function agregar_marcacion_manual(
  p_colaborador uuid,
  p_momento timestamptz,
  p_tipo tipo_marcacion,
  p_motivo text,
  p_usuario uuid
) returns uuid
language plpgsql as $$
declare
  texto text := nullif(trim(coalesce(p_motivo, '')), '');
  dia date := (p_momento at time zone 'America/Guatemala')::date;
  nueva uuid;
begin
  if not exists (select 1 from colaboradores where id = p_colaborador) then
    raise exception 'El colaborador no existe' using errcode = 'P0002';
  end if;
  if texto is null then
    raise exception 'El motivo es obligatorio' using errcode = '22023';
  end if;
  if p_tipo not in ('entrada', 'salida') then
    raise exception 'Indica si es una entrada o una salida' using errcode = '22023';
  end if;
  if p_momento > now() then
    raise exception 'La marcacion no puede ser futura' using errcode = '22023';
  end if;
  if exists (select 1 from periodos_planilla
             where estado = 'cerrado' and dia between fecha_inicio and fecha_fin) then
    raise exception 'Esa quincena ya esta cerrada' using errcode = '55000';
  end if;

  insert into marcaciones (colaborador_id, marcado_en, tipo, origen)
  values (p_colaborador, p_momento, p_tipo, 'manual')
  returning id into nueva;

  insert into correcciones_marcacion (marcacion_nueva_id, motivo, corregido_por)
  values (nueva, texto, p_usuario);

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'agregar_marcacion', 'marcaciones', nueva,
          jsonb_build_object('colaborador_id', p_colaborador, 'momento', p_momento, 'tipo', p_tipo, 'motivo', texto));

  perform calcular_jornadas(dia - 1, dia + 1, p_usuario);

  update alertas al
  set estado = 'resuelta', resuelta_por = p_usuario, resuelta_en = now()
  where al.colaborador_id = p_colaborador and al.estado = 'abierta'
    and al.tipo in ('marcacion_faltante', 'por_confirmar')
    and al.fecha between dia - 1 and dia + 1
    and not exists (select 1 from jornadas j
                    where j.colaborador_id = al.colaborador_id and j.fecha = al.fecha
                      and j.estado in ('incompleta', 'por_confirmar'));

  return nueva;
end;
$$;

create function confirmar_jornada(p_jornada uuid, p_motivo text, p_usuario uuid) returns void
language plpgsql as $$
declare
  actual jornadas%rowtype;
  texto text := nullif(trim(coalesce(p_motivo, '')), '');
begin
  select * into actual from jornadas where id = p_jornada for update;
  if not found then
    raise exception 'La jornada no existe' using errcode = 'P0002';
  end if;
  if exists (select 1 from periodos_planilla
             where estado = 'cerrado' and actual.fecha between fecha_inicio and fecha_fin) then
    raise exception 'Esa quincena ya esta cerrada' using errcode = '55000';
  end if;
  if actual.estado <> 'por_confirmar' then
    raise exception 'Solo se pueden confirmar jornadas por confirmar' using errcode = '22023';
  end if;
  if texto is null then
    raise exception 'El motivo es obligatorio' using errcode = '22023';
  end if;

  update jornadas
  set estado = 'ok', confirmada_por = p_usuario, confirmada_en = now(), motivo_confirmacion = texto
  where id = p_jornada;

  update alertas
  set estado = 'resuelta', resuelta_por = p_usuario, resuelta_en = now()
  where tipo = 'por_confirmar' and estado = 'abierta'
    and colaborador_id = actual.colaborador_id and fecha = actual.fecha;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'confirmar', 'jornadas', p_jornada, jsonb_build_object('motivo', texto));
end;
$$;

revoke execute on function agregar_marcacion_manual(uuid, timestamptz, tipo_marcacion, text, uuid)
  from public, anon, authenticated;
revoke execute on function confirmar_jornada(uuid, text, uuid) from public, anon, authenticated;
revoke execute on function conservar_confirmacion() from public, anon, authenticated;

notify pgrst, 'reload schema';

-- correccion del motor de jornadas: salir un rato y volver no es salida anticipada

create or replace function calcular_jornadas(
  p_desde date,
  p_hasta date,
  p_usuario uuid,
  p_ahora timestamptz default now()
) returns jsonb
language plpgsql as $$
declare
  n_jornadas int;
  n_sin_programacion int;
  n_ausencias int;
  n_extras int;
begin
  if p_hasta < p_desde then
    raise exception 'El rango de fechas no es valido' using errcode = '22023';
  end if;
  if p_hasta - p_desde > 62 then
    raise exception 'El rango no puede pasar de 62 dias' using errcode = '22023';
  end if;

  drop table if exists _asig, _marcas, _asignada, _calc, _huerfanas;

  -- 1
  create temp table _asig on commit drop as
  select a.id as asignacion_id, a.colaborador_id, a.fecha, a.sucursal_id, a.turno_id, t.nombre as turno,
         (a.fecha + t.hora_inicio) at time zone 'America/Guatemala' as inicio,
         ((a.fecha + t.hora_inicio) at time zone 'America/Guatemala')
           + make_interval(secs => (case when t.cruza_medianoche
                                         then extract(epoch from (t.hora_fin - t.hora_inicio)) + 86400
                                         else extract(epoch from (t.hora_fin - t.hora_inicio)) end)::double precision) as fin,
         coalesce(parametro_en('gracia_minutos', a.fecha, a.sucursal_id, a.turno_id), 10) as gracia,
         coalesce(parametro_en('ausencia_minutos', a.fecha, a.sucursal_id, a.turno_id), 60) as ausencia,
         coalesce(parametro_en('extra_minimo_minutos', a.fecha, a.sucursal_id, a.turno_id), 30) as extra_minimo,
         coalesce(parametro_en('sesion_minima_minutos', a.fecha, a.sucursal_id, a.turno_id), 30) as sesion_minima,
         coalesce(parametro_en('ventana_previa_minutos', a.fecha, a.sucursal_id, a.turno_id), 240) as previa,
         coalesce(parametro_en('ventana_posterior_minutos', a.fecha, a.sucursal_id, a.turno_id), 240) as posterior,
         (a.fecha between p_desde and p_hasta
            and not exists (select 1 from periodos_planilla pp
                            where pp.estado = 'cerrado' and a.fecha between pp.fecha_inicio and pp.fecha_fin)) as procesar,
         exists (select 1 from licencias l
                 where l.colaborador_id = a.colaborador_id and a.fecha between l.fecha_desde and l.fecha_hasta) as con_licencia
  from asignaciones_vigentes a
  join turnos t on t.id = a.turno_id
  where a.turno_id is not null
    and a.estado = 'programado'
    and a.fecha between p_desde - 1 and p_hasta + 1;

  -- 2
  create temp table _marcas on commit drop as
  select m.id, coalesce(m.colaborador_id, cd.colaborador_id) as colaborador_id, m.marcado_en, m.tipo, d.sucursal_id
  from marcaciones m
  left join colaborador_dispositivo cd
    on cd.dispositivo_id = m.dispositivo_id and cd.id_en_dispositivo = m.id_en_dispositivo
  left join dispositivos d on d.id = m.dispositivo_id
  where not m.es_duplicada
    and coalesce(m.colaborador_id, cd.colaborador_id) is not null
    and m.marcado_en >= ((p_desde - 2)::timestamp at time zone 'America/Guatemala')
    and m.marcado_en <  ((p_hasta + 4)::timestamp at time zone 'America/Guatemala');

  -- 3
  create temp table _asignada on commit drop as
  select distinct on (m.id)
         m.id as marca_id, m.colaborador_id, m.marcado_en, m.tipo, m.sucursal_id as sucursal_marca, a.asignacion_id
  from _marcas m
  join _asig a
    on a.colaborador_id = m.colaborador_id
   and m.marcado_en >= a.inicio - make_interval(mins => a.previa::int)
   and m.marcado_en <= a.fin + make_interval(mins => a.posterior::int)
  order by m.id,
           case when m.marcado_en between a.inicio and a.fin then 0
                else least(abs(extract(epoch from (m.marcado_en - a.inicio))),
                           abs(extract(epoch from (m.marcado_en - a.fin)))) end,
           a.inicio;

  -- 4
  create temp table _calc on commit drop as
  with ordenadas as (
    select x.*, row_number() over (partition by x.asignacion_id order by x.marcado_en, x.marca_id) as rn
    from _asignada x
  ),
  primeras as (
    select * from ordenadas where rn = 1
  ),
  candidatas as (
    select o.asignacion_id, o.marca_id, o.marcado_en, o.sucursal_marca, a.fin, a.gracia,
           min(o.marcado_en) over (partition by o.asignacion_id) as primera_candidata
    from ordenadas o
    join primeras p on p.asignacion_id = o.asignacion_id
    join _asig a on a.asignacion_id = o.asignacion_id
    where o.marcado_en >= p.marcado_en + make_interval(mins => a.sesion_minima::int)
  ),
  salidas as (
    -- salida normal: la primera marca despues de la sesion minima
    select distinct on (c.asignacion_id) c.asignacion_id, c.marca_id, c.marcado_en, c.sucursal_marca
    from candidatas c
    order by c.asignacion_id,
             case when c.primera_candidata < c.fin - make_interval(mins => c.gracia::int)
                  then c.marcado_en end desc nulls last,
             c.marcado_en
  ),
  unidas as (
    select a.*, p.marca_id as primera_id, p.marcado_en as primera, p.sucursal_marca as primera_suc,
           s.marca_id as salida_id, s.marcado_en as salida_t, s.sucursal_marca as salida_suc,
           (s.marca_id is null and (p.tipo = 'salida' or p.marcado_en > a.inicio + (a.fin - a.inicio) / 2)) as solo_salida
    from _asig a
    join primeras p on p.asignacion_id = a.asignacion_id
    left join salidas s on s.asignacion_id = a.asignacion_id
  ),
  tiempos as (
    select u.*,
           case when u.solo_salida then null else u.primera_id end as e_id,
           case when u.solo_salida then null else u.primera end as e,
           case when u.solo_salida then u.primera_id else u.salida_id end as s_id,
           case when u.solo_salida then u.primera else u.salida_t end as s,
           case when u.solo_salida then u.primera_suc else u.salida_suc end as s_suc,
           case when u.solo_salida then null else u.primera_suc end as e_suc
    from unidas u
  )
  select t.asignacion_id, t.colaborador_id, t.fecha, t.sucursal_id, t.turno, t.inicio, t.fin, t.procesar,
         t.e_id, t.s_id,
         case when t.e is not null and t.e > t.inicio
              then floor(extract(epoch from (t.e - t.inicio)) / 60)::int else 0 end as min_tardanza,
         case when t.e is null then null
              when t.e <= t.inicio then 'puntual'::clasif_entrada
              when extract(epoch from (t.e - t.inicio)) <= t.gracia * 60 then 'dentro_gracia'::clasif_entrada
              else 'tardanza'::clasif_entrada end as clasif_entrada,
         case when t.s is null then null
              when t.s < t.fin - make_interval(mins => t.gracia::int) then 'anticipada'::clasif_salida
              else 'normal'::clasif_salida end as clasif_salida,
         case when t.e is not null and t.s is not null
              then floor(greatest(0, extract(epoch from (least(t.s, t.fin) - greatest(t.e, t.inicio)))) / 60)::int
              else 0 end as min_trabajados,
         case when t.s is not null and t.s < t.fin
              then floor(extract(epoch from (t.fin - t.s)) / 60)::int else 0 end as min_anticipada,
         case when t.s is not null and t.s > t.fin
                   and floor(extract(epoch from (t.s - t.fin)) / 60) >= t.extra_minimo
              then floor(extract(epoch from (t.s - t.fin)) / 60)::int else 0 end as min_extra,
         t.gracia,
         case
           when t.e is null or t.s is null then 'incompleta'::estado_jornada
           when (t.e_suc is not null and t.e_suc <> t.sucursal_id)
             or (t.s_suc is not null and t.s_suc <> t.sucursal_id)
             or t.e < t.inicio - interval '120 minutes'
             or t.e > t.inicio + (t.fin - t.inicio) / 2 then 'por_confirmar'::estado_jornada
           else 'ok'::estado_jornada
         end as estado,
         (t.fin + make_interval(mins => t.posterior::int) <= p_ahora) as cerrado
  from tiempos t;

  -- 5
  insert into jornadas (asignacion_id, colaborador_id, sucursal_id, fecha, marcacion_entrada_id, marcacion_salida_id,
                        minutos_trabajados, minutos_tardanza, minutos_faltantes, clasif_entrada, clasif_salida, estado)
  select c.asignacion_id, c.colaborador_id, c.sucursal_id, c.fecha, c.e_id, c.s_id,
         c.min_trabajados, c.min_tardanza,
         case when c.estado = 'incompleta' then 0
              else (case when c.clasif_entrada = 'tardanza' then c.min_tardanza else 0 end)
                 + (case when c.clasif_salida = 'anticipada' then c.min_anticipada else 0 end) end,
         c.clasif_entrada, c.clasif_salida, c.estado
  from _calc c
  where c.procesar and c.cerrado
  on conflict (colaborador_id, fecha) do update set
    asignacion_id = excluded.asignacion_id,
    sucursal_id = excluded.sucursal_id,
    marcacion_entrada_id = excluded.marcacion_entrada_id,
    marcacion_salida_id = excluded.marcacion_salida_id,
    minutos_trabajados = excluded.minutos_trabajados,
    minutos_tardanza = excluded.minutos_tardanza,
    minutos_faltantes = excluded.minutos_faltantes,
    clasif_entrada = excluded.clasif_entrada,
    clasif_salida = excluded.clasif_salida,
    estado = excluded.estado;
  get diagnostics n_jornadas = row_count;

  -- 6
  create temp table _huerfanas on commit drop as
  select distinct on (m.colaborador_id, (m.marcado_en at time zone 'America/Guatemala')::date)
         m.colaborador_id,
         (m.marcado_en at time zone 'America/Guatemala')::date as fecha,
         m.id as marca_id, m.marcado_en, m.tipo,
         coalesce(m.sucursal_id, c.sucursal_base_id) as sucursal_id
  from _marcas m
  join colaboradores c on c.id = m.colaborador_id
  where not exists (select 1 from _asignada x where x.marca_id = m.id)
    and (m.marcado_en at time zone 'America/Guatemala')::date between p_desde and p_hasta
    and not exists (select 1 from periodos_planilla pp
                    where pp.estado = 'cerrado'
                      and (m.marcado_en at time zone 'America/Guatemala')::date between pp.fecha_inicio and pp.fecha_fin)
  order by m.colaborador_id, (m.marcado_en at time zone 'America/Guatemala')::date, m.marcado_en;

  insert into jornadas (asignacion_id, colaborador_id, sucursal_id, fecha, marcacion_entrada_id, marcacion_salida_id,
                        minutos_trabajados, minutos_tardanza, minutos_faltantes, estado)
  select null, h.colaborador_id, h.sucursal_id, h.fecha,
         case when h.tipo = 'salida' then null else h.marca_id end,
         case when h.tipo = 'salida' then h.marca_id else s.id end,
         case when h.tipo = 'salida' then 0
              else coalesce(floor(extract(epoch from (s.marcado_en - h.marcado_en)) / 60)::int, 0) end,
         0, 0, 'sin_programacion'
  from _huerfanas h
  left join lateral (
    select m2.id, m2.marcado_en
    from _marcas m2
    where m2.colaborador_id = h.colaborador_id
      and (m2.marcado_en at time zone 'America/Guatemala')::date = h.fecha
      and not exists (select 1 from _asignada x where x.marca_id = m2.id)
      and m2.marcado_en >= h.marcado_en + interval '30 minutes'
    order by m2.marcado_en
    limit 1
  ) s on true
  on conflict (colaborador_id, fecha) do update set
    sucursal_id = excluded.sucursal_id,
    marcacion_entrada_id = excluded.marcacion_entrada_id,
    marcacion_salida_id = excluded.marcacion_salida_id,
    minutos_trabajados = excluded.minutos_trabajados
    where jornadas.asignacion_id is null and jornadas.estado = 'sin_programacion';
  get diagnostics n_sin_programacion = row_count;

  -- 7
  with retiradas as (
    delete from ausencias au
    using _asignada x
    where au.asignacion_id = x.asignacion_id and au.estado = 'sin_justificar'
    returning au.colaborador_id, au.fecha
  )
  update alertas al
  set estado = 'resuelta', resuelta_en = now()
  from retiradas r
  where al.tipo = 'ausencia' and al.estado = 'abierta'
    and al.colaborador_id = r.colaborador_id and al.fecha = r.fecha;

  insert into ausencias (asignacion_id, colaborador_id, fecha)
  select a.asignacion_id, a.colaborador_id, a.fecha
  from _asig a
  where a.procesar
    and not a.con_licencia
    and p_ahora >= a.inicio + make_interval(mins => a.ausencia::int)
    and not exists (select 1 from _asignada x where x.asignacion_id = a.asignacion_id)
  on conflict (asignacion_id) do nothing;
  get diagnostics n_ausencias = row_count;

  -- 8
  insert into horas_extra (jornada_id, minutos_detectados)
  select j.id, c.min_extra
  from _calc c
  join jornadas j on j.colaborador_id = c.colaborador_id and j.fecha = c.fecha
  where c.procesar and c.cerrado and c.min_extra > 0 and c.estado <> 'incompleta'
  on conflict (jornada_id) do update set minutos_detectados = excluded.minutos_detectados
    where horas_extra.estado = 'pendiente';
  get diagnostics n_extras = row_count;

  delete from horas_extra h
  using jornadas j, _calc c
  where h.jornada_id = j.id and j.colaborador_id = c.colaborador_id and j.fecha = c.fecha
    and c.procesar and c.cerrado and c.min_extra = 0 and h.estado = 'pendiente';

  -- 9
  insert into alertas (tipo, colaborador_id, fecha, detalle)
  select v.tipo, v.colaborador_id, v.fecha, v.detalle
  from (
    select case j.estado when 'por_confirmar' then 'por_confirmar'::tipo_alerta
                         when 'incompleta' then 'marcacion_faltante'::tipo_alerta
                         else 'sin_programacion'::tipo_alerta end as tipo,
           j.colaborador_id, j.fecha, jsonb_build_object('jornada_id', j.id) as detalle
    from jornadas j
    where j.fecha between p_desde and p_hasta and j.estado in ('por_confirmar', 'incompleta', 'sin_programacion')
    union all
    select 'ausencia'::tipo_alerta, au.colaborador_id, au.fecha, jsonb_build_object('ausencia_id', au.id)
    from ausencias au
    where au.fecha between p_desde and p_hasta and au.estado = 'sin_justificar'
  ) v
  where not exists (
    select 1 from alertas al
    where al.tipo = v.tipo and al.colaborador_id = v.colaborador_id and al.fecha = v.fecha and al.estado = 'abierta'
  );

  insert into bitacora (usuario_id, accion, tabla, detalle)
  values (
    p_usuario, 'calcular', 'jornadas',
    jsonb_build_object('desde', p_desde, 'hasta', p_hasta, 'jornadas', n_jornadas,
                       'sin_programacion', n_sin_programacion, 'ausencias', n_ausencias, 'horas_extra', n_extras)
  );

  return jsonb_build_object('jornadas', n_jornadas, 'sin_programacion', n_sin_programacion,
                            'ausencias', n_ausencias, 'horas_extra', n_extras);
end;
$$;

revoke execute on function calcular_jornadas(date, date, uuid, timestamptz) from public, anon, authenticated;

notify pgrst, 'reload schema';

-- vista previa de la planilla de una quincena, con valores de hora editables por planilla, planilla)

insert into parametros (clave, valor, vigente_desde)
values
  ('valor_hora_extra_diurna',   22, '2026-01-01'),
  ('valor_hora_extra_nocturna', 25, '2026-01-01')
on conflict do nothing;

create table ajustes_planilla (
  id uuid primary key default gen_random_uuid(),
  fecha_inicio date not null,
  fecha_fin date not null,
  colaborador_id uuid not null references colaboradores(id),
  valor_hora numeric check (valor_hora > 0),
  valor_hora_extra numeric check (valor_hora_extra > 0),
  motivo text,
  registrado_por uuid references profiles(id),
  actualizado_en timestamptz not null default now(),
  check (valor_hora is not null or valor_hora_extra is not null),
  check (fecha_fin >= fecha_inicio),
  unique (colaborador_id, fecha_inicio, fecha_fin)
);

alter table ajustes_planilla enable row level security;
create policy lectura_rrhh_jefe on ajustes_planilla
  for select to authenticated using (rol_actual() in ('rrhh', 'jefe'));
revoke insert, update, delete on ajustes_planilla from anon, authenticated;

create function guardar_ajuste_planilla(
  p_inicio date,
  p_fin date,
  p_colaborador uuid,
  p_valor_hora numeric,
  p_valor_extra numeric,
  p_motivo text,
  p_usuario uuid
) returns void
language plpgsql as $$
declare
  texto text := nullif(trim(coalesce(p_motivo, '')), '');
begin
  if p_fin < p_inicio or p_fin - p_inicio > 31 then
    raise exception 'El periodo debe ser de 1 a 32 dias' using errcode = '22023';
  end if;
  if not exists (select 1 from colaboradores where id = p_colaborador) then
    raise exception 'El colaborador no existe' using errcode = 'P0002';
  end if;
  if exists (select 1 from periodos_planilla
             where estado = 'cerrado' and fecha_inicio <= p_fin and fecha_fin >= p_inicio) then
    raise exception 'Esa quincena ya esta cerrada' using errcode = '55000';
  end if;
  if p_valor_hora is not null and (p_valor_hora <= 0 or p_valor_hora > 100000) then
    raise exception 'El valor de la hora debe ser mayor que 0' using errcode = '22023';
  end if;
  if p_valor_extra is not null and (p_valor_extra <= 0 or p_valor_extra > 100000) then
    raise exception 'El valor de la hora extra debe ser mayor que 0' using errcode = '22023';
  end if;

  if p_valor_hora is null and p_valor_extra is null then
    delete from ajustes_planilla
    where colaborador_id = p_colaborador and fecha_inicio = p_inicio and fecha_fin = p_fin;
  else
    insert into ajustes_planilla (fecha_inicio, fecha_fin, colaborador_id, valor_hora, valor_hora_extra,
                                  motivo, registrado_por)
    values (p_inicio, p_fin, p_colaborador, p_valor_hora, p_valor_extra, texto, p_usuario)
    on conflict (colaborador_id, fecha_inicio, fecha_fin) do update set
      valor_hora = excluded.valor_hora,
      valor_hora_extra = excluded.valor_hora_extra,
      motivo = excluded.motivo,
      registrado_por = excluded.registrado_por,
      actualizado_en = now();
  end if;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'ajustar', 'ajustes_planilla', p_colaborador,
          jsonb_build_object('inicio', p_inicio, 'fin', p_fin, 'valor_hora', p_valor_hora,
                             'valor_hora_extra', p_valor_extra, 'motivo', texto));
end;
$$;

create function calcular_planilla(p_inicio date, p_fin date) returns jsonb
language plpgsql stable as $$
declare
  v_dias numeric := coalesce(parametro_en('dias_base_salario', p_fin), 30);
  v_horas numeric := coalesce(parametro_en('horas_base_dia', p_fin), 8);
  v_extra_dia numeric := parametro_en('valor_hora_extra_diurna', p_fin);
  v_extra_noche numeric := parametro_en('valor_hora_extra_nocturna', p_fin);
  resultado jsonb;
begin
  if p_fin < p_inicio or p_fin - p_inicio > 31 then
    raise exception 'El periodo debe ser de 1 a 32 dias' using errcode = '22023';
  end if;
  if v_extra_dia is null or v_extra_noche is null then
    raise exception 'Faltan los valores de la hora extra en los parametros' using errcode = '22023';
  end if;

  with
  personas as (
    select c.id, c.nombres, c.apellidos, c.modalidad, s.forma_pago, s.salario_mensual, s.tarifa,
           aj.valor_hora as aj_hora, aj.valor_hora_extra as aj_extra, aj.motivo as aj_motivo
    from colaboradores c
    join colaborador_salarios s
      on s.colaborador_id = c.id and s.vigente_desde <= p_fin
     and (s.vigente_hasta is null or s.vigente_hasta >= p_fin)
    left join ajustes_planilla aj
      on aj.colaborador_id = c.id and aj.fecha_inicio = p_inicio and aj.fecha_fin = p_fin
    where exists (select 1 from periodos_laborales pl
                  where pl.colaborador_id = c.id and pl.fecha_ingreso <= p_fin
                    and (pl.fecha_baja is null or pl.fecha_baja >= p_inicio))
  ),
  trabajo as (
    select j.colaborador_id, sum(j.minutos_trabajados)::int as minutos, count(*)::int as turnos
    from jornadas j
    where j.fecha between p_inicio and p_fin and j.estado = 'ok'
    group by j.colaborador_id
  ),
  extras as (
    select j.colaborador_id,
           coalesce(sum(h.minutos_pagados) filter (where t.tipo_jornada is distinct from 'nocturna'), 0)::int as min_dia,
           coalesce(sum(h.minutos_pagados) filter (where t.tipo_jornada = 'nocturna'), 0)::int as min_noche
    from horas_extra h
    join jornadas j on j.id = h.jornada_id
    left join asignaciones_turno a on a.id = j.asignacion_id
    left join turnos t on t.id = a.turno_id
    where j.fecha between p_inicio and p_fin and h.estado in ('autorizada', 'parcial')
    group by j.colaborador_id
  ),
  faltas as (
    select au.colaborador_id, count(*)::int as dias
    from ausencias au
    join tipos_ausencia ta on ta.id = au.tipo_ausencia_id
    where au.fecha between p_inicio and p_fin and au.estado <> 'sin_justificar' and ta.descuenta_dia
    group by au.colaborador_id
  ),
  tiempo as (
    select d.colaborador_id,
           sum(case when d.estado = 'aplicado' then d.minutos_detectados else d.minutos_descontados end)::int as minutos
    from descuentos_tiempo d
    where d.fecha_inicio = p_inicio and d.fecha_fin = p_fin and d.estado in ('aplicado', 'parcial')
    group by d.colaborador_id
  ),
  calculo as (
    select p.*, coalesce(t.minutos, 0) as minutos, coalesce(t.turnos, 0) as turnos,
           coalesce(e.min_dia, 0) as extra_dia_min, coalesce(e.min_noche, 0) as extra_noche_min,
           coalesce(f.dias, 0) as faltas, coalesce(d.minutos, 0) as min_descontados,
           case p.forma_pago
             when 'por_hora' then p.tarifa
             when 'por_turno' then round(p.tarifa / v_horas, 4)
             else round(p.salario_mensual / (v_dias * v_horas), 4) end as hora_defecto,
           case when p.forma_pago = 'por_hora' then coalesce(p.aj_hora, p.tarifa) end as hora_pago,
           coalesce(p.aj_extra, v_extra_dia) as extra_dia,
           coalesce(p.aj_extra, v_extra_noche) as extra_noche
    from personas p
    left join trabajo t on t.colaborador_id = p.id
    left join extras e on e.colaborador_id = p.id
    left join faltas f on f.colaborador_id = p.id
    left join tiempo d on d.colaborador_id = p.id
  ),
  lineas as (
    select id, 1 as orden, 'ingreso' as tipo, 'Horas trabajadas' as concepto,
           round(minutos / 60.0, 2) as cantidad, hora_pago as valor,
           round(minutos / 60.0 * hora_pago, 2) as monto
    from calculo where forma_pago = 'por_hora'
    union all
    select id, 1, 'ingreso', 'Turnos trabajados', turnos, tarifa, round(turnos * tarifa, 2)
    from calculo where forma_pago = 'por_turno'
    union all
    select id, 1, 'ingreso', 'Salario quincenal', 1, round(salario_mensual / 2, 2), round(salario_mensual / 2, 2)
    from calculo where forma_pago = 'salario_fijo'
    union all
    select id, 2, 'ingreso', 'Horas extra de dia', round(extra_dia_min / 60.0, 2), extra_dia,
           round(extra_dia_min / 60.0 * extra_dia, 2)
    from calculo where extra_dia_min > 0
    union all
    select id, 3, 'ingreso', 'Horas extra nocturnas', round(extra_noche_min / 60.0, 2), extra_noche,
           round(extra_noche_min / 60.0 * extra_noche, 2)
    from calculo where extra_noche_min > 0
    union all
    select id, 4, 'descuento', 'Dias de ausencia descontados', faltas, round(salario_mensual / v_dias, 2),
           round(faltas * salario_mensual / v_dias, 2)
    from calculo where forma_pago = 'salario_fijo' and faltas > 0
    union all
    select id, 5, 'descuento', 'Minutos descontados por tardanza o salida anticipada', min_descontados,
           round(salario_mensual / v_dias / v_horas / 60, 4),
           round(min_descontados * salario_mensual / v_dias / v_horas / 60, 2)
    from calculo where forma_pago = 'salario_fijo' and min_descontados > 0
  ),
  resumen as (
    select c.*,
           coalesce((select jsonb_agg(jsonb_build_object('tipo', l.tipo, 'concepto', l.concepto, 'cantidad', l.cantidad,
                                                         'valor_unitario', l.valor, 'monto', l.monto) order by l.orden)
                     from lineas l where l.id = c.id), '[]'::jsonb) as detalle,
           coalesce((select sum(l.monto) from lineas l where l.id = c.id and l.tipo = 'ingreso'), 0) as ingresos,
           coalesce((select sum(l.monto) from lineas l where l.id = c.id and l.tipo = 'descuento'), 0) as descuentos
    from calculo c
  )
  select coalesce(jsonb_agg(jsonb_build_object(
           'colaborador_id', r.id,
           'nombre', r.nombres || ' ' || r.apellidos,
           'modalidad', r.modalidad,
           'forma_pago', r.forma_pago,
           'minutos_trabajados', r.minutos,
           'turnos', r.turnos,
           'valor_hora', r.hora_pago,
           'valor_hora_defecto', case when r.forma_pago = 'por_hora' then r.tarifa end,
           'valor_extra_dia', r.extra_dia,
           'valor_extra_noche', r.extra_noche,
           'valor_extra_defecto_dia', v_extra_dia,
           'valor_extra_defecto_noche', v_extra_noche,
           'ajuste', case when r.aj_hora is not null or r.aj_extra is not null
                          then jsonb_build_object('valor_hora', r.aj_hora, 'valor_hora_extra', r.aj_extra,
                                                  'motivo', r.aj_motivo) end,
           'lineas', r.detalle,
           'total_ingresos', r.ingresos,
           'total_descuentos', r.descuentos,
           'neto', r.ingresos - r.descuentos
         ) order by r.apellidos, r.nombres), '[]'::jsonb)
  into resultado
  from resumen r;

  return resultado;
end;
$$;

revoke execute on function guardar_ajuste_planilla(date, date, uuid, numeric, numeric, text, uuid)
  from public, anon, authenticated;
revoke execute on function calcular_planilla(date, date) from public, anon, authenticated;

notify pgrst, 'reload schema';

-- correccion del motor de jornadas: la marcacion que rr hh agrega a mano puede caer mucho despues

insert into parametros (clave, valor, vigente_desde)
values ('ventana_manual_minutos', 720, '2026-01-01')
on conflict do nothing;

create or replace function calcular_jornadas(
  p_desde date,
  p_hasta date,
  p_usuario uuid,
  p_ahora timestamptz default now()
) returns jsonb
language plpgsql as $$
declare
  n_jornadas int;
  n_sin_programacion int;
  n_ausencias int;
  n_extras int;
begin
  if p_hasta < p_desde then
    raise exception 'El rango de fechas no es valido' using errcode = '22023';
  end if;
  if p_hasta - p_desde > 62 then
    raise exception 'El rango no puede pasar de 62 dias' using errcode = '22023';
  end if;

  drop table if exists _asig, _marcas, _asignada, _calc, _huerfanas;

  -- 1
  create temp table _asig on commit drop as
  select a.id as asignacion_id, a.colaborador_id, a.fecha, a.sucursal_id, a.turno_id, t.nombre as turno,
         (a.fecha + t.hora_inicio) at time zone 'America/Guatemala' as inicio,
         ((a.fecha + t.hora_inicio) at time zone 'America/Guatemala')
           + make_interval(secs => (case when t.cruza_medianoche
                                         then extract(epoch from (t.hora_fin - t.hora_inicio)) + 86400
                                         else extract(epoch from (t.hora_fin - t.hora_inicio)) end)::double precision) as fin,
         coalesce(parametro_en('gracia_minutos', a.fecha, a.sucursal_id, a.turno_id), 10) as gracia,
         coalesce(parametro_en('ausencia_minutos', a.fecha, a.sucursal_id, a.turno_id), 60) as ausencia,
         coalesce(parametro_en('extra_minimo_minutos', a.fecha, a.sucursal_id, a.turno_id), 30) as extra_minimo,
         coalesce(parametro_en('sesion_minima_minutos', a.fecha, a.sucursal_id, a.turno_id), 30) as sesion_minima,
         coalesce(parametro_en('ventana_previa_minutos', a.fecha, a.sucursal_id, a.turno_id), 240) as previa,
         coalesce(parametro_en('ventana_posterior_minutos', a.fecha, a.sucursal_id, a.turno_id), 240) as posterior,
         coalesce(parametro_en('ventana_manual_minutos', a.fecha, a.sucursal_id, a.turno_id), 720) as posterior_manual,
         (a.fecha between p_desde and p_hasta
            and not exists (select 1 from periodos_planilla pp
                            where pp.estado = 'cerrado' and a.fecha between pp.fecha_inicio and pp.fecha_fin)) as procesar,
         exists (select 1 from licencias l
                 where l.colaborador_id = a.colaborador_id and a.fecha between l.fecha_desde and l.fecha_hasta) as con_licencia
  from asignaciones_vigentes a
  join turnos t on t.id = a.turno_id
  where a.turno_id is not null
    and a.estado = 'programado'
    and a.fecha between p_desde - 1 and p_hasta + 1;

  -- 2
  create temp table _marcas on commit drop as
  select m.id, coalesce(m.colaborador_id, cd.colaborador_id) as colaborador_id, m.marcado_en, m.tipo, d.sucursal_id,
         m.origen
  from marcaciones m
  left join colaborador_dispositivo cd
    on cd.dispositivo_id = m.dispositivo_id and cd.id_en_dispositivo = m.id_en_dispositivo
  left join dispositivos d on d.id = m.dispositivo_id
  where not m.es_duplicada
    and coalesce(m.colaborador_id, cd.colaborador_id) is not null
    and m.marcado_en >= ((p_desde - 2)::timestamp at time zone 'America/Guatemala')
    and m.marcado_en <  ((p_hasta + 4)::timestamp at time zone 'America/Guatemala');

  -- 3
  create temp table _asignada on commit drop as
  select distinct on (m.id)
         m.id as marca_id, m.colaborador_id, m.marcado_en, m.tipo, m.sucursal_id as sucursal_marca, a.asignacion_id
  from _marcas m
  join _asig a
    on a.colaborador_id = m.colaborador_id
   and m.marcado_en >= a.inicio - make_interval(mins => a.previa::int)
   and m.marcado_en <= a.fin + make_interval(mins => (case when m.origen = 'manual'
                                                         then greatest(a.posterior, a.posterior_manual)
                                                         else a.posterior end)::int)
  order by m.id,
           case when m.marcado_en between a.inicio and a.fin then 0
                else least(abs(extract(epoch from (m.marcado_en - a.inicio))),
                           abs(extract(epoch from (m.marcado_en - a.fin)))) end,
           a.inicio;

  -- 4
  create temp table _calc on commit drop as
  with ordenadas as (
    select x.*, row_number() over (partition by x.asignacion_id order by x.marcado_en, x.marca_id) as rn
    from _asignada x
  ),
  primeras as (
    select * from ordenadas where rn = 1
  ),
  candidatas as (
    select o.asignacion_id, o.marca_id, o.marcado_en, o.sucursal_marca, a.fin, a.gracia,
           min(o.marcado_en) over (partition by o.asignacion_id) as primera_candidata
    from ordenadas o
    join primeras p on p.asignacion_id = o.asignacion_id
    join _asig a on a.asignacion_id = o.asignacion_id
    where o.marcado_en >= p.marcado_en + make_interval(mins => a.sesion_minima::int)
  ),
  salidas as (
    -- salida normal: la primera marca despues de la sesion minima
    select distinct on (c.asignacion_id) c.asignacion_id, c.marca_id, c.marcado_en, c.sucursal_marca
    from candidatas c
    order by c.asignacion_id,
             case when c.primera_candidata < c.fin - make_interval(mins => c.gracia::int)
                  then c.marcado_en end desc nulls last,
             c.marcado_en
  ),
  unidas as (
    select a.*, p.marca_id as primera_id, p.marcado_en as primera, p.sucursal_marca as primera_suc,
           s.marca_id as salida_id, s.marcado_en as salida_t, s.sucursal_marca as salida_suc,
           (s.marca_id is null and (p.tipo = 'salida' or p.marcado_en > a.inicio + (a.fin - a.inicio) / 2)) as solo_salida
    from _asig a
    join primeras p on p.asignacion_id = a.asignacion_id
    left join salidas s on s.asignacion_id = a.asignacion_id
  ),
  tiempos as (
    select u.*,
           case when u.solo_salida then null else u.primera_id end as e_id,
           case when u.solo_salida then null else u.primera end as e,
           case when u.solo_salida then u.primera_id else u.salida_id end as s_id,
           case when u.solo_salida then u.primera else u.salida_t end as s,
           case when u.solo_salida then u.primera_suc else u.salida_suc end as s_suc,
           case when u.solo_salida then null else u.primera_suc end as e_suc
    from unidas u
  )
  select t.asignacion_id, t.colaborador_id, t.fecha, t.sucursal_id, t.turno, t.inicio, t.fin, t.procesar,
         t.e_id, t.s_id,
         case when t.e is not null and t.e > t.inicio
              then floor(extract(epoch from (t.e - t.inicio)) / 60)::int else 0 end as min_tardanza,
         case when t.e is null then null
              when t.e <= t.inicio then 'puntual'::clasif_entrada
              when extract(epoch from (t.e - t.inicio)) <= t.gracia * 60 then 'dentro_gracia'::clasif_entrada
              else 'tardanza'::clasif_entrada end as clasif_entrada,
         case when t.s is null then null
              when t.s < t.fin - make_interval(mins => t.gracia::int) then 'anticipada'::clasif_salida
              else 'normal'::clasif_salida end as clasif_salida,
         case when t.e is not null and t.s is not null
              then floor(greatest(0, extract(epoch from (least(t.s, t.fin) - greatest(t.e, t.inicio)))) / 60)::int
              else 0 end as min_trabajados,
         case when t.s is not null and t.s < t.fin
              then floor(extract(epoch from (t.fin - t.s)) / 60)::int else 0 end as min_anticipada,
         case when t.s is not null and t.s > t.fin
                   and floor(extract(epoch from (t.s - t.fin)) / 60) >= t.extra_minimo
              then floor(extract(epoch from (t.s - t.fin)) / 60)::int else 0 end as min_extra,
         t.gracia,
         case
           when t.e is null or t.s is null then 'incompleta'::estado_jornada
           when (t.e_suc is not null and t.e_suc <> t.sucursal_id)
             or (t.s_suc is not null and t.s_suc <> t.sucursal_id)
             or t.e < t.inicio - interval '120 minutes'
             or t.e > t.inicio + (t.fin - t.inicio) / 2 then 'por_confirmar'::estado_jornada
           else 'ok'::estado_jornada
         end as estado,
         (t.fin + make_interval(mins => t.posterior::int) <= p_ahora) as cerrado
  from tiempos t;

  -- 5
  insert into jornadas (asignacion_id, colaborador_id, sucursal_id, fecha, marcacion_entrada_id, marcacion_salida_id,
                        minutos_trabajados, minutos_tardanza, minutos_faltantes, clasif_entrada, clasif_salida, estado)
  select c.asignacion_id, c.colaborador_id, c.sucursal_id, c.fecha, c.e_id, c.s_id,
         c.min_trabajados, c.min_tardanza,
         case when c.estado = 'incompleta' then 0
              else (case when c.clasif_entrada = 'tardanza' then c.min_tardanza else 0 end)
                 + (case when c.clasif_salida = 'anticipada' then c.min_anticipada else 0 end) end,
         c.clasif_entrada, c.clasif_salida, c.estado
  from _calc c
  where c.procesar and c.cerrado
  on conflict (colaborador_id, fecha) do update set
    asignacion_id = excluded.asignacion_id,
    sucursal_id = excluded.sucursal_id,
    marcacion_entrada_id = excluded.marcacion_entrada_id,
    marcacion_salida_id = excluded.marcacion_salida_id,
    minutos_trabajados = excluded.minutos_trabajados,
    minutos_tardanza = excluded.minutos_tardanza,
    minutos_faltantes = excluded.minutos_faltantes,
    clasif_entrada = excluded.clasif_entrada,
    clasif_salida = excluded.clasif_salida,
    estado = excluded.estado;
  get diagnostics n_jornadas = row_count;

  -- 6
  create temp table _huerfanas on commit drop as
  select distinct on (m.colaborador_id, (m.marcado_en at time zone 'America/Guatemala')::date)
         m.colaborador_id,
         (m.marcado_en at time zone 'America/Guatemala')::date as fecha,
         m.id as marca_id, m.marcado_en, m.tipo,
         coalesce(m.sucursal_id, c.sucursal_base_id) as sucursal_id
  from _marcas m
  join colaboradores c on c.id = m.colaborador_id
  where not exists (select 1 from _asignada x where x.marca_id = m.id)
    and (m.marcado_en at time zone 'America/Guatemala')::date between p_desde and p_hasta
    and not exists (select 1 from periodos_planilla pp
                    where pp.estado = 'cerrado'
                      and (m.marcado_en at time zone 'America/Guatemala')::date between pp.fecha_inicio and pp.fecha_fin)
  order by m.colaborador_id, (m.marcado_en at time zone 'America/Guatemala')::date, m.marcado_en;

  insert into jornadas (asignacion_id, colaborador_id, sucursal_id, fecha, marcacion_entrada_id, marcacion_salida_id,
                        minutos_trabajados, minutos_tardanza, minutos_faltantes, estado)
  select null, h.colaborador_id, h.sucursal_id, h.fecha,
         case when h.tipo = 'salida' then null else h.marca_id end,
         case when h.tipo = 'salida' then h.marca_id else s.id end,
         case when h.tipo = 'salida' then 0
              else coalesce(floor(extract(epoch from (s.marcado_en - h.marcado_en)) / 60)::int, 0) end,
         0, 0, 'sin_programacion'
  from _huerfanas h
  left join lateral (
    select m2.id, m2.marcado_en
    from _marcas m2
    where m2.colaborador_id = h.colaborador_id
      and (m2.marcado_en at time zone 'America/Guatemala')::date = h.fecha
      and not exists (select 1 from _asignada x where x.marca_id = m2.id)
      and m2.marcado_en >= h.marcado_en + interval '30 minutes'
    order by m2.marcado_en
    limit 1
  ) s on true
  on conflict (colaborador_id, fecha) do update set
    sucursal_id = excluded.sucursal_id,
    marcacion_entrada_id = excluded.marcacion_entrada_id,
    marcacion_salida_id = excluded.marcacion_salida_id,
    minutos_trabajados = excluded.minutos_trabajados
    where jornadas.asignacion_id is null and jornadas.estado = 'sin_programacion';
  get diagnostics n_sin_programacion = row_count;

  -- 7
  with retiradas as (
    delete from ausencias au
    using _asignada x
    where au.asignacion_id = x.asignacion_id and au.estado = 'sin_justificar'
    returning au.colaborador_id, au.fecha
  )
  update alertas al
  set estado = 'resuelta', resuelta_en = now()
  from retiradas r
  where al.tipo = 'ausencia' and al.estado = 'abierta'
    and al.colaborador_id = r.colaborador_id and al.fecha = r.fecha;

  insert into ausencias (asignacion_id, colaborador_id, fecha)
  select a.asignacion_id, a.colaborador_id, a.fecha
  from _asig a
  where a.procesar
    and not a.con_licencia
    and p_ahora >= a.inicio + make_interval(mins => a.ausencia::int)
    and not exists (select 1 from _asignada x where x.asignacion_id = a.asignacion_id)
  on conflict (asignacion_id) do nothing;
  get diagnostics n_ausencias = row_count;

  -- 8
  insert into horas_extra (jornada_id, minutos_detectados)
  select j.id, c.min_extra
  from _calc c
  join jornadas j on j.colaborador_id = c.colaborador_id and j.fecha = c.fecha
  where c.procesar and c.cerrado and c.min_extra > 0 and c.estado <> 'incompleta'
  on conflict (jornada_id) do update set minutos_detectados = excluded.minutos_detectados
    where horas_extra.estado = 'pendiente';
  get diagnostics n_extras = row_count;

  delete from horas_extra h
  using jornadas j, _calc c
  where h.jornada_id = j.id and j.colaborador_id = c.colaborador_id and j.fecha = c.fecha
    and c.procesar and c.cerrado and c.min_extra = 0 and h.estado = 'pendiente';

  -- 9
  insert into alertas (tipo, colaborador_id, fecha, detalle)
  select v.tipo, v.colaborador_id, v.fecha, v.detalle
  from (
    select case j.estado when 'por_confirmar' then 'por_confirmar'::tipo_alerta
                         when 'incompleta' then 'marcacion_faltante'::tipo_alerta
                         else 'sin_programacion'::tipo_alerta end as tipo,
           j.colaborador_id, j.fecha, jsonb_build_object('jornada_id', j.id) as detalle
    from jornadas j
    where j.fecha between p_desde and p_hasta and j.estado in ('por_confirmar', 'incompleta', 'sin_programacion')
    union all
    select 'ausencia'::tipo_alerta, au.colaborador_id, au.fecha, jsonb_build_object('ausencia_id', au.id)
    from ausencias au
    where au.fecha between p_desde and p_hasta and au.estado = 'sin_justificar'
  ) v
  where not exists (
    select 1 from alertas al
    where al.tipo = v.tipo and al.colaborador_id = v.colaborador_id and al.fecha = v.fecha and al.estado = 'abierta'
  );

  insert into bitacora (usuario_id, accion, tabla, detalle)
  values (
    p_usuario, 'calcular', 'jornadas',
    jsonb_build_object('desde', p_desde, 'hasta', p_hasta, 'jornadas', n_jornadas,
                       'sin_programacion', n_sin_programacion, 'ausencias', n_ausencias, 'horas_extra', n_extras)
  );

  return jsonb_build_object('jornadas', n_jornadas, 'sin_programacion', n_sin_programacion,
                            'ausencias', n_ausencias, 'horas_extra', n_extras);
end;
$$;

revoke execute on function calcular_jornadas(date, date, uuid, timestamptz) from public, anon, authenticated;

notify pgrst, 'reload schema';

-- cerrar la quincena y emitir las boletas, planilla)

create function cerrar_planilla(p_inicio date, p_fin date, p_usuario uuid) returns jsonb
language plpgsql as $$
declare
  v_periodo uuid;
  v_incompletas int;
  v_confirmar int;
  v_ausencias int;
  v_extras int;
  v_descuentos int;
  v_persona jsonb;
  v_boleta uuid;
  v_linea jsonb;
  v_boletas int := 0;
  v_neto numeric := 0;
  v_pendientes text[] := '{}';
begin
  if p_fin < p_inicio or p_fin - p_inicio > 31 then
    raise exception 'El periodo debe ser de 1 a 32 dias' using errcode = '22023';
  end if;
  if exists (select 1 from periodos_planilla
             where fecha_inicio <= p_fin and fecha_fin >= p_inicio) then
    raise exception 'Esa quincena ya esta cerrada' using errcode = '55000';
  end if;

  select count(*) into v_incompletas from jornadas where fecha between p_inicio and p_fin and estado = 'incompleta';
  select count(*) into v_confirmar from jornadas where fecha between p_inicio and p_fin and estado = 'por_confirmar';
  select count(*) into v_ausencias from ausencias where fecha between p_inicio and p_fin and estado = 'sin_justificar';
  select count(*) into v_extras from horas_extra h join jornadas j on j.id = h.jornada_id
   where j.fecha between p_inicio and p_fin and h.estado = 'pendiente';
  select count(*) into v_descuentos from descuentos_tiempo
   where fecha_inicio = p_inicio and fecha_fin = p_fin and estado = 'pendiente';

  if v_incompletas > 0 then v_pendientes := v_pendientes || (v_incompletas || ' jornada(s) incompleta(s)'); end if;
  if v_confirmar > 0 then v_pendientes := v_pendientes || (v_confirmar || ' jornada(s) por confirmar'); end if;
  if v_ausencias > 0 then v_pendientes := v_pendientes || (v_ausencias || ' ausencia(s) sin justificar'); end if;
  if v_extras > 0 then v_pendientes := v_pendientes || (v_extras || ' hora(s) extra por decidir'); end if;
  if v_descuentos > 0 then v_pendientes := v_pendientes || (v_descuentos || ' descuento(s) por decidir'); end if;
  if array_length(v_pendientes, 1) > 0 then
    raise exception 'Todavia hay pendientes: %', array_to_string(v_pendientes, ', ') using errcode = '22023';
  end if;

  insert into periodos_planilla (fecha_inicio, fecha_fin, estado, cerrado_por, cerrado_en, aprobado_por)
  values (p_inicio, p_fin, 'cerrado', p_usuario, now(), p_usuario)
  returning id into v_periodo;

  for v_persona in select * from jsonb_array_elements(calcular_planilla(p_inicio, p_fin))
  loop
    continue when jsonb_array_length(v_persona -> 'lineas') = 0;

    insert into boletas (periodo_id, colaborador_id, total_ingresos, total_descuentos, neto, snapshot_valores)
    values (v_periodo, (v_persona ->> 'colaborador_id')::uuid, (v_persona ->> 'total_ingresos')::numeric,
            (v_persona ->> 'total_descuentos')::numeric, (v_persona ->> 'neto')::numeric,
            v_persona - 'lineas')
    returning id into v_boleta;

    for v_linea in select * from jsonb_array_elements(v_persona -> 'lineas')
    loop
      insert into boleta_detalles (boleta_id, tipo, concepto, cantidad, valor_unitario, monto)
      values (v_boleta, (v_linea ->> 'tipo')::tipo_detalle_boleta, v_linea ->> 'concepto',
              (v_linea ->> 'cantidad')::numeric, (v_linea ->> 'valor_unitario')::numeric,
              (v_linea ->> 'monto')::numeric);
    end loop;

    v_boletas := v_boletas + 1;
    v_neto := v_neto + (v_persona ->> 'neto')::numeric;
  end loop;

  if v_boletas = 0 then
    raise exception 'No hay nada que pagar en esa quincena' using errcode = '22023';
  end if;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'cerrar', 'periodos_planilla', v_periodo,
          jsonb_build_object('inicio', p_inicio, 'fin', p_fin, 'boletas', v_boletas, 'neto_total', v_neto));

  return jsonb_build_object('periodo_id', v_periodo, 'boletas', v_boletas, 'neto_total', v_neto);
end;
$$;

create function marcar_boletas_pagadas(p_periodo uuid, p_usuario uuid) returns int
language plpgsql as $$
declare
  n int;
begin
  if not exists (select 1 from periodos_planilla where id = p_periodo and estado = 'cerrado') then
    raise exception 'El periodo no existe' using errcode = 'P0002';
  end if;

  update boletas set estado = 'pagada', pagada_en = now(), pagada_por = p_usuario
  where periodo_id = p_periodo and estado = 'generada';
  get diagnostics n = row_count;

  if n = 0 then
    raise exception 'No hay boletas por marcar como pagadas' using errcode = '22023';
  end if;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'pagar', 'periodos_planilla', p_periodo, jsonb_build_object('boletas', n));

  return n;
end;
$$;

revoke execute on function cerrar_planilla(date, date, uuid) from public, anon, authenticated;
revoke execute on function marcar_boletas_pagadas(uuid, uuid) from public, anon, authenticated;

notify pgrst, 'reload schema';

-- correccion del motor de jornadas: dos turnos seguidos (noche y luego manana)

create or replace function calcular_jornadas(
  p_desde date,
  p_hasta date,
  p_usuario uuid,
  p_ahora timestamptz default now()
) returns jsonb
language plpgsql as $$
declare
  n_jornadas int;
  n_sin_programacion int;
  n_ausencias int;
  n_extras int;
begin
  if p_hasta < p_desde then
    raise exception 'El rango de fechas no es valido' using errcode = '22023';
  end if;
  if p_hasta - p_desde > 62 then
    raise exception 'El rango no puede pasar de 62 dias' using errcode = '22023';
  end if;

  drop table if exists _asig, _marcas, _asignada, _calc, _huerfanas;

  -- 1
  create temp table _asig on commit drop as
  select a.id as asignacion_id, a.colaborador_id, a.fecha, a.sucursal_id, a.turno_id, t.nombre as turno,
         (a.fecha + t.hora_inicio) at time zone 'America/Guatemala' as inicio,
         ((a.fecha + t.hora_inicio) at time zone 'America/Guatemala')
           + make_interval(secs => (case when t.cruza_medianoche
                                         then extract(epoch from (t.hora_fin - t.hora_inicio)) + 86400
                                         else extract(epoch from (t.hora_fin - t.hora_inicio)) end)::double precision) as fin,
         coalesce(parametro_en('gracia_minutos', a.fecha, a.sucursal_id, a.turno_id), 10) as gracia,
         coalesce(parametro_en('ausencia_minutos', a.fecha, a.sucursal_id, a.turno_id), 60) as ausencia,
         coalesce(parametro_en('extra_minimo_minutos', a.fecha, a.sucursal_id, a.turno_id), 30) as extra_minimo,
         coalesce(parametro_en('sesion_minima_minutos', a.fecha, a.sucursal_id, a.turno_id), 30) as sesion_minima,
         coalesce(parametro_en('ventana_previa_minutos', a.fecha, a.sucursal_id, a.turno_id), 240) as previa,
         coalesce(parametro_en('ventana_posterior_minutos', a.fecha, a.sucursal_id, a.turno_id), 240) as posterior,
         coalesce(parametro_en('ventana_manual_minutos', a.fecha, a.sucursal_id, a.turno_id), 720) as posterior_manual,
         (a.fecha between p_desde and p_hasta
            and not exists (select 1 from periodos_planilla pp
                            where pp.estado = 'cerrado' and a.fecha between pp.fecha_inicio and pp.fecha_fin)) as procesar,
         exists (select 1 from licencias l
                 where l.colaborador_id = a.colaborador_id and a.fecha between l.fecha_desde and l.fecha_hasta) as con_licencia
  from asignaciones_vigentes a
  join turnos t on t.id = a.turno_id
  where a.turno_id is not null
    and a.estado = 'programado'
    and a.fecha between p_desde - 1 and p_hasta + 1;

  -- 2
  create temp table _marcas on commit drop as
  select m.id, coalesce(m.colaborador_id, cd.colaborador_id) as colaborador_id, m.marcado_en, m.tipo, d.sucursal_id,
         m.origen
  from marcaciones m
  left join colaborador_dispositivo cd
    on cd.dispositivo_id = m.dispositivo_id and cd.id_en_dispositivo = m.id_en_dispositivo
  left join dispositivos d on d.id = m.dispositivo_id
  where not m.es_duplicada
    and coalesce(m.colaborador_id, cd.colaborador_id) is not null
    and m.marcado_en >= ((p_desde - 2)::timestamp at time zone 'America/Guatemala')
    and m.marcado_en <  ((p_hasta + 4)::timestamp at time zone 'America/Guatemala');

  -- 3
  create temp table _asignada on commit drop as
  select distinct on (m.id)
         m.id as marca_id, m.colaborador_id, m.marcado_en, m.tipo, m.sucursal_id as sucursal_marca, a.asignacion_id
  from _marcas m
  join _asig a
    on a.colaborador_id = m.colaborador_id
   and m.marcado_en >= a.inicio - make_interval(mins => a.previa::int)
   and m.marcado_en <= a.fin + make_interval(mins => (case when m.origen = 'manual'
                                                         then greatest(a.posterior, a.posterior_manual)
                                                         else a.posterior end)::int)
  order by m.id,
           case when m.marcado_en between a.inicio and a.fin then 0
                else least(abs(extract(epoch from (m.marcado_en - a.inicio))),
                           abs(extract(epoch from (m.marcado_en - a.fin)))) end,
           a.inicio;

  -- 4
  create temp table _calc on commit drop as
  with ordenadas as (
    select x.*, row_number() over (partition by x.asignacion_id order by x.marcado_en, x.marca_id) as rn
    from _asignada x
  ),
  primeras as (
    select * from ordenadas where rn = 1
  ),
  candidatas as (
    select o.asignacion_id, o.marca_id, o.marcado_en, o.sucursal_marca, a.fin, a.gracia,
           min(o.marcado_en) over (partition by o.asignacion_id) as primera_candidata
    from ordenadas o
    join primeras p on p.asignacion_id = o.asignacion_id
    join _asig a on a.asignacion_id = o.asignacion_id
    where o.marcado_en >= p.marcado_en + make_interval(mins => a.sesion_minima::int)
  ),
  salidas_propias as (
    -- salida normal: la primera marca despues de la sesion minima
    select distinct on (c.asignacion_id) c.asignacion_id, c.marca_id, c.marcado_en, c.sucursal_marca
    from candidatas c
    order by c.asignacion_id,
             case when c.primera_candidata < c.fin - make_interval(mins => c.gracia::int)
                  then c.marcado_en end desc nulls last,
             c.marcado_en
  ),
  frontera as (
    -- dos turnos seguidos (noche y manana del dia siguiente): una sola marca en el cambio es la salida
    select distinct on (a.asignacion_id) a.asignacion_id, m.id as marca_id, m.marcado_en,
           m.sucursal_id as sucursal_marca
    from _asig a
    join primeras p on p.asignacion_id = a.asignacion_id
    join _marcas m on m.colaborador_id = a.colaborador_id
    where m.marcado_en between a.fin - make_interval(mins => a.gracia::int)
                           and a.fin + make_interval(mins => a.gracia::int)
      and m.marcado_en >= p.marcado_en + make_interval(mins => a.sesion_minima::int)
      and exists (select 1 from _asig b
                  where b.colaborador_id = a.colaborador_id and b.asignacion_id <> a.asignacion_id
                    and b.inicio between a.fin - interval '1 minute' and a.fin + make_interval(mins => a.gracia::int))
    order by a.asignacion_id, abs(extract(epoch from (m.marcado_en - a.fin)))
  ),
  salidas as (
    select sp.asignacion_id, sp.marca_id, sp.marcado_en, sp.sucursal_marca from salidas_propias sp
    union all
    select f.asignacion_id, f.marca_id, f.marcado_en, f.sucursal_marca from frontera f
    where not exists (select 1 from salidas_propias sp where sp.asignacion_id = f.asignacion_id)
  ),
  unidas as (
    select a.*, p.marca_id as primera_id, p.marcado_en as primera, p.sucursal_marca as primera_suc,
           s.marca_id as salida_id, s.marcado_en as salida_t, s.sucursal_marca as salida_suc,
           (s.marca_id is null and (p.tipo = 'salida' or p.marcado_en > a.inicio + (a.fin - a.inicio) / 2)) as solo_salida
    from _asig a
    join primeras p on p.asignacion_id = a.asignacion_id
    left join salidas s on s.asignacion_id = a.asignacion_id
  ),
  tiempos as (
    select u.*,
           case when u.solo_salida then null else u.primera_id end as e_id,
           case when u.solo_salida then null else u.primera end as e,
           case when u.solo_salida then u.primera_id else u.salida_id end as s_id,
           case when u.solo_salida then u.primera else u.salida_t end as s,
           case when u.solo_salida then u.primera_suc else u.salida_suc end as s_suc,
           case when u.solo_salida then null else u.primera_suc end as e_suc
    from unidas u
  )
  select t.asignacion_id, t.colaborador_id, t.fecha, t.sucursal_id, t.turno, t.inicio, t.fin, t.procesar,
         t.e_id, t.s_id,
         case when t.e is not null and t.e > t.inicio
              then floor(extract(epoch from (t.e - t.inicio)) / 60)::int else 0 end as min_tardanza,
         case when t.e is null then null
              when t.e <= t.inicio then 'puntual'::clasif_entrada
              when extract(epoch from (t.e - t.inicio)) <= t.gracia * 60 then 'dentro_gracia'::clasif_entrada
              else 'tardanza'::clasif_entrada end as clasif_entrada,
         case when t.s is null then null
              when t.s < t.fin - make_interval(mins => t.gracia::int) then 'anticipada'::clasif_salida
              else 'normal'::clasif_salida end as clasif_salida,
         case when t.e is not null and t.s is not null
              then floor(greatest(0, extract(epoch from (least(t.s, t.fin) - greatest(t.e, t.inicio)))) / 60)::int
              else 0 end as min_trabajados,
         case when t.s is not null and t.s < t.fin
              then floor(extract(epoch from (t.fin - t.s)) / 60)::int else 0 end as min_anticipada,
         case when t.s is not null and t.s > t.fin
                   and floor(extract(epoch from (t.s - t.fin)) / 60) >= t.extra_minimo
              then floor(extract(epoch from (t.s - t.fin)) / 60)::int else 0 end as min_extra,
         t.gracia,
         case
           when t.e is null or t.s is null then 'incompleta'::estado_jornada
           when (t.e_suc is not null and t.e_suc <> t.sucursal_id)
             or (t.s_suc is not null and t.s_suc <> t.sucursal_id)
             or t.e < t.inicio - interval '120 minutes'
             or t.e > t.inicio + (t.fin - t.inicio) / 2 then 'por_confirmar'::estado_jornada
           else 'ok'::estado_jornada
         end as estado,
         (t.fin + make_interval(mins => t.posterior::int) <= p_ahora) as cerrado
  from tiempos t;

  -- 5
  insert into jornadas (asignacion_id, colaborador_id, sucursal_id, fecha, marcacion_entrada_id, marcacion_salida_id,
                        minutos_trabajados, minutos_tardanza, minutos_faltantes, clasif_entrada, clasif_salida, estado)
  select c.asignacion_id, c.colaborador_id, c.sucursal_id, c.fecha, c.e_id, c.s_id,
         c.min_trabajados, c.min_tardanza,
         case when c.estado = 'incompleta' then 0
              else (case when c.clasif_entrada = 'tardanza' then c.min_tardanza else 0 end)
                 + (case when c.clasif_salida = 'anticipada' then c.min_anticipada else 0 end) end,
         c.clasif_entrada, c.clasif_salida, c.estado
  from _calc c
  where c.procesar and c.cerrado
  on conflict (colaborador_id, fecha) do update set
    asignacion_id = excluded.asignacion_id,
    sucursal_id = excluded.sucursal_id,
    marcacion_entrada_id = excluded.marcacion_entrada_id,
    marcacion_salida_id = excluded.marcacion_salida_id,
    minutos_trabajados = excluded.minutos_trabajados,
    minutos_tardanza = excluded.minutos_tardanza,
    minutos_faltantes = excluded.minutos_faltantes,
    clasif_entrada = excluded.clasif_entrada,
    clasif_salida = excluded.clasif_salida,
    estado = excluded.estado;
  get diagnostics n_jornadas = row_count;

  -- 6
  create temp table _huerfanas on commit drop as
  select distinct on (m.colaborador_id, (m.marcado_en at time zone 'America/Guatemala')::date)
         m.colaborador_id,
         (m.marcado_en at time zone 'America/Guatemala')::date as fecha,
         m.id as marca_id, m.marcado_en, m.tipo,
         coalesce(m.sucursal_id, c.sucursal_base_id) as sucursal_id
  from _marcas m
  join colaboradores c on c.id = m.colaborador_id
  where not exists (select 1 from _asignada x where x.marca_id = m.id)
    and (m.marcado_en at time zone 'America/Guatemala')::date between p_desde and p_hasta
    and not exists (select 1 from periodos_planilla pp
                    where pp.estado = 'cerrado'
                      and (m.marcado_en at time zone 'America/Guatemala')::date between pp.fecha_inicio and pp.fecha_fin)
  order by m.colaborador_id, (m.marcado_en at time zone 'America/Guatemala')::date, m.marcado_en;

  insert into jornadas (asignacion_id, colaborador_id, sucursal_id, fecha, marcacion_entrada_id, marcacion_salida_id,
                        minutos_trabajados, minutos_tardanza, minutos_faltantes, estado)
  select null, h.colaborador_id, h.sucursal_id, h.fecha,
         case when h.tipo = 'salida' then null else h.marca_id end,
         case when h.tipo = 'salida' then h.marca_id else s.id end,
         case when h.tipo = 'salida' then 0
              else coalesce(floor(extract(epoch from (s.marcado_en - h.marcado_en)) / 60)::int, 0) end,
         0, 0, 'sin_programacion'
  from _huerfanas h
  left join lateral (
    select m2.id, m2.marcado_en
    from _marcas m2
    where m2.colaborador_id = h.colaborador_id
      and (m2.marcado_en at time zone 'America/Guatemala')::date = h.fecha
      and not exists (select 1 from _asignada x where x.marca_id = m2.id)
      and m2.marcado_en >= h.marcado_en + interval '30 minutes'
    order by m2.marcado_en
    limit 1
  ) s on true
  on conflict (colaborador_id, fecha) do update set
    sucursal_id = excluded.sucursal_id,
    marcacion_entrada_id = excluded.marcacion_entrada_id,
    marcacion_salida_id = excluded.marcacion_salida_id,
    minutos_trabajados = excluded.minutos_trabajados
    where jornadas.asignacion_id is null and jornadas.estado = 'sin_programacion';
  get diagnostics n_sin_programacion = row_count;

  -- 7
  with retiradas as (
    delete from ausencias au
    using _asignada x
    where au.asignacion_id = x.asignacion_id and au.estado = 'sin_justificar'
    returning au.colaborador_id, au.fecha
  )
  update alertas al
  set estado = 'resuelta', resuelta_en = now()
  from retiradas r
  where al.tipo = 'ausencia' and al.estado = 'abierta'
    and al.colaborador_id = r.colaborador_id and al.fecha = r.fecha;

  insert into ausencias (asignacion_id, colaborador_id, fecha)
  select a.asignacion_id, a.colaborador_id, a.fecha
  from _asig a
  where a.procesar
    and not a.con_licencia
    and p_ahora >= a.inicio + make_interval(mins => a.ausencia::int)
    and not exists (select 1 from _asignada x where x.asignacion_id = a.asignacion_id)
  on conflict (asignacion_id) do nothing;
  get diagnostics n_ausencias = row_count;

  -- 8
  insert into horas_extra (jornada_id, minutos_detectados)
  select j.id, c.min_extra
  from _calc c
  join jornadas j on j.colaborador_id = c.colaborador_id and j.fecha = c.fecha
  where c.procesar and c.cerrado and c.min_extra > 0 and c.estado <> 'incompleta'
  on conflict (jornada_id) do update set minutos_detectados = excluded.minutos_detectados
    where horas_extra.estado = 'pendiente';
  get diagnostics n_extras = row_count;

  delete from horas_extra h
  using jornadas j, _calc c
  where h.jornada_id = j.id and j.colaborador_id = c.colaborador_id and j.fecha = c.fecha
    and c.procesar and c.cerrado and c.min_extra = 0 and h.estado = 'pendiente';

  -- 9
  insert into alertas (tipo, colaborador_id, fecha, detalle)
  select v.tipo, v.colaborador_id, v.fecha, v.detalle
  from (
    select case j.estado when 'por_confirmar' then 'por_confirmar'::tipo_alerta
                         when 'incompleta' then 'marcacion_faltante'::tipo_alerta
                         else 'sin_programacion'::tipo_alerta end as tipo,
           j.colaborador_id, j.fecha, jsonb_build_object('jornada_id', j.id) as detalle
    from jornadas j
    where j.fecha between p_desde and p_hasta and j.estado in ('por_confirmar', 'incompleta', 'sin_programacion')
    union all
    select 'ausencia'::tipo_alerta, au.colaborador_id, au.fecha, jsonb_build_object('ausencia_id', au.id)
    from ausencias au
    where au.fecha between p_desde and p_hasta and au.estado = 'sin_justificar'
  ) v
  where not exists (
    select 1 from alertas al
    where al.tipo = v.tipo and al.colaborador_id = v.colaborador_id and al.fecha = v.fecha and al.estado = 'abierta'
  );

  insert into bitacora (usuario_id, accion, tabla, detalle)
  values (
    p_usuario, 'calcular', 'jornadas',
    jsonb_build_object('desde', p_desde, 'hasta', p_hasta, 'jornadas', n_jornadas,
                       'sin_programacion', n_sin_programacion, 'ausencias', n_ausencias, 'horas_extra', n_extras)
  );

  return jsonb_build_object('jornadas', n_jornadas, 'sin_programacion', n_sin_programacion,
                            'ausencias', n_ausencias, 'horas_extra', n_extras);
end;
$$;

revoke execute on function calcular_jornadas(date, date, uuid, timestamptz) from public, anon, authenticated;

notify pgrst, 'reload schema';

-- correccion de cerrar_planilla: no se puede cerrar una quincena sin calcular

create or replace function cerrar_planilla(p_inicio date, p_fin date, p_usuario uuid) returns jsonb
language plpgsql as $$
declare
  v_periodo uuid;
  v_incompletas int;
  v_confirmar int;
  v_ausencias int;
  v_extras int;
  v_descuentos int;
  v_sin_calcular int;
  v_persona jsonb;
  v_boleta uuid;
  v_linea jsonb;
  v_boletas int := 0;
  v_neto numeric := 0;
  v_pendientes text[] := '{}';
begin
  if p_fin < p_inicio or p_fin - p_inicio > 31 then
    raise exception 'El periodo debe ser de 1 a 32 dias' using errcode = '22023';
  end if;
  if exists (select 1 from periodos_planilla
             where fecha_inicio <= p_fin and fecha_fin >= p_inicio) then
    raise exception 'Esa quincena ya esta cerrada' using errcode = '55000';
  end if;

  select count(*) into v_incompletas from jornadas where fecha between p_inicio and p_fin and estado = 'incompleta';
  select count(*) into v_confirmar from jornadas where fecha between p_inicio and p_fin and estado = 'por_confirmar';
  select count(*) into v_ausencias from ausencias where fecha between p_inicio and p_fin and estado = 'sin_justificar';
  select count(*) into v_extras from horas_extra h join jornadas j on j.id = h.jornada_id
   where j.fecha between p_inicio and p_fin and h.estado = 'pendiente';
  select count(*) into v_descuentos from descuentos_tiempo
   where fecha_inicio = p_inicio and fecha_fin = p_fin and estado = 'pendiente';

  select count(*) into v_sin_calcular from asignaciones_vigentes a
   where a.fecha between p_inicio and p_fin and a.estado = 'programado' and a.turno_id is not null
     and not exists (select 1 from jornadas j
                     where j.colaborador_id = a.colaborador_id and j.fecha = a.fecha and j.estado <> 'sin_programacion')
     and not exists (select 1 from ausencias au where au.asignacion_id = a.id);

  if v_sin_calcular > 0 then
    v_pendientes := v_pendientes || (v_sin_calcular || ' turno(s) programado(s) sin calcular: pulsa "Calcular jornadas"');
  end if;
  if v_incompletas > 0 then v_pendientes := v_pendientes || (v_incompletas || ' jornada(s) incompleta(s)'); end if;
  if v_confirmar > 0 then v_pendientes := v_pendientes || (v_confirmar || ' jornada(s) por confirmar'); end if;
  if v_ausencias > 0 then v_pendientes := v_pendientes || (v_ausencias || ' ausencia(s) sin justificar'); end if;
  if v_extras > 0 then v_pendientes := v_pendientes || (v_extras || ' hora(s) extra por decidir'); end if;
  if v_descuentos > 0 then v_pendientes := v_pendientes || (v_descuentos || ' descuento(s) por decidir'); end if;
  if array_length(v_pendientes, 1) > 0 then
    raise exception 'Todavia hay pendientes: %', array_to_string(v_pendientes, ', ') using errcode = '22023';
  end if;

  insert into periodos_planilla (fecha_inicio, fecha_fin, estado, cerrado_por, cerrado_en, aprobado_por)
  values (p_inicio, p_fin, 'cerrado', p_usuario, now(), p_usuario)
  returning id into v_periodo;

  for v_persona in select * from jsonb_array_elements(calcular_planilla(p_inicio, p_fin))
  loop
    continue when jsonb_array_length(v_persona -> 'lineas') = 0;

    insert into boletas (periodo_id, colaborador_id, total_ingresos, total_descuentos, neto, snapshot_valores)
    values (v_periodo, (v_persona ->> 'colaborador_id')::uuid, (v_persona ->> 'total_ingresos')::numeric,
            (v_persona ->> 'total_descuentos')::numeric, (v_persona ->> 'neto')::numeric,
            v_persona - 'lineas')
    returning id into v_boleta;

    for v_linea in select * from jsonb_array_elements(v_persona -> 'lineas')
    loop
      insert into boleta_detalles (boleta_id, tipo, concepto, cantidad, valor_unitario, monto)
      values (v_boleta, (v_linea ->> 'tipo')::tipo_detalle_boleta, v_linea ->> 'concepto',
              (v_linea ->> 'cantidad')::numeric, (v_linea ->> 'valor_unitario')::numeric,
              (v_linea ->> 'monto')::numeric);
    end loop;

    v_boletas := v_boletas + 1;
    v_neto := v_neto + (v_persona ->> 'neto')::numeric;
  end loop;

  if v_boletas = 0 or v_neto <= 0 then
    raise exception 'No hay nada que pagar en esa quincena: revisa que las jornadas esten calculadas' using errcode = '22023';
  end if;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'cerrar', 'periodos_planilla', v_periodo,
          jsonb_build_object('inicio', p_inicio, 'fin', p_fin, 'boletas', v_boletas, 'neto_total', v_neto));

  return jsonb_build_object('periodo_id', v_periodo, 'boletas', v_boletas, 'neto_total', v_neto);
end;
$$;

revoke execute on function cerrar_planilla(date, date, uuid) from public, anon, authenticated;

notify pgrst, 'reload schema';

-- baja, reactivacion y licencias (permisos y suspensiones) de colaboradores

create function dar_de_baja(p_colaborador uuid, p_fecha date, p_motivo text, p_usuario uuid) returns jsonb
language plpgsql as $$
declare
  v_periodo periodos_laborales%rowtype;
  v_motivo text := nullif(trim(coalesce(p_motivo, '')), '');
  v_liberadas int;
begin
  if not exists (select 1 from colaboradores where id = p_colaborador) then
    raise exception 'El colaborador no existe' using errcode = 'P0002';
  end if;
  select * into v_periodo from periodos_laborales
   where colaborador_id = p_colaborador and fecha_baja is null
   order by fecha_ingreso desc limit 1 for update;
  if not found then
    raise exception 'Ese colaborador ya esta de baja' using errcode = '22023';
  end if;
  if v_motivo is null then
    raise exception 'El motivo de la baja es obligatorio' using errcode = '22023';
  end if;
  if p_fecha < v_periodo.fecha_ingreso then
    raise exception 'La baja no puede ser antes de su ingreso (%)', v_periodo.fecha_ingreso using errcode = '22023';
  end if;
  if exists (select 1 from boletas b join periodos_planilla pp on pp.id = b.periodo_id
             where b.colaborador_id = p_colaborador and pp.fecha_inicio > p_fecha) then
    raise exception 'Ya tiene boletas de quincenas posteriores a esa fecha' using errcode = '55000';
  end if;

  update periodos_laborales set fecha_baja = p_fecha, motivo_baja = v_motivo where id = v_periodo.id;

  update asignaciones_turno set estado = 'a_reasignar'
   where colaborador_id = p_colaborador and fecha > p_fecha and estado = 'programado';
  get diagnostics v_liberadas = row_count;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'baja', 'colaboradores', p_colaborador,
          jsonb_build_object('fecha', p_fecha, 'motivo', v_motivo, 'turnos_liberados', v_liberadas));

  return jsonb_build_object('turnos_liberados', v_liberadas);
end;
$$;

create function reactivar_colaborador(p_colaborador uuid, p_fecha date, p_usuario uuid) returns void
language plpgsql as $$
declare
  v_ultimo periodos_laborales%rowtype;
begin
  if not exists (select 1 from colaboradores where id = p_colaborador) then
    raise exception 'El colaborador no existe' using errcode = 'P0002';
  end if;
  select * into v_ultimo from periodos_laborales
   where colaborador_id = p_colaborador order by fecha_ingreso desc limit 1 for update;
  if found and v_ultimo.fecha_baja is null then
    raise exception 'Ese colaborador ya esta activo' using errcode = '22023';
  end if;
  if found and p_fecha <= v_ultimo.fecha_baja then
    raise exception 'El reingreso debe ser despues de la baja (%)', v_ultimo.fecha_baja using errcode = '22023';
  end if;

  insert into periodos_laborales (colaborador_id, fecha_ingreso) values (p_colaborador, p_fecha);

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'reactivar', 'colaboradores', p_colaborador, jsonb_build_object('fecha', p_fecha));
end;
$$;

create function registrar_licencia(
  p_colaborador uuid,
  p_tipo uuid,
  p_desde date,
  p_hasta date,
  p_motivo text,
  p_usuario uuid
) returns uuid
language plpgsql as $$
declare
  v_id uuid;
  v_motivo text := nullif(trim(coalesce(p_motivo, '')), '');
  v_ausencias int;
begin
  if not exists (select 1 from colaboradores where id = p_colaborador) then
    raise exception 'El colaborador no existe' using errcode = 'P0002';
  end if;
  if not exists (select 1 from tipos_ausencia where id = p_tipo) then
    raise exception 'El tipo no existe' using errcode = 'P0002';
  end if;
  if p_hasta < p_desde or p_hasta - p_desde > 366 then
    raise exception 'Las fechas no son validas (maximo un ano)' using errcode = '22023';
  end if;
  if v_motivo is null then
    raise exception 'El motivo es obligatorio' using errcode = '22023';
  end if;
  if exists (select 1 from periodos_planilla where estado = 'cerrado' and fecha_inicio <= p_hasta and fecha_fin >= p_desde) then
    raise exception 'Esas fechas tocan una quincena ya cerrada' using errcode = '55000';
  end if;
  if exists (select 1 from licencias where colaborador_id = p_colaborador
             and fecha_desde <= p_hasta and fecha_hasta >= p_desde) then
    raise exception 'Ya tiene una licencia en esas fechas' using errcode = '22023';
  end if;

  insert into licencias (colaborador_id, tipo_ausencia_id, fecha_desde, fecha_hasta, motivo, registrado_por)
  values (p_colaborador, p_tipo, p_desde, p_hasta, v_motivo, p_usuario)
  returning id into v_id;

  update ausencias
     set estado = case when (select nombre from tipos_ausencia where id = p_tipo) = 'Falta injustificada'
                       then 'reclasificada'::estado_ausencia else 'justificada'::estado_ausencia end,
         tipo_ausencia_id = p_tipo, licencia_id = v_id
   where colaborador_id = p_colaborador and fecha between p_desde and p_hasta and estado = 'sin_justificar';
  get diagnostics v_ausencias = row_count;

  update alertas set estado = 'resuelta', resuelta_por = p_usuario, resuelta_en = now()
   where tipo = 'ausencia' and estado = 'abierta' and colaborador_id = p_colaborador
     and fecha between p_desde and p_hasta;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'crear', 'licencias', v_id,
          jsonb_build_object('colaborador_id', p_colaborador, 'tipo', p_tipo, 'desde', p_desde, 'hasta', p_hasta,
                             'motivo', v_motivo, 'ausencias_justificadas', v_ausencias));
  return v_id;
end;
$$;

create function anular_licencia(p_licencia uuid, p_usuario uuid) returns void
language plpgsql as $$
declare
  v_lic licencias%rowtype;
begin
  select * into v_lic from licencias where id = p_licencia for update;
  if not found then
    raise exception 'La licencia no existe' using errcode = 'P0002';
  end if;
  if exists (select 1 from periodos_planilla where estado = 'cerrado'
             and fecha_inicio <= v_lic.fecha_hasta and fecha_fin >= v_lic.fecha_desde) then
    raise exception 'Esa licencia toca una quincena ya cerrada' using errcode = '55000';
  end if;

  update ausencias set estado = 'sin_justificar', tipo_ausencia_id = null, licencia_id = null
   where licencia_id = p_licencia;
  delete from licencias where id = p_licencia;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'anular', 'licencias', p_licencia,
          jsonb_build_object('colaborador_id', v_lic.colaborador_id, 'desde', v_lic.fecha_desde, 'hasta', v_lic.fecha_hasta));
end;
$$;

revoke execute on function dar_de_baja(uuid, date, text, uuid) from public, anon, authenticated;
revoke execute on function reactivar_colaborador(uuid, date, uuid) from public, anon, authenticated;
revoke execute on function registrar_licencia(uuid, uuid, date, date, text, uuid) from public, anon, authenticated;
revoke execute on function anular_licencia(uuid, uuid) from public, anon, authenticated;

notify pgrst, 'reload schema';

-- alertas laborales automaticas y resolver alertas (bloque de alertas en inicio)

create function revisar_alertas(p_desde date, p_hasta date) returns int
language plpgsql as $$
declare
  v_tardanzas numeric := coalesce(parametro_en('tardanzas_alerta_quincena', p_hasta), 3);
  v_extra_dia numeric := coalesce(parametro_en('extra_maximo_dia_minutos', p_hasta), 120);
  v_extra_sem numeric := coalesce(parametro_en('extra_maximo_semana_minutos', p_hasta), 720);
  v_descanso numeric := coalesce(parametro_en('descanso_minimo_horas', p_hasta), 8);
  v_inicio date := case when extract(day from p_desde) <= 15 then date_trunc('month', p_desde)::date
                        else date_trunc('month', p_desde)::date + 15 end;
  v_total int := 0;
  n int;
begin
  -- tardanzas frecuentes por quincena
  insert into alertas (tipo, colaborador_id, fecha, detalle)
  select 'tardanzas_frecuentes', q.colaborador_id, q.inicio,
         jsonb_build_object('tardanzas', q.total, 'minimo', v_tardanzas)
  from (
    select j.colaborador_id,
           case when extract(day from j.fecha) <= 15 then date_trunc('month', j.fecha)::date
                else date_trunc('month', j.fecha)::date + 15 end as inicio,
           count(*) as total
    from jornadas j
    where j.fecha between v_inicio and p_hasta + 16 and j.clasif_entrada = 'tardanza'
    group by 1, 2
  ) q
  where q.total >= v_tardanzas and q.inicio <= p_hasta
    and not exists (select 1 from alertas a where a.tipo = 'tardanzas_frecuentes'
                    and a.colaborador_id = q.colaborador_id and a.fecha = q.inicio);
  get diagnostics n = row_count; v_total := v_total + n;

  -- exceso de horas extra en un dia
  insert into alertas (tipo, colaborador_id, fecha, detalle)
  select 'exceso_horas_extra', j.colaborador_id, j.fecha,
         jsonb_build_object('alcance', 'dia', 'minutos', h.minutos_detectados, 'maximo', v_extra_dia)
  from horas_extra h join jornadas j on j.id = h.jornada_id
  where j.fecha between p_desde and p_hasta and h.minutos_detectados > v_extra_dia
    and not exists (select 1 from alertas a where a.tipo = 'exceso_horas_extra'
                    and a.colaborador_id = j.colaborador_id and a.fecha = j.fecha and a.detalle ->> 'alcance' = 'dia');
  get diagnostics n = row_count; v_total := v_total + n;

  -- exceso de horas extra en una semana (lunes a domingo)
  insert into alertas (tipo, colaborador_id, fecha, detalle)
  select 'exceso_horas_extra', w.colaborador_id, w.semana,
         jsonb_build_object('alcance', 'semana', 'minutos', w.minutos, 'maximo', v_extra_sem)
  from (
    select j.colaborador_id, date_trunc('week', j.fecha)::date as semana, sum(h.minutos_detectados) as minutos
    from horas_extra h join jornadas j on j.id = h.jornada_id
    where j.fecha between p_desde - 7 and p_hasta + 7
    group by 1, 2
  ) w
  where w.minutos > v_extra_sem and w.semana between p_desde - 6 and p_hasta
    and not exists (select 1 from alertas a where a.tipo = 'exceso_horas_extra'
                    and a.colaborador_id = w.colaborador_id and a.fecha = w.semana and a.detalle ->> 'alcance' = 'semana');
  get diagnostics n = row_count; v_total := v_total + n;

  -- descanso insuficiente entre un turno y el siguiente
  insert into alertas (tipo, colaborador_id, fecha, detalle)
  select 'descanso_insuficiente', t.colaborador_id, t.fecha,
         jsonb_build_object('horas', round((extract(epoch from (t.entrada - t.salida_anterior)) / 3600)::numeric, 1),
                            'minimo', v_descanso)
  from (
    select j.colaborador_id, j.fecha, e.marcado_en as entrada,
           lag(s.marcado_en) over (partition by j.colaborador_id order by j.fecha) as salida_anterior
    from jornadas j
    left join marcaciones e on e.id = j.marcacion_entrada_id
    left join marcaciones s on s.id = j.marcacion_salida_id
    where j.fecha between p_desde - 3 and p_hasta and j.estado in ('ok', 'por_confirmar')
  ) t
  where t.fecha between p_desde and p_hasta and t.entrada is not null and t.salida_anterior is not null
    and t.entrada - t.salida_anterior < make_interval(hours => v_descanso::int)
    and not exists (select 1 from alertas a where a.tipo = 'descanso_insuficiente'
                    and a.colaborador_id = t.colaborador_id and a.fecha = t.fecha);
  get diagnostics n = row_count; v_total := v_total + n;

  return v_total;
end;
$$;

create function resolver_alerta(p_alerta uuid, p_usuario uuid) returns void
language plpgsql as $$
begin
  update alertas set estado = 'resuelta', resuelta_por = p_usuario, resuelta_en = now()
   where id = p_alerta and estado = 'abierta';
  if not found then
    if not exists (select 1 from alertas where id = p_alerta) then
      raise exception 'La alerta no existe' using errcode = 'P0002';
    end if;
    return;
  end if;
  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'resolver', 'alertas', p_alerta, '{}'::jsonb);
end;
$$;

create or replace function calcular_jornadas(
  p_desde date,
  p_hasta date,
  p_usuario uuid,
  p_ahora timestamptz default now()
) returns jsonb
language plpgsql as $$
declare
  n_jornadas int;
  n_sin_programacion int;
  n_ausencias int;
  n_extras int;
begin
  if p_hasta < p_desde then
    raise exception 'El rango de fechas no es valido' using errcode = '22023';
  end if;
  if p_hasta - p_desde > 62 then
    raise exception 'El rango no puede pasar de 62 dias' using errcode = '22023';
  end if;

  drop table if exists _asig, _marcas, _asignada, _calc, _huerfanas;

  -- 1
  create temp table _asig on commit drop as
  select a.id as asignacion_id, a.colaborador_id, a.fecha, a.sucursal_id, a.turno_id, t.nombre as turno,
         (a.fecha + t.hora_inicio) at time zone 'America/Guatemala' as inicio,
         ((a.fecha + t.hora_inicio) at time zone 'America/Guatemala')
           + make_interval(secs => (case when t.cruza_medianoche
                                         then extract(epoch from (t.hora_fin - t.hora_inicio)) + 86400
                                         else extract(epoch from (t.hora_fin - t.hora_inicio)) end)::double precision) as fin,
         coalesce(parametro_en('gracia_minutos', a.fecha, a.sucursal_id, a.turno_id), 10) as gracia,
         coalesce(parametro_en('ausencia_minutos', a.fecha, a.sucursal_id, a.turno_id), 60) as ausencia,
         coalesce(parametro_en('extra_minimo_minutos', a.fecha, a.sucursal_id, a.turno_id), 30) as extra_minimo,
         coalesce(parametro_en('sesion_minima_minutos', a.fecha, a.sucursal_id, a.turno_id), 30) as sesion_minima,
         coalesce(parametro_en('ventana_previa_minutos', a.fecha, a.sucursal_id, a.turno_id), 240) as previa,
         coalesce(parametro_en('ventana_posterior_minutos', a.fecha, a.sucursal_id, a.turno_id), 240) as posterior,
         coalesce(parametro_en('ventana_manual_minutos', a.fecha, a.sucursal_id, a.turno_id), 720) as posterior_manual,
         (a.fecha between p_desde and p_hasta
            and not exists (select 1 from periodos_planilla pp
                            where pp.estado = 'cerrado' and a.fecha between pp.fecha_inicio and pp.fecha_fin)) as procesar,
         exists (select 1 from licencias l
                 where l.colaborador_id = a.colaborador_id and a.fecha between l.fecha_desde and l.fecha_hasta) as con_licencia
  from asignaciones_vigentes a
  join turnos t on t.id = a.turno_id
  where a.turno_id is not null
    and a.estado = 'programado'
    and a.fecha between p_desde - 1 and p_hasta + 1;

  -- 2
  create temp table _marcas on commit drop as
  select m.id, coalesce(m.colaborador_id, cd.colaborador_id) as colaborador_id, m.marcado_en, m.tipo, d.sucursal_id,
         m.origen
  from marcaciones m
  left join colaborador_dispositivo cd
    on cd.dispositivo_id = m.dispositivo_id and cd.id_en_dispositivo = m.id_en_dispositivo
  left join dispositivos d on d.id = m.dispositivo_id
  where not m.es_duplicada
    and coalesce(m.colaborador_id, cd.colaborador_id) is not null
    and m.marcado_en >= ((p_desde - 2)::timestamp at time zone 'America/Guatemala')
    and m.marcado_en <  ((p_hasta + 4)::timestamp at time zone 'America/Guatemala');

  -- 3
  create temp table _asignada on commit drop as
  select distinct on (m.id)
         m.id as marca_id, m.colaborador_id, m.marcado_en, m.tipo, m.sucursal_id as sucursal_marca, a.asignacion_id
  from _marcas m
  join _asig a
    on a.colaborador_id = m.colaborador_id
   and m.marcado_en >= a.inicio - make_interval(mins => a.previa::int)
   and m.marcado_en <= a.fin + make_interval(mins => (case when m.origen = 'manual'
                                                         then greatest(a.posterior, a.posterior_manual)
                                                         else a.posterior end)::int)
  order by m.id,
           case when m.marcado_en between a.inicio and a.fin then 0
                else least(abs(extract(epoch from (m.marcado_en - a.inicio))),
                           abs(extract(epoch from (m.marcado_en - a.fin)))) end,
           a.inicio;

  -- 4
  create temp table _calc on commit drop as
  with ordenadas as (
    select x.*, row_number() over (partition by x.asignacion_id order by x.marcado_en, x.marca_id) as rn
    from _asignada x
  ),
  primeras as (
    select * from ordenadas where rn = 1
  ),
  candidatas as (
    select o.asignacion_id, o.marca_id, o.marcado_en, o.sucursal_marca, a.fin, a.gracia,
           min(o.marcado_en) over (partition by o.asignacion_id) as primera_candidata
    from ordenadas o
    join primeras p on p.asignacion_id = o.asignacion_id
    join _asig a on a.asignacion_id = o.asignacion_id
    where o.marcado_en >= p.marcado_en + make_interval(mins => a.sesion_minima::int)
  ),
  salidas_propias as (
    -- salida normal: la primera marca despues de la sesion minima
    select distinct on (c.asignacion_id) c.asignacion_id, c.marca_id, c.marcado_en, c.sucursal_marca
    from candidatas c
    order by c.asignacion_id,
             case when c.primera_candidata < c.fin - make_interval(mins => c.gracia::int)
                  then c.marcado_en end desc nulls last,
             c.marcado_en
  ),
  frontera as (
    -- dos turnos seguidos (noche y manana del dia siguiente): una sola marca en el cambio es la salida
    select distinct on (a.asignacion_id) a.asignacion_id, m.id as marca_id, m.marcado_en,
           m.sucursal_id as sucursal_marca
    from _asig a
    join primeras p on p.asignacion_id = a.asignacion_id
    join _marcas m on m.colaborador_id = a.colaborador_id
    where m.marcado_en between a.fin - make_interval(mins => a.gracia::int)
                           and a.fin + make_interval(mins => a.gracia::int)
      and m.marcado_en >= p.marcado_en + make_interval(mins => a.sesion_minima::int)
      and exists (select 1 from _asig b
                  where b.colaborador_id = a.colaborador_id and b.asignacion_id <> a.asignacion_id
                    and b.inicio between a.fin - interval '1 minute' and a.fin + make_interval(mins => a.gracia::int))
    order by a.asignacion_id, abs(extract(epoch from (m.marcado_en - a.fin)))
  ),
  salidas as (
    select sp.asignacion_id, sp.marca_id, sp.marcado_en, sp.sucursal_marca from salidas_propias sp
    union all
    select f.asignacion_id, f.marca_id, f.marcado_en, f.sucursal_marca from frontera f
    where not exists (select 1 from salidas_propias sp where sp.asignacion_id = f.asignacion_id)
  ),
  unidas as (
    select a.*, p.marca_id as primera_id, p.marcado_en as primera, p.sucursal_marca as primera_suc,
           s.marca_id as salida_id, s.marcado_en as salida_t, s.sucursal_marca as salida_suc,
           (s.marca_id is null and (p.tipo = 'salida' or p.marcado_en > a.inicio + (a.fin - a.inicio) / 2)) as solo_salida
    from _asig a
    join primeras p on p.asignacion_id = a.asignacion_id
    left join salidas s on s.asignacion_id = a.asignacion_id
  ),
  tiempos as (
    select u.*,
           case when u.solo_salida then null else u.primera_id end as e_id,
           case when u.solo_salida then null else u.primera end as e,
           case when u.solo_salida then u.primera_id else u.salida_id end as s_id,
           case when u.solo_salida then u.primera else u.salida_t end as s,
           case when u.solo_salida then u.primera_suc else u.salida_suc end as s_suc,
           case when u.solo_salida then null else u.primera_suc end as e_suc
    from unidas u
  )
  select t.asignacion_id, t.colaborador_id, t.fecha, t.sucursal_id, t.turno, t.inicio, t.fin, t.procesar,
         t.e_id, t.s_id,
         case when t.e is not null and t.e > t.inicio
              then floor(extract(epoch from (t.e - t.inicio)) / 60)::int else 0 end as min_tardanza,
         case when t.e is null then null
              when t.e <= t.inicio then 'puntual'::clasif_entrada
              when extract(epoch from (t.e - t.inicio)) <= t.gracia * 60 then 'dentro_gracia'::clasif_entrada
              else 'tardanza'::clasif_entrada end as clasif_entrada,
         case when t.s is null then null
              when t.s < t.fin - make_interval(mins => t.gracia::int) then 'anticipada'::clasif_salida
              else 'normal'::clasif_salida end as clasif_salida,
         case when t.e is not null and t.s is not null
              then floor(greatest(0, extract(epoch from (least(t.s, t.fin) - greatest(t.e, t.inicio)))) / 60)::int
              else 0 end as min_trabajados,
         case when t.s is not null and t.s < t.fin
              then floor(extract(epoch from (t.fin - t.s)) / 60)::int else 0 end as min_anticipada,
         case when t.s is not null and t.s > t.fin
                   and floor(extract(epoch from (t.s - t.fin)) / 60) >= t.extra_minimo
              then floor(extract(epoch from (t.s - t.fin)) / 60)::int else 0 end as min_extra,
         t.gracia,
         case
           when t.e is null or t.s is null then 'incompleta'::estado_jornada
           when (t.e_suc is not null and t.e_suc <> t.sucursal_id)
             or (t.s_suc is not null and t.s_suc <> t.sucursal_id)
             or t.e < t.inicio - interval '120 minutes'
             or t.e > t.inicio + (t.fin - t.inicio) / 2 then 'por_confirmar'::estado_jornada
           else 'ok'::estado_jornada
         end as estado,
         (t.fin + make_interval(mins => t.posterior::int) <= p_ahora) as cerrado
  from tiempos t;

  -- 5
  insert into jornadas (asignacion_id, colaborador_id, sucursal_id, fecha, marcacion_entrada_id, marcacion_salida_id,
                        minutos_trabajados, minutos_tardanza, minutos_faltantes, clasif_entrada, clasif_salida, estado)
  select c.asignacion_id, c.colaborador_id, c.sucursal_id, c.fecha, c.e_id, c.s_id,
         c.min_trabajados, c.min_tardanza,
         case when c.estado = 'incompleta' then 0
              else (case when c.clasif_entrada = 'tardanza' then c.min_tardanza else 0 end)
                 + (case when c.clasif_salida = 'anticipada' then c.min_anticipada else 0 end) end,
         c.clasif_entrada, c.clasif_salida, c.estado
  from _calc c
  where c.procesar and c.cerrado
  on conflict (colaborador_id, fecha) do update set
    asignacion_id = excluded.asignacion_id,
    sucursal_id = excluded.sucursal_id,
    marcacion_entrada_id = excluded.marcacion_entrada_id,
    marcacion_salida_id = excluded.marcacion_salida_id,
    minutos_trabajados = excluded.minutos_trabajados,
    minutos_tardanza = excluded.minutos_tardanza,
    minutos_faltantes = excluded.minutos_faltantes,
    clasif_entrada = excluded.clasif_entrada,
    clasif_salida = excluded.clasif_salida,
    estado = excluded.estado;
  get diagnostics n_jornadas = row_count;

  -- 6
  create temp table _huerfanas on commit drop as
  select distinct on (m.colaborador_id, (m.marcado_en at time zone 'America/Guatemala')::date)
         m.colaborador_id,
         (m.marcado_en at time zone 'America/Guatemala')::date as fecha,
         m.id as marca_id, m.marcado_en, m.tipo,
         coalesce(m.sucursal_id, c.sucursal_base_id) as sucursal_id
  from _marcas m
  join colaboradores c on c.id = m.colaborador_id
  where not exists (select 1 from _asignada x where x.marca_id = m.id)
    and (m.marcado_en at time zone 'America/Guatemala')::date between p_desde and p_hasta
    and not exists (select 1 from periodos_planilla pp
                    where pp.estado = 'cerrado'
                      and (m.marcado_en at time zone 'America/Guatemala')::date between pp.fecha_inicio and pp.fecha_fin)
  order by m.colaborador_id, (m.marcado_en at time zone 'America/Guatemala')::date, m.marcado_en;

  insert into jornadas (asignacion_id, colaborador_id, sucursal_id, fecha, marcacion_entrada_id, marcacion_salida_id,
                        minutos_trabajados, minutos_tardanza, minutos_faltantes, estado)
  select null, h.colaborador_id, h.sucursal_id, h.fecha,
         case when h.tipo = 'salida' then null else h.marca_id end,
         case when h.tipo = 'salida' then h.marca_id else s.id end,
         case when h.tipo = 'salida' then 0
              else coalesce(floor(extract(epoch from (s.marcado_en - h.marcado_en)) / 60)::int, 0) end,
         0, 0, 'sin_programacion'
  from _huerfanas h
  left join lateral (
    select m2.id, m2.marcado_en
    from _marcas m2
    where m2.colaborador_id = h.colaborador_id
      and (m2.marcado_en at time zone 'America/Guatemala')::date = h.fecha
      and not exists (select 1 from _asignada x where x.marca_id = m2.id)
      and m2.marcado_en >= h.marcado_en + interval '30 minutes'
    order by m2.marcado_en
    limit 1
  ) s on true
  on conflict (colaborador_id, fecha) do update set
    sucursal_id = excluded.sucursal_id,
    marcacion_entrada_id = excluded.marcacion_entrada_id,
    marcacion_salida_id = excluded.marcacion_salida_id,
    minutos_trabajados = excluded.minutos_trabajados
    where jornadas.asignacion_id is null and jornadas.estado = 'sin_programacion';
  get diagnostics n_sin_programacion = row_count;

  -- 7
  with retiradas as (
    delete from ausencias au
    using _asignada x
    where au.asignacion_id = x.asignacion_id and au.estado = 'sin_justificar'
    returning au.colaborador_id, au.fecha
  )
  update alertas al
  set estado = 'resuelta', resuelta_en = now()
  from retiradas r
  where al.tipo = 'ausencia' and al.estado = 'abierta'
    and al.colaborador_id = r.colaborador_id and al.fecha = r.fecha;

  insert into ausencias (asignacion_id, colaborador_id, fecha)
  select a.asignacion_id, a.colaborador_id, a.fecha
  from _asig a
  where a.procesar
    and not a.con_licencia
    and p_ahora >= a.inicio + make_interval(mins => a.ausencia::int)
    and not exists (select 1 from _asignada x where x.asignacion_id = a.asignacion_id)
  on conflict (asignacion_id) do nothing;
  get diagnostics n_ausencias = row_count;

  -- 8
  insert into horas_extra (jornada_id, minutos_detectados)
  select j.id, c.min_extra
  from _calc c
  join jornadas j on j.colaborador_id = c.colaborador_id and j.fecha = c.fecha
  where c.procesar and c.cerrado and c.min_extra > 0 and c.estado <> 'incompleta'
  on conflict (jornada_id) do update set minutos_detectados = excluded.minutos_detectados
    where horas_extra.estado = 'pendiente';
  get diagnostics n_extras = row_count;

  delete from horas_extra h
  using jornadas j, _calc c
  where h.jornada_id = j.id and j.colaborador_id = c.colaborador_id and j.fecha = c.fecha
    and c.procesar and c.cerrado and c.min_extra = 0 and h.estado = 'pendiente';

  -- 9
  insert into alertas (tipo, colaborador_id, fecha, detalle)
  select v.tipo, v.colaborador_id, v.fecha, v.detalle
  from (
    select case j.estado when 'por_confirmar' then 'por_confirmar'::tipo_alerta
                         when 'incompleta' then 'marcacion_faltante'::tipo_alerta
                         else 'sin_programacion'::tipo_alerta end as tipo,
           j.colaborador_id, j.fecha, jsonb_build_object('jornada_id', j.id) as detalle
    from jornadas j
    where j.fecha between p_desde and p_hasta and j.estado in ('por_confirmar', 'incompleta', 'sin_programacion')
    union all
    select 'ausencia'::tipo_alerta, au.colaborador_id, au.fecha, jsonb_build_object('ausencia_id', au.id)
    from ausencias au
    where au.fecha between p_desde and p_hasta and au.estado = 'sin_justificar'
  ) v
  where not exists (
    select 1 from alertas al
    where al.tipo = v.tipo and al.colaborador_id = v.colaborador_id and al.fecha = v.fecha and al.estado = 'abierta'
  );

  perform revisar_alertas(p_desde, p_hasta);

  insert into bitacora (usuario_id, accion, tabla, detalle)
  values (
    p_usuario, 'calcular', 'jornadas',
    jsonb_build_object('desde', p_desde, 'hasta', p_hasta, 'jornadas', n_jornadas,
                       'sin_programacion', n_sin_programacion, 'ausencias', n_ausencias, 'horas_extra', n_extras)
  );

  return jsonb_build_object('jornadas', n_jornadas, 'sin_programacion', n_sin_programacion,
                            'ausencias', n_ausencias, 'horas_extra', n_extras);
end;
$$;

revoke execute on function calcular_jornadas(date, date, uuid, timestamptz) from public, anon, authenticated;

notify pgrst, 'reload schema';

revoke execute on function revisar_alertas(date, date) from public, anon, authenticated;
revoke execute on function resolver_alerta(uuid, uuid) from public, anon, authenticated;
revoke execute on function calcular_jornadas(date, date, uuid, timestamptz) from public, anon, authenticated;

notify pgrst, 'reload schema';

-- endurecimiento de seguridad

create trigger bitacora_inmutable
  before update or delete on bitacora
  for each row execute function bloquear_cambios();

create trigger bitacora_sin_vaciar
  before truncate on bitacora
  for each statement execute function bloquear_cambios();

revoke select on dispositivos from anon, authenticated;
grant select (id, sucursal_id, serie, nombre, modelo, activo, ultima_sincronizacion)
  on dispositivos to authenticated;

notify pgrst, 'reload schema';

-- modalidad diurna (oficina / administracion): se paga sin programacion

alter type modalidad_laboral add value if not exists 'diurna';

alter table turnos add column almuerzo_minutos int not null default 0 check (almuerzo_minutos between 0 and 180);
alter table turnos add column de_oficina boolean not null default false;
alter table programaciones add column automatica boolean not null default false;

insert into turnos (nombre, hora_inicio, hora_fin, cruza_medianoche, tipo_jornada, horas_ordinarias, almuerzo_minutos, de_oficina)
values
  ('Oficina', '08:00', '17:00', false, 'diurna', 8, 60, true),
  ('Oficina sábado', '08:00', '12:00', false, 'diurna', 4, 0, true)
on conflict (nombre) do nothing;

-- horario base de la oficina por dia de la semana (0 = domingo ..
create table horario_diurno (
  dia_semana smallint primary key check (dia_semana between 0 and 6),
  turno_id uuid not null references turnos(id),
  trabaja_por_defecto boolean not null
);

insert into horario_diurno (dia_semana, turno_id, trabaja_por_defecto)
select d, (select id from turnos where nombre = case when d = 6 then 'Oficina sábado' else 'Oficina' end), d <> 0
from generate_series(0, 6) as d;

-- excepciones: un dia en que alguien trabaja aunque no le tocaba, o descansa aunque le tocaba
create table dias_diurno (
  colaborador_id uuid not null references colaboradores(id),
  fecha date not null,
  tipo text not null check (tipo in ('trabaja', 'libre')),
  motivo text,
  actualizado_por uuid references profiles(id),
  actualizado_en timestamptz not null default now(),
  primary key (colaborador_id, fecha)
);

alter table horario_diurno enable row level security;
create policy lectura_rrhh_jefe on horario_diurno for select to authenticated
  using (rol_actual() in ('rrhh', 'jefe'));
alter table dias_diurno enable row level security;
create policy lectura_rrhh_jefe on dias_diurno for select to authenticated
  using (rol_actual() in ('rrhh', 'jefe'));

-- convierte el horario de oficina en asignaciones reales para el rango pedido
create function materializar_oficina(p_desde date, p_hasta date) returns void
language plpgsql as $$
declare
  v_lunes date;
  v_programacion uuid;
begin
  for v_lunes in
    select distinct (d::date - ((extract(isodow from d)::int) - 1)) from generate_series(p_desde::timestamp, p_hasta::timestamp, interval '1 day') d
  loop
    select id into v_programacion from programaciones
     where automatica and fecha_inicio = v_lunes order by version desc limit 1;
    if v_programacion is null then
      insert into programaciones (tipo, fecha_inicio, fecha_fin, version, estado, publicada_en, automatica)
      values ('semanal', v_lunes, v_lunes + 6, 1000, 'publicada', now(), true)
      returning id into v_programacion;
    end if;

    create temp table _debe_trabajar on commit drop as
    select c.id as colaborador_id, c.sucursal_base_id as sucursal_id, d::date as fecha, h.turno_id
    from colaboradores c
    cross join generate_series(greatest(v_lunes, p_desde)::timestamp, least(v_lunes + 6, p_hasta)::timestamp, interval '1 day') d
    join horario_diurno h on h.dia_semana = extract(dow from d)::int
    left join dias_diurno x on x.colaborador_id = c.id and x.fecha = d::date
    where c.modalidad = 'diurna'
      and exists (select 1 from periodos_laborales pl
                  where pl.colaborador_id = c.id and d::date >= pl.fecha_ingreso
                    and (pl.fecha_baja is null or d::date <= pl.fecha_baja))
      and coalesce(x.tipo = 'trabaja', x.tipo is null and h.trabaja_por_defecto, false)
      and not exists (select 1 from periodos_planilla pp
                      where pp.estado = 'cerrado' and d::date between pp.fecha_inicio and pp.fecha_fin);

    insert into asignaciones_turno (programacion_id, colaborador_id, fecha, turno_id, sucursal_id)
    select v_programacion, t.colaborador_id, t.fecha, t.turno_id, t.sucursal_id from _debe_trabajar t
    on conflict (programacion_id, colaborador_id, fecha) do update set turno_id = excluded.turno_id
      where asignaciones_turno.turno_id is distinct from excluded.turno_id
        and not exists (select 1 from jornadas j where j.asignacion_id = asignaciones_turno.id);

    -- lo que ya no corresponde (paso a libre, o dejo de ser diurna) y no tiene jornada ni ausencia
    delete from asignaciones_turno a
    where a.programacion_id = v_programacion
      and a.fecha between p_desde and p_hasta
      and not exists (select 1 from _debe_trabajar t where t.colaborador_id = a.colaborador_id and t.fecha = a.fecha)
      and not exists (select 1 from periodos_planilla pp
                      where pp.estado = 'cerrado' and a.fecha between pp.fecha_inicio and pp.fecha_fin)
      and not exists (select 1 from jornadas j where j.asignacion_id = a.id)
      and not exists (select 1 from ausencias au where au.asignacion_id = a.id)
      and not exists (select 1 from cambios_turno ct where ct.asignacion_id = a.id);

    drop table _debe_trabajar;
  end loop;
end;
$$;

-- rr hh marca que una persona trabaja o descansa un dia (p_tipo null quita la excepcion)
create function guardar_dia_diurno(
  p_colaborador uuid,
  p_fecha date,
  p_tipo text,
  p_motivo text,
  p_usuario uuid
) returns jsonb
language plpgsql as $$
declare
  v_modalidad modalidad_laboral;
begin
  select modalidad into v_modalidad from colaboradores where id = p_colaborador;
  if not found then
    raise exception 'El colaborador no existe' using errcode = 'P0002';
  end if;
  if v_modalidad <> 'diurna' then
    raise exception 'Solo las personas con modalidad diurna se manejan aqui' using errcode = '22023';
  end if;
  if p_tipo is not null and p_tipo not in ('trabaja', 'libre') then
    raise exception 'El tipo debe ser trabaja o libre' using errcode = '22023';
  end if;
  if exists (select 1 from periodos_planilla pp
             where pp.estado = 'cerrado' and p_fecha between pp.fecha_inicio and pp.fecha_fin) then
    raise exception 'Esa quincena ya está cerrada' using errcode = '55000';
  end if;

  if p_tipo is null then
    delete from dias_diurno where colaborador_id = p_colaborador and fecha = p_fecha;
  else
    insert into dias_diurno (colaborador_id, fecha, tipo, motivo, actualizado_por, actualizado_en)
    values (p_colaborador, p_fecha, p_tipo, nullif(p_motivo, ''), p_usuario, now())
    on conflict (colaborador_id, fecha) do update
      set tipo = excluded.tipo, motivo = excluded.motivo,
          actualizado_por = excluded.actualizado_por, actualizado_en = excluded.actualizado_en;
  end if;

  if p_tipo = 'libre' then
    -- si ese dia ya se habia detectado una ausencia sin justificar, deja de aplicar
    delete from ausencias where colaborador_id = p_colaborador and fecha = p_fecha and estado = 'sin_justificar';
    update alertas set estado = 'resuelta', resuelta_en = now()
     where tipo = 'ausencia' and estado = 'abierta' and colaborador_id = p_colaborador and fecha = p_fecha;
  end if;

  perform materializar_oficina(p_fecha, p_fecha);

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'guardar', 'dias_diurno', p_colaborador,
          jsonb_build_object('fecha', p_fecha, 'tipo', p_tipo, 'motivo', nullif(p_motivo, '')));

  return jsonb_build_object('colaborador_id', p_colaborador, 'fecha', p_fecha, 'tipo', p_tipo);
end;
$$;

revoke execute on function materializar_oficina(date, date) from public, anon, authenticated;
revoke execute on function guardar_dia_diurno(uuid, date, text, text, uuid) from public, anon, authenticated;

create or replace function calcular_jornadas(
  p_desde date,
  p_hasta date,
  p_usuario uuid,
  p_ahora timestamptz default now()
) returns jsonb
language plpgsql as $$
declare
  n_jornadas int;
  n_sin_programacion int;
  n_ausencias int;
  n_extras int;
begin
  if p_hasta < p_desde then
    raise exception 'El rango de fechas no es valido' using errcode = '22023';
  end if;
  if p_hasta - p_desde > 62 then
    raise exception 'El rango no puede pasar de 62 dias' using errcode = '22023';
  end if;

  drop table if exists _asig, _marcas, _asignada, _calc, _huerfanas;

  -- 0
  perform materializar_oficina(p_desde - 1, p_hasta + 1);

  -- 1
  create temp table _asig on commit drop as
  select a.id as asignacion_id, a.colaborador_id, a.fecha, a.sucursal_id, a.turno_id, t.nombre as turno, t.almuerzo_minutos as almuerzo,
         (a.fecha + t.hora_inicio) at time zone 'America/Guatemala' as inicio,
         ((a.fecha + t.hora_inicio) at time zone 'America/Guatemala')
           + make_interval(secs => (case when t.cruza_medianoche
                                         then extract(epoch from (t.hora_fin - t.hora_inicio)) + 86400
                                         else extract(epoch from (t.hora_fin - t.hora_inicio)) end)::double precision) as fin,
         coalesce(parametro_en('gracia_minutos', a.fecha, a.sucursal_id, a.turno_id), 10) as gracia,
         coalesce(parametro_en('ausencia_minutos', a.fecha, a.sucursal_id, a.turno_id), 60) as ausencia,
         coalesce(parametro_en('extra_minimo_minutos', a.fecha, a.sucursal_id, a.turno_id), 30) as extra_minimo,
         coalesce(parametro_en('sesion_minima_minutos', a.fecha, a.sucursal_id, a.turno_id), 30) as sesion_minima,
         coalesce(parametro_en('ventana_previa_minutos', a.fecha, a.sucursal_id, a.turno_id), 240) as previa,
         coalesce(parametro_en('ventana_posterior_minutos', a.fecha, a.sucursal_id, a.turno_id), 240) as posterior,
         coalesce(parametro_en('ventana_manual_minutos', a.fecha, a.sucursal_id, a.turno_id), 720) as posterior_manual,
         (a.fecha between p_desde and p_hasta
            and not exists (select 1 from periodos_planilla pp
                            where pp.estado = 'cerrado' and a.fecha between pp.fecha_inicio and pp.fecha_fin)) as procesar,
         exists (select 1 from licencias l
                 where l.colaborador_id = a.colaborador_id and a.fecha between l.fecha_desde and l.fecha_hasta) as con_licencia
  from asignaciones_vigentes a
  join turnos t on t.id = a.turno_id
  where a.turno_id is not null
    and a.estado = 'programado'
    and a.fecha between p_desde - 1 and p_hasta + 1;

  -- 2
  create temp table _marcas on commit drop as
  select m.id, coalesce(m.colaborador_id, cd.colaborador_id) as colaborador_id, m.marcado_en, m.tipo, d.sucursal_id,
         m.origen
  from marcaciones m
  left join colaborador_dispositivo cd
    on cd.dispositivo_id = m.dispositivo_id and cd.id_en_dispositivo = m.id_en_dispositivo
  left join dispositivos d on d.id = m.dispositivo_id
  where not m.es_duplicada
    and coalesce(m.colaborador_id, cd.colaborador_id) is not null
    and m.marcado_en >= ((p_desde - 2)::timestamp at time zone 'America/Guatemala')
    and m.marcado_en <  ((p_hasta + 4)::timestamp at time zone 'America/Guatemala')
    -- las marcaciones reemplazadas por una correccion ya no cuentan
    and not exists (select 1 from correcciones_marcacion cm where cm.marcacion_original_id = m.id);

  -- 3
  create temp table _asignada on commit drop as
  select distinct on (m.id)
         m.id as marca_id, m.colaborador_id, m.marcado_en, m.tipo, m.sucursal_id as sucursal_marca, a.asignacion_id
  from _marcas m
  join _asig a
    on a.colaborador_id = m.colaborador_id
   and m.marcado_en >= a.inicio - make_interval(mins => a.previa::int)
   and m.marcado_en <= a.fin + make_interval(mins => (case when m.origen = 'manual'
                                                         then greatest(a.posterior, a.posterior_manual)
                                                         else a.posterior end)::int)
  order by m.id,
           case when m.marcado_en between a.inicio and a.fin then 0
                else least(abs(extract(epoch from (m.marcado_en - a.inicio))),
                           abs(extract(epoch from (m.marcado_en - a.fin)))) end,
           a.inicio;

  -- 4
  create temp table _calc on commit drop as
  with ordenadas as (
    select x.*, row_number() over (partition by x.asignacion_id order by x.marcado_en, x.marca_id) as rn
    from _asignada x
  ),
  primeras as (
    select * from ordenadas where rn = 1
  ),
  candidatas as (
    select o.asignacion_id, o.marca_id, o.marcado_en, o.sucursal_marca, a.fin, a.gracia,
           min(o.marcado_en) over (partition by o.asignacion_id) as primera_candidata
    from ordenadas o
    join primeras p on p.asignacion_id = o.asignacion_id
    join _asig a on a.asignacion_id = o.asignacion_id
    where o.marcado_en >= p.marcado_en + make_interval(mins => a.sesion_minima::int)
  ),
  salidas_propias as (
    -- salida normal: la primera marca despues de la sesion minima
    select distinct on (c.asignacion_id) c.asignacion_id, c.marca_id, c.marcado_en, c.sucursal_marca
    from candidatas c
    order by c.asignacion_id,
             case when c.primera_candidata < c.fin - make_interval(mins => c.gracia::int)
                  then c.marcado_en end desc nulls last,
             c.marcado_en
  ),
  frontera as (
    -- dos turnos seguidos (noche y manana del dia siguiente): una sola marca en el cambio es la salida
    select distinct on (a.asignacion_id) a.asignacion_id, m.id as marca_id, m.marcado_en,
           m.sucursal_id as sucursal_marca
    from _asig a
    join primeras p on p.asignacion_id = a.asignacion_id
    join _marcas m on m.colaborador_id = a.colaborador_id
    where m.marcado_en between a.fin - make_interval(mins => a.gracia::int)
                           and a.fin + make_interval(mins => a.gracia::int)
      and m.marcado_en >= p.marcado_en + make_interval(mins => a.sesion_minima::int)
      and exists (select 1 from _asig b
                  where b.colaborador_id = a.colaborador_id and b.asignacion_id <> a.asignacion_id
                    and b.inicio between a.fin - interval '1 minute' and a.fin + make_interval(mins => a.gracia::int))
    order by a.asignacion_id, abs(extract(epoch from (m.marcado_en - a.fin)))
  ),
  salidas as (
    select sp.asignacion_id, sp.marca_id, sp.marcado_en, sp.sucursal_marca from salidas_propias sp
    union all
    select f.asignacion_id, f.marca_id, f.marcado_en, f.sucursal_marca from frontera f
    where not exists (select 1 from salidas_propias sp where sp.asignacion_id = f.asignacion_id)
  ),
  unidas as (
    select a.*, p.marca_id as primera_id, p.marcado_en as primera, p.sucursal_marca as primera_suc,
           s.marca_id as salida_id, s.marcado_en as salida_t, s.sucursal_marca as salida_suc,
           (s.marca_id is null and (p.tipo = 'salida' or p.marcado_en > a.inicio + (a.fin - a.inicio) / 2)) as solo_salida
    from _asig a
    join primeras p on p.asignacion_id = a.asignacion_id
    left join salidas s on s.asignacion_id = a.asignacion_id
  ),
  tiempos as (
    select u.*,
           case when u.solo_salida then null else u.primera_id end as e_id,
           case when u.solo_salida then null else u.primera end as e,
           case when u.solo_salida then u.primera_id else u.salida_id end as s_id,
           case when u.solo_salida then u.primera else u.salida_t end as s,
           case when u.solo_salida then u.primera_suc else u.salida_suc end as s_suc,
           case when u.solo_salida then null else u.primera_suc end as e_suc
    from unidas u
  )
  select t.asignacion_id, t.colaborador_id, t.fecha, t.sucursal_id, t.turno, t.inicio, t.fin, t.procesar,
         t.e_id, t.s_id,
         case when t.e is not null and t.e > t.inicio
              then floor(extract(epoch from (t.e - t.inicio)) / 60)::int else 0 end as min_tardanza,
         case when t.e is null then null
              when t.e <= t.inicio then 'puntual'::clasif_entrada
              when extract(epoch from (t.e - t.inicio)) <= t.gracia * 60 then 'dentro_gracia'::clasif_entrada
              else 'tardanza'::clasif_entrada end as clasif_entrada,
         case when t.s is null then null
              when t.s < t.fin - make_interval(mins => t.gracia::int) then 'anticipada'::clasif_salida
              else 'normal'::clasif_salida end as clasif_salida,
         case when t.e is not null and t.s is not null
              then greatest(0, floor(extract(epoch from (t.fin - t.inicio)) / 60)::int
                   - case when floor(extract(epoch from (t.fin - t.inicio)) / 60) >= 300 then t.almuerzo else 0 end)
              end as min_jornada,
         case when t.e is not null and t.s is not null
              then greatest(0, floor(greatest(0, extract(epoch from (least(t.s, t.fin) - greatest(t.e, t.inicio)))) / 60)::int
                   - case when floor(greatest(0, extract(epoch from (least(t.s, t.fin) - greatest(t.e, t.inicio)))) / 60) >= 300
                          then t.almuerzo else 0 end)
              else 0 end as min_trabajados,
         case when t.s is not null and t.s < t.fin
              then floor(extract(epoch from (t.fin - t.s)) / 60)::int else 0 end as min_anticipada,
         -- las horas extra no acumulan minutos: solo cuenta la hora completa
         case when t.s is not null and t.s > t.fin
                   and floor(extract(epoch from (t.s - t.fin)) / 60) >= 60
              then floor(extract(epoch from (t.s - t.fin)) / 60)::int / 60 * 60 else 0 end as min_extra,
         t.gracia,
         case
           when t.e is null or t.s is null then 'incompleta'::estado_jornada
           when (t.e_suc is not null and t.e_suc <> t.sucursal_id)
             or (t.s_suc is not null and t.s_suc <> t.sucursal_id)
             or t.e < t.inicio - interval '120 minutes'
             or t.e > t.inicio + (t.fin - t.inicio) / 2 then 'por_confirmar'::estado_jornada
           else 'ok'::estado_jornada
         end as estado,
         (t.fin + make_interval(mins => t.posterior::int) <= p_ahora) as cerrado
  from tiempos t;

  -- 5
  insert into jornadas (asignacion_id, colaborador_id, sucursal_id, fecha, marcacion_entrada_id, marcacion_salida_id,
                        minutos_trabajados, minutos_tardanza, minutos_faltantes, minutos_jornada,
                        clasif_entrada, clasif_salida, estado)
  select c.asignacion_id, c.colaborador_id, c.sucursal_id, c.fecha, c.e_id, c.s_id,
         c.min_trabajados, c.min_tardanza,
         -- lo que falto de la jornada completa, tardanza y salida anticipada juntas
         case when c.estado = 'incompleta' then 0
              else greatest(0, coalesce(c.min_jornada, 0) - c.min_trabajados) end,
         c.min_jornada,
         c.clasif_entrada, c.clasif_salida, c.estado
  from _calc c
  where c.procesar and c.cerrado
  on conflict (colaborador_id, fecha) do update set
    asignacion_id = excluded.asignacion_id,
    sucursal_id = excluded.sucursal_id,
    marcacion_entrada_id = excluded.marcacion_entrada_id,
    marcacion_salida_id = excluded.marcacion_salida_id,
    minutos_trabajados = excluded.minutos_trabajados,
    minutos_tardanza = excluded.minutos_tardanza,
    minutos_faltantes = excluded.minutos_faltantes,
    minutos_jornada = excluded.minutos_jornada,
    clasif_entrada = excluded.clasif_entrada,
    clasif_salida = excluded.clasif_salida,
    estado = excluded.estado;
  get diagnostics n_jornadas = row_count;

  -- 6
  create temp table _huerfanas on commit drop as
  select distinct on (m.colaborador_id, (m.marcado_en at time zone 'America/Guatemala')::date)
         m.colaborador_id,
         (m.marcado_en at time zone 'America/Guatemala')::date as fecha,
         m.id as marca_id, m.marcado_en, m.tipo,
         coalesce(m.sucursal_id, c.sucursal_base_id) as sucursal_id
  from _marcas m
  join colaboradores c on c.id = m.colaborador_id
  where not exists (select 1 from _asignada x where x.marca_id = m.id)
    and (m.marcado_en at time zone 'America/Guatemala')::date between p_desde and p_hasta
    and not exists (select 1 from periodos_planilla pp
                    where pp.estado = 'cerrado'
                      and (m.marcado_en at time zone 'America/Guatemala')::date between pp.fecha_inicio and pp.fecha_fin)
  order by m.colaborador_id, (m.marcado_en at time zone 'America/Guatemala')::date, m.marcado_en;

  insert into jornadas (asignacion_id, colaborador_id, sucursal_id, fecha, marcacion_entrada_id, marcacion_salida_id,
                        minutos_trabajados, minutos_tardanza, minutos_faltantes, estado)
  select null, h.colaborador_id, h.sucursal_id, h.fecha,
         case when h.tipo = 'salida' then null else h.marca_id end,
         case when h.tipo = 'salida' then h.marca_id else s.id end,
         case when h.tipo = 'salida' then 0
              else coalesce(floor(extract(epoch from (s.marcado_en - h.marcado_en)) / 60)::int, 0) end,
         0, 0, 'sin_programacion'
  from _huerfanas h
  left join lateral (
    select m2.id, m2.marcado_en
    from _marcas m2
    where m2.colaborador_id = h.colaborador_id
      and (m2.marcado_en at time zone 'America/Guatemala')::date = h.fecha
      and not exists (select 1 from _asignada x where x.marca_id = m2.id)
      and m2.marcado_en >= h.marcado_en + interval '30 minutes'
    order by m2.marcado_en
    limit 1
  ) s on true
  on conflict (colaborador_id, fecha) do update set
    sucursal_id = excluded.sucursal_id,
    marcacion_entrada_id = excluded.marcacion_entrada_id,
    marcacion_salida_id = excluded.marcacion_salida_id,
    minutos_trabajados = excluded.minutos_trabajados
    where jornadas.asignacion_id is null and jornadas.estado = 'sin_programacion';
  get diagnostics n_sin_programacion = row_count;

  -- 7
  with retiradas as (
    delete from ausencias au
    where au.estado = 'sin_justificar'
      and (exists (select 1 from _asignada x where x.asignacion_id = au.asignacion_id)
           -- la programacion cambio y esa asignacion ya no es la vigente
           or (au.fecha between p_desde and p_hasta
               and not exists (select 1 from asignaciones_vigentes v
                               where v.id = au.asignacion_id and v.turno_id is not null and v.estado = 'programado')
               and not exists (select 1 from periodos_planilla pp
                               where pp.estado = 'cerrado' and au.fecha between pp.fecha_inicio and pp.fecha_fin)
               and not exists (select 1 from notas_asistencia n where n.ausencia_id = au.id)))
    returning au.colaborador_id, au.fecha
  )
  update alertas al
  set estado = 'resuelta', resuelta_en = now()
  from retiradas r
  where al.tipo = 'ausencia' and al.estado = 'abierta'
    and al.colaborador_id = r.colaborador_id and al.fecha = r.fecha;

  insert into ausencias (asignacion_id, colaborador_id, fecha)
  select a.asignacion_id, a.colaborador_id, a.fecha
  from _asig a
  where a.procesar
    and not a.con_licencia
    and p_ahora >= a.inicio + make_interval(mins => a.ausencia::int)
    and not exists (select 1 from _asignada x where x.asignacion_id = a.asignacion_id)
  on conflict (asignacion_id) do nothing;
  get diagnostics n_ausencias = row_count;

  -- 8
  insert into horas_extra (jornada_id, minutos_detectados)
  select j.id, c.min_extra
  from _calc c
  join jornadas j on j.colaborador_id = c.colaborador_id and j.fecha = c.fecha
  where c.procesar and c.cerrado and c.min_extra > 0 and c.estado <> 'incompleta'
  on conflict (jornada_id) do update set minutos_detectados = excluded.minutos_detectados
    where horas_extra.estado = 'pendiente';
  get diagnostics n_extras = row_count;

  delete from horas_extra h
  using jornadas j, _calc c
  where h.jornada_id = j.id and j.colaborador_id = c.colaborador_id and j.fecha = c.fecha
    and c.procesar and c.cerrado and c.min_extra = 0 and h.estado = 'pendiente';

  -- 9
  insert into alertas (tipo, colaborador_id, fecha, detalle)
  select v.tipo, v.colaborador_id, v.fecha, v.detalle
  from (
    select case j.estado when 'por_confirmar' then 'por_confirmar'::tipo_alerta
                         when 'incompleta' then 'marcacion_faltante'::tipo_alerta
                         else 'sin_programacion'::tipo_alerta end as tipo,
           j.colaborador_id, j.fecha, jsonb_build_object('jornada_id', j.id) as detalle
    from jornadas j
    where j.fecha between p_desde and p_hasta and j.estado in ('por_confirmar', 'incompleta', 'sin_programacion')
    union all
    select 'ausencia'::tipo_alerta, au.colaborador_id, au.fecha, jsonb_build_object('ausencia_id', au.id)
    from ausencias au
    where au.fecha between p_desde and p_hasta and au.estado = 'sin_justificar'
  ) v
  where not exists (
    select 1 from alertas al
    where al.tipo = v.tipo and al.colaborador_id = v.colaborador_id and al.fecha = v.fecha and al.estado = 'abierta'
  );

  perform revisar_alertas(p_desde, p_hasta);

  insert into bitacora (usuario_id, accion, tabla, detalle)
  values (
    p_usuario, 'calcular', 'jornadas',
    jsonb_build_object('desde', p_desde, 'hasta', p_hasta, 'jornadas', n_jornadas,
                       'sin_programacion', n_sin_programacion, 'ausencias', n_ausencias, 'horas_extra', n_extras)
  );

  return jsonb_build_object('jornadas', n_jornadas, 'sin_programacion', n_sin_programacion,
                            'ausencias', n_ausencias, 'horas_extra', n_extras);
end;
$$;

revoke execute on function calcular_jornadas(date, date, uuid, timestamptz) from public, anon, authenticated;

notify pgrst, 'reload schema';

-- planilla: quien se dio de baja dentro de la quincena y no trabajo ni falto en ella (por ejemplo

create or replace function calcular_planilla(p_inicio date, p_fin date) returns jsonb
language plpgsql stable as $$
declare
  v_dias numeric := coalesce(parametro_en('dias_base_salario', p_fin), 30);
  v_horas numeric := coalesce(parametro_en('horas_base_dia', p_fin), 8);
  v_extra_dia numeric := parametro_en('valor_hora_extra_diurna', p_fin);
  v_extra_noche numeric := parametro_en('valor_hora_extra_nocturna', p_fin);
  resultado jsonb;
begin
  if p_fin < p_inicio or p_fin - p_inicio > 31 then
    raise exception 'El periodo debe ser de 1 a 32 dias' using errcode = '22023';
  end if;
  if v_extra_dia is null or v_extra_noche is null then
    raise exception 'Faltan los valores de la hora extra en los parametros' using errcode = '22023';
  end if;

  with
  personas as (
    select c.id, c.nombres, c.apellidos, c.modalidad, s.forma_pago, s.salario_mensual, s.tarifa,
           aj.valor_hora as aj_hora, aj.valor_hora_extra as aj_extra, aj.motivo as aj_motivo
    from colaboradores c
    join colaborador_salarios s
      on s.colaborador_id = c.id and s.vigente_desde <= p_fin
     and (s.vigente_hasta is null or s.vigente_hasta >= p_fin)
    left join ajustes_planilla aj
      on aj.colaborador_id = c.id and aj.fecha_inicio = p_inicio and aj.fecha_fin = p_fin
    where exists (select 1 from periodos_laborales pl
                  where pl.colaborador_id = c.id and pl.fecha_ingreso <= p_fin
                    and (pl.fecha_baja is null or pl.fecha_baja >= p_fin
                         -- dado de baja dentro de la quincena: solo aparece si trabajo o falto en ella
                         or (pl.fecha_baja >= p_inicio
                             and (exists (select 1 from jornadas j
                                          where j.colaborador_id = c.id and j.fecha between p_inicio and p_fin)
                                  or exists (select 1 from ausencias au
                                             where au.colaborador_id = c.id and au.fecha between p_inicio and p_fin)))))
  ),
  trabajo as (
    -- se paga la jornada completa; lo registrado se muestra aparte
    select j.colaborador_id, sum(coalesce(j.minutos_jornada, j.minutos_trabajados))::int as minutos,
           sum(j.minutos_trabajados)::int as registrados, count(*)::int as turnos
    from jornadas j
    where j.fecha between p_inicio and p_fin and j.estado = 'ok'
    group by j.colaborador_id
  ),
  extras as (
    select j.colaborador_id,
           coalesce(sum(h.minutos_pagados) filter (where t.tipo_jornada is distinct from 'nocturna'), 0)::int as min_dia,
           coalesce(sum(h.minutos_pagados) filter (where t.tipo_jornada = 'nocturna'), 0)::int as min_noche
    from horas_extra h
    join jornadas j on j.id = h.jornada_id
    left join asignaciones_turno a on a.id = j.asignacion_id
    left join turnos t on t.id = a.turno_id
    where j.fecha between p_inicio and p_fin and h.estado in ('autorizada', 'parcial')
    group by j.colaborador_id
  ),
  faltas as (
    select au.colaborador_id, count(*)::int as dias
    from ausencias au
    join tipos_ausencia ta on ta.id = au.tipo_ausencia_id
    where au.fecha between p_inicio and p_fin and au.estado <> 'sin_justificar' and ta.descuenta_dia
    group by au.colaborador_id
  ),
  tiempo as (
    select d.colaborador_id,
           sum(case when d.estado = 'aplicado' then d.minutos_detectados else d.minutos_descontados end)::int as minutos
    from descuentos_tiempo d
    where d.fecha_inicio = p_inicio and d.fecha_fin = p_fin and d.estado in ('aplicado', 'parcial')
    group by d.colaborador_id
  ),
  calculo as (
    select p.*, coalesce(t.minutos, 0) as minutos, coalesce(t.registrados, 0) as registrados, coalesce(t.turnos, 0) as turnos,
           coalesce(e.min_dia, 0) as extra_dia_min, coalesce(e.min_noche, 0) as extra_noche_min,
           coalesce(f.dias, 0) as faltas, coalesce(d.minutos, 0) as min_descontados,
           case p.forma_pago
             when 'por_hora' then p.tarifa
             when 'por_turno' then round(p.tarifa / v_horas, 4)
             else round(p.salario_mensual / (v_dias * v_horas), 4) end as hora_defecto,
           case when p.forma_pago = 'por_hora' then coalesce(p.aj_hora, p.tarifa) end as hora_pago,
           coalesce(p.aj_extra, v_extra_dia) as extra_dia,
           coalesce(p.aj_extra, v_extra_noche) as extra_noche
    from personas p
    left join trabajo t on t.colaborador_id = p.id
    left join extras e on e.colaborador_id = p.id
    left join faltas f on f.colaborador_id = p.id
    left join tiempo d on d.colaborador_id = p.id
  ),
  lineas as (
    select id, 1 as orden, 'ingreso' as tipo, 'Horas de jornada' as concepto,
           round(minutos / 60.0, 2) as cantidad, hora_pago as valor,
           round(minutos / 60.0 * hora_pago, 2) as monto
    from calculo where forma_pago = 'por_hora'
    union all
    select id, 1, 'ingreso', 'Turnos trabajados', turnos, tarifa, round(turnos * tarifa, 2)
    from calculo where forma_pago = 'por_turno'
    union all
    select id, 1, 'ingreso', 'Salario quincenal', 1, round(salario_mensual / 2, 2), round(salario_mensual / 2, 2)
    from calculo where forma_pago = 'salario_fijo'
    union all
    select id, 2, 'ingreso', 'Horas extra de dia', round(extra_dia_min / 60.0, 2), extra_dia,
           round(extra_dia_min / 60.0 * extra_dia, 2)
    from calculo where extra_dia_min > 0
    union all
    select id, 3, 'ingreso', 'Horas extra nocturnas', round(extra_noche_min / 60.0, 2), extra_noche,
           round(extra_noche_min / 60.0 * extra_noche, 2)
    from calculo where extra_noche_min > 0
    union all
    select id, 4, 'descuento', 'Dias de ausencia descontados', faltas, round(salario_mensual / v_dias, 2),
           round(faltas * salario_mensual / v_dias, 2)
    from calculo where forma_pago = 'salario_fijo' and faltas > 0
    union all
    select id, 5, 'descuento', 'Horas descontadas por tardanza o salida anticipada', round(min_descontados / 60.0, 2),
           coalesce(hora_pago, hora_defecto),
           round(min_descontados / 60.0 * coalesce(hora_pago, hora_defecto), 2)
    from calculo where min_descontados > 0
    union all
    -- descuentos manuales: la nota sale en la boleta
    select dm.colaborador_id, 6, 'descuento', 'Descuento: ' || dm.motivo, 1, dm.monto, dm.monto
    from descuentos_manuales dm
    where dm.fecha_inicio = p_inicio and dm.fecha_fin = p_fin
      and exists (select 1 from calculo c where c.id = dm.colaborador_id)
  ),
  resumen as (
    select c.*,
           coalesce((select jsonb_agg(jsonb_build_object('tipo', l.tipo, 'concepto', l.concepto, 'cantidad', l.cantidad,
                                                         'valor_unitario', l.valor, 'monto', l.monto) order by l.orden)
                     from lineas l where l.id = c.id), '[]'::jsonb) as detalle,
           coalesce((select sum(l.monto) from lineas l where l.id = c.id and l.tipo = 'ingreso'), 0) as ingresos,
           coalesce((select sum(l.monto) from lineas l where l.id = c.id and l.tipo = 'descuento'), 0) as descuentos
    from calculo c
  )
  select coalesce(jsonb_agg(jsonb_build_object(
           'colaborador_id', r.id,
           'nombre', r.nombres || ' ' || r.apellidos,
           'modalidad', r.modalidad,
           'forma_pago', r.forma_pago,
           'minutos_trabajados', r.registrados,
           'minutos_jornada', r.minutos,
           'turnos', r.turnos,
           'valor_hora', r.hora_pago,
           'valor_hora_defecto', case when r.forma_pago = 'por_hora' then r.tarifa end,
           'valor_extra_dia', r.extra_dia,
           'valor_extra_noche', r.extra_noche,
           'valor_extra_defecto_dia', v_extra_dia,
           'valor_extra_defecto_noche', v_extra_noche,
           'ajuste', case when r.aj_hora is not null or r.aj_extra is not null
                          then jsonb_build_object('valor_hora', r.aj_hora, 'valor_hora_extra', r.aj_extra,
                                                  'motivo', r.aj_motivo) end,
           'lineas', r.detalle,
           'total_ingresos', r.ingresos,
           'total_descuentos', r.descuentos,
           'neto', r.ingresos - r.descuentos
         ) order by r.apellidos, r.nombres), '[]'::jsonb)
  into resultado
  from resumen r;

  return resultado;
end;
$$;

notify pgrst, 'reload schema';

-- corregir la hora de entrada o de salida de una jornada, dejando el motivo
-- la marcacion original no se toca: se crea una manual nueva que la reemplaza
create function corregir_jornada(
  p_jornada uuid,
  p_entrada timestamptz,
  p_salida timestamptz,
  p_motivo text,
  p_usuario uuid
) returns jsonb
language plpgsql as $$
declare
  j jornadas%rowtype;
  turno record;
  texto text := nullif(trim(coalesce(p_motivo, '')), '');
  previa int;
  posterior int;
  limite_ini timestamptz;
  limite_fin timestamptz;
  anterior_entrada timestamptz;
  anterior_salida timestamptz;
  nueva uuid;
begin
  select * into j from jornadas where id = p_jornada for update;
  if not found then
    raise exception 'La jornada no existe' using errcode = 'P0002';
  end if;
  if texto is null then
    raise exception 'El motivo es obligatorio' using errcode = '22023';
  end if;
  if p_entrada is null and p_salida is null then
    raise exception 'Indica la hora de entrada o la de salida' using errcode = '22023';
  end if;
  if j.estado = 'sin_programacion' or j.asignacion_id is null then
    raise exception 'Esa jornada no tiene turno programado' using errcode = '22023';
  end if;
  if exists (select 1 from periodos_planilla
             where estado = 'cerrado' and j.fecha between fecha_inicio and fecha_fin) then
    raise exception 'Esa quincena ya esta cerrada' using errcode = '55000';
  end if;
  if exists (select 1 from horas_extra h where h.jornada_id = j.id and h.estado <> 'pendiente') then
    raise exception 'Esa jornada tiene horas extra ya decididas: corrigelas primero en Pendientes'
      using errcode = '22023';
  end if;
  if greatest(p_entrada, p_salida) > now() then
    raise exception 'La hora no puede ser futura' using errcode = '22023';
  end if;
  if p_entrada is not null and p_salida is not null and p_salida <= p_entrada then
    raise exception 'La salida debe ser despues de la entrada' using errcode = '22023';
  end if;

  -- la hora corregida debe caer dentro de la ventana del turno, o el motor no la usaria
  select (a.fecha + t.hora_inicio) at time zone 'America/Guatemala' as inicio,
         ((a.fecha + t.hora_inicio) at time zone 'America/Guatemala')
           + make_interval(secs => (case when t.cruza_medianoche
                                         then extract(epoch from (t.hora_fin - t.hora_inicio)) + 86400
                                         else extract(epoch from (t.hora_fin - t.hora_inicio)) end)::double precision) as fin,
         a.turno_id
    into turno
    from asignaciones_turno a join turnos t on t.id = a.turno_id
   where a.id = j.asignacion_id;
  previa := coalesce(parametro_en('ventana_previa_minutos', j.fecha, j.sucursal_id, turno.turno_id), 240);
  posterior := greatest(
    coalesce(parametro_en('ventana_posterior_minutos', j.fecha, j.sucursal_id, turno.turno_id), 240),
    coalesce(parametro_en('ventana_manual_minutos', j.fecha, j.sucursal_id, turno.turno_id), 720));
  limite_ini := turno.inicio - make_interval(mins => previa);
  limite_fin := turno.fin + make_interval(mins => posterior);
  if p_entrada < limite_ini or p_entrada > limite_fin or p_salida < limite_ini or p_salida > limite_fin then
    raise exception 'La hora queda fuera del turno de ese dia' using errcode = '22023';
  end if;

  select marcado_en into anterior_entrada from marcaciones where id = j.marcacion_entrada_id;
  select marcado_en into anterior_salida from marcaciones where id = j.marcacion_salida_id;

  if p_entrada is not null then
    insert into marcaciones (colaborador_id, marcado_en, tipo, origen)
    values (j.colaborador_id, p_entrada, 'entrada', 'manual')
    returning id into nueva;
    insert into correcciones_marcacion (marcacion_nueva_id, marcacion_original_id, motivo, corregido_por)
    values (nueva, j.marcacion_entrada_id, texto, p_usuario);
  end if;
  if p_salida is not null then
    insert into marcaciones (colaborador_id, marcado_en, tipo, origen)
    values (j.colaborador_id, p_salida, 'salida', 'manual')
    returning id into nueva;
    insert into correcciones_marcacion (marcacion_nueva_id, marcacion_original_id, motivo, corregido_por)
    values (nueva, j.marcacion_salida_id, texto, p_usuario);
  end if;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'corregir', 'jornadas', p_jornada,
          jsonb_build_object('colaborador_id', j.colaborador_id, 'fecha', j.fecha,
                             'entrada_antes', anterior_entrada, 'entrada_despues', p_entrada,
                             'salida_antes', anterior_salida, 'salida_despues', p_salida,
                             'motivo', texto));

  perform calcular_jornadas(j.fecha - 1, j.fecha + 1, p_usuario);

  update alertas al
     set estado = 'resuelta', resuelta_por = p_usuario, resuelta_en = now()
   where al.colaborador_id = j.colaborador_id and al.estado = 'abierta'
     and al.tipo in ('marcacion_faltante', 'por_confirmar')
     and al.fecha between j.fecha - 1 and j.fecha + 1
     and not exists (select 1 from jornadas x
                     where x.colaborador_id = al.colaborador_id and x.fecha = al.fecha
                       and x.estado in ('incompleta', 'por_confirmar'));

  return jsonb_build_object('jornada_id', p_jornada);
end;
$$;

revoke execute on function corregir_jornada(uuid, timestamptz, timestamptz, text, uuid)
  from public, anon, authenticated;

-- quien esta en turno ahora: tiene turno programado en esta ventana y una marca de entrada sin salida
create view en_turno_ahora with (security_invoker = true) as
with turnos_ahora as (
  select a.colaborador_id, a.sucursal_id, t.nombre as turno,
         (a.fecha + t.hora_inicio) at time zone 'America/Guatemala' as inicio,
         ((a.fecha + t.hora_inicio) at time zone 'America/Guatemala')
           + make_interval(secs => (case when t.cruza_medianoche
                                         then extract(epoch from (t.hora_fin - t.hora_inicio)) + 86400
                                         else extract(epoch from (t.hora_fin - t.hora_inicio)) end)::double precision) as fin
  from asignaciones_vigentes a
  join turnos t on t.id = a.turno_id
  where a.turno_id is not null and a.estado = 'programado'
    and a.fecha between (now() at time zone 'America/Guatemala')::date - 1
                    and (now() at time zone 'America/Guatemala')::date
)
select t.colaborador_id, t.sucursal_id, t.turno, c.nombres, c.apellidos, p.nombre as puesto,
       min(m.marcado_en) as entrada
from turnos_ahora t
join colaboradores c on c.id = t.colaborador_id
left join puestos p on p.id = c.puesto_id
join marcaciones_resueltas m
  on m.colaborador_id = t.colaborador_id
 and not m.es_duplicada
 and m.marcado_en between t.inicio - interval '240 minutes' and least(now(), t.fin + interval '240 minutes')
 and not exists (select 1 from correcciones_marcacion cm where cm.marcacion_original_id = m.id)
where now() between t.inicio - interval '240 minutes' and t.fin + interval '240 minutes'
group by t.colaborador_id, t.sucursal_id, t.turno, t.inicio, c.nombres, c.apellidos, p.nombre
having count(*) % 2 = 1;

notify pgrst, 'reload schema';

-- descuentos manuales por quincena, con la nota que sale en la boleta
create table descuentos_manuales (
  id uuid primary key default gen_random_uuid(),
  colaborador_id uuid not null references colaboradores(id),
  fecha_inicio date not null,
  fecha_fin date not null,
  monto numeric not null check (monto > 0),
  motivo text not null check (length(trim(motivo)) between 3 and 200),
  creado_por uuid references profiles(id),
  creado_en timestamptz not null default now(),
  check (fecha_fin >= fecha_inicio)
);

alter table descuentos_manuales enable row level security;
create policy lectura_rrhh_jefe on descuentos_manuales
  for select to authenticated using (rol_actual() in ('rrhh', 'jefe'));
revoke insert, update, delete on descuentos_manuales from anon, authenticated;

create function agregar_descuento_manual(
  p_colaborador uuid,
  p_inicio date,
  p_fin date,
  p_monto numeric,
  p_motivo text,
  p_usuario uuid
) returns uuid
language plpgsql as $$
declare
  texto text := nullif(trim(coalesce(p_motivo, '')), '');
  nuevo uuid;
  persona jsonb;
begin
  if not exists (select 1 from colaboradores where id = p_colaborador) then
    raise exception 'El colaborador no existe' using errcode = 'P0002';
  end if;
  if texto is null or length(texto) < 3 or length(texto) > 200 then
    raise exception 'El motivo es obligatorio (de 3 a 200 caracteres)' using errcode = '22023';
  end if;
  if p_monto is null or p_monto <= 0 or p_monto > 100000 then
    raise exception 'El monto debe ser mayor que 0' using errcode = '22023';
  end if;
  if p_fin < p_inicio then
    raise exception 'El periodo no es valido' using errcode = '22023';
  end if;
  if exists (select 1 from periodos_planilla
             where estado = 'cerrado' and p_inicio between fecha_inicio and fecha_fin) then
    raise exception 'Esa quincena ya esta cerrada' using errcode = '55000';
  end if;

  insert into descuentos_manuales (colaborador_id, fecha_inicio, fecha_fin, monto, motivo, creado_por)
  values (p_colaborador, p_inicio, p_fin, round(p_monto, 2), texto, p_usuario)
  returning id into nuevo;

  -- debe estar en la planilla de esa quincena y no quedar con pago negativo
  select e into persona
    from jsonb_array_elements(calcular_planilla(p_inicio, p_fin)) e
   where e ->> 'colaborador_id' = p_colaborador::text;
  if persona is null then
    raise exception 'Esa persona no esta en la planilla de esa quincena' using errcode = '22023';
  end if;
  if (persona ->> 'neto')::numeric < 0 then
    raise exception 'El descuento deja el pago en negativo' using errcode = '22023';
  end if;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'crear', 'descuentos_manuales', nuevo,
          jsonb_build_object('colaborador_id', p_colaborador, 'inicio', p_inicio, 'fin', p_fin,
                             'monto', round(p_monto, 2), 'motivo', texto));
  return nuevo;
end;
$$;

create function quitar_descuento_manual(p_id uuid, p_usuario uuid) returns void
language plpgsql as $$
declare
  d descuentos_manuales%rowtype;
begin
  select * into d from descuentos_manuales where id = p_id for update;
  if not found then
    raise exception 'El descuento no existe' using errcode = 'P0002';
  end if;
  if exists (select 1 from periodos_planilla
             where estado = 'cerrado' and d.fecha_inicio between fecha_inicio and fecha_fin) then
    raise exception 'Esa quincena ya esta cerrada' using errcode = '55000';
  end if;

  delete from descuentos_manuales where id = p_id;

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'eliminar', 'descuentos_manuales', p_id,
          jsonb_build_object('colaborador_id', d.colaborador_id, 'inicio', d.fecha_inicio, 'fin', d.fecha_fin,
                             'monto', d.monto, 'motivo', d.motivo));
end;
$$;

revoke execute on function agregar_descuento_manual(uuid, date, date, numeric, text, uuid)
  from public, anon, authenticated;
revoke execute on function quitar_descuento_manual(uuid, uuid) from public, anon, authenticated;

notify pgrst, 'reload schema';

-- ausencia sin justificar donde la persona si llego y olvido marcar: se registran su entrada y su salida
-- las marcas quedan como manuales con el motivo, y la ausencia se convierte en jornada al recalcular
create function registrar_asistencia_en_ausencia(
  p_ausencia uuid,
  p_entrada timestamptz,
  p_salida timestamptz,
  p_motivo text,
  p_usuario uuid
) returns jsonb
language plpgsql as $$
declare
  aus ausencias%rowtype;
  turno record;
  texto text := nullif(trim(coalesce(p_motivo, '')), '');
  previa int;
  posterior int;
  limite_ini timestamptz;
  limite_fin timestamptz;
  nueva uuid;
begin
  select * into aus from ausencias where id = p_ausencia for update;
  if not found then
    raise exception 'La ausencia no existe' using errcode = 'P0002';
  end if;
  if aus.estado <> 'sin_justificar' then
    raise exception 'Solo se puede registrar la asistencia de una ausencia sin justificar' using errcode = '22023';
  end if;
  if texto is null then
    raise exception 'El motivo es obligatorio' using errcode = '22023';
  end if;
  if p_entrada is null or p_salida is null then
    raise exception 'Indica la hora de entrada y la de salida' using errcode = '22023';
  end if;
  if p_salida <= p_entrada then
    raise exception 'La salida debe ser despues de la entrada' using errcode = '22023';
  end if;
  if greatest(p_entrada, p_salida) > now() then
    raise exception 'La hora no puede ser futura' using errcode = '22023';
  end if;
  if exists (select 1 from periodos_planilla
             where estado = 'cerrado' and aus.fecha between fecha_inicio and fecha_fin) then
    raise exception 'Esa quincena ya esta cerrada' using errcode = '55000';
  end if;

  -- las horas deben caer dentro de la ventana del turno, o el motor no las usaria
  select (a.fecha + t.hora_inicio) at time zone 'America/Guatemala' as inicio,
         ((a.fecha + t.hora_inicio) at time zone 'America/Guatemala')
           + make_interval(secs => (case when t.cruza_medianoche
                                         then extract(epoch from (t.hora_fin - t.hora_inicio)) + 86400
                                         else extract(epoch from (t.hora_fin - t.hora_inicio)) end)::double precision) as fin,
         a.turno_id, a.sucursal_id
    into turno
    from asignaciones_turno a join turnos t on t.id = a.turno_id
   where a.id = aus.asignacion_id;
  previa := coalesce(parametro_en('ventana_previa_minutos', aus.fecha, turno.sucursal_id, turno.turno_id), 240);
  posterior := greatest(
    coalesce(parametro_en('ventana_posterior_minutos', aus.fecha, turno.sucursal_id, turno.turno_id), 240),
    coalesce(parametro_en('ventana_manual_minutos', aus.fecha, turno.sucursal_id, turno.turno_id), 720));
  limite_ini := turno.inicio - make_interval(mins => previa);
  limite_fin := turno.fin + make_interval(mins => posterior);
  if p_entrada < limite_ini or p_entrada > limite_fin or p_salida < limite_ini or p_salida > limite_fin then
    raise exception 'La hora queda fuera del turno de ese dia' using errcode = '22023';
  end if;

  insert into marcaciones (colaborador_id, marcado_en, tipo, origen)
  values (aus.colaborador_id, p_entrada, 'entrada', 'manual')
  returning id into nueva;
  insert into correcciones_marcacion (marcacion_nueva_id, motivo, corregido_por)
  values (nueva, texto, p_usuario);

  insert into marcaciones (colaborador_id, marcado_en, tipo, origen)
  values (aus.colaborador_id, p_salida, 'salida', 'manual')
  returning id into nueva;
  insert into correcciones_marcacion (marcacion_nueva_id, motivo, corregido_por)
  values (nueva, texto, p_usuario);

  insert into bitacora (usuario_id, accion, tabla, registro_id, detalle)
  values (p_usuario, 'registrar_asistencia', 'ausencias', p_ausencia,
          jsonb_build_object('colaborador_id', aus.colaborador_id, 'fecha', aus.fecha,
                             'entrada', p_entrada, 'salida', p_salida, 'motivo', texto));

  perform calcular_jornadas(aus.fecha - 1, aus.fecha + 1, p_usuario);

  return jsonb_build_object(
    'jornada', exists (select 1 from jornadas j where j.colaborador_id = aus.colaborador_id and j.fecha = aus.fecha),
    'ausencia_vigente', exists (select 1 from ausencias x where x.id = p_ausencia));
end;
$$;

revoke execute on function registrar_asistencia_en_ausencia(uuid, timestamptz, timestamptz, text, uuid)
  from public, anon, authenticated;

notify pgrst, 'reload schema';
