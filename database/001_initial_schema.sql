create extension if not exists pgcrypto;

-- Bronze: one row per API response.
create table if not exists public.raw_api_responses (
    response_id uuid primary key default gen_random_uuid(),
    run_id uuid not null,
    endpoint_name text not null,
    requested_date date not null,
    fetched_at timestamptz not null default now(),
    http_status integer not null,
    response_hash text not null,
    payload jsonb not null
);

create index if not exists idx_raw_api_responses_run_id
    on public.raw_api_responses (run_id);

create index if not exists idx_raw_api_responses_requested_date
    on public.raw_api_responses (requested_date);

-- Silver: one observation time x region x metric.
create table if not exists public.air_quality_readings (
    observed_at timestamptz not null,
    published_at timestamptz not null,
    region text not null,
    metric text not null,
    value numeric not null,
    unit text not null,
    source_endpoint text not null,
    requested_date date not null,
    first_ingested_at timestamptz not null default now(),
    last_ingested_at timestamptz not null default now(),
    run_id uuid not null,

    constraint pk_air_quality_readings
        primary key (observed_at, region, metric),

    constraint chk_air_quality_region
        check (region in ('central', 'north', 'south', 'east', 'west')),

    constraint chk_air_quality_value
        check (value >= 0)
);

create index if not exists idx_air_quality_observed_at
    on public.air_quality_readings (observed_at desc);

create index if not exists idx_air_quality_metric
    on public.air_quality_readings (metric);

create index if not exists idx_air_quality_region
    on public.air_quality_readings (region);

-- Region dimension. Coordinates are representative label points.
create table if not exists public.dim_region (
    region text primary key,
    latitude numeric not null,
    longitude numeric not null,
    display_order integer not null
);

insert into public.dim_region (
    region,
    latitude,
    longitude,
    display_order
)
values
    ('central', 1.35735, 103.82, 1),
    ('north',   1.41803, 103.82, 2),
    ('south',   1.29587, 103.82, 3),
    ('east',    1.35735, 103.94, 4),
    ('west',    1.35735, 103.70, 5)
on conflict (region) do update
set
    latitude = excluded.latitude,
    longitude = excluded.longitude,
    display_order = excluded.display_order;

-- Audit tables.
create table if not exists public.pipeline_runs (
    run_id uuid primary key,
    started_at timestamptz not null,
    finished_at timestamptz,
    status text not null,
    rows_extracted integer not null default 0,
    rows_affected integer not null default 0,
    api_requests integer not null default 0,
    error_message text,
    github_run_id text,
    github_sha text,

    constraint chk_pipeline_status
        check (status in ('RUNNING', 'SUCCESS', 'FAILED'))
);

create table if not exists public.data_quality_results (
    quality_result_id bigint generated always as identity primary key,
    run_id uuid not null,
    checked_at timestamptz not null default now(),
    rule_name text not null,
    status text not null,
    actual_value text,
    expected_value text,
    details text,

    constraint chk_quality_status
        check (status in ('PASS', 'WARN', 'FAIL'))
);

create index if not exists idx_quality_results_run_id
    on public.data_quality_results (run_id);

