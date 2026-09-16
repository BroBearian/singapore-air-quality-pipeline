# Singapore hourly air-quality ETL

An hourly portfolio pipeline for Singapore NEA air-quality readings:

```text
NEA / data.gov.sg → GitHub Actions → Python ETL → Supabase PostgreSQL → Streamlit
                                                           ↘ optional Looker Studio
```

**Primary indicator:** one-hour PM2.5. **Context:** 24-hour PSI. The scheduled workflow runs at `HH:52` Singapore time, requests today and yesterday from both APIs, and upserts observations by time, region, and metric. Historical backfills use the same transformation path.

## Start here

1. Create a Supabase project. In its SQL Editor run [`database/001_initial_schema.sql`](database/001_initial_schema.sql) in full. The script creates the raw, cleaned, analytical, and audit objects and their access rules.
2. Copy `.env.example` to `.env` and fill in `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`. Optionally add `DATA_GOV_API_KEY`. Never commit `.env`.
3. Create a Python 3.12 virtual environment, then run `pip install -r requirements.txt`.
4. Execute `python scripts/run_etl.py`. Confirm success in `pipeline_runs` and data in `v_latest_air_quality` via Supabase SQL Editor.
5. Re-run the ETL and verify Silver's primary-key count stays stable.
6. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`; fill in the project URL and **anonymous/public** key. Run `streamlit run app/streamlit_app.py`.
7. Add GitHub Actions repository secrets `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and optionally `DATA_GOV_API_KEY`. Push to GitHub; manually trigger **Scheduled air-quality ETL** in Actions to prove it works.
8. Backfill manually with `days_back: 6` (seven dates), check results, then run with `days_back: 89` (90 dates). The scheduled default stays `1`.
9. Deploy `app/streamlit_app.py` to Streamlit Community Cloud and enter only the project URL and anonymous key into its secrets settings.

The complete step-by-step instructions and optional Looker Studio setup are in [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

## Run quality checks

```bash
pytest -q
ruff check .
python -m compileall -q src scripts app
```

CI runs the first two checks on pushes and pull requests. The scheduled ETL runs every hour and can also be started manually. No live API, Supabase credentials, or deployed dashboard are required for local tests.

## Operational behaviour

- Raw JSON is retained per API request; normalised observations are unique by observation timestamp, region, and metric.
- Source corrections with a newer publication timestamp are applied. Reprocessing the same date does not duplicate observations.
- Failed runs are logged; a subsequent run reprocesses today and yesterday to recover short gaps.
- A warning records incomplete five-region hourly PM2.5 data. An empty batch or invalid data fails a run.
- Data older than two hours is marked delayed; older than three hours is marked stale.
- GitHub schedules are best-effort. This dashboard is informational; use [NEA's Haze portal](https://www.haze.gov.sg/) for official readings and advice.

## Security

Only the GitHub ETL uses the Supabase service-role key. The public app uses the anonymous key and reads views through controlled RLS rules. Do not put database passwords or service-role keys into the app or Git history.

## Source

[Hourly PM2.5](https://api-open.data.gov.sg/v2/real-time/api/pm25) · [PSI](https://api-open.data.gov.sg/v2/real-time/api/psi) · [Data.gov.sg API guidance](https://guide.data.gov.sg/developer-guide/api-overview)
