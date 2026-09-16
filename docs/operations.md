# Operation and recovery

## Hourly checks

The scheduled workflow runs at `HH:52` Singapore time. GitHub scheduling is best-effort. Inspect the **Actions** tab and the latest row in `pipeline_runs` after setup and during incidents.

```sql
select status, started_at, finished_at, rows_extracted, rows_affected,
       api_requests, error_message
from public.pipeline_runs
order by started_at desc limit 24;
```

```sql
select * from public.v_pipeline_freshness;
```

- **Fresh:** latest source observation is no more than two hours old.
- **Delayed:** more than two and up to three hours old.
- **Stale:** more than three hours old.

## Recovery

1. Inspect the failed GitHub Actions step and `pipeline_runs.error_message` privately.
2. Resolve API, credential, network, schema or database errors.
3. Trigger the workflow manually with `days_back: 1` for today and yesterday. For longer interruptions, use a larger value up to 89.
4. Check latest readings, freshness, duplicate keys and quality results.
5. Do not repeatedly trigger large backfills; monitor database usage, especially Bronze JSON retention.

A failed backfill may have committed earlier dates. Rerunning is safe because the Silver business key prevents duplicates. Bronze is append-only by design.

## Manual validation

```sql
select observed_at, region, metric, count(*)
from public.air_quality_readings
 group by observed_at, region, metric
having count(*) > 1;
```

```sql
select observed_at, count(*) as region_count
from public.air_quality_readings
where metric = 'pm25_one_hourly'
group by observed_at
having count(*) <> 5
order by observed_at desc;
```

**Limit:** The dashboard is an informational portfolio product; it is not an emergency alert service.
