-- Ejecutar en el proyecto dedicado a las estadísticas de Price List Normalizer.
create table if not exists public.usage_events (
    id uuid primary key,
    created_at timestamptz not null default now(),
    provider text not null check (provider in ('Intcomex', 'Ingram', 'Tecnoglobal', 'Fujicorp', 'Coimco', 'Kepler', 'Nexsys', 'SolutionBox', 'Demco Ltda.', 'Gerona', 'Facciatech', 'Gtc ribbon', 'Compu Soluciones', 'Otro')),
    status text not null check (status in ('Procesado', 'Error')),
    rows_read integer not null check (rows_read >= 0),
    rows_valid integer not null check (rows_valid >= 0),
    rows_discarded integer not null check (rows_discarded >= 0)
);
alter table public.usage_events enable row level security;
revoke all on public.usage_events from anon, authenticated;
grant select, insert on public.usage_events to service_role;
grant select, insert on public.usage_events to anon;
create policy "Read anonymous aggregate usage data" on public.usage_events
for select to anon using (true);
create policy "Append usage counters only" on public.usage_events
for insert to anon with check (
    created_at between now() - interval '7 days' and now() + interval '5 minutes'
    and rows_read <= 1000000 and rows_valid <= rows_read
    and rows_discarded <= rows_read
);
create index if not exists usage_events_created_at_idx
on public.usage_events (created_at desc);

