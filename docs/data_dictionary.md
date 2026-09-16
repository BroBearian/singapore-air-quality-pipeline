# Data dictionary

## Bronze: `raw_api_responses`

| Column | Meaning |
|---|---|
| `response_id` | Unique identifier for the stored response |
| `run_id` | GitHub or local pipeline execution identifier |
| `endpoint_name` | `pm25` or `psi` |
| `requested_date` | Singapore calendar date requested |
| `fetched_at` | Time the API response was fetched, stored as `timestamptz` |
| `http_status` | HTTP status received from the source |
| `response_hash` | SHA-256 of canonical JSON for comparison |
| `payload` | Full source JSON response |

## Silver: `air_quality_readings`

**Grain:** one observed hour, region and source metric.

| Column | Meaning |
|---|---|
| `observed_at` | Source observation timestamp; UTC internally via `timestamptz` |
| `published_at` | Source `updatedTimestamp` |
| `region` | `central`, `north`, `south`, `east` or `west` |
| `metric` | Exact source metric key |
| `value` | Nonnegative numeric source reading |
| `unit` | Display unit mapped in `transform.py` |
| `source_endpoint` | API that supplied this metric |
| `requested_date` | Date used in the request |
| `first_ingested_at` | First time this business key was stored |
| `last_ingested_at` | Last time this business key was changed or reconfirmed |
| `run_id` | Pipeline execution that last wrote the reading |

## Gold views

| View | Purpose |
|---|---|
| `v_air_quality_hourly` | Region-hour row with selected metrics as columns |
| `v_air_quality_hourly_enriched` | Adds NEA PM2.5 bands and PSI categories |
| `v_air_quality_hourly_change` | Adds differences only when the preceding observation is exactly one hour earlier |
| `v_latest_air_quality` | Latest region-hour per region |
| `v_air_quality_daily_summary` | Daily regional summary |
| `v_haze_events` | Observations in Elevated/High PM2.5 bands or Unhealthy PSI |
| `v_pipeline_freshness` | Latest observation and age |
| `v_pipeline_status` | Sanitised public pipeline status |

The representative coordinates in `dim_region` are label points, not boundary polygons. `observed_at_sgt` in analytical views is Singapore local wall-clock time; `observed_at` retains the timezone-aware timestamp. Refer to [NEA's Haze portal](https://www.haze.gov.sg/) for official band definitions and health guidance.
