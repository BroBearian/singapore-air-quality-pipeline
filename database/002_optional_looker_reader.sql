-- Optional: run only if you intend to connect Looker Studio to PostgreSQL.
-- Replace the placeholder with a unique strong password before running.
-- Store that password in your password manager, not in Git.
create role looker_reader with login password 'REPLACE_WITH_STRONG_PASSWORD';

grant usage on schema public to looker_reader;
grant select on public.air_quality_readings to looker_reader;
grant select on public.dim_region to looker_reader;

grant select on public.v_air_quality_hourly to looker_reader;
grant select on public.v_air_quality_hourly_enriched to looker_reader;
grant select on public.v_air_quality_hourly_change to looker_reader;
grant select on public.v_latest_air_quality to looker_reader;
grant select on public.v_air_quality_daily_summary to looker_reader;
grant select on public.v_haze_events to looker_reader;
grant select on public.v_pipeline_freshness to looker_reader;
grant select on public.v_pipeline_status to looker_reader;

create policy "Looker may read air quality"
on public.air_quality_readings for select to looker_reader using (true);

create policy "Looker may read regions"
on public.dim_region for select to looker_reader using (true);

-- v_pipeline_status is a sanitised owner-rights view.
-- This role receives no access to the underlying pipeline_runs table.