-- Controlled idempotent upsert.
create or replace function public.upsert_air_quality_readings(
    p_rows jsonb
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    affected_rows integer;
begin
    insert into public.air_quality_readings (
        observed_at,
        published_at,
        region,
        metric,
        value,
        unit,
        source_endpoint,
        requested_date,
        last_ingested_at,
        run_id
    )
    select
        x.observed_at,
        x.published_at,
        x.region,
        x.metric,
        x.value,
        x.unit,
        x.source_endpoint,
        x.requested_date,
        now(),
        x.run_id
    from jsonb_to_recordset(p_rows) as x (
        observed_at timestamptz,
        published_at timestamptz,
        region text,
        metric text,
        value numeric,
        unit text,
        source_endpoint text,
        requested_date date,
        run_id uuid
    )
    on conflict (observed_at, region, metric)
    do update set
        published_at = excluded.published_at,
        value = excluded.value,
        unit = excluded.unit,
        source_endpoint = excluded.source_endpoint,
        requested_date = excluded.requested_date,
        last_ingested_at = now(),
        run_id = excluded.run_id
    where excluded.published_at >= public.air_quality_readings.published_at;

    get diagnostics affected_rows = row_count;
    return affected_rows;
end;
$$;

revoke all on function public.upsert_air_quality_readings(jsonb)
from public, anon, authenticated;

grant execute
on function public.upsert_air_quality_readings(jsonb)
to service_role;

create or replace view public.v_air_quality_hourly
with (security_invoker = true)
as
select
    r.observed_at,
    timezone('Asia/Singapore', r.observed_at) as observed_at_sgt,
    timezone('Asia/Singapore', r.observed_at)::date as date_sgt,
    extract(hour from timezone('Asia/Singapore', r.observed_at))::integer
        as hour_sgt,
    r.region,
    d.latitude,
    d.longitude,

    max(r.value) filter (
        where r.metric = 'pm25_one_hourly'
    ) as pm25_1h,

    max(r.value) filter (
        where r.metric = 'pm25_twenty_four_hourly'
    ) as pm25_24h,

    max(r.value) filter (
        where r.metric = 'pm10_twenty_four_hourly'
    ) as pm10_24h,

    max(r.value) filter (
        where r.metric = 'psi_twenty_four_hourly'
    ) as psi_24h,

    max(r.value) filter (
        where r.metric = 'so2_twenty_four_hourly'
    ) as so2_24h,

    max(r.value) filter (
        where r.metric = 'co_eight_hour_max'
    ) as co_8h_max,

    max(r.value) filter (
        where r.metric = 'o3_eight_hour_max'
    ) as o3_8h_max,

    max(r.value) filter (
        where r.metric = 'no2_one_hour_max'
    ) as no2_1h_max

from public.air_quality_readings r
join public.dim_region d
    on d.region = r.region
group by
    r.observed_at,
    r.region,
    d.latitude,
    d.longitude;

create or replace view public.v_air_quality_hourly_enriched
with (security_invoker = true)
as
select
    h.*,
    case
        when h.pm25_1h is null then 'Unknown'
        when h.pm25_1h <= 55 then 'Normal'
        when h.pm25_1h <= 150 then 'Elevated'
        when h.pm25_1h <= 250 then 'High'
        else 'Very High'
    end as pm25_1h_band,
    case
        when h.psi_24h is null then 'Unknown'
        when h.psi_24h <= 50 then 'Good'
        when h.psi_24h <= 100 then 'Moderate'
        when h.psi_24h <= 200 then 'Unhealthy'
        when h.psi_24h <= 300 then 'Very Unhealthy'
        else 'Hazardous'
    end as psi_24h_category
from public.v_air_quality_hourly h;

create or replace view public.v_air_quality_hourly_change
with (security_invoker = true)
as
with previous as (
    select
        h.*,
        lag(h.observed_at) over (
            partition by h.region order by h.observed_at
        ) as previous_observed_at,
        lag(h.pm25_1h) over (
            partition by h.region order by h.observed_at
        ) as previous_pm25_1h,
        lag(h.psi_24h) over (
            partition by h.region order by h.observed_at
        ) as previous_psi_24h
    from public.v_air_quality_hourly_enriched h
)
select
    p.*,
    case when p.observed_at - p.previous_observed_at = interval '1 hour'
        then p.pm25_1h - p.previous_pm25_1h
    end as pm25_change_1h,
    case when p.observed_at - p.previous_observed_at = interval '1 hour'
        then p.psi_24h - p.previous_psi_24h
    end as psi_change_1h
from previous p;

create or replace view public.v_latest_air_quality
with (security_invoker = true)
as
select distinct on (region)
    *
from public.v_air_quality_hourly_change
order by region, observed_at desc;

create or replace view public.v_air_quality_daily_summary
with (security_invoker = true)
as
select
    date_sgt,
    region,
    min(pm25_1h) as min_pm25_1h,
    avg(pm25_1h) as avg_pm25_1h,
    max(pm25_1h) as max_pm25_1h,
    min(psi_24h) as min_psi_24h,
    avg(psi_24h) as avg_psi_24h,
    max(psi_24h) as max_psi_24h,
    count(pm25_1h) as pm25_observation_count
from public.v_air_quality_hourly
group by date_sgt, region;

create or replace view public.v_haze_events
with (security_invoker = true)
as
select
    observed_at,
    observed_at_sgt,
    region,
    pm25_1h,
    pm25_1h_band,
    pm25_change_1h,
    psi_24h,
    psi_24h_category,
    case
        when pm25_1h >= 251 then 'CRITICAL'
        when pm25_1h >= 151 then 'HIGH'
        when pm25_1h >= 56 then 'ELEVATED'
        when psi_24h > 100 then 'UNHEALTHY_PSI'
        else 'NORMAL'
    end as event_level
from public.v_air_quality_hourly_change
where pm25_1h >= 56 or psi_24h > 100;

create or replace view public.v_pipeline_freshness
with (security_invoker = true)
as
select
    max(observed_at) as latest_observation_utc,
    timezone('Asia/Singapore', max(observed_at))
        as latest_observation_sgt,
    max(last_ingested_at) as latest_ingestion_utc,
    extract(epoch from (now() - max(observed_at))) / 3600.0
        as observation_age_hours,
    case
        when extract(epoch from (now() - max(observed_at))) / 3600.0 <= 2
            then 'FRESH'
        when extract(epoch from (now() - max(observed_at))) / 3600.0 <= 3
            then 'DELAYED'
        else 'STALE'
    end as freshness_status
from public.air_quality_readings;

-- Sanitised public run information: no raw error message or commit SHA.
-- This deliberately uses the view owner's privileges so anon users never
-- receive direct permission on the underlying audit table.
create or replace view public.v_pipeline_status
as
select
    run_id,
    started_at,
    finished_at,
    status,
    rows_extracted,
    rows_affected,
    api_requests
from public.pipeline_runs;

alter table public.raw_api_responses enable row level security;
alter table public.air_quality_readings enable row level security;
alter table public.pipeline_runs enable row level security;
alter table public.data_quality_results enable row level security;
alter table public.dim_region enable row level security;

create policy "Public may read air-quality readings"
on public.air_quality_readings
for select
to anon
using (true);

create policy "Public may read region dimension"
on public.dim_region
for select
to anon
using (true);

-- The public can read the sanitised view, but not pipeline_runs directly.
grant select on public.air_quality_readings to anon;
grant select on public.dim_region to anon;
grant select on public.v_air_quality_hourly to anon;
grant select on public.v_air_quality_hourly_enriched to anon;
grant select on public.v_air_quality_hourly_change to anon;
grant select on public.v_latest_air_quality to anon;
grant select on public.v_air_quality_daily_summary to anon;
grant select on public.v_haze_events to anon;
grant select on public.v_pipeline_freshness to anon;
grant select on public.v_pipeline_status to anon;

revoke all on public.pipeline_runs from anon;
