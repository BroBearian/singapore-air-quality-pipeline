# ruff: noqa: E402, I001
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, UTC
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from supabase import create_client  # noqa: E402

from air_quality.api_client import DataGovClient  # noqa: E402
from air_quality.config import (
    DATA_GOV_API_KEY,
    DAYS_BACK,
    PM25_URL,
    PSI_URL,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_URL,
)
from air_quality.load import (  # noqa: E402
    save_quality_results,
    save_raw_response,
    upsert_readings,
)
from air_quality.quality import run_quality_checks  # noqa: E402
from air_quality.transform import flatten_payload  # noqa: E402

SGT = ZoneInfo("Asia/Singapore")


def canonical_hash(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def requested_dates(days_back: int) -> list[str]:
    today_sgt = datetime.now(SGT).date()
    return [
        (today_sgt - timedelta(days=offset)).isoformat()
        for offset in range(days_back + 1)
    ]


def main() -> None:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
    if not 0 <= DAYS_BACK <= 89:
        raise ValueError("DAYS_BACK must be between 0 and 89")

    run_id = str(uuid.uuid4())
    started_at = datetime.now(UTC).isoformat()

    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    supabase.table("pipeline_runs").insert(
        {
            "run_id": run_id,
            "started_at": started_at,
            "status": "RUNNING",
            "github_run_id": os.getenv("GITHUB_RUN_ID"),
            "github_sha": os.getenv("GITHUB_SHA"),
        }
    ).execute()

    api_client = DataGovClient(DATA_GOV_API_KEY)
    endpoints = [("pm25", PM25_URL), ("psi", PSI_URL)]

    extracted_count = 0
    request_count = 0
    affected_count = 0

    try:
        for requested_date in requested_dates(DAYS_BACK):
            day_rows: list[dict] = []
            for endpoint_name, url in endpoints:
                payload, status_code = api_client.get_readings(
                    url=url,
                    requested_date=requested_date,
                )
                request_count += 1

                save_raw_response(
                    supabase,
                    {
                        "run_id": run_id,
                        "endpoint_name": endpoint_name,
                        "requested_date": requested_date,
                        "fetched_at": datetime.now(UTC).isoformat(),
                        "http_status": status_code,
                        "response_hash": canonical_hash(payload),
                        "payload": payload,
                    },
                )

                day_rows.extend(
                    flatten_payload(
                        payload=payload,
                        endpoint_name=endpoint_name,
                        requested_date=requested_date,
                        run_id=run_id,
                    )
                )

                if DAYS_BACK > 1:
                    time.sleep(2)

            extracted_count += len(day_rows)
            quality_results = run_quality_checks(day_rows, run_id)
            save_quality_results(supabase, quality_results)

            failed_rules = [
                result["rule_name"]
                for result in quality_results
                if result["status"] == "FAIL"
            ]
            if failed_rules:
                raise RuntimeError(
                    f"Quality checks failed on {requested_date}: {failed_rules}"
                )

            affected_count += upsert_readings(supabase, day_rows)

        supabase.table("pipeline_runs").update(
            {
                "finished_at": datetime.now(UTC).isoformat(),
                "status": "SUCCESS",
                "rows_extracted": extracted_count,
                "rows_affected": affected_count,
                "api_requests": request_count,
            }
        ).eq("run_id", run_id).execute()

        print(
            f"ETL succeeded: extracted={extracted_count}, "
            f"affected={affected_count}"
        )

    except Exception as exc:
        supabase.table("pipeline_runs").update(
            {
                "finished_at": datetime.now(UTC).isoformat(),
                "status": "FAILED",
                "rows_extracted": extracted_count,
                "rows_affected": affected_count,
                "api_requests": request_count,
                "error_message": str(exc)[:2000],
            }
        ).eq("run_id", run_id).execute()
        raise


if __name__ == "__main__":
    main()
